from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import re
from services.auth_service import (
    signup,
    login,
    get_user,
    update_profile,
    update_profile_fields,
    change_password,
    create_token,
    verify_token,
    initiate_signup_otp,
    verify_signup_otp,
)

router = APIRouter(prefix="/auth")


class SignupInput(BaseModel):
    email: str
    password: str
    name: str
    age: int


class LoginInput(BaseModel):
    email: str
    password: str


class VerifySignupInput(BaseModel):
    email: str
    otp: str


class ForgotPasswordInitiateInput(BaseModel):
    email: str


class ForgotPasswordResetInput(BaseModel):
    email: str
    otp: str
    new_password: str


ALLOWED_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "yahoo.co.in",
    "yahoo.co.uk", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com",
    "proton.me", "zoho.com", "zoho.in", "yandex.com", "mail.com",
    "gmx.com", "gmx.net", "tutanota.com", "tuta.io", "fastmail.com",
    "hey.com", "pm.me", "rediffmail.com", "in.com", "sify.com",
    "email.com", "usa.com", "inbox.com", "mail.ru", "rambler.ru",
    "cox.net", "sbcglobal.net", "att.net", "comcast.net", "verizon.net",
    "bellsouth.net", "charter.net", "earthlink.net", "optonline.net",
    "web.de", "t-online.de", "libero.it", "virgilio.it",
    "laposte.net", "orange.fr", "wanadoo.fr", "free.fr",
    "naver.com", "hanmail.net", "daum.net", "qq.com", "163.com",
    "126.com", "sina.com", "yeah.net"
}


def _is_allowed_domain(email: str) -> bool:
    parts = email.split("@")
    if len(parts) < 2:
        return False
    domain = parts[1].lower().strip()
    return domain in ALLOWED_DOMAINS


class UpdateProfileInput(BaseModel):
    name: Optional[str] = None
    profile_photo: Optional[str] = None


class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip()))


def _require_user_id(authorization: Optional[str]) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


@router.post("/signup")
def handle_signup(payload: SignupInput):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if not _is_valid_email(payload.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if not _is_allowed_domain(payload.email):
        raise HTTPException(status_code=400, detail="Please use a valid email provider (e.g. Gmail, Yahoo, Outlook)")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if payload.age < 1 or payload.age > 150:
        raise HTTPException(status_code=400, detail="Please enter a valid age")

    user = signup(payload.email, payload.password, payload.name, payload.age)
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    try:
        from services.auth_service import send_welcome_email
        send_welcome_email(user["email"], user["name"])
    except Exception as e:
        print(f"[Welcome Email Warning] Failed to send welcome email: {e}")

    token = create_token(user["id"])
    return {"token": token, "user": user}


@router.post("/signup/initiate")
def handle_signup_initiate(payload: SignupInput):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if not _is_valid_email(payload.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if not _is_allowed_domain(payload.email):
        raise HTTPException(status_code=400, detail="Please use a valid email provider (e.g. Gmail, Yahoo, Outlook)")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if payload.age < 1 or payload.age > 150:
        raise HTTPException(status_code=400, detail="Please enter a valid age")

    # Check if user already exists
    from services.auth_service import user_exists
    if user_exists(payload.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    try:
        initiate_signup_otp(payload.email, payload.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Verification OTP sent"}


@router.post("/signup/verify")
def handle_signup_verify(payload: VerifySignupInput):
    if not payload.email or not payload.otp:
        raise HTTPException(status_code=400, detail="Email and OTP code are required")

    signup_payload = verify_signup_otp(payload.email, payload.otp)
    if signup_payload is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")

    user = signup(
        signup_payload["email"],
        signup_payload["password"],
        signup_payload["name"],
        signup_payload["age"]
    )
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    try:
        from services.auth_service import send_welcome_email
        send_welcome_email(user["email"], user["name"])
    except Exception as e:
        print(f"[Welcome Email Warning] Failed to send welcome email: {e}")

    token = create_token(user["id"])
    return {"token": token, "user": user}


@router.post("/login")
def handle_login(payload: LoginInput):
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if not _is_valid_email(payload.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    from services.auth_service import user_exists
    if not user_exists(payload.email):
        raise HTTPException(status_code=404, detail="Account not found")

    user = login(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"])
    return {"token": token, "user": user}


@router.post("/forgot-password/initiate")
def handle_forgot_password_initiate(payload: ForgotPasswordInitiateInput):
    if not payload.email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not _is_valid_email(payload.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    from services.auth_service import user_exists, initiate_forgot_password_otp
    if not user_exists(payload.email):
        # Return generic success to prevent email enumeration
        return {"message": "If this email is registered, a password reset code has been sent."}

    try:
        initiate_forgot_password_otp(payload.email)
    except Exception as e:
        print(f"Error initiating forgot password: {e}")
        # Still return success to prevent enumeration, or we could return 500
    
    return {"message": "If this email is registered, a password reset code has been sent."}


@router.post("/forgot-password/reset")
def handle_forgot_password_reset(payload: ForgotPasswordResetInput):
    if not payload.email or not payload.otp or not payload.new_password:
        raise HTTPException(status_code=400, detail="Email, OTP, and new password are required")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    from services.auth_service import reset_password_with_otp
    success = reset_password_with_otp(payload.email, payload.otp, payload.new_password)
    
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")

    return {"message": "Password changed successfully"}


@router.get("/me")
def handle_me(authorization: Optional[str] = Header(None)):
    user_id = _require_user_id(authorization)

    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.patch("/profile")
def handle_update_profile(payload: UpdateProfileInput, authorization: Optional[str] = Header(None)):
    user_id = _require_user_id(authorization)
    
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

    user = update_profile_fields(user_id, updated_fields)
    if user is None:
        raise HTTPException(status_code=400, detail="Could not update profile")
    return user


@router.post("/change-password")
def handle_change_password(payload: ChangePasswordInput, authorization: Optional[str] = Header(None)):
    user_id = _require_user_id(authorization)
    if not payload.current_password or not payload.new_password:
        raise HTTPException(status_code=400, detail="Both current and new password are required")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    ok = change_password(user_id, payload.current_password, payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    return {"success": True}
