"use client";

import { useState, useRef } from "react";

type InputType = "github" | "image" | "text";

interface InputSelectorProps {
  onChange: (type: InputType, value: string) => void;
}

const TABS: { key: InputType; label: string }[] = [
  { key: "github", label: "GitHub" },
  { key: "image", label: "Image" },
  { key: "text", label: "Text" },
];

export default function InputSelector({ onChange }: InputSelectorProps) {
  const [activeTab, setActiveTab] = useState<InputType>("github");
  const [githubUrl, setGithubUrl] = useState("");
  const [imageB64, setImageB64] = useState("");
  const [textValue, setTextValue] = useState("");
  const [imageName, setImageName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleTabChange(tab: InputType) {
    setActiveTab(tab);
    const currentValue = tab === "github" ? githubUrl : tab === "image" ? imageB64 : textValue;
    onChange(tab, currentValue);
  }

  function handleGithubChange(e: React.ChangeEvent<HTMLInputElement>) {
    setGithubUrl(e.target.value);
    onChange("github", e.target.value);
  }

  function handleTextChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setTextValue(e.target.value);
    onChange("text", e.target.value);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = reader.result as string;
      setImageB64(b64);
      onChange("image", b64);
    };
    reader.readAsDataURL(file);
  }

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "0.75rem",
        overflow: "hidden",
      }}
    >
      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--color-border)" }}>
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              style={{
                flex: 1,
                padding: "0.75rem 1rem",
                background: "transparent",
                border: "none",
                borderBottom: isActive ? "2px solid var(--color-primary)" : "2px solid transparent",
                color: isActive ? "var(--color-primary)" : "var(--color-muted)",
                fontFamily: "var(--font-geist-sans), sans-serif",
                fontSize: "0.875rem",
                fontWeight: isActive ? 600 : 400,
                cursor: "pointer",
                transition: "color 0.2s, border-color 0.2s",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Input area */}
      <div style={{ padding: "1rem" }}>
        {activeTab === "github" && (
          <input
            type="url"
            placeholder="https://github.com/user/repo"
            value={githubUrl}
            onChange={handleGithubChange}
            style={{
              width: "100%",
              padding: "0.625rem 0.875rem",
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: "0.5rem",
              color: "var(--color-ink)",
              fontFamily: "var(--font-geist-sans), sans-serif",
              fontSize: "0.875rem",
              outline: "none",
            }}
          />
        )}

        {activeTab === "image" && (
          <div
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: "2px dashed var(--color-border)",
              borderRadius: "0.5rem",
              padding: "2rem",
              textAlign: "center",
              cursor: "pointer",
              color: "var(--color-muted)",
              fontSize: "0.875rem",
              transition: "border-color 0.2s",
            }}
            onMouseEnter={(e) =>
              ((e.currentTarget as HTMLElement).style.borderColor = "var(--color-primary)")
            }
            onMouseLeave={(e) =>
              ((e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)")
            }
          >
            {imageName ? (
              <span style={{ color: "var(--color-ink)" }}>{imageName}</span>
            ) : (
              "Drop image or click to upload"
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
          </div>
        )}

        {activeTab === "text" && (
          <textarea
            rows={5}
            placeholder="Share what you've been working on, learning, or thinking about..."
            value={textValue}
            onChange={handleTextChange}
            style={{
              width: "100%",
              padding: "0.625rem 0.875rem",
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: "0.5rem",
              color: "var(--color-ink)",
              fontFamily: "var(--font-geist-sans), sans-serif",
              fontSize: "0.875rem",
              resize: "vertical",
              outline: "none",
            }}
          />
        )}
      </div>
    </div>
  );
}
