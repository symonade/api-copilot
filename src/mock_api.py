# src/mock_api.py
from fastapi import FastAPI, HTTPException, Header, Path
from pydantic import BaseModel
from typing import Optional, List
import os
import time
import random

app = FastAPI(title="ConTech Mock API")

# Features Coming Soon page (FastAPI router)
from src.ui.features import router as features_router
app.include_router(features_router)
# --- Config knobs for demos ---
FORCE_503 = os.getenv("MOCK_FORCE_503", "false").lower() == "true"
ARTIFICIAL_LATENCY_MS = int(os.getenv("MOCK_LATENCY_MS", "0"))

# --- Models matching your docs ---
class TokenRequest(BaseModel):
    client_id: str
    client_secret: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectCreateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class CostItem(BaseModel):
    code: str
    amount: float

class AddCostItemsRequest(BaseModel):
    items: List[CostItem]

class AddCostItemsResponse(BaseModel):
    project_id: str
    added_count: int

def maybe_fail_or_delay():
    # Optional latency
    if ARTIFICIAL_LATENCY_MS > 0:
        time.sleep(ARTIFICIAL_LATENCY_MS / 1000.0)
    # Optional forced outages
    if FORCE_503:
        raise HTTPException(status_code=503, detail="Service Unavailable (mock)")

@app.get("/status")
def get_status():
    maybe_fail_or_delay()
    return {"status": "OK", "uptime": "mock", "version": "0.0.1-mock"}

@app.get("/health")
def get_health():
    maybe_fail_or_delay()
    return {"status": "healthy", "checks": {"db": "ok", "queue": "ok"}}

@app.post("/auth/token", response_model=TokenResponse)
def get_token(payload: TokenRequest):
    maybe_fail_or_delay()
    # In mock: accept any creds, return a fake token
    if not payload.client_id or not payload.client_secret:
        raise HTTPException(status_code=400, detail="Missing credentials")
    return TokenResponse(access_token="mock-access-token")

@app.post("/projects", response_model=ProjectCreateResponse)
def create_project(
    payload: ProjectCreateRequest,
    authorization: Optional[str] = Header(default=None)
):
    maybe_fail_or_delay()
    # Simple mock auth check
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized (mock)")
    pid = f"proj_{random.randint(1000, 9999)}"
    return ProjectCreateResponse(id=pid, name=payload.name, description=payload.description)

@app.post("/projects/{projectId}/cost-items", response_model=AddCostItemsResponse)
def add_cost_items(
    projectId: str = Path(..., min_length=5),
    payload: AddCostItemsRequest = None,
    authorization: Optional[str] = Header(default=None)
):
    maybe_fail_or_delay()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized (mock)")
    if not payload or not payload.items:
        raise HTTPException(status_code=400, detail="No items provided")
    return AddCostItemsResponse(project_id=projectId, added_count=len(payload.items))

