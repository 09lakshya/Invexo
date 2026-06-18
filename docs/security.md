# Invexo Security Hardening Architecture

This document describes the security controls, authentication mechanisms, and access policies implemented in the Invexo platform.

---

## 1. Authentication & Session Management

### Double-Token Scheme (JWT)
Invexo utilizes a standard secure double-token authentication architecture:
1. **Access Token**: Short-lived (15 minutes), used to authorize API requests. Signed using HMAC-SHA256 containing user ID and expiration claims.
2. **Refresh Token**: Long-lived (7 days), stored in Redis (or in-memory fallback) and used to request new Access Tokens.

### Refresh Token Rotation (RTR)
To mitigate the risk of stolen refresh tokens, RTR is enforced:
* When `/auth/refresh` is requested with a valid refresh token, that refresh token is **invalidated immediately** in Redis.
* A brand new refresh token and access token pair is issued.
* If a client attempts to replay or reuse an old refresh token, the validation check fails (returns `401 Unauthorized`), protecting against session hijacking.
* Unique `jti` (JWT ID) claims are embedded in every token payload using UUIDs to prevent generation collisions in quick succession.

---

## 2. Role-Based Access Control (RBAC)

User privileges are governed by roles: `user` (basic), `premium`, and `admin`.

* Roles are persisted in the `users` table under the `role` column.
* Role checking is decoupled into a reusable FastAPI dependency pattern:
  ```python
  def require_role(allowed_roles: List[str]):
      def dependency(current_user: User = Depends(get_current_user)):
          if current_user.role not in allowed_roles:
              raise HTTPException(status_code=403, detail="Operation not permitted")
          return current_user
      return dependency
  ```
* High-value APIs, such as the AI advisor recommendations, require the caller to possess either `premium` or `admin` scopes. Regular users calling these routes receive a `403 Forbidden` response.

---

## 3. Rate Limiting & Denial of Service Protection

To prevent brute-force attacks and abuse of external API credits, rate limiting is applied:
* Powered by **SlowAPI** (built on `limits`), backed by the Redis cluster.
* Rate limits are applied globally per endpoint based on the client IP address:
  * **Auth Endpoints** (signup, login, reset password): Limited to **5-10 requests per minute**.
  * **Advisor Recommendations**: Limited to **10 requests per minute**.

---

## 4. Multi-Factor OTP Flow

Registration and password recovery require validation via One-Time Passwords (OTPs):
* On initiating signup, an OTP is generated, saved in Redis with a 5-minute expiration (TTL), and dispatched via the configured mail client (Resend or SMTP server).
* The user must present the OTP to complete registration.
* To prevent OTP guessing, verification attempts are tracked. If a user inputs an incorrect OTP more than 5 times, the key is permanently destroyed.
