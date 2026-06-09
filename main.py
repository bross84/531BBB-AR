from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import init_db
import hevy_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="531 BBB-AR", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse("index.html")


# ── Settings ───────────────────────────────────────────────────────────────────

class ApiKeyInput(BaseModel):
    api_key: str


@app.get("/settings")
def get_settings():
    """Return whether the Hevy API key is configured. Never returns the key itself."""
    key = hevy_client.get_api_key()
    if key and len(key) >= 4:
        preview = "···" + key[-4:]
    elif key:
        preview = "···"
    else:
        preview = None
    return {"hevy_api_key_set": bool(key), "hevy_api_key_preview": preview}


@app.post("/settings/api-key", status_code=204)
def save_api_key(data: ApiKeyInput):
    """Encrypt and store the Hevy API key. Returns 204 on success."""
    key = data.api_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API key cannot be empty.")
    hevy_client.save_api_key(key)
