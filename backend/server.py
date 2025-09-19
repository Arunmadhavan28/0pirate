import os
import uuid
import asyncio
import traceback
import tempfile
import zipfile
import shutil
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from src.config import settings
from src.secure_wrapper import process_code_submission

# -------------------------------------------
# Logging
# -------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# -------------------------------------------
# App + Supabase client init
# -------------------------------------------
APP_NAME = "0pirate-backend"
app = FastAPI(title=APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.supabase_url or not settings.supabase_key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in config.py")

supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# Admin client for accessing Vault securely is not needed here
# as RPC functions handle the security context.

JOB_STORE: Dict[str, Dict[str, Any]] = {}

# -------------------------------------------
# Auth, Tier, and Key Management (Full Implementation)
# -------------------------------------------
async def get_current_user(req: Request) -> dict:
    """Securely validates the Supabase JWT and returns user data."""
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    try:
        user_resp = supabase.auth.get_user(token)
        if user_resp and getattr(user_resp, "user", None):
            u = user_resp.user
            return {"id": u.id, "email": u.email}
        else:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

TIER_LIMITS = {
    "free": {"max_jobs_per_day": 10, "max_files": 3},
    "pro": {"max_jobs_per_day": 50, "max_files": 20},
    "enterprise": {"max_jobs_per_day": 500, "max_files": 100},
}

async def get_user_tier(user_id: str) -> str:
    """Securely fetches the user's tier from the 'profiles' table."""
    try:
        resp = supabase.table("profiles").select("tier").eq("id", user_id).single().execute()
        if resp.data and resp.data.get("tier"):
            return resp.data["tier"]
    except Exception as e:
        logger.error(f"Could not fetch tier for user {user_id}: {e}")
    return "free"

async def check_tier_quota(user_id: str, tier: str):
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time()).isoformat()
    
    try:
        resp = supabase.table("jobs").select("id", count="exact").eq("user_id", user_id).gte("created_at", start_of_day).execute()
        if resp.count >= limits["max_jobs_per_day"]:
            raise HTTPException(status_code=429, detail="Daily job quota exceeded for your plan.")
    except Exception as e:
        logger.error(f"Could not check quota for user {user_id}: {e}")
        # Fail open or closed? For now, let it pass but log error.
        pass


class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str

class ApiKeyDeleteRequest(BaseModel):
    provider: str

