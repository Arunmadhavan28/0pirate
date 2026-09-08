from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
import logging
from src.api.models import ApiKeyRequest, ApiKeyDeleteRequest
from src.api.dependencies import get_current_user
from src.api.globals import supabase

router = APIRouter(prefix="/api/keys", tags=["auth"])
logger = logging.getLogger("server")

@router.post("")
async def save_api_key(req: Request, body: ApiKeyRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        supabase.rpc("upsert_user_api_key", {
            "p_user_id": user_id, "p_provider": body.provider.lower(), "p_name": body.name, "p_api_key": body.api_key
        }).execute()
        return JSONResponse({"status": "ok", "provider": body.provider, "name": body.name})
    except Exception as e:
        logger.error(f"Failed to save API key for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save key.")

@router.delete("")
async def delete_api_key(req: Request, body: ApiKeyDeleteRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        supabase.rpc("delete_user_api_key", {"p_user_id": user_id, "p_key_name": body.name}).execute()
        return JSONResponse({"status": "ok", "message": f"Key '{body.name}' deleted."})
    except Exception as e:
        logger.error(f"Failed to delete API key with name {body.name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete key")

@router.get("")
async def get_user_keys(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        resp = supabase.rpc("get_user_api_keys", {"p_user_id": user_id}).execute()
        return JSONResponse({"keys": resp.data or []})
    except Exception as e:
        logger.error(f"Could not retrieve keys for user {user_id}: {str(e)}", exc_info=True)
        return JSONResponse({"keys": []})
