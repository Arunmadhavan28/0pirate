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
import hashlib
import subprocess
from src.client_redactor import run_redaction
from typing import Union

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError
from src.validator import validate_files
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
        except HTTPException as http_exc:
            raise http_exc
        except Exception as exc:
            logger.error(f"Global error at {request.url}: {traceback.format_exc()}")
            return JSONResponse(status_code=500, content={"detail": "An internal server error occurred."})


# CORS configuration (allows your frontend origins)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000", 
    "http://0.0.0.0:3000", 
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
    # Convert errors to JSON-serializable format
    errors = []
    for error in exc.errors():
        error_dict = {
            "type": error.get("type"),
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "url": error.get("url", "")
        }
        # Don't include the 'input' field which contains UploadFile
        errors.append(error_dict)
    
    return JSONResponse(status_code=422, content={"detail": errors})

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

def get_country_code(req: Request) -> str:
    # 1. Check Vercel header
    country = req.headers.get("x-vercel-ip-country")
    if country: return country.upper()
    
    # 2. Check Cloudflare header (common if using Cloudflare)
    country = req.headers.get("cf-ipcountry")

    print(f"DEBUG: Cloudflare Header: {cf_country} | Client IP: {req.client.host}")
    if country: return country.upper()
    
    # 3. Check for Fly.io or other proxy headers if needed
    # (Fly.io doesn't provide a country header by default, you may need an IP lookup service)
    
    # 4. Localhost / Development check
    client_ip = req.client.host
    if client_ip in ("127.0.0.1", "localhost", "::1"):
        return "IN"
        
    # 5. Default Fallback
    # If you are in India and testing on a server without headers, change this to "IN" temporarily.
    # Otherwise, keep it "US".
    return "US"

async def get_optional_current_user(req: Request) -> Optional[dict]:
    """
    Tries to get the current user via JWT, but returns None instead of raising
    an exception if the user is not authenticated via JWT.
    """
    try:
        user = await get_current_user(req)
        return user
    except HTTPException as e:
        if e.status_code == 401:
            return None
        raise e
    except Exception:
        return None

async def get_optional_authenticated_user(req: Request) -> Optional[dict]:
    """
    Tries to authenticate a user via JWT first, then falls back to Action Token.
    Returns None if neither method works, instead of raising 401.
    """
    # Try Supabase JWT first
    user = await get_optional_current_user(req)
    if user:
        return user

    # Fallback to Action Token
    action_token = req.headers.get("X-0Pirate-Action-Token")
    if not action_token:
        return None

    try:
        user_resp = supabase.rpc("get_user_by_action_token", {"p_token": action_token}).execute()
        if user_resp.data:
            return user_resp.data
        else:
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
        raise http_exc
    except Exception as e:
        logger.error(f"Quota check failed for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not verify usage quota.")
    
async def check_anonymous_quota(req: Request):
    ip = req.client.host
    try:
        today = datetime.utcnow().date().isoformat()
        
        # --- ADD THIS DEBUG PRINT ---
        limit_being_used = TIER_LIMITS["free"]["max_jobs_per_day"]
        print(f"DEBUG: Checking anonymous quota for IP {ip}. Limit being used: {limit_being_used}")
        # --- END OF DEBUG PRINT ---

        count_resp = supabase.table("jobs") \
            .select("*", count="exact", head=True) \
            .eq("ip_address", ip) \
            .is_("user_id", None) \
            .gte("created_at", f"{today}T00:00:00") \
            .execute()
        job_count = count_resp.count if count_resp.count is not None else 0
        
        # --- Optional: Print the current count ---
        print(f"DEBUG: Current job count for IP {ip} today: {job_count}")
        # --- End Optional Print ---

        if job_count >= limit_being_used: # Use the variable here
            raise HTTPException(status_code=429, detail="Daily anonymous job limit exceeded")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Anonymous quota check failed for IP {ip}: {str(e)}", exc_info=True)
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

