from fastapi import Header, HTTPException, Depends
from typing import Optional
from app.core.security import verify_access_token
from app.repositories.user_repository import UserRepository

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Dependency to retrieve the current authenticated user from JWT access token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header. Use Bearer token.")

    token = authorization.split(" ", 1)[1]
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid, expired or blacklisted access token.")

    user = UserRepository.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User account not found.")
        
    return user

def require_role(allowed_roles: list[str]):
    """Enforce Role-Based Access Control (RBAC) on endpoints."""
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "user")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Forbidden: Access requires one of these roles: {allowed_roles}. Current role: {user_role}"
            )
        return current_user
    return dependency
