"use client";

import { motion, useReducedMotion } from "motion/react";
import { SpinnerGap, ArrowRight } from "@phosphor-icons/react";

interface GenerateButtonProps {
  loading: boolean;
  onClick: () => void;
  disabled: boolean;
}

export default function GenerateButton({ loading, onClick, disabled }: GenerateButtonProps) {
  const reduced = useReducedMotion();

  return (
    <motion.button
      onClick={onClick}
      disabled={disabled || loading}
      whileTap={reduced ? {} : { scale: 0.97 }}
      transition={{ type: "spring", duration: 0.4, bounce: 0.15 }}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.5rem",
        padding: "0.75rem 1.5rem",
        background: "var(--color-primary)",
        border: "none",
        borderRadius: "0.5rem",
        color: "#fff",
        fontFamily: "var(--font-geist-sans), sans-serif",
        fontSize: "1rem",
        fontWeight: 600,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        transition: "opacity 0.2s",
      }}
    >
      {loading ? (
        <>
          <SpinnerGap size={18} className="animate-spin" />
          Generating...
        </>
      ) : (
        <>
          Generate Posts
          <ArrowRight size={18} />
        </>
      )}
    </motion.button>
  );
}
