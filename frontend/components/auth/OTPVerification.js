import { useState, useEffect } from "react";

export default function OTPVerification({ email, onVerify, onResend, onBack }) {
  const [otpVal, setOtpVal] = useState(["", "", "", "", "", ""]);
  const [cooldown, setCooldown] = useState(60);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Focus first input on mount
  useEffect(() => {
    const firstInput = document.getElementById("otp-input-0");
    if (firstInput) firstInput.focus();
  }, []);

  // Cooldown countdown timer
  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  // Handle OTP focus shifting
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

  const handleResendOtp = async () => {
    if (cooldown > 0) return;
    setError("");
    setSubmitting(true);
    try {
      await onResend();
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
      await onVerify(code);
    } catch (err) {
      const msg = err?.response?.data?.detail || "Invalid or expired OTP code.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
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
          <span style={{ fontSize: "1rem" }}>⚠️</span>
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
          "Verify & Register"
        )}
      </button>

      {/* Actions: Resend / Back */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.85rem" }}>
        <button
          type="button"
          onClick={() => {
            onBack();
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
  );
}
