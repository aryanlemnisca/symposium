from fastapi import APIRouter, HTTPException
from backend.auth import verify_password, create_token
from backend.models.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if not verify_password(req.password):
        raise HTTPException(status_code=401, detail="Wrong password")
    return LoginResponse(token=create_token())
