import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { useAuth } from "../context/AuthContext";
import SignupForm from "../components/auth/SignupForm";
import OTPVerification from "../components/auth/OTPVerification";
import ForgotPassword from "../components/auth/ForgotPassword";

export default function LoginPage() {
  const router = useRouter();
  const {
    user,
    loading,
    login,
    initiateSignupOtp,
    verifySignupOtp,
    initiateForgotPassword,
    verifyForgotPasswordOtp,
    resetPassword,
  } = useAuth();

  const submitLock = useRef(false);

  const [mode, setMode] = useState("login"); // "login" | "signup" | "forgot-password"
  const [flowMode, setFlowMode] = useState("credentials"); // "credentials" | "otp" | "new-password"
  
  // Shared state for authentication details
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [rememberMe, setRememberMe] = useState(true);

  // States specific to the Login credentials flow in this page
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Already logged in → go home
  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user]);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    if (submitLock.current) return;

    // Read directly from DOM to bypass React state bugs with password managers
    const emailNode = document.getElementById("email");
    const passwordNode = document.getElementById("password");
    
    const currentEmail = (emailNode?.value || email).trim();
    const currentPassword = passwordNode?.value || password;

    if (!currentEmail || !currentPassword) {
      setError("Please fill in all fields.");
      return;
    }

    submitLock.current = true;
    setError("");
    setSubmitting(true);
    try {
      await login(currentEmail, currentPassword, rememberMe);
      router.replace("/");
    } catch (err) {
      let msg = err?.response?.data?.detail;
      if (Array.isArray(msg)) {
        msg = msg[0]?.msg || "Validation error";
      }
      msg = typeof msg === "string" ? msg : "Something went wrong. Please try again.";
      
      if (
        msg.toLowerCase().includes("email not found") || 
        msg.toLowerCase().includes("details not found") || 
        msg.toLowerCase().includes("account not found")
      ) {
        setError(
          <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
            Account not found.{" "}
            <button
              type="button"
              onClick={() => {
                setError("");
                setMode("signup");
                setFlowMode("credentials");
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
              Sign up instead
            </button>
          </span>
        );
      } else {
        setError(msg);
      }
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  };

  const handleSignupSubmit = async ({ name, age, email, password, rememberMe }) => {
    setName(name);
    setAge(age);
    setEmail(email);
    setPassword(password);
    setRememberMe(rememberMe);

    await initiateSignupOtp(email, password, name, age);
    setFlowMode("otp");
  };

  const handleSignupOtpVerify = async (code) => {
    await verifySignupOtp(email, code, rememberMe);
    router.replace("/");
  };

  const handleSignupOtpResend = async () => {
    await initiateSignupOtp(email, password, name, age);
  };

  const handleSignupOtpBack = () => {
    setFlowMode("credentials");
  };

  const handleForgotPasswordBackToLogin = () => {
    setMode("login");
    setFlowMode("credentials");
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-primary)",
        }}
      >
        <div className="spinner" />
      </div>
    );
  }

  if (user) return null; // redirect happening

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

  return (
    <>
      <Head>
        <title>{mode === "login" ? "Sign In" : mode === "forgot-password" ? "Reset Password" : "Create Account"} — Invexo</title>
        <meta name="description" content="Sign in to Invexo to access your portfolio, AI advisor, and live market data." />
      </Head>

      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-primary)",
          padding: "24px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "440px",
            animation: "fadeInUp 0.5s ease forwards",
            position: "relative",
            zIndex: 1,
          }}
        >
          {/* Logo */}
          <div style={{ textAlign: "center", marginBottom: "36px" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <img
                src="/logo-512.png"
                alt="Invexo Logo"
                width={120}
                height={120}
                style={{
                  width: "120px",
                  height: "120px",
                  aspectRatio: "1 / 1",
                  filter: "drop-shadow(0 4px 20px var(--accent-glow))",
                  objectFit: "contain",
                  borderRadius: "20px",
                }}
              />
            </div>
            <p
              style={{
                color: "var(--text-muted)",
                fontSize: "0.9rem",
                fontWeight: 400,
              }}
            >
              {mode === "login"
                ? "Welcome back. Sign in to continue."
                : mode === "signup" && flowMode === "otp"
                ? "We've sent a 6-digit verification code to your email."
                : mode === "signup" && flowMode === "credentials"
                ? "Create your account to get started."
                : mode === "forgot-password" && flowMode === "otp"
                ? "We've sent a 6-digit verification code to your email."
                : mode === "forgot-password" && flowMode === "new-password"
                ? "Choose a new password for your account."
                : mode === "forgot-password"
                ? "Enter your email to reset your password."
                : ""}
            </p>
          </div>

          {/* Card */}
          <div
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "24px",
              padding: "36px 32px",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              boxShadow: "var(--shadow-card)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {/* Top accent line */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                height: "2px",
                background: "linear-gradient(90deg, var(--accent), var(--purple), transparent)",
              }}
            />

            {/* Heading */}
            <h2
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 800,
                fontSize: "1.3rem",
                color: "var(--text-primary)",
                marginBottom: "24px",
                letterSpacing: "-0.01em",
              }}
            >
              {mode === "login"
                ? "Sign In"
                : mode === "signup" && flowMode === "otp"
                ? "Verify Email"
                : mode === "signup"
                ? "Create Account"
                : mode === "forgot-password" && flowMode === "otp"
                ? "Verify Email"
                : "Reset Password"}
            </h2>

            {mode === "login" && (
              <form onSubmit={handleLoginSubmit}>
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
                <div style={{ marginBottom: "20px" }}>
                  <label style={labelStyle}>Password</label>
                  <div style={{ position: "relative" }}>
                    <input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="current-password"
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
                  <div style={{ textAlign: "right", marginTop: "8px" }}>
                    <button
                      type="button"
                      onClick={() => {
                        setMode("forgot-password");
                        setFlowMode("credentials");
                        setPassword(""); // clear any autofilled password
                        setError("");
                      }}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--accent)",
                        fontSize: "0.8rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        padding: 0,
                        textDecoration: "none",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.textDecoration = "underline")}
                      onMouseLeave={(e) => (e.currentTarget.style.textDecoration = "none")}
                    >
                      Forgot Password?
                    </button>
                  </div>
                </div>

                {/* Keep me signed in */}
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
                    <span style={{ fontSize: "1rem" }}>⚠️</span>
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
                      Signing in…
                    </span>
                  ) : (
                    "Sign In"
                  )}
                </button>
              </form>
            )}

            {/* Mode switcher for login mode */}
            {mode === "login" && (
              <p
                style={{
                  textAlign: "center",
                  marginTop: "24px",
                  fontSize: "0.85rem",
                  color: "var(--text-muted)",
                }}
              >
                Don't have an account?{" "}
                <span
                  onClick={() => {
                    setMode("signup");
                    setFlowMode("credentials");
                    setError("");
                  }}
                  style={{
                    color: "var(--accent)",
                    fontWeight: 700,
                    cursor: "pointer",
                    transition: "opacity 0.2s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.8")}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                >
                  Sign Up
                </span>
              </p>
            )}

            {mode === "signup" && flowMode === "credentials" && (
              <SignupForm
                onSubmit={handleSignupSubmit}
                onSwitchToLogin={() => {
                  setMode("login");
                  setFlowMode("credentials");
                }}
              />
            )}

            {mode === "signup" && flowMode === "otp" && (
              <OTPVerification
                email={email}
                onVerify={handleSignupOtpVerify}
                onResend={handleSignupOtpResend}
                onBack={handleSignupOtpBack}
              />
            )}

            {mode === "forgot-password" && (
              <ForgotPassword
                email={email}
                setEmail={setEmail}
                flowMode={flowMode}
                setFlowMode={setFlowMode}
                initiateForgotPassword={initiateForgotPassword}
                verifyForgotPasswordOtp={verifyForgotPasswordOtp}
                resetPassword={resetPassword}
                onBackToLogin={handleForgotPasswordBackToLogin}
              />
            )}
          </div>

          {/* Footer */}
          <p
            style={{
              textAlign: "center",
              marginTop: "28px",
              fontSize: "0.72rem",
              color: "var(--text-muted)",
            }}
          >
            By continuing, you agree to Invexo's Terms of Service.
          </p>
        </div>
      </div>
    </>
  );
}
