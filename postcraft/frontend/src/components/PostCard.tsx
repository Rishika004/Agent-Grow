"use client";

import { useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { CopySimple, LinkedinLogo, LightbulbFilament } from "@phosphor-icons/react";

interface PostVariant {
  text: string;
  score: number;
  improvement: string;
}

interface PostCardProps {
  variant: PostVariant;
  index: number;
  isBest: boolean;
  onPublish: (text: string) => void;
}

export default function PostCard({ variant, index, isBest, onPublish }: PostCardProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [copied, setCopied] = useState(false);
  const reduced = useReducedMotion();

  async function handleCopy() {
    const text = textareaRef.current?.value ?? variant.text;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handlePublish() {
    const text = textareaRef.current?.value ?? variant.text;
    onPublish(text);
  }

  return (
    <motion.div
      initial={reduced ? {} : { opacity: 0, y: 16 }}
      animate={reduced ? {} : { opacity: 1, y: 0 }}
      transition={{ type: "spring", duration: 0.4, bounce: 0.15, delay: index * 0.08 }}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "0.75rem",
        padding: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        boxShadow: isBest ? "0 0 0 1px var(--color-primary)" : "none",
      }}
    >
      {/* Top row */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <span style={{ color: "var(--color-muted)", fontSize: "0.75rem" }}>
          Variant {index + 1}
        </span>
        <span
          style={{
            background: "var(--color-accent)",
            color: "oklch(0.080 0.000 0)",
            fontFamily: "var(--font-geist-mono), monospace",
            fontSize: "0.7rem",
            fontWeight: 600,
            padding: "0.125rem 0.5rem",
            borderRadius: "9999px",
          }}
        >
          {variant.score}/10
        </span>
        {isBest && (
          <span
            style={{
              background: "var(--color-primary)",
              color: "#fff",
              fontSize: "0.7rem",
              fontWeight: 600,
              padding: "0.125rem 0.5rem",
              borderRadius: "9999px",
            }}
          >
            Best pick
          </span>
        )}
      </div>

      {/* Editable post text */}
      <textarea
        ref={textareaRef}
        defaultValue={variant.text}
        rows={6}
        style={{
          width: "100%",
          background: "transparent",
          border: "none",
          color: "var(--color-ink)",
          fontFamily: "var(--font-geist-sans), sans-serif",
          fontSize: "0.875rem",
          lineHeight: 1.6,
          resize: "vertical",
          outline: "none",
        }}
      />

      {/* Improvement tip */}
      <div style={{ display: "flex", gap: "0.375rem", alignItems: "flex-start" }}>
        <LightbulbFilament size={14} style={{ color: "var(--color-muted)", marginTop: "0.125rem", flexShrink: 0 }} />
        <p
          style={{
            color: "var(--color-muted)",
            fontSize: "0.75rem",
            fontStyle: "italic",
            margin: 0,
          }}
        >
          {variant.improvement}
        </p>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button
          onClick={handleCopy}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            padding: "0.5rem 0.875rem",
            background: "var(--color-bg)",
            border: "1px solid var(--color-border)",
            borderRadius: "0.5rem",
            color: "var(--color-muted)",
            fontFamily: "var(--font-geist-sans), sans-serif",
            fontSize: "0.8rem",
            cursor: "pointer",
            transition: "color 0.15s",
          }}
        >
          <CopySimple size={14} />
          {copied ? "Copied!" : "Copy"}
        </button>

        <button
          onClick={handlePublish}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            padding: "0.5rem 0.875rem",
            background: "var(--color-primary)",
            border: "none",
            borderRadius: "0.5rem",
            color: "#fff",
            fontFamily: "var(--font-geist-sans), sans-serif",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <LinkedinLogo size={14} />
          Publish
        </button>
      </div>
    </motion.div>
  );
}
