from typing import Dict, Any
from supabase import create_client, Client
import razorpay
from src.config import settings

if not settings.supabase_url or not settings.supabase_key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in config.py")

supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

JOB_STORE: Dict[str, Dict[str, Any]] = {}

TIER_LIMITS = {
    "free": {"max_jobs_per_day": 20, "max_files": 5},
    "developer": {"max_jobs_per_day": 50, "max_files": 20},
    "professional": {"max_jobs_per_day": 200, "max_files": 50},
    "enterprise": {"max_jobs_per_day": 500, "max_files": 100},
}

razorpay_client = razorpay.Client(
    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
)
