"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { X, WarningCircle } from "@phosphor-icons/react";

interface PublishModalProps {
  text: string;
  onClose: () => void;
}

export default function PublishModal({ text, onClose }: PublishModalProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const reduced = useReducedMotion();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setErrorMsg("");
    try {
      const res = await fetch("/api/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail ?? "Failed to publish.");
        setStatus("error");
      } else {
        setStatus("success");
      }
    } catch {
      setErrorMsg("Network error. Please try again.");
      setStatus("error");
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "0.625rem 0.875rem",
    background: "var(--color-bg)",
    border: "1px solid var(--color-border)",
    borderRadius: "0.5rem",
    color: "var(--color-ink)",
    fontFamily: "var(--font-geist-sans), sans-serif",
    fontSize: "0.875rem",
    outline: "none",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
        padding: "1rem",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <motion.div
        initial={reduced ? {} : { scale: 0.95, opacity: 0 }}
        animate={reduced ? {} : { scale: 1, opacity: 1 }}
        exit={reduced ? {} : { scale: 0.95, opacity: 0 }}
        transition={{ type: "spring", duration: 0.4, bounce: 0.15 }}
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "0.75rem",
          padding: "1.5rem",
          width: "100%",
          maxWidth: "420px",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
          <h2 style={{ margin: 0, color: "var(--color-ink)", fontFamily: "var(--font-geist-sans), sans-serif", fontSize: "1.125rem", fontWeight: 700 }}>
            Publish to LinkedIn
          </h2>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", color: "var(--color-muted)", cursor: "pointer", display: "flex" }}
          >
            <X size={20} />
          </button>
        </div>

        {status === "success" ? (
          <div style={{ textAlign: "center", padding: "1.5rem 0", color: "var(--color-primary)", fontFamily: "var(--font-geist-sans), sans-serif", fontWeight: 600, fontSize: "1rem" }}>
            Posted to LinkedIn!
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "var(--color-muted)", marginBottom: "0.375rem" }}>
                LinkedIn email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={inputStyle}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "var(--color-muted)", marginBottom: "0.375rem" }}>
                LinkedIn password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={inputStyle}
              />
            </div>

            <div style={{ display: "flex", gap: "0.375rem", alignItems: "flex-start" }}>
              <WarningCircle size={14} style={{ color: "var(--color-muted)", marginTop: "0.125rem", flexShrink: 0 }} />
              <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--color-muted)", fontStyle: "italic" }}>
                Your credentials are sent securely and never stored.
              </p>
            </div>

            {status === "error" && (
              <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--color-error)" }}>{errorMsg}</p>
            )}

            <button
              type="submit"
              disabled={status === "loading"}
              style={{
                padding: "0.75rem",
                background: "var(--color-primary)",
                border: "none",
                borderRadius: "0.5rem",
                color: "#fff",
                fontFamily: "var(--font-geist-sans), sans-serif",
                fontSize: "0.9rem",
                fontWeight: 600,
                cursor: status === "loading" ? "not-allowed" : "pointer",
                opacity: status === "loading" ? 0.7 : 1,
              }}
            >
              {status === "loading" ? "Publishing..." : "Publish"}
            </button>
          </form>
        )}
      </motion.div>
    </div>
  );
}
