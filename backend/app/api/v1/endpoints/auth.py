from fastapi import APIRouter, HTTPException, Depends, Request, Header
from typing import Optional
from app.schemas.auth import (
    SignupInput, LoginInput, VerifySignupInput, 
    ForgotPasswordInitiateInput, ForgotPasswordResetInput, 
    VerifyForgotPasswordOtpInput, ChangePasswordInput, 
    UpdateProfileInput, TokenRefreshInput
)
from app.services.auth.auth_service import AuthService
from app.core.security import verify_refresh_token, revoke_refresh_token, create_access_token, create_refresh_token
from app.core.limiter import limiter
from app.api.v1.dependencies import get_current_user
from app.utils.logger import get_logger

logger = get_logger("auth_endpoints")

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup/initiate")
@limiter.limit("5/minute")
def handle_signup_initiate(payload: SignupInput, request: Request):
    try:
        AuthService.initiate_signup_otp(payload.email, payload.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Verification OTP sent"}

@router.post("/signup/verify")
@limiter.limit("5/minute")
def handle_signup_verify(payload: VerifySignupInput, request: Request):
    signup_payload = AuthService.verify_signup_otp(payload.email, payload.otp)
    if signup_payload is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")

    user = AuthService.signup(
        signup_payload["email"],
        signup_payload["password"],
        signup_payload["name"],
        signup_payload["age"],
        role="user"
    )
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    try:
        AuthService.send_welcome_email(user["email"], user["name"])
    except Exception as e:
        pass

    access_token = create_access_token(user["id"])
    refresh_token = create_refresh_token(user["id"])
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login")
@limiter.limit("10/minute")
def handle_login(payload: LoginInput, request: Request):
    try:
        user = AuthService.login(payload.email, payload.password)
    except Exception as e:
        logger.error(f"Login failed for '{payload.email}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login service temporarily unavailable. Please try again.")
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user["id"])
    refresh_token = create_refresh_token(user["id"])
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/refresh")
@limiter.limit("5/minute")
def handle_refresh(payload: TokenRefreshInput, request: Request):
    user_id = verify_refresh_token(payload.refresh_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid, expired or revoked refresh token")
        
    # Rotate refresh tokens: revoke the old, issue new pair
    revoke_refresh_token(user_id, payload.refresh_token)
    
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer"
    }

@router.post("/logout")
def handle_logout(payload: TokenRefreshInput, current_user: dict = Depends(get_current_user)):
    revoke_refresh_token(current_user["id"], payload.refresh_token)
    return {"success": True, "message": "Successfully logged out."}

@router.post("/forgot-password/initiate")
@limiter.limit("5/minute")
def handle_forgot_password_initiate(payload: ForgotPasswordInitiateInput, request: Request):
    try:
        AuthService.initiate_forgot_password_otp(payload.email)
    except Exception:
        pass
    return {"message": "If this email is registered, a password reset code has been sent."}

@router.post("/forgot-password/verify-otp")
@limiter.limit("5/minute")
def handle_forgot_password_verify_otp(payload: VerifyForgotPasswordOtpInput, request: Request):
    if not AuthService.verify_forgot_password_otp_only(payload.email, payload.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")
    return {"message": "OTP verified"}

@router.post("/forgot-password/reset")
@limiter.limit("5/minute")
def handle_forgot_password_reset(payload: ForgotPasswordResetInput, request: Request):
    success = AuthService.reset_password_with_otp(payload.email, payload.otp, payload.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")
    return {"message": "Password changed successfully"}

@router.get("/me")
def handle_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.patch("/profile")
def handle_update_profile(payload: UpdateProfileInput, current_user: dict = Depends(get_current_user)):
    updated_fields = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        updated_fields["name"] = name
        
    if payload.profile_photo is not None:
        updated_fields["profile_photo"] = payload.profile_photo

    if not updated_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    from app.repositories.user_repository import UserRepository
    UserRepository.update_profile_fields(current_user["id"], updated_fields)
    return UserRepository.get_user_by_id(current_user["id"])

@router.post("/change-password")
@limiter.limit("5/minute")
def handle_change_password(payload: ChangePasswordInput, request: Request, current_user: dict = Depends(get_current_user)):
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    ok = AuthService.change_password(current_user["id"], payload.current_password, payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    return {"success": True}
