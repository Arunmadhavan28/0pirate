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
import json
import razorpay
from fastapi import Header
from typing import Annotated

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError

from src.config import settings
from src.secure_wrapper import process_code_submission

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

APP_NAME = "0pirate-backend"
app = FastAPI(title=APP_NAME)

# Global middleware to catch exceptions and ensure responses

class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        # --- THIS IS THE FIX ---
        # It now checks if the exception is an HTTPException (like our 429 quota error)
        # and lets FastAPI handle it correctly, instead of turning it into a 500 error.
        except HTTPException as http_exc:
            raise http_exc
        except Exception as exc:
            logger.error(f"Global error at {request.url}: {traceback.format_exc()}")
            return JSONResponse(status_code=500, content={"detail": "An internal server error occurred."})


# CORS configuration (allows your frontend origins)
origins = [
    "http://localhost:3000",
    "https://*.0pirate.com",
    "https://0pirate.com",
    "https://backend-muddy-moon-310.fly.dev",
    "https://api.0pirate.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.0pirate\.com|http://localhost:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Explicit handlers for validation and general exceptions (ensures CORS on errors)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error at {request.url}: {exc}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url}: {traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error occurred."})

if not settings.supabase_url or not settings.supabase_key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in config.py")

supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

JOB_STORE: Dict[str, Dict[str, Any]] = {}

TIER_LIMITS = {
    "free": {"max_jobs_per_day": 2, "max_files": 5},
    "developer": {"max_jobs_per_day": 50, "max_files": 20},
    "professional": {"max_jobs_per_day": 200, "max_files": 50},
    "enterprise": {"max_jobs_per_day": 500, "max_files": 100},
}

async def get_current_user(req: Request) -> dict:
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
    
async def get_optional_current_user(req: Request) -> Optional[dict]:
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        user_resp = supabase.auth.get_user(token)
        if user_resp and getattr(user_resp, "user", None):
            u = user_resp.user
            return {"id": u.id, "email": u.email}
        return None
    except Exception:
        return None

async def get_user_tier(user_id: str) -> str:
    try:
        resp = supabase.table("profiles").select("tier").eq("id", user_id).single().execute()
        if resp.data and resp.data.get("tier"):
            return resp.data["tier"]
    except Exception as e:
        logger.error(f"Could not fetch tier for user {user_id}: {e}")
    return "free"

async def check_tier_quota(user_id: str, tier: str):
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    try:
        today = datetime.utcnow().date().isoformat()
        count_resp = supabase.table("jobs") \
            .select("*", count="exact", head=True) \
            .eq("user_id", user_id) \
            .gte("created_at", f"{today}T00:00:00") \
            .execute()
        job_count = count_resp.count if count_resp.count is not None else 0
        if job_count >= limits["max_jobs_per_day"]:
            raise HTTPException(status_code=429, detail="Daily job limit exceeded for your tier")
    except HTTPException as http_exc:
        # This is the crucial change: re-raise the specific 429 error
        raise http_exc
    except Exception as e:
        logger.error(f"Quota check failed for user {user_id}: {str(e)}", exc_info=True)
        # This now only runs for TRUE internal errors (e.g., database down)
        raise HTTPException(status_code=500, detail="Could not verify usage quota.")
    
async def check_anonymous_quota(req: Request):
    ip = req.client.host
    try:
        today = datetime.utcnow().date().isoformat()
        count_resp = supabase.table("jobs") \
            .select("*", count="exact", head=True) \
            .eq("ip_address", ip) \
            .is_("user_id", None) \
            .gte("created_at", f"{today}T00:00:00") \
            .execute()
        job_count = count_resp.count if count_resp.count is not None else 0
        if job_count >= TIER_LIMITS["free"]["max_jobs_per_day"]:
            raise HTTPException(status_code=429, detail="Daily anonymous job limit exceeded")
    except HTTPException as http_exc:
        # Re-raise the specific 429 error
        raise http_exc
    except Exception as e:
        logger.error(f"Anonymous quota check failed for IP {ip}: {str(e)}", exc_info=True)
        # This now only runs for TRUE internal errors
        raise HTTPException(status_code=500, detail="Could not verify usage quota.")

