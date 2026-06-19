import os

filepath = "frontend/context/AuthContext.js" # dummy
filepath = "backend/app/services/auth/auth_service.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Define the new helper method
helper = """    @staticmethod
    def _send_email(to: str, subject: str, text: str, html: str = None) -> bool:
        \"\"\"Sends an email via Resend API with SMTP fallback. Returns True on success.\"\"\"
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
    def send_otp_email(email_addr: str, otp: str):"""

# Update send_otp_email
old_send_otp_email = """    @staticmethod
    def send_otp_email(email_addr: str, otp: str):
        if os.environ.get("ENV") != "production":
            logger.info(f"[OTP DEBUG] OTP for {email_addr}: {otp}")
        logger.info(f"Sending signup OTP email to {email_addr}")
        
        # 1. Try Resend HTTP API
        resend_key = os.environ.get("RESEND_API_KEY", "")
        if resend_key:
            try:
                import requests
                sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
                res = requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    json={
                        "from": sender,
                        "to": [email_addr],
                        "subject": "Invexo - Verify Your Email",
                        "text": (
                            f"Thank you for signing up for Invexo!\\n\\n"
                            f"Your 6-digit verification code (OTP) is: {otp}\\n\\n"
                            f"This code will expire in 5 minutes. Please do not share it with anyone."
                        )
                    },
                    timeout=10
                )
                if res.status_code in [200, 201]:
                    logger.info(f"[Resend] Successfully sent OTP email to {email_addr}")
                    return
                else:
                    raise RuntimeError(f"Resend API error (status {res.status_code}): {res.text}")
            except Exception as e:
                logger.error(f"[Resend ERROR] Failed to send email to {email_addr}: {e}")
                raise RuntimeError(f"Email delivery failed via Resend API: {str(e)}")

        # 2. Try SMTP
        host = os.environ.get("SMTP_HOST", "")
        port_str = os.environ.get("SMTP_PORT", "")
        user = os.environ.get("SMTP_USER", "")
        password = os.environ.get("SMTP_PASSWORD", "")
        sender = os.environ.get("SMTP_FROM", user)

        if host and port_str and user and password:
            try:
                import smtplib
                port = int(port_str)
                msg = MIMEText(
                    f"Thank you for signing up for Invexo!\\n\\n"
                    f"Your 6-digit verification code (OTP) is: {otp}\\n\\n"
                    f"This code will expire in 5 minutes. Please do not share it with anyone."
                )
                msg["Subject"] = "Invexo - Verify Your Email"
                msg["From"] = sender
                msg["To"] = email_addr

                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=10)
                else:
                    server = smtplib.SMTP(host, port, timeout=10)
                    server.starttls()
                server.login(user, password)
                server.sendmail(sender, [email_addr], msg.as_string())
                server.quit()
                logger.info(f"[SMTP] Successfully sent OTP email to {email_addr}")
            except Exception as e:
                logger.error(f"[SMTP ERROR] Failed to send email to {email_addr}: {e}")
                raise RuntimeError(f"Email delivery failed: {str(e)}")"""

new_send_otp_email = """    @staticmethod
    def send_otp_email(email_addr: str, otp: str):
        if os.environ.get("ENV") != "production":
            logger.info(f"[OTP DEBUG] OTP for {email_addr}: {otp}")
        logger.info(f"Sending signup OTP email to {email_addr}")
        
        subject = "Invexo - Verify Your Email"
        text_content = (
            f"Thank you for signing up for Invexo!\\n\\n"
            f"Your 6-digit verification code (OTP) is: {otp}\\n\\n"
            f"This code will expire in 5 minutes. Please do not share it with anyone."
        )
        AuthService._send_email(email_addr, subject, text_content)"""

content = content.replace(old_send_otp_email, new_send_otp_email)
content = content.replace("    @staticmethod\n    def send_otp_email(email_addr: str, otp: str):", helper)


# Replace send_reset_otp_email
old_send_reset_otp_email = """    @staticmethod
    def send_reset_otp_email(email_addr: str, otp: str):
        if os.environ.get("ENV") != "production":
            logger.info(f"[RESET OTP DEBUG] Reset OTP for {email_addr}: {otp}")
        logger.info(f"Sending reset OTP email to {email_addr}")
        
        subject = "Invexo - Password Reset Verification Code"
        text_content = (
            f"You requested a password reset for your Invexo account.\\n\\n"
            f"Your 6-digit verification code (OTP) is: {otp}\\n\\n"
            f"This code will expire in 5 minutes. If you did not request this, please ignore this email."
        )
        
        resend_key = os.environ.get("RESEND_API_KEY", "")
        if resend_key:
            try:
                import requests
                sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
                requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    json={"from": sender, "to": [email_addr], "subject": subject, "text": text_content},
                    timeout=10
                )
            except Exception as e:
                logger.error(f"[Resend ERROR] Failed to send reset email: {e}")

        host = os.environ.get("SMTP_HOST", "")
        port_str = os.environ.get("SMTP_PORT", "")
        user = os.environ.get("SMTP_USER", "")
        password = os.environ.get("SMTP_PASSWORD", "")
        sender = os.environ.get("SMTP_FROM", user)

        if host and port_str and user and password:
            try:
                port = int(port_str)
                msg = MIMEText(text_content)
                msg["Subject"] = subject
                msg["From"] = sender
                msg["To"] = email_addr
                import smtplib
                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=10)
                else:
                    server = smtplib.SMTP(host, port, timeout=10)
                    server.starttls()
                server.login(user, password)
                server.sendmail(sender, [email_addr], msg.as_string())
                server.quit()
            except Exception as e:
                logger.error(f"[SMTP ERROR] Failed to send reset email: {e}")"""

