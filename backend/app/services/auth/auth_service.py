import random
import json
import os
import threading
from datetime import datetime
from email.mime.text import MIMEText
from app.repositories.user_repository import UserRepository
from app.core.redis import redis_client
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.utils.logger import get_logger

logger = get_logger("auth_service")

class AuthService:
    @staticmethod
    def _dispatch_email(*args, **kwargs):
        """Send an email off the request path. Email delivery (Resend/SMTP) can
        take 1-2s — or up to 20-30s on timeouts — so it must never block the
        signup/login/reset response. OTPs are persisted to Redis before this is
        called, so backgrounding the send is safe."""
        thread = threading.Thread(
            target=AuthService._send_email, args=args, kwargs=kwargs, daemon=True
        )
        thread.start()

    @staticmethod
    def _send_email(to: str, subject: str, text: str, html: str = None, reply_to: str = None) -> bool:
        """Sends an email via Resend API with SMTP fallback. Returns True on success."""
        resend_key = os.environ.get("RESEND_API_KEY", "")
        if resend_key:
            try:
                import requests
                sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
                payload = {
                    "from": sender,
                    "to": [to],
                    "subject": subject
                }
                if reply_to:
                    payload["reply_to"] = reply_to
                if html:
                    payload["html"] = html
                else:
                    payload["text"] = text

                res = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    json=payload,
                    timeout=10
                )
                if res.status_code in [200, 201]:
                    logger.info(f"[Resend] Successfully sent email to {to}")
                    return True
                else:
                    logger.error(f"[Resend ERROR] Failed to send email to {to}: {res.text}")
            except Exception as e:
                logger.error(f"[Resend ERROR] Failed to send email to {to}: {e}")

        # Try SMTP if Resend fails or is not configured
        host = os.environ.get("SMTP_HOST", "")
        port_str = os.environ.get("SMTP_PORT", "")
        user = os.environ.get("SMTP_USER", "")
        password = os.environ.get("SMTP_PASSWORD", "")
        sender = os.environ.get("SMTP_FROM", user)

        if host and port_str and user and password:
            try:
                import smtplib
                from email.mime.multipart import MIMEMultipart
                
                port = int(port_str)
                if html:
                    msg = MIMEMultipart("alternative")
                    msg.attach(MIMEText(html, "html"))
                else:
                    msg = MIMEText(text)

                msg["Subject"] = subject
                msg["From"] = sender
                msg["To"] = to
                if reply_to:
                    msg["Reply-To"] = reply_to

                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=10)
                else:
                    server = smtplib.SMTP(host, port, timeout=10)
                    server.starttls()
                server.login(user, password)
                server.sendmail(sender, [to], msg.as_string())
                server.quit()
                logger.info(f"[SMTP] Successfully sent email to {to}")
                return True
            except Exception as e:
                logger.error(f"[SMTP ERROR] Failed to send email to {to}: {e}")
                
        return False

    @staticmethod
    def send_otp_email(email_addr: str, otp: str):
        if os.environ.get("ENV") != "production":
            logger.info(f"[OTP DEBUG] OTP for {email_addr}: {otp}")
        logger.info(f"Sending signup OTP email to {email_addr}")
        
        subject = "Invexo - Verify Your Email"
        text_content = (
            f"Thank you for signing up for Invexo!\n\n"
            f"Your 6-digit verification code (OTP) is: {otp}\n\n"
            f"This code will expire in 5 minutes. Please do not share it with anyone."
        )
        AuthService._dispatch_email(email_addr, subject, text_content)

    @staticmethod
    def send_welcome_email(email_addr: str, name: str):
        logger.info(f"[WELCOME DEBUG] Sending welcome email to {email_addr}")
        subject = "Welcome to Invexo - Your Financial Journey Starts Here!"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Welcome to Invexo</title>
    <style>
        body {{
            font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #0b0f19;
            color: #f3f4f6;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: linear-gradient(135deg, #111827 0%, #0f172a 100%);
            border: 1px solid #1e293b;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: inline-block;
            letter-spacing: -0.5px;
        }}
        .welcome-title {{
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .content {{
            font-size: 16px;
            line-height: 1.6;
            color: #cbd5e1;
        }}
        .highlight {{
            color: #38bdf8;
            font-weight: 600;
        }}
        .features {{
            margin: 25px 0;
            padding-left: 0;
            list-style: none;
        }}
        .feature-item {{
            margin-bottom: 12px;
            padding-left: 24px;
            position: relative;
        }}
        .feature-item::before {{
            content: "✦";
            position: absolute;
            left: 0;
            color: #818cf8;
        }}
        .cta-button {{
            display: block;
            width: fit-content;
            margin: 30px auto 10px auto;
            padding: 14px 28px;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: #ffffff !important;
            text-decoration: none;
            font-weight: 600;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #1e293b;
            text-align: center;
            font-size: 12px;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">INVEXO</div>
        </div>
        <h1 class="welcome-title">Hi {name}, Welcome to Invexo!</h1>
        <div class="content">
            <p>We're thrilled to have you join our community. Invexo is designed to give you modern, state-of-the-art tools to analyze markets, track your investments, and build your wealth.</p>
            <p>Here's what you can explore right away:</p>
            <ul class="features">
                <li class="feature-item"><span class="highlight">Real-time Dashboard:</span> Monitor global stock markets, view advanced charts, and track daily top-movers.</li>
                <li class="feature-item"><span class="highlight">AI Predictions:</span> Leverage our machine learning models to forecast asset prices and trends.</li>
                <li class="feature-item"><span class="highlight">Interactive Advisor:</span> Consult with our virtual AI advisor to optimize your investment strategy.</li>
                <li class="feature-item"><span class="highlight">Live Portfolio:</span> Easily construct and keep track of your holdings in one unified interface.</li>
            </ul>
            <p>Get started by setting up your profile or creating your first portfolio today!</p>
            <a href="https://invexo-one.vercel.app" class="cta-button">Go to Dashboard</a>
        </div>
        <div class="footer">
            <p>© 2026 Invexo. All rights reserved.</p>
            <p>This email was sent to {email_addr}. If you did not sign up for Invexo, you can safely ignore this email.</p>
        </div>
    </div>
</body>
</html>"""

        AuthService._dispatch_email(email_addr, subject, "", html_content)

    @staticmethod
    def initiate_signup_otp(email_addr: str, payload: dict) -> str:
        otp = f"{random.randint(100000, 999999)}"
        key = f"signup_otp:{email_addr.lower().strip()}"
        record = {
            "otp": otp,
            "payload": payload,
            "attempts": 0,
            "verified": False
        }
        redis_client.setex(key, 300, json.dumps(record))
        AuthService.send_otp_email(email_addr, otp)
        return otp

    @staticmethod
    def verify_signup_otp(email_addr: str, otp: str) -> dict | None:
        key = f"signup_otp:{email_addr.lower().strip()}"
        val = redis_client.get(key)
        if not val:
            return None
        
        record = json.loads(val)
        record["attempts"] = record.get("attempts", 0) + 1
        if record["attempts"] > 5:
            redis_client.delete(key)
            return None
            
        if record["otp"] != otp:
            if record["attempts"] >= 5:
                redis_client.delete(key)
            else:
                redis_client.setex(key, 300, json.dumps(record))
            return None
            
        payload = record["payload"]
        redis_client.delete(key)
        return payload

    @staticmethod
    def signup(email: str, password: str, name: str, age: int, role: str = "user") -> dict | None:
        if UserRepository.get_user_by_email(email):
            return None
        pwd_hash = hash_password(password)
        return UserRepository.create_user(email, pwd_hash, name, age, role)

    @staticmethod
    def login(email: str, password: str) -> dict | None:
        user = UserRepository.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        # Return cleaned dict
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "age": user["age"],
            "profile_photo": user.get("profile_photo"),
            "role": user.get("role", "user")
        }

    @staticmethod
    def initiate_forgot_password_otp(email_addr: str) -> str:
        otp = f"{random.randint(100000, 999999)}"
        key = f"reset_otp:{email_addr.lower().strip()}"
        record = {
            "otp": otp,
            "payload": {"type": "reset"},
            "attempts": 0,
            "verified": False
        }
        redis_client.setex(key, 300, json.dumps(record))
        AuthService.send_reset_otp_email(email_addr, otp)
        return otp

    @staticmethod
    def send_reset_otp_email(email_addr: str, otp: str):
        if os.environ.get("ENV") != "production":
            logger.info(f"[RESET OTP DEBUG] Reset OTP for {email_addr}: {otp}")
        logger.info(f"Sending reset OTP email to {email_addr}")
        
        subject = "Invexo - Password Reset Verification Code"
        text_content = (
            f"You requested a password reset for your Invexo account.\n\n"
            f"Your 6-digit verification code (OTP) is: {otp}\n\n"
            f"This code will expire in 5 minutes. If you did not request this, please ignore this email."
        )
        AuthService._dispatch_email(email_addr, subject, text_content)

    @staticmethod
    def verify_forgot_password_otp_only(email_addr: str, otp: str) -> bool:
        key = f"reset_otp:{email_addr.lower().strip()}"
        val = redis_client.get(key)
        if not val:
            return False
            
        record = json.loads(val)
        if record.get("payload", {}).get("type") != "reset":
            redis_client.delete(key)
            return False
            
        record["attempts"] = record.get("attempts", 0) + 1
        if record["attempts"] > 5:
            redis_client.delete(key)
            return False
            
        if record["otp"] != otp:
            if record["attempts"] >= 5:
                redis_client.delete(key)
            else:
                ttl = redis_client.ttl(key)
                if ttl > 0:
                    redis_client.setex(key, ttl, json.dumps(record))
            return False
            
        record["verified"] = True
        ttl = redis_client.ttl(key)
        if ttl > 0:
            redis_client.setex(key, ttl, json.dumps(record))
        return True

    @staticmethod
    def reset_password_with_otp(email_addr: str, otp: str, new_password: str) -> bool:
        key = f"reset_otp:{email_addr.lower().strip()}"
        val = redis_client.get(key)
        if not val:
            return False
            
        record = json.loads(val)
        is_verified = record.get("verified", False)
        
        if not is_verified:
            record["attempts"] = record.get("attempts", 0) + 1
            if record["attempts"] > 5:
                redis_client.delete(key)
                return False
            if record["otp"] != otp:
                if record["attempts"] >= 5:
                    redis_client.delete(key)
                else:
                    ttl = redis_client.ttl(key)
                    if ttl > 0:
                        redis_client.setex(key, ttl, json.dumps(record))
                return False
                
        if record.get("payload", {}).get("type") != "reset":
            return False
            
        redis_client.delete(key)
        
        new_hash = hash_password(new_password)
        user = UserRepository.get_user_by_email(email_addr)
        if not user:
            return False
            
        updated = UserRepository.update_password(user["id"], new_hash)
        if updated:
            # Send confirmation email
            AuthService.send_password_updated_email(email_addr)
        return updated

    @staticmethod
    def send_password_updated_email(email_addr: str):
        subject = "Invexo - Password Updated Successfully"
        text_content = (
            f"Hello,\n\n"
            f"Your password for your Invexo account has been successfully updated.\n\n"
            f"If you did not make this change, please contact our support team immediately.\n\n"
            f"Best regards,\nThe Invexo Team"
        )
        AuthService._dispatch_email(email_addr, subject, text_content)
