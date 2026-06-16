"use client";

import { useState } from "react";
import InputSelector from "@/components/InputSelector";
import AudienceSelector from "@/components/AudienceSelector";
import ToneSelector from "@/components/ToneSelector";
import VoiceSamples from "@/components/VoiceSamples";
import GenerateButton from "@/components/GenerateButton";
import PostVariants from "@/components/PostVariants";
import PublishModal from "@/components/PublishModal";

interface Variant {
  text: string;
  score: number;
  improvement: string;
}

export default function Home() {
  const [inputType, setInputType] = useState<string>("github");
  const [inputValue, setInputValue] = useState<string>("");
  const [audience, setAudience] = useState<string>("");
  const [tone, setTone] = useState<string>("");
  const [voiceSamples, setVoiceSamples] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [bestIndex, setBestIndex] = useState(0);
  const [genTime, setGenTime] = useState(0);
  const [publishTarget, setPublishTarget] = useState<string | null>(null);
  const [error, setError] = useState("");

  function handleInputChange(type: string, value: string) {
    setInputType(type);
    setInputValue(value);
  }

  async function handleGenerate() {
    setLoading(true);
    setVariants([]);
    setError("");
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_type: inputType,
          input_value: inputValue,
          audience,
          tone,
          voice_samples: voiceSamples,
        }),
      });
      const data = await res.json();
      setVariants(data.variants);
      setBestIndex(data.best_index);
      setGenTime(data.generation_time_ms);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const isDisabled = !inputValue.trim();

  const sectionLabelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "0.8rem",
    fontWeight: 600,
    color: "var(--color-muted)",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    marginBottom: "0.625rem",
  };

  return (
    <main
      style={{
        maxWidth: "896px",
        margin: "0 auto",
        padding: "3rem 1.5rem",
        minHeight: "100dvh",
      }}
    >
      {/* Header */}
      <header style={{ marginBottom: "0.5rem" }}>
        <span
          style={{
            color: "var(--color-primary)",
            fontFamily: "var(--font-geist-sans), sans-serif",
            fontWeight: 700,
            fontSize: "1.25rem",
            letterSpacing: "-0.01em",
          }}
        >
          LNKD
        </span>
        <p
          style={{
            margin: "0.25rem 0 0",
            color: "var(--color-muted)",
            fontFamily: "var(--font-geist-sans), sans-serif",
            fontSize: "0.9rem",
          }}
        >
          Generate LinkedIn posts from anything
        </p>
      </header>

      {/* Form */}
      <section style={{ display: "flex", flexDirection: "column", gap: "1.5rem", marginTop: "2.5rem" }}>
        <div>
          <label style={sectionLabelStyle}>1. What are you sharing?</label>
          <InputSelector onChange={handleInputChange} />
        </div>

        <div>
          <label style={sectionLabelStyle}>2. Who is your audience?</label>
          <AudienceSelector value={audience} onChange={setAudience} />
        </div>

        <div>
          <label style={sectionLabelStyle}>3. What is the tone?</label>
          <ToneSelector value={tone} onChange={setTone} />
        </div>

        <div>
          <VoiceSamples onChange={setVoiceSamples} />
        </div>

        <GenerateButton loading={loading} onClick={handleGenerate} disabled={isDisabled} />

        {error && (
          <p
            style={{
              margin: 0,
              color: "var(--color-error)",
              fontFamily: "var(--font-geist-sans), sans-serif",
              fontSize: "0.875rem",
            }}
          >
            {error}
          </p>
        )}
      </section>

      {/* Results */}
      {variants.length > 0 && (
        <section style={{ marginTop: "3rem" }}>
          <PostVariants
            variants={variants}
            bestIndex={bestIndex}
            generationTimeMs={genTime}
            onPublish={(text) => setPublishTarget(text)}
          />
        </section>
      )}

      {/* Publish modal */}
      {publishTarget && (
        <PublishModal text={publishTarget} onClose={() => setPublishTarget(null)} />
      )}
    </main>
  );
}
