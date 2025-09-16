
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

# Admin client for accessing Vault securely
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key,
    options=ClientOptions(schema="vault")
)

JOB_STORE: Dict[str, Dict[str, Any]] = {}

# -------------------------------------------
# Auth Helpers (SECURE)
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

# -------------------------------------------
# Tier Limits
# -------------------------------------------
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
    return "free"  # Default if missing/error

async def check_tier_quota(user_id: str, tier: str):
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    today = datetime.utcnow().date()

    resp = supabase.table("jobs").select("created_at").eq("user_id", user_id).execute()
    jobs_today = [j for j in resp.data if datetime.strptime(j["created_at"], "%Y-%m-%dT%H:%M:%S.%f%z").date() == today]
    if len(jobs_today) >= limits["max_jobs_per_day"]:
        raise HTTPException(status_code=429, detail="Daily job quota exceeded for your plan.")

# -------------------------------------------
# API Key Management
# -------------------------------------------
class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str

@app.post("/api/keys")
async def save_api_key(req: Request, body: ApiKeyRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    provider_lower = body.provider.lower()

    try:
        # Check if user already has a key for this provider
        existing_key = supabase.table("user_api_keys") \
            .select("id, encrypted_api_key_id") \
            .eq("user_id", user_id) \
            .eq("provider", provider_lower) \
            .execute()

        # --- NEW LOGIC: If a key exists, delete it first ---
        if existing_key.data:
            key_id_to_delete = existing_key.data[0]["id"]
            secret_id_to_delete = existing_key.data[0]["encrypted_api_key_id"]

            # Delete the reference in user_api_keys
            supabase.table("user_api_keys").delete().eq("id", key_id_to_delete).execute()
            
            # Delete the actual secret from the vault
            supabase.rpc("delete_secret_wrapper", {"secret_id": secret_id_to_delete}).execute()

        # --- ALWAYS CREATE A NEW SECRET ---
        resp = supabase.rpc("create_secret_wrapper", {
            "new_secret": body.api_key,
            "new_name": f"{user_id}_{provider_lower}_key",
            "new_description": "API key for provider",
            "new_key_id": str(uuid.uuid4())  # Ensure this matches your create_secret_wrapper args
        }).execute()

        secret_id = resp.data

        supabase.table("user_api_keys").insert({
            "user_id": user_id,
            "provider": provider_lower,
            "encrypted_api_key_id": secret_id
        }).execute()

        return JSONResponse({"status": "ok", "provider": body.provider})

    except Exception as e:
        logger.error("Failed to save API key: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save key")
    
class ApiKeyDeleteRequest(BaseModel):
    provider: str

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
# Processing Endpoint
# -------------------------------------------
class ProcessRequestForm:
    def __init__(
        self,
        task: str = Form(...),
        provider: str = Form(...),
        model: Optional[str] = Form(None),
        token_saver_enabled: Optional[bool] = Form(False),
        abstraction_enabled: Optional[bool] = Form(True),
    ):
        self.task = task
        self.provider = provider
        self.model = model
        self.token_saver_enabled = token_saver_enabled
        self.abstraction_enabled = abstraction_enabled

@app.post("/api/process_code")
async def api_process_code(
    req: Request,
    files: List[UploadFile] = File(...),
    form_data: ProcessRequestForm = Depends(),
    user: dict = Depends(get_current_user)
):
    user_id = user["id"]

    user_tier = await get_user_tier(user_id)
    await check_tier_quota(user_id, user_tier)

    api_key = None
    provider = form_data.provider.lower()
    if provider not in ["ollama", "auto", "qwen"]:
        try:
            key_ref_resp = supabase.table("user_api_keys").select("encrypted_api_key_id").eq("user_id", user_id).eq("provider", provider).limit(1).execute()
            if not key_ref_resp.data:
                raise HTTPException(status_code=400, detail=f"API key for provider '{provider}' not found.")
            secret_id = key_ref_resp.data[0]["encrypted_api_key_id"]
            decrypted_resp = supabase.rpc("reveal_secret", {"secret_id": secret_id}).execute()
            api_key = decrypted_resp.data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not retrieve API key: {e}")

    project_files: Dict[str, str] = {}
    is_zip = len(files) == 1 and files[0].filename and files[0].filename.lower().endswith(".zip")

    with tempfile.TemporaryDirectory() as tmpdir:
        if is_zip:
            zip_path = os.path.join(tmpdir, files[0].filename)
            with open(zip_path, "wb") as f:
                shutil.copyfileobj(files[0].file, f)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
            for root, _, fnames in os.walk(tmpdir):
                for fname in fnames:
                    if not fname.endswith(".zip"):
                        fpath = os.path.join(root, fname)
                        rpath = os.path.relpath(fpath, tmpdir)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                project_files[rpath] = f.read()
                        except Exception:
                            pass
        else:
            for file in files:
                contents = await file.read()
                if file.filename:
                    project_files[file.filename] = contents.decode("utf-8")

    if not project_files:
        raise HTTPException(status_code=400, detail="No processable files found in the upload.")

    job_id = str(uuid.uuid4())
    job_payload = {**form_data.__dict__, "project_files": project_files, "api_keys": {"api_key": api_key}}

    JOB_STORE[job_id] = {
        "job_id": job_id,
        "payload": job_payload,
        "user_id": user_id,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table("jobs").insert(JOB_STORE[job_id]).execute()

    asyncio.create_task(process_job_background(job_id))

    return JSONResponse({"job_id": job_id})

# -------------------------------------------
# Background Job Processor
# -------------------------------------------
async def call_llm_and_process(payload: dict) -> dict:
    try:
        result_dict = await asyncio.to_thread(
            process_code_submission,
            project_files=payload.get("project_files", {}),
            provider_name=payload.get("provider"),
            model=payload.get("model"),
            task=payload.get("task"),
            token_saver=payload.get("token_saver_enabled", False),
            abstraction_enabled=payload.get("abstraction_enabled", True),
            api_keys=payload.get("api_keys"),
        )
        return {"success": True, "result": result_dict.get("result"), "notice": result_dict.get("notice")}
    except Exception as e:
        logger.error("Job failed: %s", e)
        return {"success": False, "result": f"Unexpected error: {e}", "notice": "Internal server error"}

async def process_job_background(job_id: str):
    job = JOB_STORE.get(job_id)
    if not job: 
        return
    job["status"] = "running"
    supabase.table("jobs").update({"status": "running"}).eq("job_id", job_id).execute()

    try:
        response = await call_llm_and_process(job["payload"])
        if response.get("success"):
            job["status"] = "completed"
            job["result"] = response.get("result")
            job["notice"] = response.get("notice")
        else:
            job["status"] = "failed"
            job["result"] = response.get("result") or "LLM failed without details"
            job["notice"] = response.get("notice")
    except Exception as e:
        job["status"] = "failed"
        job["result"] = f"Internal error: {str(e)}\n{traceback.format_exc()}"
        job["notice"] = "Internal processing error."

    JOB_STORE[job_id] = job
    supabase.table("jobs").update(job).eq("job_id", job_id).execute()

# -------------------------------------------
# Secure Job Status Endpoint
# -------------------------------------------
@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    """Fetches job status, ensuring the requesting user owns the job."""
    user_id = user["id"]

    try:
        resp = supabase.table("jobs").select("*").eq("job_id", job_id).single().execute()
        if resp.data and resp.data.get("user_id") == user_id:
            return JSONResponse(resp.data)
    except Exception as e:
        logger.debug("Failed to fetch job from Supabase: %s", e)

    job = JOB_STORE.get(job_id)
    if job and job.get("user_id") == user_id:
        return JSONResponse(job)

    raise HTTPException(status_code=404, detail="Job not found or not authorized")

# -------------------------------------------
# Health Check
# -------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
