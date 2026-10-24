import json
import logging
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.schemas import ChatRequest
from core.config import get_settings
from core.model_manager import get_provider
from core.request_limits import RequestBodyLimitMiddleware
from core.security import create_key, record_usage, revoke_key, usage_summary, valid_key

settings = get_settings()
logging.basicConfig(level=settings.log_level)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Puffx AI Engine", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_bytes)
app.mount(
    "/admin/ui",
    StaticFiles(directory=Path(__file__).resolve().parents[1] / "dashboard", html=True),
    name="dashboard",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def auth(authorization: str | None = Header(default=None)):
    key = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not valid_key(key):
        raise HTTPException(401, "Invalid or missing API key")
    return key


def admin(authorization: str | None = Header(default=None)):
    key = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not settings.admin_password or not secrets.compare_digest(key, settings.admin_password):
        raise HTTPException(401, "Admin authentication required")
    return True


@app.get("/health")
async def health():
    models = await get_provider().models()
    return {
        "status": "ok",
        "backend": settings.inference_backend,
        "model_available": any(model["id"] == settings.model_name for model in models),
        "available_models": models,
    }


@app.get("/v1/models")
@limiter.limit(settings.rate_limit)
async def models(request: Request, _=Depends(auth)):
    return {"object": "list", "data": await get_provider().models()}


@app.post("/v1/chat/completions")
@limiter.limit(settings.rate_limit)
async def chat(request: Request, body: ChatRequest, key=Depends(auth)):
    if body.max_tokens > settings.max_tokens:
        raise HTTPException(400, "max_tokens exceeds configured limit")

    try:
        result = await get_provider().chat(body.model_dump(exclude_none=True))
    except Exception as exc:
        logging.warning("Inference failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Inference backend unavailable or request failed") from exc

    # Count completed inference requests only; provider failures should not inflate usage.
    record_usage(key, "/v1/chat/completions")

    if body.stream:
        choice = result["choices"][0]
        chunk = {
            "id": result["id"],
            "object": "chat.completion.chunk",
            "created": result["created"],
            "model": result["model"],
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "content": choice["message"]["content"]},
                "finish_reason": None,
            }],
        }

        async def events():
            yield "data: " + json.dumps(chunk) + "\n\n"
            final = {
                "id": result["id"],
                "object": "chat.completion.chunk",
                "created": result["created"],
                "model": result["model"],
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": choice.get("finish_reason") or "stop",
                }],
            }
            yield "data: " + json.dumps(final) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return result


@app.get("/admin/usage")
@limiter.limit(settings.admin_rate_limit)
async def usage(request: Request, _=Depends(admin)):
    return usage_summary()


@app.post("/admin/keys")
@limiter.limit(settings.admin_rate_limit)
async def new_key(
    request: Request,
    label: str = Query(default="API key", min_length=1, max_length=80),
    _=Depends(admin),
):
    label = label.strip()
    if not label:
        raise HTTPException(400, "Key label cannot be empty")
    return create_key(label)


@app.delete("/admin/keys/{key_id}")
@limiter.limit(settings.admin_rate_limit)
async def delete_key(request: Request, key_id: str, _=Depends(admin)):
    if not revoke_key(key_id):
        raise HTTPException(404, "Key not found")
    return {"revoked": True}


@app.get("/admin/status")
@limiter.limit(settings.admin_rate_limit)
async def status(request: Request, _=Depends(admin)):
    return {
        "backend": settings.inference_backend,
        "model": settings.model_name,
        "models": await get_provider().models(),
    }
