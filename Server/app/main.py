from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.middleware import MaxBodySizeMiddleware
from app.meetings.router import router as meetings_router

settings = get_settings()

app = FastAPI(title="VoxIntel API", version="0.1.0")

# A little headroom over the configured limit to account for multipart
# boundary/header overhead around the actual file content.
app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.max_upload_size_bytes + 1024 * 1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(meetings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