new_send_reset_otp_email = """    @staticmethod
    def send_reset_otp_email(email_addr: str, otp: str):
        if os.environ.get("ENV") != "production":
            logger.info(f"[RESET OTP DEBUG] Reset OTP for {email_addr}: {otp}")
        logger.info(f"Sending reset OTP email to {email_addr}")
        
        subject = "Invexo - Password Reset Verification Code"
        text_content = (
            f"You requested a password reset for your Invexo account.\\n\\n"
            f"Your 6-digit verification code (OTP) is: {otp}\\n\\n"
            f"This code will expire in 5 minutes. If you did not request this, please ignore this email."
        )
        AuthService._send_email(email_addr, subject, text_content)"""

content = content.replace(old_send_reset_otp_email, new_send_reset_otp_email)


# Replace send_password_updated_email
old_send_password_updated_email = """    @staticmethod
    def send_password_updated_email(email_addr: str):
        subject = "Invexo - Password Updated Successfully"
        text_content = (
            f"Hello,\\n\\n"
            f"Your password for your Invexo account has been successfully updated.\\n\\n"
            f"If you did not make this change, please contact our support team immediately.\\n\\n"
            f"Best regards,\\nThe Invexo Team"
        )
        resend_key = os.environ.get("RESEND_API_KEY", "")
        if resend_key:
            try:
                import requests
                sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
                requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    json={"from": sender, "to": [email_addr], "subject": subject, "text": text_content},
                    timeout=10
                )
                return
            except Exception as e:
                logger.error(f"[Resend ERROR] Failed to send password update email: {e}")

        host = os.environ.get("SMTP_HOST", "")
        port_str = os.environ.get("SMTP_PORT", "")
        user = os.environ.get("SMTP_USER", "")
        password = os.environ.get("SMTP_PASSWORD", "")
        sender = os.environ.get("SMTP_FROM", user)

        if host and port_str and user and password:
            try:
                port = int(port_str)
                msg = MIMEText(text_content)
                msg["Subject"] = subject
                msg["From"] = sender
                msg["To"] = email_addr
                import smtplib
                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=10)
                else:
                    server = smtplib.SMTP(host, port, timeout=10)
                    server.starttls()
                server.login(user, password)
                server.sendmail(sender, [email_addr], msg.as_string())
                server.quit()
            except Exception as e:
                logger.error(f"[SMTP ERROR] Failed to send password update email: {e}")"""

new_send_password_updated_email = """    @staticmethod
    def send_password_updated_email(email_addr: str):
        subject = "Invexo - Password Updated Successfully"
        text_content = (
            f"Hello,\\n\\n"
            f"Your password for your Invexo account has been successfully updated.\\n\\n"
            f"If you did not make this change, please contact our support team immediately.\\n\\n"
            f"Best regards,\\nThe Invexo Team"
        )
        AuthService._send_email(email_addr, subject, text_content)"""

content = content.replace(old_send_password_updated_email, new_send_password_updated_email)


# Refactor send_welcome_email as well
old_send_welcome_email_bottom = """        resend_key = os.environ.get("RESEND_API_KEY", "")
        if resend_key:
            try:
                import requests
                sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
                requests.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}"},
                    json={"from": sender, "to": [email_addr], "subject": subject, "html": html_content},
                    timeout=10
                )
                return
            except Exception as e:
                logger.error(f"[Resend ERROR] Failed to send welcome email: {e}")

        host = os.environ.get("SMTP_HOST", "")
        port_str = os.environ.get("SMTP_PORT", "")
        user = os.environ.get("SMTP_USER", "")
        password = os.environ.get("SMTP_PASSWORD", "")
        sender = os.environ.get("SMTP_FROM", user)

        if host and port_str and user and password:
            try:
                from email.mime.multipart import MIMEMultipart
                port = int(port_str)
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = sender
                msg["To"] = email_addr
                msg.attach(MIMEText(html_content, "html"))

                import smtplib
                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=10)
                else:
                    server = smtplib.SMTP(host, port, timeout=10)
                    server.starttls()
                server.login(user, password)
                server.sendmail(sender, [email_addr], msg.as_string())
                server.quit()
                logger.info(f"[SMTP] Successfully sent welcome email to {email_addr}")
            except Exception as e:
                logger.error(f"[SMTP ERROR] Failed to send welcome email: {e}")"""

new_send_welcome_email_bottom = """        AuthService._send_email(email_addr, subject, "", html_content)"""

content = content.replace(old_send_welcome_email_bottom, new_send_welcome_email_bottom)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored successfully")
