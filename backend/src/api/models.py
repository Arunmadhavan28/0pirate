from pydantic import BaseModel
from fastapi import Form
from typing import Optional

class ApiKeyRequest(BaseModel):
    provider: str
    name: str
    api_key: str

class ApiKeyDeleteRequest(BaseModel):
    name: str

class CreateOrderRequest(BaseModel):
    plan_id: str
    billing_cycle: str

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
