"use client";

import { motion, useReducedMotion } from "motion/react";

const OPTIONS = ["Founder", "Engineer", "Job Seeker", "Recruiter"];

interface AudienceSelectorProps {
  value: string;
  onChange: (v: string) => void;
}

export default function AudienceSelector({ value, onChange }: AudienceSelectorProps) {
  const reduced = useReducedMotion();

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
      {OPTIONS.map((opt) => {
        const isSelected = value === opt;
        return (
          <motion.button
            key={opt}
            onClick={() => onChange(opt)}
            animate={reduced ? {} : { scale: isSelected ? 1.02 : 1 }}
            transition={{ type: "spring", duration: 0.4, bounce: 0.15 }}
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "9999px",
              border: "1px solid var(--color-border)",
              background: isSelected ? "var(--color-primary)" : "var(--color-surface)",
              color: isSelected ? "#fff" : "var(--color-muted)",
              fontFamily: "var(--font-geist-sans), sans-serif",
              fontSize: "0.875rem",
              fontWeight: isSelected ? 600 : 400,
              cursor: "pointer",
              transition: "background 0.2s, color 0.2s",
            }}
          >
            {opt}
          </motion.button>
        );
      })}
    </div>
  );
}
