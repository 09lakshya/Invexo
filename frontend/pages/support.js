import { useState, useEffect } from "react";
import Head from "next/head";
import Link from "next/link";
import Navbar from "../components/Navbar";
import { useAuth } from "../context/AuthContext";
import emailjs from "@emailjs/browser";

export default function SupportPage() {
  const { user } = useAuth();
  
  // Form state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState("general");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  
  // Status state
  const [status, setStatus] = useState({ type: "", text: "" }); // types: "success", "error", "loading"

  // Pre-fill user details when loaded
  useEffect(() => {
    if (user) {
      setName(user.name || "");
      setEmail(user.email || "");
    }
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Field validation
    if (!name.trim() || !email.trim() || !subject.trim() || !message.trim()) {
      setStatus({ type: "error", text: "Please fill in all fields." });
      return;
    }

    setStatus({ type: "loading", text: "Sending your message..." });

    // Grab keys from env
    const serviceId = process.env.NEXT_PUBLIC_EMAILJS_SERVICE_ID;
    const templateId = process.env.NEXT_PUBLIC_EMAILJS_TEMPLATE_ID;
    const publicKey = process.env.NEXT_PUBLIC_EMAILJS_PUBLIC_KEY;

    if (!serviceId || !templateId || !publicKey) {
      // Configuration fallback
      console.warn("EmailJS keys are missing. Simulating successful send.");
      setTimeout(() => {
        setStatus({
          type: "success",
          text: "Thank you! Your message has been sent (Developer Mode: Mock success).",
        });
        setSubject("");
        setMessage("");
      }, 1500);
      return;
    }

    try {
      const result = await emailjs.send(
        serviceId,
        templateId,
        {
          from_name: name,
          from_email: email,
          subject: subject,
          category: category.toUpperCase(),
          message: message,
        },
        publicKey
      );

      if (result.status === 200) {
        setStatus({
          type: "success",
          text: "Your message has been sent successfully. We will get back to you soon!",
        });
        setSubject("");
        setMessage("");
      } else {
        throw new Error("Unable to send message");
      }
    } catch (error) {
      console.error("EmailJS Error:", error);
      setStatus({
        type: "error",
        text: error?.text || "Failed to send the message. Please try again later or contact us directly.",
      });
    }
  };

  // FAQs Accordion states
  const [openFaq, setOpenFaq] = useState(null);
  const toggleFaq = (index) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  const faqs = [
    {
      q: "Is Invexo SEBI registered?",
      a: "No, Invexo is not SEBI registered. All tools, evaluations, stock recommendations, and portfolio tracking systems are purely for educational and training purposes.",
    },
    {
      q: "How does the AI Advisor work?",
      a: "Our AI Advisor processes technical indicators, historical pricing trends, and market news sentiments to generate educational insights about stocks. It does not provide professional financial advice.",
    },
    {
      q: "Can I track a real brokerage portfolio?",
      a: "Currently, Invexo features hypothetical paper portfolios to help you test strategies risk-free. You can manually enter your buys and sells to mirror your real-world portfolio.",
    },
    {
      q: "How do I configure my alert preferences?",
      a: "Navigate to the Settings tab in your profile menu dropdown. Under 'Notifications', you can enable or disable trade alerts, newsletters, and course updates.",
    },
  ];

  return (
    <>
      <Head>
        <title>Support & Feedback - Invexo</title>
        <meta name="description" content="Get help, submit bug reports, or send feedback to the Invexo development team." />
      </Head>

      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />

        <div className="page-wrapper-narrow" style={{ marginTop: "20px" }}>
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: "40px" }} className="animate-fadeInUp">
            <h1
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "clamp(2rem, 5vmin, 3rem)",
                fontWeight: 800,
                letterSpacing: "-0.02em",
                marginBottom: "12px",
              }}
            >
              Support & <span className="text-gradient">Feedback</span>
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem", maxWidth: "600px", margin: "0 auto" }}>
              Have questions, feedback, or encountered an issue? Let us know and we'll resolve it as soon as possible.
            </p>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(340px, 100%), 1fr))",
              gap: "32px",
              alignItems: "start",
            }}
          >
            {/* Form Column */}
            <div
              className="glass animate-fadeInUp"
              style={{
                padding: "32px",
                boxShadow: "var(--shadow-card)",
              }}
            >
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: "20px", fontFamily: "'Space Grotesk', sans-serif" }}>
                Send a Message
              </h2>

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                {/* Status Indicator */}
                {status.text && (
                  <div
                    style={{
                      padding: "12px 16px",
                      borderRadius: "10px",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      background:
                        status.type === "success"
                          ? "var(--green-dim)"
                          : status.type === "error"
                          ? "var(--red-dim)"
                          : "var(--accent-dim)",
                      color:
                        status.type === "success"
                          ? "var(--green)"
                          : status.type === "error"
                          ? "var(--red)"
                          : "var(--accent)",
                      border: `1px solid ${
                        status.type === "success"
                          ? "rgba(0, 230, 118, 0.2)"
                          : status.type === "error"
                          ? "rgba(255, 23, 68, 0.2)"
                          : "rgba(0, 229, 255, 0.2)"
                      }`,
                      transition: "all 0.3s ease",
                    }}
                  >
                    {status.type === "loading" && (
                      <span style={{ display: "inline-block", marginRight: "8px", animation: "spin 1s linear infinite" }}>
                        ⏳
                      </span>
                    )}
                    {status.text}
                  </div>
                )}

                {/* Name */}
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "8px" }}>
                    Your Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="input-premium"
                    placeholder="Enter your name"
                    disabled={status.type === "loading"}
                  />
                </div>

                {/* Email */}
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "8px" }}>
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-premium"
                    placeholder="name@provider.com"
                    disabled={status.type === "loading"}
                  />
                </div>

                {/* Category Selection */}
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "8px" }}>
                    Inquiry Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="input-premium"
                    style={{ background: "var(--input-bg)", color: "var(--text-primary)" }}
                    disabled={status.type === "loading"}
                  >
                    <option value="general">General Inquiry</option>
                    <option value="bug">Bug Report</option>
                    <option value="feature">Feature Request</option>
                    <option value="account">Account or Login Issue</option>
                  </select>
                </div>

                {/* Subject */}
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "8px" }}>
                    Subject
                  </label>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="input-premium"
                    placeholder="What is this regarding?"
                    disabled={status.type === "loading"}
                  />
                </div>

                {/* Message */}
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "8px" }}>
                    Message
                  </label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="input-premium"
                    placeholder="Please type your message in detail..."
                    rows={5}
                    style={{ resize: "vertical" }}
                    disabled={status.type === "loading"}
                  />
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ width: "100%", marginTop: "10px" }}
                  disabled={status.type === "loading"}
                >
                  {status.type === "loading" ? "Sending..." : "Submit Inquiry"}
                </button>
              </form>
            </div>

            {/* FAQs Column */}
            <div style={{ display: "flex", flexDirection: "column", gap: "24px" }} className="animate-fadeInUp animate-delay-100">
              <div
                className="glass"
                style={{
                  padding: "32px",
                  boxShadow: "var(--shadow-card)",
                }}
              >
                <h2 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: "8px", fontFamily: "'Space Grotesk', sans-serif" }}>
                  Frequently Asked Questions
                </h2>
                <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginBottom: "24px" }}>
                  Take a look at our quick responses to some common questions.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {faqs.map((faq, idx) => {
                    const isOpen = openFaq === idx;
                    return (
                      <div
                        key={idx}
                        style={{
                          borderBottom: "1px solid var(--border-subtle)",
                          paddingBottom: "12px",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => toggleFaq(idx)}
                          style={{
                            width: "100%",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            padding: "8px 0",
                            textAlign: "left",
                            color: "var(--text-primary)",
                            fontSize: "0.9rem",
                            fontWeight: 600,
                            fontFamily: "inherit",
                          }}
                        >
                          <span style={{ paddingRight: "12px" }}>{faq.q}</span>
                          <span style={{ color: "var(--accent)", fontSize: "0.8rem", transition: "transform 0.2s", transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}>
                            ▼
                          </span>
                        </button>
                        <div
                          style={{
                            maxHeight: isOpen ? "200px" : "0px",
                            overflow: "hidden",
                            transition: "all 0.3s cubic-bezier(0, 1, 0, 1)",
                            opacity: isOpen ? 1 : 0,
                            marginTop: isOpen ? "8px" : "0px",
                          }}
                        >
                          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: "1.5" }}>
                            {faq.a}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Direct email fallback card */}
              <div
                className="glass"
                style={{
                  padding: "24px",
                  display: "flex",
                  alignItems: "center",
                  gap: "16px",
                  boxShadow: "var(--shadow-card)",
                }}
              >
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "12px",
                    background: "var(--accent-dim)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--accent)",
                    fontSize: "1.2rem",
                  }}
                >
                  ✉️
                </div>
                <div>
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    Alternative Support
                  </h3>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "4px" }}>
                    Email us directly at{" "}
                    <a
                      href="mailto:support@invexo.com"
                      style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}
                    >
                      support@invexo.com
                    </a>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