def get_api_key_for_provider(provider_name: str, user_api_key: Optional[str] = None) -> Optional[str]:
    provider_name = provider_name.lower()

    if user_api_key:
        user_api_key = user_api_key.strip()
        if len(user_api_key) < 10:
            raise HTTPException(status_code=400, detail="Invalid API key provided.")
        return user_api_key

    if provider_name in ["openai", "gpt"]:
        return settings.openai_key
    elif provider_name == "gemini":
        return settings.google_key
    elif provider_name == "claude":
        return settings.anthropic_key
    elif provider_name == "deepseek":
        return settings.deepseek_key
    elif provider_name == "mistral":
        return settings.mistral_key
    elif provider_name == "groq":
        return settings.groq_key
    else:
        return None

class ApiKeyRequest(BaseModel):
    provider: str
    name: str
    api_key: str

class ApiKeyDeleteRequest(BaseModel):
    name: str

@app.post("/api/keys")
async def save_api_key(req: Request, body: ApiKeyRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        supabase.rpc("upsert_user_api_key", {
            "p_user_id": user_id,
            "p_provider": body.provider.lower(),
            "p_name": body.name,
            "p_api_key": body.api_key
        }).execute()
        return JSONResponse({"status": "ok", "provider": body.provider, "name": body.name})
    except Exception as e:
        logger.error(f"Failed to save API key for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save key.")

@app.delete("/api/keys")
async def delete_api_key(req: Request, body: ApiKeyDeleteRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        supabase.rpc("delete_user_api_key", {
            "p_user_id": user_id,
            "p_key_name": body.name
        }).execute()
        return JSONResponse({"status": "ok", "message": f"Key '{body.name}' deleted."})
    except Exception as e:
        logger.error(f"Failed to delete API key with name {body.name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete key")

@app.get("/api/keys")
async def get_user_keys(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        resp = supabase.rpc("get_user_api_keys", {"p_user_id": user_id}).execute()
        return JSONResponse({"keys": resp.data or []})
    except Exception as e:
        logger.error(f"Could not retrieve keys for user {user_id}: {str(e)}", exc_info=True)
        return JSONResponse({"keys": []})
    
@app.get("/api/plans")
async def get_plans(req: Request):
    country = req.headers.get("x-vercel-ip-country")
    if not country:
        client_ip = req.client.host 
        country = "IN" if client_ip in ("127.0.0.1", "localhost") else "US"

    if country == "IN":
        price_monthly_col = "price_monthly_inr"
        price_yearly_col = "price_yearly_inr"
        plan_monthly_col = "razorpay_plan_id_monthly_inr"
        plan_yearly_col = "razorpay_plan_id_yearly_inr"
        currency = "INR"
    else:
        price_monthly_col = "price_monthly_usd"
        price_yearly_col = "price_yearly_usd"
        plan_monthly_col = "razorpay_plan_id_monthly_usd"
        plan_yearly_col = "razorpay_plan_id_yearly_usd"
        currency = "USD"

    try:
        resp = supabase.table("plans") \
            .select(f"id, name, features, {price_monthly_col}, {price_yearly_col}, {plan_monthly_col}, {plan_yearly_col}") \
            .eq("active", True) \
            .order("price_monthly_usd", desc=False) \
            .execute()

        if not resp.data:
            return JSONResponse({"plans": []})

        formatted_plans = []
        for plan in resp.data:
            formatted_plans.append({
                "id": plan["id"],
                "name": plan["name"],
                "features": plan["features"],
                "currency": currency,
                "monthly": {
                    "price": plan[price_monthly_col],
                    "razorpay_plan_id": plan[plan_monthly_col]
                },
                "yearly": {
                    "price": plan[price_yearly_col],
                    "razorpay_plan_id": plan[plan_yearly_col]
                }
            })

        return JSONResponse({"plans": formatted_plans})
    except Exception as e:
        logger.error(f"Failed to fetch plans: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not retrieve pricing plans.")
    
class CreateOrderRequest(BaseModel):
    plan_id: str
    billing_cycle: str

razorpay_client = razorpay.Client(
    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
)

@app.post("/api/create-order")
async def create_order(req: Request, body: CreateOrderRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    country = req.headers.get("x-vercel-ip-country")
    if not country:
        client_ip = req.client.host
        country = "IN" if client_ip in ("127.0.0.1", "localhost") else "US"

    if country == "IN":
        price_col = f"price_{body.billing_cycle}_inr"
        currency = "INR"
    else:
        price_col = f"price_{body.billing_cycle}_usd"
        currency = "USD"
    
    try:
        plan_resp = supabase.table("plans").select(price_col).eq("id", body.plan_id).single().execute()
        if not plan_resp.data:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        amount_in_smallest_unit = plan_resp.data[price_col]

        order_data = {
            "amount": amount_in_smallest_unit,
            "currency": currency,
            "receipt": f"order_{uuid.uuid4().hex[:16]}",
            "notes": { "user_id": user_id, "plan_id": body.plan_id }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        return JSONResponse({
            "order_id": order["id"],
            "razorpay_key_id": settings.razorpay_key_id,
            "amount": order["amount"],
            "currency": order["currency"]
        })
    except Exception as e:
        logger.error(f"Error creating Razorpay order for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create payment order.")

@app.post("/api/razorpay-webhook")
async def razorpay_webhook(req: Request, x_razoray_signature: Annotated[str | None, Header()] = None):
    print("--- WEBHOOK FUNCTION IS RUNNING THE LATEST CODE ---")
    body = await req.body()
    try:
        payload_str = body.decode('utf-8')
        
        razorpay_client.utility.verify_webhook_signature(
            payload_str,
            x_razoray_signature,
            settings.razorpay_webhook_secret
        )
        
        webhook_data = json.loads(payload_str)
        event = webhook_data.get("event")

        if event == "payment.captured":
            payload = webhook_data["payload"]["payment"]["entity"]
            user_id = payload["notes"]["user_id"]
            plan_id = payload["notes"]["plan_id"]
            
            supabase.table("profiles").update({"tier": plan_id}).eq("id", user_id).execute()
            logger.info(f"Successfully upgraded user {user_id} to plan {plan_id}")

        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook verification failed or error during processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid webhook signature or processing error")

class ProcessRequestForm:
    def __init__(
        self,
        task: str = Form(...),
        provider: str = Form(...),
        error_log: Optional[str] = Form(None),
        model: Optional[str] = Form(None),
        api_key_name: Optional[str] = Form(None),
        api_key: Optional[str] = Form(None),
        token_saver_enabled: Optional[bool] = Form(False),
        abstraction_enabled: Optional[bool] = Form(True),
        abstraction_level: Optional[str] = Form("paranoid"),
    ):
        self.task = task
        self.provider = provider
        self.error_log = error_log
        self.model = model
        self.api_key_name = api_key_name
        self.api_key = api_key
        self.token_saver_enabled = token_saver_enabled
        self.abstraction_enabled = abstraction_enabled
        self.abstraction_level = abstraction_level

@app.post("/api/process_code")
async def api_process_code(
    req: Request,
    files: List[UploadFile] = File(...),
    form_data: ProcessRequestForm = Depends(),
    user: Optional[dict] = Depends(get_optional_current_user)
):
    user_id = None
    ip_address = None
    api_key = form_data.api_key

    # The logic is now unified: every job needs a key.
    if user:
        # --- LOGGED-IN USER LOGIC ---
        user_id = user["id"]

        # FIXED: Get the user's tier and check their quota BEFORE proceeding.
        user_tier = await get_user_tier(user_id)
        await check_tier_quota(user_id, user_tier)

        # Logged-in users must use a saved key by providing its name.
        if form_data.provider.lower() not in ["auto", "ollama"] and not form_data.api_key_name:
            raise HTTPException(status_code=400, detail="Please select a saved API key.")
        
        if form_data.api_key_name:
            try:
                # Fetches the user's saved API key
                key_ref_resp = supabase.table("user_api_keys").select("encrypted_api_key_id").eq("user_id", user_id).eq("name", form_data.api_key_name).limit(1).single().execute()
                if not key_ref_resp.data:
                    raise HTTPException(status_code=400, detail=f"API key named '{form_data.api_key_name}' not found.")
                secret_id = key_ref_resp.data["encrypted_api_key_id"]
                decrypted_resp = supabase.rpc("reveal_secret", {"secret_id": secret_id}).execute()
                api_key = decrypted_resp.data
            except Exception as e:
                raise HTTPException(status_code=500, detail="Could not retrieve your saved API key.")

    else:
        # --- ANONYMOUS USER LOGIC ---
        ip_address = req.client.host
        
        # FIXED: Check the anonymous user's quota BEFORE proceeding.
        await check_anonymous_quota(req)

        # For an anonymous user, a raw API key is ALWAYS required.
        if form_data.provider.lower() != 'ollama' and not api_key:
            raise HTTPException(status_code=401, detail="Please provide an API key to run an analysis.")

    # --- (File processing and job creation logic is the same) ---
    project_files: Dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        is_zip = len(files) == 1 and files[0].filename and files[0].filename.lower().endswith(".zip")
        if is_zip:
            zip_path = os.path.join(tmpdir, files[0].filename)
            with open(zip_path, "wb") as f: shutil.copyfileobj(files[0].file, f)
            with zipfile.ZipFile(zip_path, "r") as zf: zf.extractall(tmpdir)
            for root, _, fnames in os.walk(tmpdir):
                for fname in fnames:
                    if not fname.lower().endswith(".zip") and not fname.startswith("._"):
                        fpath = os.path.join(root, fname)
                        rpath = os.path.relpath(fpath, tmpdir)
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f: project_files[rpath] = f.read()
                        except (IOError, OSError): pass
        else:
            for file in files:
                contents = await file.read()
                if file.filename: project_files[file.filename] = contents.decode("utf-8", errors="ignore")

    if not project_files:
        raise HTTPException(status_code=400, detail="No processable files found.")

    job_id = str(uuid.uuid4())
    job_payload = {**form_data.__dict__, "project_files": project_files, "api_keys": {"api_key": api_key}}
    
    job_metadata = {
        "job_id": job_id, "user_id": user_id, "ip_address": ip_address, "status": "pending",
        "task": form_data.task, "provider": form_data.provider, "created_at": datetime.utcnow().isoformat()
    }
    
    JOB_STORE[job_id] = job_metadata
    supabase.table("jobs").insert(job_metadata).execute()

    asyncio.create_task(process_job_background(job_id, job_payload))
    return JSONResponse({"job_id": job_id})


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
            abstraction_enabled=payload.get("abstraction_enabled"),
            abstraction_level=payload.get("abstraction_level"),
            abstraction_chunking=payload.get("abstraction_chunking"),
            abstraction_noise=payload.get("abstraction_noise"),
        )
        return {"success": True, **result_dict}
    except Exception as e:
        logger.error(f"Job failed: {str(e)}", exc_info=True)
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
async def get_job_status(req: Request, job_id: str, user: Optional[dict] = Depends(get_optional_current_user)):
    job = JOB_STORE.get(job_id)
    if job:
        if user and job.get("user_id") == user["id"]:
            return JSONResponse(job)
        if not user and job.get("ip_address") == req.client.host:
            return JSONResponse(job)

    try:
        resp = supabase.table("jobs").select("*").eq("job_id", job_id).single().execute()
        if resp.data:
            db_job = resp.data
            if user and db_job.get("user_id") == user["id"]:
                return JSONResponse(db_job)
            if not user and db_job.get("ip_address") == req.client.host:
                return JSONResponse(db_job)
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail="Job not found or not authorized")

@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
