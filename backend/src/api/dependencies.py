from fastapi import Request, HTTPException
from typing import Optional
import logging
from datetime import datetime
from src.api.globals import supabase, TIER_LIMITS
from src.config import settings

logger = logging.getLogger("server")

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
    country = req.headers.get("x-vercel-ip-country")
    if country: return country.upper()
    country = req.headers.get("cf-ipcountry")
    if country: return country.upper()
    client_ip = req.client.host
    if client_ip in ("127.0.0.1", "localhost", "::1"):
        return "IN"
    return "US"

async def get_optional_current_user(req: Request) -> Optional[dict]:
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
    user = await get_optional_current_user(req)
    if user: return user
    action_token = req.headers.get("X-0Pirate-Action-Token")
    if not action_token: return None
    try:
        user_resp = supabase.rpc("get_user_by_action_token", {"p_token": action_token}).execute()
        if user_resp.data: return user_resp.data
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
        count_resp = supabase.table("jobs").select("*", count="exact", head=True).eq("user_id", user_id).gte("created_at", f"{today}T00:00:00").execute()
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
        limit_being_used = TIER_LIMITS["free"]["max_jobs_per_day"]
        count_resp = supabase.table("jobs").select("*", count="exact", head=True).eq("ip_address", ip).is_("user_id", None).gte("created_at", f"{today}T00:00:00").execute()
        job_count = count_resp.count if count_resp.count is not None else 0
        if job_count >= limit_being_used:
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
    if provider_name in ["openai", "gpt"]: return settings.openai_key
    elif provider_name == "gemini": return settings.google_key
    elif provider_name == "claude": return settings.anthropic_key
    elif provider_name == "deepseek": return settings.deepseek_key
    elif provider_name == "mistral": return settings.mistral_key
    elif provider_name == "groq": return settings.groq_key
    else: return None
