from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class SignupInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    name: str = Field(..., min_length=1, description="Name is required")
    age: int = Field(..., ge=1, le=150, description="Age must be between 1 and 150")

class VerifySignupInput(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, description="OTP must be 6 digits")

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordInitiateInput(BaseModel):
    email: EmailStr

class VerifyForgotPasswordOtpInput(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)

class ForgotPasswordResetInput(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)

class ChangePasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class UpdateProfileInput(BaseModel):
    name: Optional[str] = None
    profile_photo: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefreshInput(BaseModel):
    refresh_token: str