@app.post("/api/redact")
async def api_redact_code(
    files: List[UploadFile] = File(...),
    allow_list_json: Optional[str] = Form(None)
):
    """
    A stateless endpoint that only performs redaction and abstraction.
    """
    project_files: Dict[str, str] = {}
    for file in files:
        contents = await file.read()
        if file.filename:
            project_files[file.filename] = contents.decode("utf-8", errors="ignore")

    if not project_files:
        raise HTTPException(status_code=400, detail="No files provided for redaction.")

    allow_list: Optional[List[str]] = None
    if allow_list_json:
        try:
            allow_list = json.loads(allow_list_json)
            if not isinstance(allow_list, list):
                allow_list = None
        except json.JSONDecodeError:
            logger.warning("Invalid allow_list_json received, ignoring.")
            allow_list = None

    try:
        redaction_result = await asyncio.to_thread(
            run_redaction, 
            project_files=project_files, 
            allow_list=allow_list
        )
        return JSONResponse(content=redaction_result)
    except Exception as e:
        logger.error(f"Redaction failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"An error occurred during redaction: {e}")

@app.get("/api/plans")
async def get_plans(req: Request):
    # Use the helper function
    country = get_country_code(req)

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
    
    # Use the same helper function to ensure currency matches what they saw on the pricing page
    country = get_country_code(req)

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
        tamper_evident_hash: Optional[str] = Form(None),
        cove_hardening_enabled: Optional[bool] = Form(False),
        user_prompt: Optional[str] = Form(None),
        language_hint: Optional[str] = Form(None)
    ):
        self.task = task
        self.provider = provider
        self.error_log = error_log
        self.model = model
        self.api_key_name = api_key_name
        self.api_key = api_key
        self.token_saver_enabled = token_saver_enabled
        self.tamper_evident_hash = tamper_evident_hash
        self.cove_hardening_enabled = cove_hardening_enabled
        self.user_prompt = user_prompt
        self.language_hint = language_hint

async def get_authenticated_user(req: Request) -> dict:
    """
    Authenticates a user via Supabase JWT (for web app) or a long-lived
    action token (for GitHub Action).
    """
    user = await get_optional_current_user(req)
    if user:
        return user

    action_token = req.headers.get("X-0Pirate-Action-Token")

    if action_token:
        logger.info(f"Received action token ending in: ...{action_token[-4:]}")

    if not action_token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    
    try:
        user_resp = supabase.rpc("get_user_by_action_token", {"p_token": action_token}).execute()
        if user_resp.data:
            return user_resp.data
        else:
            raise HTTPException(status_code=401, detail="Invalid or expired action token.")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired action token.")


