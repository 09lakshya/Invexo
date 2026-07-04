import { useState, useEffect } from "react";
import Icon from "../Icon";

export default function ForgotPassword({
  email,
  setEmail,
  flowMode,
  setFlowMode,
  initiateForgotPassword,
  verifyForgotPasswordOtp,
  resetPassword,
  onBackToLogin,
}) {
  // Local states
  const [otpVal, setOtpVal] = useState(["", "", "", "", "", ""]);
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  const [cooldown, setCooldown] = useState(0);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const inputStyle = {
    width: "100%",
    background: "var(--input-bg)",
    border: "1.5px solid var(--input-border)",
    borderRadius: "12px",
    padding: "14px 16px",
    color: "var(--text-primary)",
    fontSize: "0.95rem",
    fontFamily: "inherit",
    outline: "none",
    transition: "all 0.25s",
  };

  const labelStyle = {
    display: "block",
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    marginBottom: "8px",
  };

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  // Focus shifts for OTP
  useEffect(() => {
    if (flowMode === "otp") {
      const firstInput = document.getElementById("otp-input-0");
      if (firstInput) firstInput.focus();
    }
  }, [flowMode]);

  const handleOtpChange = (value, index) => {
    const cleaned = value.replace(/[^0-9]/g, "");
    if (!cleaned) {
      const newOtp = [...otpVal];
      newOtp[index] = "";
      setOtpVal(newOtp);
      return;
    }

    const val = cleaned[cleaned.length - 1];
    const newOtp = [...otpVal];
    newOtp[index] = val;
    setOtpVal(newOtp);

    // Auto-advance
    if (index < 5) {
      const nextInput = document.getElementById(`otp-input-${index + 1}`);
      if (nextInput) nextInput.focus();
    }
  };

  const handleOtpKeyDown = (e, index) => {
    if (e.key === "Backspace") {
      if (!otpVal[index] && index > 0) {
        const prevInput = document.getElementById(`otp-input-${index - 1}`);
        if (prevInput) {
          prevInput.focus();
          const newOtp = [...otpVal];
          newOtp[index - 1] = "";
          setOtpVal(newOtp);
        }
      } else {
        const newOtp = [...otpVal];
        newOtp[index] = "";
        setOtpVal(newOtp);
      }
    }
  };

  const handleOtpPaste = (e) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData("text");
    const digits = pastedText.replace(/[^0-9]/g, "").slice(0, 6).split("");
    const newOtp = [...otpVal];
    for (let i = 0; i < 6; i++) {
      newOtp[i] = digits[i] || "";
    }
    setOtpVal(newOtp);
    const focusIndex = Math.min(digits.length, 5);
    const focusInput = document.getElementById(`otp-input-${focusIndex}`);
    if (focusInput) focusInput.focus();
  };

  // Submits
  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    const currentEmail = email.trim();
    if (!currentEmail) {
      setError("Please fill in all fields.");
      return;
    }

    setError("");
    setSubmitting(true);
    try {
      await initiateForgotPassword(currentEmail);
      setFlowMode("otp");
      setPassword(""); // ensure new password field starts empty
      setConfirmPw(""); // clear confirm password as well
      setCooldown(60);
    } catch (err) {
      let msg = err?.response?.data?.detail;
      if (Array.isArray(msg)) {
        msg = msg[0]?.msg || "Validation error";
      }
      msg = typeof msg === "string" ? msg : "Something went wrong. Please try again.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleOtpSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const code = otpVal.join("");
    if (code.length < 6) {
      setError("Please enter all 6 digits of the verification code.");
      return;
    }

    setSubmitting(true);
    try {
      await verifyForgotPasswordOtp(email.trim(), code);
      setFlowMode("new-password");
    } catch (err) {
      const msg = err?.response?.data?.detail || "Invalid or expired OTP code.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResendOtp = async () => {
    if (cooldown > 0) return;
    setError("");
    setSubmitting(true);
    try {
      await initiateForgotPassword(email.trim());
      setCooldown(60);
      setOtpVal(["", "", "", "", "", ""]);
      setTimeout(() => {
        const firstInput = document.getElementById("otp-input-0");
        if (firstInput) firstInput.focus();
      }, 50);
    } catch (err) {
      const msg = err?.response?.data?.detail || "Failed to resend OTP. Please try again.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNewPasswordSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPw) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }

    setSubmitting(true);
    try {
      const code = otpVal.join("");
      await resetPassword(email.trim(), code, password);
      // Success: reset states and go back to login credentials step
      setPassword("");
      setConfirmPw("");
      setOtpVal(["", "", "", "", "", ""]);
      onBackToLogin();
    } catch (err) {
      const msg = err?.response?.data?.detail || "Something went wrong.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {flowMode === "credentials" && (
        <form onSubmit={handleEmailSubmit}>
          {/* Email */}
          <div style={{ marginBottom: "18px" }}>
            <label style={labelStyle}>Email Address</label>
            <input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username email"
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--input-border)")}
            />
          </div>

          {/* Error */}
          {error && (
            <div
              style={{
                background: "var(--red-dim)",
                border: "1px solid var(--red-dim)",
                borderRadius: "12px",
                padding: "12px 16px",
                marginBottom: "20px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <Icon name="alert" size={16} style={{ color: "var(--red)" }} />
              <span style={{ color: "var(--red)", fontSize: "0.85rem", fontWeight: 600 }}>
                {error}
              </span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            style={{
              width: "100%",
              padding: "15px 0",
              borderRadius: "14px",
              border: "none",
              cursor: submitting ? "not-allowed" : "pointer",
              fontFamily: "inherit",
              fontWeight: 800,
              fontSize: "1rem",
              letterSpacing: "0.02em",
              background: submitting
                ? "var(--accent-dim)"
                : "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
              color: "var(--bg-primary)",
              boxShadow: submitting ? "none" : "0 8px 32px var(--accent-glow)",
              transition: "all 0.3s",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {submitting ? (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Sending code…
              </span>
            ) : (
              "Send Reset Code"
            )}
          </button>

          {/* Back to Login link */}
          <p
            style={{
              textAlign: "center",
              marginTop: "24px",
              fontSize: "0.85rem",
              color: "var(--text-muted)",
            }}
          >
            <span
              onClick={onBackToLogin}
              style={{
                color: "var(--accent)",
                fontWeight: 700,
                cursor: "pointer",
                transition: "opacity 0.2s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.8")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
            >
              Back to Sign In
            </span>
          </p>
        </form>
      )}

      {flowMode === "otp" && (
        <form onSubmit={handleOtpSubmit}>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "20px", lineHeight: 1.5 }}>
            Please enter the 6-digit verification code sent to <strong style={{ color: "var(--accent)" }}>{email}</strong>:
          </p>

          {/* 6 Digit Inputs */}
          <div style={{ display: "flex", gap: "10px", justifyContent: "space-between", marginBottom: "20px" }}>
            {otpVal.map((digit, index) => (
              <input
                key={index}
                id={`otp-input-${index}`}
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={6}
                value={digit}
                onChange={(e) => handleOtpChange(e.target.value, index)}
                onKeyDown={(e) => handleOtpKeyDown(e, index)}
                onPaste={handleOtpPaste}
                style={{
                  width: "100%",
                  height: "52px",
                  background: "var(--input-bg)",
                  border: "1.5px solid var(--input-border)",
                  borderRadius: "12px",
                  textAlign: "center",
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  color: "var(--text-primary)",
                  outline: "none",
                  transition: "all 0.25s",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "var(--accent)";
                  e.target.style.boxShadow = "0 0 0 3px var(--accent-glow)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "var(--input-border)";
                  e.target.style.boxShadow = "none";
                }}
              />
            ))}
          </div>

          {/* Error */}
          {error && (
            <div
              style={{
                background: "var(--red-dim)",
                border: "1px solid var(--red-dim)",
                borderRadius: "12px",
                padding: "12px 16px",
                marginBottom: "20px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <Icon name="alert" size={16} style={{ color: "var(--red)" }} />
              <span style={{ color: "var(--red)", fontSize: "0.85rem", fontWeight: 600 }}>
                {error}
              </span>
            </div>
          )}

          {/* Submit OTP */}
          <button
            type="submit"
            disabled={submitting}
            style={{
              width: "100%",
              padding: "15px 0",
              borderRadius: "14px",
              border: "none",
              cursor: submitting ? "not-allowed" : "pointer",
              fontFamily: "inherit",
              fontWeight: 800,
              fontSize: "1rem",
              letterSpacing: "0.02em",
              background: submitting
                ? "var(--accent-dim)"
                : "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
              color: "var(--bg-primary)",
              boxShadow: submitting ? "none" : "0 8px 32px var(--accent-glow)",
              transition: "all 0.3s",
              marginBottom: "20px",
            }}
          >
            {submitting ? (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Verifying...
              </span>
            ) : (
              "Verify OTP"
            )}
          </button>

          {/* Actions: Resend / Back */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem" }}>
            <button
              type="button"
              onClick={() => {
                setFlowMode("credentials");
                setError("");
              }}
              style={{
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
                fontFamily: "inherit",
              }}
            >
              Edit Details
            </button>

            {cooldown > 0 ? (
              <span style={{ color: "var(--text-muted)" }}>
                Resend code in {cooldown}s
              </span>
            ) : (
              <button
                type="button"
                onClick={handleResendOtp}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--accent)",
                  fontWeight: 700,
                  cursor: "pointer",
                  padding: 0,
                  textDecoration: "underline",
                  fontFamily: "inherit",
                }}
              >
                Resend Code
              </button>
            )}
          </div>
        </form>
      )}

      {flowMode === "new-password" && (
        <form onSubmit={handleNewPasswordSubmit}>
          {/* New Password */}
          <div style={{ marginBottom: "20px" }}>
            <label style={labelStyle}>New Password</label>
            <div style={{ position: "relative" }}>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                style={{
                  width: "100%",
                  background: "var(--input-bg)",
                  border: "1.5px solid var(--input-border)",
                  borderRadius: "12px",
                  padding: "14px 16px",
                  paddingRight: "46px",
                  color: "var(--text-primary)",
                  fontSize: "0.95rem",
                  fontFamily: "inherit",
                  outline: "none",
                  transition: "all 0.25s",
                }}
                onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                onBlur={(e) => (e.target.style.borderColor = "var(--input-border)")}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: "absolute",
                  right: "14px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "4px",
                  color: "var(--text-muted)",
                  display: "flex",
                  alignItems: "center",
                  transition: "color 0.2s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                tabIndex={-1}
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div style={{ marginBottom: "20px" }}>
            <label style={labelStyle}>Confirm Password</label>
            <div style={{ position: "relative" }}>
              <input
                type={showConfirmPw ? "text" : "password"}
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                autoComplete="new-password"
                style={{
                  width: "100%",
                  background: "var(--input-bg)",
                  border: "1.5px solid var(--input-border)",
                  borderRadius: "12px",
                  padding: "14px 16px",
                  paddingRight: "46px",
                  color: "var(--text-primary)",
                  fontSize: "0.95rem",
                  fontFamily: "inherit",
                  outline: "none",
                  transition: "all 0.25s",
                }}
                onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                onBlur={(e) => (e.target.style.borderColor = "var(--input-border)")}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPw(!showConfirmPw)}
                style={{
                  position: "absolute",
                  right: "14px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "4px",
                  color: "var(--text-muted)",
                  display: "flex",
                  alignItems: "center",
                  transition: "color 0.2s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                tabIndex={-1}
                title={showConfirmPw ? "Hide password" : "Show password"}
              >
                {showConfirmPw ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div
              style={{
                background: "var(--red-dim)",
                border: "1px solid var(--red-dim)",
                borderRadius: "12px",
                padding: "12px 16px",
                marginBottom: "20px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <Icon name="alert" size={16} style={{ color: "var(--red)" }} />
              <span style={{ color: "var(--red)", fontSize: "0.85rem", fontWeight: 600 }}>
                {error}
              </span>
            </div>
          )}

          {/* Submit Password */}
          <button
            type="submit"
            disabled={submitting}
            style={{
              width: "100%",
              padding: "15px 0",
              borderRadius: "14px",
              border: "none",
              cursor: submitting ? "not-allowed" : "pointer",
              fontFamily: "inherit",
              fontWeight: 800,
              fontSize: "1rem",
              letterSpacing: "0.02em",
              background: submitting
                ? "var(--accent-dim)"
                : "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
              color: "var(--bg-primary)",
              boxShadow: submitting ? "none" : "0 8px 32px var(--accent-glow)",
              transition: "all 0.3s",
              marginBottom: "20px",
            }}
          >
            {submitting ? (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Resetting...
              </span>
            ) : (
              "Reset Password"
            )}
          </button>
        </form>
      )}
    </>
  );
}
