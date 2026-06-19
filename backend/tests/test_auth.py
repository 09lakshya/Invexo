from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_password, create_access_token, create_refresh_token
from app.repositories.user_repository import UserRepository
from app.services.auth.auth_service import AuthService

client = TestClient(app)

def test_signup_initiate_and_verify():
    # 1. Initiate signup (sends OTP)
    response = client.post("/api/v1/auth/signup/initiate", json={
        "email": "test@gmail.com",
        "password": "testpassword",
        "name": "Test User",
        "age": 25
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Verification OTP sent"

    # Get the OTP from Redis client fallback memory
    import json
    from app.core.redis import redis_client
    otp_data = redis_client.get("signup_otp:test@gmail.com")
    assert otp_data is not None
    otp = json.loads(otp_data)["otp"]
    assert otp is not None

    # 2. Verify OTP
    response = client.post("/api/v1/auth/signup/verify", json={
        "email": "test@gmail.com",
        "otp": otp
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "test@gmail.com"
    assert data["user"]["role"] == "user"

def test_login_success_and_failure():
    # Setup user
    pwd_hash = hash_password("mypassword")
    UserRepository.create_user("user@gmail.com", pwd_hash, "User", 30)

    # Success login
    response = client.post("/api/v1/auth/login", json={
        "email": "user@gmail.com",
        "password": "mypassword"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "user@gmail.com"

    # Failure login
    response = client.post("/api/v1/auth/login", json={
        "email": "user@gmail.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_token_rotation_and_logout():
    # Setup user
    pwd_hash = hash_password("mypassword")
    user = UserRepository.create_user("rotate@gmail.com", pwd_hash, "Rotate", 22)
    user_id = user["id"]

    # Generate tokens
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)

    # Refresh token rotation
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    new_refresh = data["refresh_token"]

    # Old refresh token should be revoked and not work anymore
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh
    })
    assert response.status_code == 401

    # Logout
    response = client.post("/api/v1/auth/logout", json={
        "refresh_token": new_refresh
    }, headers={"Authorization": f"Bearer {access}"})
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_rbac_endpoints():
    # Setup user (role: user)
    pwd_hash = hash_password("pwd")
    reg_user = UserRepository.create_user("reg@gmail.com", pwd_hash, "Regular", 25, role="user")
    prem_user = UserRepository.create_user("prem@gmail.com", pwd_hash, "Premium", 35, role="premium")

    reg_token = create_access_token(reg_user["id"])
    prem_token = create_access_token(prem_user["id"])

    # Try accessing advisor recommendations as regular user -> Forbidden
    response = client.get("/api/v1/advisor/recommendations?goal=wealth&budget=1000", headers={"Authorization": f"Bearer {reg_token}"})
    assert response.status_code == 403

    # Try accessing advisor recommendations as premium user -> Success
    response = client.get("/api/v1/advisor/recommendations?goal=wealth&budget=1000", headers={"Authorization": f"Bearer {prem_token}"})
    assert response.status_code == 200