@app.post("/api/keys")
async def save_api_key(req: Request, body: ApiKeyRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    provider_lower = body.provider.lower()
    try:
        # Securely delete old key if it exists, using an RPC function
        supabase.rpc("delete_user_api_key", { "p_user_id": user_id, "p_provider": provider_lower }).execute()

        # Create new secret in the vault
        resp = supabase.rpc("create_secret_wrapper", {
            "new_secret": body.api_key,
            "new_name": f"{user_id}_{provider_lower}_key_{uuid.uuid4()}",
        }).execute()

        secret_id = resp.data
        if not secret_id:
            raise Exception("Failed to create secret in vault.")

        # Store the reference to the new secret
        supabase.table("user_api_keys").insert({
            "user_id": user_id,
            "provider": provider_lower,
            "encrypted_api_key_id": secret_id
        }).execute()

        return JSONResponse({"status": "ok", "provider": body.provider})
    except Exception as e:
        logger.error("Failed to save API key for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save key: {e}")


@app.delete("/api/keys")
async def delete_api_key(req: Request, body: ApiKeyDeleteRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    provider_lower = body.provider.lower()
    try:
        supabase.rpc("delete_user_api_key", {
            "p_user_id": user_id,
            "p_provider": provider_lower
        }).execute()
        return JSONResponse({"status": "ok", "message": f"Key for {provider_lower} deleted."})
    except Exception as e:
        logger.error(f"Failed to delete API key for provider {provider_lower}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete key")

@app.get("/api/keys")
async def get_user_keys(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    resp = supabase.table("user_api_keys").select("provider").eq("user_id", user_id).execute()
    providers = [item["provider"] for item in resp.data]
    return JSONResponse({"providers": providers})

# -------------------------------------------
# PROCESSING ENDPOINT (CORRECTED AND FINAL)
# -------------------------------------------
class ProcessRequestForm:
    def __init__(
        self,
        task: str = Form(...),
        error_log: Optional[str] = Form(None),
        provider: str = Form(...),
        model: Optional[str] = Form(None),
        token_saver_enabled: Optional[bool] = Form(False),
        # --- ADD THESE NEW OPTIONAL PARAMETERS ---
        abstraction_enabled: Optional[bool] = Form(True),
        abstraction_level: Optional[str] = Form("paranoid"),
        abstraction_chunking: Optional[bool] = Form(False),
        abstraction_noise: Optional[bool] = Form(True),
    ):
        self.task = task
        self.error_log = error_log
        self.provider = provider
        self.model = model
        self.token_saver_enabled = token_saver_enabled
        self.abstraction_enabled = abstraction_enabled
        self.abstraction_level = abstraction_level
        self.abstraction_chunking = abstraction_chunking
        self.abstraction_noise = abstraction_noise

@app.post("/api/process_code")
async def api_process_code(
    req: Request,
    files: List[UploadFile] = File(...),
    form_data: ProcessRequestForm = Depends(),
    user: dict = Depends(get_current_user)
):
    user_id = user["id"]

    if form_data.task == "fix_and_secure" and not form_data.error_log:
        raise HTTPException(status_code=400, detail="Terminal output is required for the 'Fix & Secure' task.")

    user_tier = await get_user_tier(user_id)
    await check_tier_quota(user_id, user_tier)

    api_key = None
    provider = form_data.provider.lower()
    if provider not in ["ollama", "auto", "qwen"]:
        try:
            key_ref_resp = supabase.table("user_api_keys").select("encrypted_api_key_id").eq("user_id", user_id).eq("provider", provider).limit(1).single().execute()
            if not key_ref_resp.data:
                raise HTTPException(status_code=400, detail=f"API key for provider '{provider}' not found.")
            secret_id = key_ref_resp.data["encrypted_api_key_id"]
            decrypted_resp = supabase.rpc("reveal_secret", {"secret_id": secret_id}).execute()
            api_key = decrypted_resp.data
        except Exception as e:
            logger.error(f"Could not retrieve API key for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not retrieve API key.")

    project_files: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        is_zip = len(files) == 1 and files[0].filename and files[0].filename.lower().endswith(".zip")
        if is_zip:
            zip_path = os.path.join(tmpdir, files[0].filename)
            with open(zip_path, "wb") as f:
                shutil.copyfileobj(files[0].file, f)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
            for root, _, fnames in os.walk(tmpdir):
                for fname in fnames:
                    if not fname.lower().endswith(".zip") and not fname.startswith("._"):
                        fpath = os.path.join(root, fname)
                        rpath = os.path.relpath(fpath, tmpdir)
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                project_files[rpath] = f.read()
                        except (IOError, OSError):
                            pass
        else:
            for file in files:
                contents = await file.read()
                if file.filename:
                    project_files[file.filename] = contents.decode("utf-8", errors="ignore")

    if not project_files:
        raise HTTPException(status_code=400, detail="No processable files found in the upload.")

    job_id = str(uuid.uuid4())
    job_payload = {**form_data.__dict__, "project_files": project_files, "api_keys": {"api_key": api_key}}

    job_metadata = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "pending",
        "task": form_data.task,
        "provider": form_data.provider,
        "created_at": datetime.utcnow().isoformat()
    }
    
    JOB_STORE[job_id] = job_metadata
    supabase.table("jobs").insert(job_metadata).execute()

    asyncio.create_task(process_job_background(job_id, job_payload))
    return JSONResponse({"job_id": job_id})

# -------------------------------------------
# Background Job Processor & Status Endpoint
# -------------------------------------------
async def call_llm_and_process(payload: dict) -> dict:
    try:
        result_dict = await asyncio.to_thread(
            process_code_submission,
            project_files=payload.get("project_files", {}),
            provider_name=payload.get("provider"),
            model=payload.get("model"),
            task=payload.get("task"),
            error_log=payload.get("error_log"),
            token_saver=payload.get("token_saver_enabled", False),
            api_keys=payload.get("api_keys"),
            # --- PASS THE NEW PARAMETERS THROUGH ---
            abstraction_enabled=payload.get("abstraction_enabled"),
            abstraction_level=payload.get("abstraction_level"),
            abstraction_chunking=payload.get("abstraction_chunking"),
            abstraction_noise=payload.get("abstraction_noise"),
        )
        return {"success": True, **result_dict}
    except Exception as e:
        logger.error("Job failed: %s", e, exc_info=True)
        return {"success": False, "notice": "An internal error occurred during processing."}

async def process_job_background(job_id: str, payload: dict):
    job = JOB_STORE.get(job_id)
    if not job: return

    job["status"] = "running"
    supabase.table("jobs").update({"status": "running"}).eq("job_id", job_id).execute()

    try:
        response = await call_llm_and_process(payload)
        job_update = {
            "status": "completed" if response.get("success") else "failed",
            "result": response.get("result"),
            "notice": response.get("notice"),
            "analysis": response.get("analysis"),
            "validator_report": response.get("validator_report"),
            "sandbox_result": response.get("sandbox_result"),
        }
    except Exception as e:
        job_update = {
            "status": "failed",
            "result": None,
            "notice": f"Internal error: {str(e)}",
        }
    
    JOB_STORE[job_id].update(job_update)
    supabase.table("jobs").update(job_update).eq("job_id", job_id).execute()

@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    job = JOB_STORE.get(job_id)
    if job and job.get("user_id") == user_id:
        return JSONResponse(job)

    try:
        resp = supabase.table("jobs").select("*").eq("job_id", job_id).single().execute()
        if resp.data and resp.data.get("user_id") == user_id:
            return JSONResponse(resp.data)
    except Exception as e:
        logger.debug("Failed to fetch job from Supabase: %s", e)

    raise HTTPException(status_code=404, detail="Job not found or not authorized")

@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

