import { useState } from "react";
import Icon from "../Icon";

export default function SignupForm({ onSubmit, onSwitchToLogin }) {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [rememberMe, setRememberMe] = useState(true);

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const currentEmail = email.trim();
    const currentPassword = password;

    if (!currentEmail || !currentPassword) {
      setError("Please fill in all fields.");
      return;
    }

    // Validate email domain
    const domain = currentEmail.split("@")[1]?.toLowerCase();
    const allowedDomains = [
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
      "126.com", "sina.com", "yeah.net",
    ];

    if (!domain || !allowedDomains.includes(domain)) {
      setError("Please use a valid email provider (e.g. Gmail, Yahoo, Outlook).");
      return;
    }

    if (currentPassword !== confirmPw) {
      setError("Passwords do not match.");
      return;
    }
    if (currentPassword.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (!name.trim()) {
      setError("Please enter your name.");
      return;
    }
    if (!age || parseInt(age) < 1 || parseInt(age) > 150) {
      setError("Please enter a valid age.");
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        age: parseInt(age),
        email: currentEmail,
        password: currentPassword,
        rememberMe,
      });
    } catch (err) {
      let msg = err?.response?.data?.detail;
      if (Array.isArray(msg)) {
        msg = msg[0]?.msg || "Validation error";
      }
      msg = typeof msg === "string" ? msg : "Something went wrong. Please try again.";

      if (msg.toLowerCase().includes("already exists")) {
        setError(
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            This email is already registered.{" "}
            <button
              type="button"
              onClick={() => {
                setError("");
                onSwitchToLogin();
              }}
              style={{
                background: "none",
                border: "none",
                color: "var(--accent)",
                fontWeight: 700,
                cursor: "pointer",
                padding: 0,
                textDecoration: "underline",
                fontSize: "inherit"
              }}
            >
              Sign In Instead
            </button>
          </span>
        );
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Name & Age */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          marginBottom: "18px",
          animation: "fadeInUp 0.3s ease forwards",
        }}
      >
        <div style={{ flex: "2 1 0" }}>
          <label style={labelStyle}>Full Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="John Doe"
            style={inputStyle}
            onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--input-border)")}
          />
        </div>
        <div style={{ flex: "1 1 0", minWidth: "80px" }}>
          <label style={labelStyle}>Age</label>
          <input
            type="number"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            placeholder="25"
            min="1"
            max="150"
            style={inputStyle}
            onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--input-border)")}
          />
        </div>
      </div>

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

      {/* Password */}
      <div style={{ marginBottom: "18px" }}>
        <label style={labelStyle}>Password</label>
        <div style={{ position: "relative" }}>
          <input
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            style={{ ...inputStyle, paddingRight: "46px" }}
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
      <div
        style={{
          marginBottom: "20px",
          animation: "fadeInUp 0.3s ease forwards",
        }}
      >
        <label style={labelStyle}>Confirm Password</label>
        <div style={{ position: "relative" }}>
          <input
            type={showConfirmPw ? "text" : "password"}
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            autoComplete="new-password"
            style={{ ...inputStyle, paddingRight: "46px" }}
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

      {/* Remember me */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          marginBottom: "24px",
        }}
      >
        <div
          onClick={() => setRememberMe(!rememberMe)}
          style={{
            width: "18px",
            height: "18px",
            borderRadius: "5px",
            border: `1.5px solid ${
              rememberMe ? "var(--accent)" : "var(--border-medium)"
            }`,
            background: rememberMe ? "var(--accent-dim)" : "transparent",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "all 0.2s",
            flexShrink: 0,
          }}
        >
          {rememberMe && (
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--accent)"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </div>
        <span
          onClick={() => setRememberMe(!rememberMe)}
          style={{
            fontSize: "0.85rem",
            color: "var(--text-muted)",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          Keep me signed in
        </span>
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
            Signing up…
          </span>
        ) : (
          "Create Account"
        )}
      </button>

      {/* Switch to login prompt */}
      <p
        style={{
          textAlign: "center",
          marginTop: "24px",
          fontSize: "0.85rem",
          color: "var(--text-muted)",
        }}
      >
        Already have an account?{" "}
        <span
          onClick={() => onSwitchToLogin()}
          style={{
            color: "var(--accent)",
            fontWeight: 700,
            cursor: "pointer",
            transition: "opacity 0.2s",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.8")}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
        >
          Sign In
        </span>
      </p>
    </form>
  );
}
