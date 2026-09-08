from fastapi import APIRouter, Depends, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Annotated
import logging
import uuid
import json
from src.api.models import CreateOrderRequest
from src.api.dependencies import get_current_user, get_country_code
from src.api.globals import supabase, razorpay_client
from src.config import settings

router = APIRouter(prefix="/api", tags=["billing"])
logger = logging.getLogger("server")

@router.get("/plans")
async def get_plans(req: Request):
    country = get_country_code(req)
    if country == "IN":
        price_monthly_col, price_yearly_col = "price_monthly_inr", "price_yearly_inr"
        plan_monthly_col, plan_yearly_col = "razorpay_plan_id_monthly_inr", "razorpay_plan_id_yearly_inr"
        currency = "INR"
    else:
        price_monthly_col, price_yearly_col = "price_monthly_usd", "price_yearly_usd"
        plan_monthly_col, plan_yearly_col = "razorpay_plan_id_monthly_usd", "razorpay_plan_id_yearly_usd"
        currency = "USD"
    try:
        resp = supabase.table("plans").select(f"id, name, features, {price_monthly_col}, {price_yearly_col}, {plan_monthly_col}, {plan_yearly_col}").eq("active", True).order("price_monthly_usd", desc=False).execute()
        if not resp.data: return JSONResponse({"plans": []})
        formatted_plans = []
        for plan in resp.data:
            formatted_plans.append({
                "id": plan["id"], "name": plan["name"], "features": plan["features"], "currency": currency,
                "monthly": {"price": plan[price_monthly_col], "razorpay_plan_id": plan[plan_monthly_col]},
                "yearly": {"price": plan[price_yearly_col], "razorpay_plan_id": plan[plan_yearly_col]}
            })
        return JSONResponse({"plans": formatted_plans})
    except Exception as e:
        logger.error(f"Failed to fetch plans: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not retrieve pricing plans.")

@router.post("/create-order")
async def create_order(req: Request, body: CreateOrderRequest, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    country = get_country_code(req)
    if country == "IN": price_col, currency = f"price_{body.billing_cycle}_inr", "INR"
    else: price_col, currency = f"price_{body.billing_cycle}_usd", "USD"
    try:
        plan_resp = supabase.table("plans").select(price_col).eq("id", body.plan_id).single().execute()
        if not plan_resp.data: raise HTTPException(status_code=404, detail="Plan not found")
        order_data = {
            "amount": plan_resp.data[price_col], "currency": currency,
            "receipt": f"order_{uuid.uuid4().hex[:16]}", "notes": { "user_id": user_id, "plan_id": body.plan_id }
        }
        order = razorpay_client.order.create(data=order_data)
        return JSONResponse({"order_id": order["id"], "razorpay_key_id": settings.razorpay_key_id, "amount": order["amount"], "currency": order["currency"]})
    except Exception as e:
        logger.error(f"Error creating Razorpay order for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create payment order.")

@router.post("/razorpay-webhook")
async def razorpay_webhook(req: Request, x_razoray_signature: Annotated[str | None, Header()] = None):
    body = await req.body()
    try:
        payload_str = body.decode('utf-8')
        razorpay_client.utility.verify_webhook_signature(payload_str, x_razoray_signature, settings.razorpay_webhook_secret)
        webhook_data = json.loads(payload_str)
        if webhook_data.get("event") == "payment.captured":
            payload = webhook_data["payload"]["payment"]["entity"]
            user_id, plan_id = payload["notes"]["user_id"], payload["notes"]["plan_id"]
            supabase.table("profiles").update({"tier": plan_id}).eq("id", user_id).execute()
            logger.info(f"Successfully upgraded user {user_id} to plan {plan_id}")
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook verification failed or error during processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid webhook signature or processing error")