@app.post("/api/process_code")
async def api_process_code(
    req: Request,
    files: Optional[Union[UploadFile, List[UploadFile]]] = File(None),  
    form_data: ProcessRequestForm = Depends(),
    user: Optional[dict] = Depends(get_optional_authenticated_user) 
    #user: Optional[dict] = None 

):
    # ✅ Normalize files to always be a list
    file_list = []
    if files:
        if isinstance(files, list):
            file_list = files
        else:
            file_list = [files]  # Wrap single file in list
    
    # Hash Validation
    combined_content = ""
    if file_list:
        sorted_files = sorted(file_list, key=lambda f: f.filename or "")
        for file in sorted_files:
            contents = await file.read()
            await file.seek(0)
            combined_content += contents.decode("utf-8", errors="ignore")

    is_generate_with_context = (form_data.task == "generate_code" and file_list)
    is_other_task = (form_data.task != "generate_code")

    # FIXED: Added missing closing parenthesis
    if is_other_task or is_generate_with_context:
        if not form_data.tamper_evident_hash:
            if combined_content:
                raise HTTPException(status_code=400, detail="Tamper-evident hash is required for file uploads.")
        
        if form_data.tamper_evident_hash:
            server_hash = hashlib.sha256(combined_content.encode("utf-8")).hexdigest()
            if server_hash != form_data.tamper_evident_hash:
                raise HTTPException(status_code=400, detail="Data integrity check failed.")

    user_id = None
    ip_address = None
    api_key = form_data.api_key

    # Authentication and Quota Logic
    if user:
        user_id = user["id"]
        user_tier = await get_user_tier(user_id)
        await check_tier_quota(user_id, user_tier)

        if form_data.provider.lower() not in ["auto", "ollama"] and form_data.api_key_name:
            try:
                key_ref_resp = supabase.table("user_api_keys").select("encrypted_api_key_id").eq("user_id", user_id).eq("name", form_data.api_key_name).limit(1).single().execute()
                if not key_ref_resp.data:
                    raise HTTPException(status_code=400, detail=f"API key '{form_data.api_key_name}' not found.")
                secret_id = key_ref_resp.data["encrypted_api_key_id"]
                decrypted_resp = supabase.rpc("reveal_secret", {"secret_id": secret_id}).execute()
                api_key = decrypted_resp.data
                if not api_key:
                    raise HTTPException(status_code=500, detail=f"Failed to decrypt key '{form_data.api_key_name}'.")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        elif form_data.provider.lower() not in ["auto", "ollama"] and not form_data.api_key_name and not api_key:
            raise HTTPException(status_code=400, detail="Please select a saved API key or provide one.")

    else:
        # Anonymous (guest) flow
        ip_address = req.client.host
        await check_anonymous_quota(req)
        # If client provided an api_key in form_data, use it (already in `api_key` variable).
        # Otherwise, attempt to use the server-owned provider key (if configured).
        provider_name = form_data.provider.lower() if form_data.provider else ""
        if provider_name not in ['ollama', 'auto']:
            # Try server-level key if client didn't pass one
            if not api_key:
                # --- FIX 1: MOVE QUOTA CHECK HERE ---
                # The user has NO key and wants to use the server's.
                # NOW we check the quota for using server resources.      
                try:
                    server_key = get_api_key_for_provider(provider_name, user_api_key=None)
                    if server_key:
                        api_key = server_key
                    else:
                        # --- FIX 2: CHANGE 401 to 503 ---
                        # This is a server config issue, not an auth issue.
                        raise HTTPException(status_code=503, detail=f"This server is not configured for anonymous '{provider_name}' use. Please sign in or provide your own API key.")
                except HTTPException:
                    # Re-raise quota (429) or 503 HTTPExceptions
                    raise
                except Exception as e:
                    logger.error(f"Failed to fetch server API key for provider '{provider_name}': {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Server configuration error for provider keys.")
            # If the user *did* provide an api_key (api_key was not empty),
            # we skip this entire block, no quota is checked, and their key is used.

    # File Processing - Handle .zip files
    project_files: Dict[str, str] = {}
    
    if file_list:
        for file in file_list:
            await file.seek(0)
            contents = await file.read()
            filename = file.filename or "unknown"
            
            # ✅ Check if it's a .zip file
            if filename.endswith('.zip'):
                try:
                    # Extract .zip contents
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                        tmp_zip.write(contents)
                        tmp_zip_path = tmp_zip.name
                    
                    # Extract and read all files from zip
                    with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                        for zip_info in zip_ref.infolist():
                            if not zip_info.is_dir():
                                with zip_ref.open(zip_info) as zipped_file:
                                    file_content = zipped_file.read().decode("utf-8", errors="ignore")
                                    project_files[zip_info.filename] = file_content
                    
                    # Cleanup temp file
                    os.remove(tmp_zip_path)
                    logger.info(f"Extracted {len(project_files)} files from {filename}")
                    
                except zipfile.BadZipFile:
                    raise HTTPException(status_code=400, detail=f"Invalid zip file: {filename}")
                except Exception as e:
                    logger.error(f"Failed to extract zip file {filename}: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to process zip file: {str(e)}")
            else:
                # ✅ Regular file (single file)
                project_files[filename] = contents.decode("utf-8", errors="ignore")

    # Validation based on task
    if form_data.task != "generate_code" and not project_files:
        raise HTTPException(status_code=400, detail="File upload is required for this task.")
    if form_data.task == "generate_code" and not form_data.user_prompt:
        raise HTTPException(status_code=400, detail="A text prompt is required to generate code.")

    job_id = str(uuid.uuid4())

    job_payload = {
        "abstracted_project_files": project_files,
        "original_project_files": project_files,
        "provider_name": form_data.provider,
        "model": form_data.model,
        "task": form_data.task,
        "error_log": form_data.error_log,
        "token_saver": form_data.token_saver_enabled,
        "api_keys": {"api_key": api_key},
        "use_cove_hardening": form_data.cove_hardening_enabled,
        "user_prompt_for_generation": form_data.user_prompt,
        "language_hint_for_generation": form_data.language_hint
    }

    job_metadata = {
        "job_id": job_id, "user_id": user_id, "ip_address": ip_address, "status": "pending",
        "task": form_data.task, "provider": form_data.provider, "created_at": datetime.utcnow().isoformat()
    }
    
    JOB_STORE[job_id] = {**job_metadata, "result": None, "analysis": None, "notice": None, "sandbox_result": None, "validation_result": None}
    
    try:
        supabase.table("jobs").insert(job_metadata).execute()
    except Exception as db_exc:
        logger.error(f"Failed to insert job metadata into Supabase: {db_exc}")

    asyncio.create_task(process_job_background(job_id, job_payload))

    return JSONResponse({"job_id": job_id})


