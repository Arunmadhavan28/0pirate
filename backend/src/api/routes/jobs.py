from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Union
import logging
import asyncio
import tempfile
import zipfile
import os
import traceback
import hashlib
import uuid
import json
from datetime import datetime

from src.api.models import ProcessRequestForm
from src.api.dependencies import (
    get_optional_authenticated_user, 
    get_user_tier, 
    check_tier_quota, 
    check_anonymous_quota, 
    get_api_key_for_provider
)
from src.api.globals import supabase, JOB_STORE
from src.client_redactor import run_redaction
from src.secure_wrapper import process_code_submission

router = APIRouter(prefix="/api", tags=["jobs"])
logger = logging.getLogger("server")

@router.post("/redact")
async def api_redact_code(files: List[UploadFile] = File(...), allow_list_json: Optional[str] = Form(None)):
    project_files: Dict[str, str] = {}
    for file in files:
        contents = await file.read()
        if file.filename: project_files[file.filename] = contents.decode("utf-8", errors="ignore")
    if not project_files: raise HTTPException(status_code=400, detail="No files provided for redaction.")

    allow_list: Optional[List[str]] = None
    if allow_list_json:
        try:
            allow_list = json.loads(allow_list_json)
            if not isinstance(allow_list, list): allow_list = None
        except json.JSONDecodeError:
            allow_list = None

    try:
        redaction_result = await asyncio.to_thread(run_redaction, project_files=project_files, allow_list=allow_list)
        return JSONResponse(content=redaction_result)
    except Exception as e:
        logger.error(f"Redaction failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"An error occurred during redaction: {e}")

@router.post("/process_code")
async def api_process_code(
    req: Request, files: Optional[Union[UploadFile, List[UploadFile]]] = File(None),  
    form_data: ProcessRequestForm = Depends(), user: Optional[dict] = Depends(get_optional_authenticated_user) 
):
    file_list = []
    if files:
        if isinstance(files, list): file_list = files
        else: file_list = [files]
    
    combined_content = ""
    if file_list:
        sorted_files = sorted(file_list, key=lambda f: f.filename or "")
        for file in sorted_files:
            contents = await file.read()
            await file.seek(0)
            combined_content += contents.decode("utf-8", errors="ignore")

    is_generate_with_context = (form_data.task == "generate_code" and file_list)
    is_other_task = (form_data.task != "generate_code")

    if is_other_task or is_generate_with_context:
        if not form_data.tamper_evident_hash and combined_content:
            raise HTTPException(status_code=400, detail="Tamper-evident hash is required for file uploads.")
        if form_data.tamper_evident_hash:
            server_hash = hashlib.sha256(combined_content.encode("utf-8")).hexdigest()
            if server_hash != form_data.tamper_evident_hash:
                raise HTTPException(status_code=400, detail="Data integrity check failed.")

    user_id = None
    ip_address = None
    api_key = form_data.api_key

    if user:
        user_id = user["id"]
        user_tier = await get_user_tier(user_id)
        await check_tier_quota(user_id, user_tier)

        if form_data.provider.lower() not in ["auto", "ollama"] and form_data.api_key_name:
            try:
                key_ref_resp = supabase.table("user_api_keys").select("encrypted_api_key_id").eq("user_id", user_id).eq("name", form_data.api_key_name).limit(1).single().execute()
                if not key_ref_resp.data: raise HTTPException(status_code=400, detail=f"API key '{form_data.api_key_name}' not found.")
                secret_id = key_ref_resp.data["encrypted_api_key_id"]
                decrypted_resp = supabase.rpc("reveal_secret", {"secret_id": secret_id}).execute()
                api_key = decrypted_resp.data
                if not api_key: raise HTTPException(status_code=500, detail=f"Failed to decrypt key '{form_data.api_key_name}'.")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        elif form_data.provider.lower() not in ["auto", "ollama"] and not form_data.api_key_name and not api_key:
            raise HTTPException(status_code=400, detail="Please select a saved API key or provide one.")
    else:
        ip_address = req.client.host
        await check_anonymous_quota(req)
        provider_name = form_data.provider.lower() if form_data.provider else ""
        if provider_name not in ['ollama', 'auto']:
            if not api_key:
                try:
                    server_key = get_api_key_for_provider(provider_name, user_api_key=None)
                    if server_key: api_key = server_key
                    else: raise HTTPException(status_code=503, detail=f"This server is not configured for anonymous '{provider_name}' use. Please sign in or provide your own API key.")
                except HTTPException: raise
                except Exception as e:
                    logger.error(f"Failed to fetch server API key for provider '{provider_name}': {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Server configuration error for provider keys.")

    project_files: Dict[str, str] = {}
    if file_list:
        for file in file_list:
            await file.seek(0)
            contents = await file.read()
            filename = file.filename or "unknown"
            
            if filename.endswith('.zip'):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_zip:
                        tmp_zip.write(contents)
                        tmp_zip_path = tmp_zip.name
                    with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                        for zip_info in zip_ref.infolist():
                            if not zip_info.is_dir():
                                with zip_ref.open(zip_info) as zipped_file:
                                    project_files[zip_info.filename] = zipped_file.read().decode("utf-8", errors="ignore")
                    os.remove(tmp_zip_path)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to process zip file: {str(e)}")
            else:
                project_files[filename] = contents.decode("utf-8", errors="ignore")

    if form_data.task != "generate_code" and not project_files:
        raise HTTPException(status_code=400, detail="File upload is required for this task.")
    if form_data.task == "generate_code" and not form_data.user_prompt:
        raise HTTPException(status_code=400, detail="A text prompt is required to generate code.")

    job_id = str(uuid.uuid4())
    job_payload = {
        "abstracted_project_files": project_files, "original_project_files": project_files,
        "provider_name": form_data.provider, "model": form_data.model, "task": form_data.task,
        "error_log": form_data.error_log, "token_saver": form_data.token_saver_enabled,
        "api_keys": {"api_key": api_key}, "use_cove_hardening": form_data.cove_hardening_enabled,
        "user_prompt_for_generation": form_data.user_prompt, "language_hint_for_generation": form_data.language_hint
    }

    job_metadata = {
        "job_id": job_id, "user_id": user_id, "ip_address": ip_address, "status": "pending",
        "task": form_data.task, "provider": form_data.provider, "created_at": datetime.utcnow().isoformat()
    }
    
    JOB_STORE[job_id] = {**job_metadata, "result": None, "analysis": None, "notice": None, "sandbox_result": None, "validation_result": None}
    
    try: supabase.table("jobs").insert(job_metadata).execute()
    except Exception as db_exc: logger.error(f"Failed to insert job metadata into Supabase: {db_exc}")

    asyncio.create_task(process_job_background(job_id, job_payload))
    return JSONResponse({"job_id": job_id})

async def call_llm_and_process(payload: dict) -> dict:
    try:
        result_dict = await asyncio.to_thread(process_code_submission, **payload)
        output = {"success": True, **result_dict}
        if "validation_result" in result_dict: output["validation_result"] = result_dict["validation_result"]
        return output
    except Exception as e:
        logger.error(f"Job failed during call_llm_and_process: {str(e)}\nTraceback:\n{traceback.format_exc()}")
        return {"success": False, "notice": str(e) if isinstance(e, (ValueError, HTTPException)) else "An internal error occurred during processing."}

async def process_job_background(job_id: str, payload: dict):
    job = JOB_STORE.get(job_id)
    if not job: return
    job["status"] = "running"
    try: supabase.table("jobs").update({"status": "running"}).eq("job_id", job_id).execute()
    except Exception as db_exc: logger.warning(f"Failed to update job status to running in DB for {job_id}: {db_exc}")

    db_update = {}
    try:
        response = await call_llm_and_process(payload)
        full_result_update = {
            "status": "completed" if response.get("success") else "failed", "result": response.get("result"),
            "notice": response.get("notice"), "analysis": response.get("analysis"),
            "sandbox_result": response.get("sandbox_result"), "validation_result": response.get("validation_result")
        }
        JOB_STORE[job_id].update(full_result_update)
        db_update = {"status": full_result_update["status"], "notice": full_result_update["notice"]}
    except Exception as e:
        db_update = {"status": "failed", "notice": f"Internal processing error: {str(e)}"}
        if job_id in JOB_STORE: JOB_STORE[job_id].update(db_update)

    try: supabase.table("jobs").update(db_update).eq("job_id", job_id).execute()
    except Exception as db_exc: logger.error(f"Failed to update job final status in Supabase for {job_id}: {db_exc}")

@router.get("/status/{job_id}")
async def get_job_status(req: Request, job_id: str, user: Optional[dict] = Depends(get_optional_authenticated_user)):
    job = JOB_STORE.get(job_id)
    if job:
        if user and job.get("user_id") == user["id"]: return JSONResponse(job)
        if not user and job.get("ip_address") == req.client.host: return JSONResponse(job)

    try:
        resp = supabase.table("jobs").select("*").eq("job_id", job_id).single().execute()
        if resp.data:
            db_job = resp.data
            if user and db_job.get("user_id") == user["id"]: return JSONResponse(db_job)
            if not user and db_job.get("ip_address") == req.client.host: return JSONResponse(db_job)
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        logger.error(f"Failed to fetch job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail="Job not found or not authorized")
    
    raise HTTPException(status_code=403, detail="Not authorized to view this job")
