import logging
import traceback
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.exceptions import RequestValidationError

from src.api.routes import auth, billing, jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

APP_NAME = "0pirate-backend"
app = FastAPI(title=APP_NAME)

class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Global error at {request.url}: {traceback.format_exc()}")
            return JSONResponse(status_code=500, content={"detail": "An internal server error occurred."})

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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"type": err.get("type"), "loc": err.get("loc"), "msg": err.get("msg")} for err in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url}: {traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error occurred."})

# Include modular API routes
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(jobs.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}