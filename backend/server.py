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
    "free": {"max_jobs_per_day": 2, "max_files": 5},
    "developer": {"max_jobs_per_day": 50, "max_files": 20},
    "professional": {"max_jobs_per_day": 200, "max_files": 50},
    "enterprise": {"max_jobs_per_day": 500, "max_files": 100}, # For custom plans
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
    name: str  # NEW: Custom name for the key
    api_key: str

class ApiKeyDeleteRequest(BaseModel):
    name: str  # CHANGED: We now delete by name

@app.post("/api/keys")
async def save_api_key(req: Request, body: ApiKeyRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        # The Python server securely gets the user_id from the token and passes it to the RPC.
        # THIS IS THE FIX: We are now correctly passing the p_user_id parameter.
        supabase.rpc("upsert_user_api_key", {
            "p_user_id": user_id,
            "p_provider": body.provider.lower(),
            "p_name": body.name,
            "p_api_key": body.api_key
        }).execute()

        return JSONResponse({"status": "ok", "provider": body.provider, "name": body.name})
    except Exception as e:
        logger.error("Failed to save API key for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save key.")



@app.delete("/api/keys")
async def delete_api_key(req: Request, body: ApiKeyDeleteRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        # The Python server securely gets the user_id and passes it to the RPC.
        supabase.rpc("delete_user_api_key", {
            "p_user_id": user_id,
            "p_key_name": body.name
        }).execute()
        return JSONResponse({"status": "ok", "message": f"Key '{body.name}' deleted."})
    except Exception as e:
        logger.error(f"Failed to delete API key with name {body.name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete key")

@app.get("/api/keys")
async def get_user_keys(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        # It must call the 'get_user_api_keys' RPC function
        resp = supabase.rpc("get_user_api_keys", {"p_user_id": user_id}).execute()
        return JSONResponse({"keys": resp.data or []})
    except Exception as e:
        logger.error(f"Could not retrieve keys for user {user_id}: {e}")
        return JSONResponse({"keys": []})
    
@app.get("/api/plans")
async def get_plans(req: Request):
    """
    Fetches plans and returns prices based on user's country.
    Defaults to USD if the country is not India.
    """
    # In production, this IP would come from a header like 'X-Forwarded-For'.
    # We'll simulate the logic for local testing.
    client_ip = req.client.host 
    
    # This is a placeholder for a real GeoIP lookup.
    # It checks if the IP is local to simulate a user from India.
    country = "IN" if client_ip in ("127.0.0.1", "localhost") else "US"

    if country == "IN":
        price_monthly_col = "price_monthly_inr"
        price_yearly_col = "price_yearly_inr"
        plan_monthly_col = "razorpay_plan_id_monthly_inr"
        plan_yearly_col = "razorpay_plan_id_yearly_inr"
        currency = "INR"
    else:
        # Default to US Dollar prices for everyone else
        price_monthly_col = "price_monthly_usd"
        price_yearly_col = "price_yearly_usd"
        plan_monthly_col = "razorpay_plan_id_monthly_usd"
        plan_yearly_col = "razorpay_plan_id_yearly_usd"
        currency = "USD"

    try:
        # Fetch the relevant columns from the Supabase table
        resp = supabase.table("plans") \
            .select(f"id, name, features, {price_monthly_col}, {price_yearly_col}, {plan_monthly_col}, {plan_yearly_col}") \
            .eq("active", True) \
            .order("price_monthly_usd", desc=False) \
            .execute()

        if not resp.data:
            return JSONResponse({"plans": []})

        # Structure the data cleanly for the frontend to use
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
        logger.error(f"Failed to fetch plans: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve pricing plans.")
    
# Add this Pydantic model with your other models
class CreateOrderRequest(BaseModel):
    plan_id: str
    billing_cycle: str # 'monthly' or 'yearly'

# Initialize the Razorpay client (place this near your Supabase client)
razorpay_client = razorpay.Client(
    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
)

# Add this new endpoint
@app.post("/api/create-order")
async def create_order(req: Request, body: CreateOrderRequest, user: dict = Depends(get_current_user)):
    print(f"--- DEBUG: Creating order for Plan ID: {body.plan_id}, Cycle: {body.billing_cycle} ---")
    user_id = user["id"]
    client_ip = req.client.host
    country = "IN" if client_ip in ("127.0.0.1", "localhost") else "US"

    # Determine which database columns to use based on location and billing cycle
    if country == "IN":
        price_col = f"price_{body.billing_cycle}_inr"
        currency = "INR"
    else:
        price_col = f"price_{body.billing_cycle}_usd"
        currency = "USD"
    
    try:
        # Fetch the plan price from your Supabase 'plans' table
        plan_resp = supabase.table("plans").select(price_col).eq("id", body.plan_id).single().execute()
        if not plan_resp.data:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        amount_in_smallest_unit = plan_resp.data[price_col]

        order_data = {
            "amount": amount_in_smallest_unit,
            "currency": currency,
            "receipt": f"order_{uuid.uuid4().hex[:16]}",
            "notes": {
                "user_id": user_id,
                "plan_id": body.plan_id
            }
        }
        
        # Create the order with Razorpay
        order = razorpay_client.order.create(data=order_data)
        
        return JSONResponse({
            "order_id": order["id"],
            "razorpay_key_id": settings.razorpay_key_id,
            "amount": order["amount"],
            "currency": order["currency"]
        })

    except Exception as e:
        logger.error(f"Error creating Razorpay order for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not create payment order.")

@app.post("/api/razorpay-webhook")
async def razorpay_webhook(req: Request, x_razoray_signature: Annotated[str | None, Header()] = None):
    print("--- WEBHOOK FUNCTION IS RUNNING THE LATEST CODE ---")
    # Read the request body ONCE
    body = await req.body()
    try:
        # Decode the raw body to a string
        payload_str = body.decode('utf-8')
        
        # Use the decoded string to verify the signature
        razorpay_client.utility.verify_webhook_signature(
            payload_str,
            x_razoray_signature,
            settings.razorpay_webhook_secret
        )
        
        # Parse the SAME string into a JSON object
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
        logger.error(f"Webhook verification failed or error during processing: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature or processing error")





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
        api_key_name: str = Form(...),  # NEW: User must specify which key to use
        token_saver_enabled: Optional[bool] = Form(False),
        abstraction_enabled: Optional[bool] = Form(True),
        abstraction_level: Optional[str] = Form("paranoid"),
        abstraction_chunking: Optional[bool] = Form(False),
        abstraction_noise: Optional[bool] = Form(True),
    ):
        self.task = task
        self.error_log = error_log
        self.provider = provider
        self.model = model
        self.api_key_name = api_key_name
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
            # UPDATED LOGIC: Fetch the key by its custom name for the current user.
            key_ref_resp = supabase.table("user_api_keys") \
                .select("encrypted_api_key_id") \
                .eq("user_id", user_id) \
                .eq("name", form_data.api_key_name) \
                .limit(1).single().execute()

            if not key_ref_resp.data:
                raise HTTPException(status_code=400, detail=f"API key named '{form_data.api_key_name}' not found.")
            
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