async def call_llm_and_process(payload: dict) -> dict:
    try:
        result_dict = await asyncio.to_thread(
            process_code_submission,
            abstracted_project_files=payload.get("abstracted_project_files", {}),
            original_project_files=payload.get("original_project_files", {}),
            provider_name=payload.get("provider_name"),
            model=payload.get("model"),
            task=payload.get("task"),
            error_log=payload.get("error_log"),
            token_saver=payload.get("token_saver", False),
            api_keys=payload.get("api_keys"),
            use_cove_hardening=payload.get("use_cove_hardening", False),
            user_prompt_for_generation=payload.get("user_prompt_for_generation"),
            language_hint_for_generation=payload.get("language_hint_for_generation")
        )
        output = {"success": True, **result_dict}
        if "validation_result" in result_dict:
            output["validation_result"] = result_dict["validation_result"]
        return output

    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"Job failed during call_llm_and_process: {str(e)}\nTraceback:\n{tb_str}")
        error_msg = str(e) if isinstance(e, (ValueError, HTTPException)) else "An internal error occurred during processing."
        return {"success": False, "notice": error_msg}

async def process_job_background(job_id: str, payload: dict):
    job = JOB_STORE.get(job_id)
    if not job:
        return

    job["status"] = "running"
    try:
        supabase.table("jobs").update({"status": "running"}).eq("job_id", job_id).execute()
    except Exception as db_exc:
        logger.warning(f"Failed to update job status to running in DB for {job_id}: {db_exc}")

    db_update = {}
    try:
        response = await call_llm_and_process(payload)
        full_result_update = {
            "status": "completed" if response.get("success") else "failed",
            "result": response.get("result"),
            "notice": response.get("notice"),
            "analysis": response.get("analysis"),
            "sandbox_result": response.get("sandbox_result"),
            "validation_result": response.get("validation_result")
        }
        JOB_STORE[job_id].update(full_result_update)

        db_update = {
            "status": full_result_update["status"],
            "notice": full_result_update["notice"],
        }

    except Exception as e:
        db_update = {"status": "failed", "notice": f"Internal processing error: {str(e)}"}
        if job_id in JOB_STORE:
            JOB_STORE[job_id].update(db_update)

    try:
        supabase.table("jobs").update(db_update).eq("job_id", job_id).execute()
    except Exception as db_exc:
        logger.error(f"Failed to update job final status in Supabase for {job_id}: {db_exc}")

@app.get("/api/status/{job_id}")
async def get_job_status(
    req: Request, 
    job_id: str, 
    user: Optional[dict] = Depends(get_optional_authenticated_user)
    #user: Optional[dict] = None 

   

):
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
    
    raise HTTPException(status_code=403, detail="Not authorized to view this job")

@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}