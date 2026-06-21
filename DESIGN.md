# Design

## Theme

Dark mode. Sharp, confident, electric. A professional tool that feels like it was built by engineers who care about craft. No gradients on surfaces. The teal does all the work.

Mood: "midnight instrument room — electric teal on deep black, the quiet confidence of a tool that just works."

Strategy: Committed — teal carries 40-60% of the visual identity. Everything else is near-neutral.

## Color Palette

```css
:root {
  /* Brand */
  --color-primary:  oklch(0.720 0.130 188.0); /* electric teal — CTAs, active states, highlights */
  --color-accent:   oklch(0.820 0.080 210.0); /* ice blue — badges, scores, secondary signals */

  /* Surfaces */
  --color-bg:       oklch(0.080 0.000 0);     /* near-black — main background */
  --color-surface:  oklch(0.120 0.000 0);     /* dark card — panels, cards, input areas */
  --color-border:   oklch(0.200 0.008 188.0); /* subtle teal-tinted border */

  /* Text */
  --color-ink:      oklch(0.960 0.004 188.0); /* near-white with teal tint — body text */
  --color-muted:    oklch(0.560 0.008 188.0); /* secondary text — labels, hints */

  /* Semantic */
  --color-success:  oklch(0.720 0.130 188.0); /* same as primary */
  --color-error:    oklch(0.620 0.180 25.0);  /* warm red-orange */
}
```

## Typography

- **Primary font:** Geist (sans) — clean, technical, modern. Loaded via `next/font/google`.
- **Mono font:** Geist Mono — for scores, numbers, code snippets.
- **Scale:**
  - Display: `text-4xl md:text-5xl`, `font-semibold`, `tracking-tight`, `leading-none`
  - Heading: `text-2xl`, `font-semibold`, `tracking-tight`
  - Body: `text-sm`, `leading-relaxed`, `text-[--color-ink]`
  - Label: `text-xs`, `font-medium`, `uppercase`, `tracking-wide`, `text-[--color-muted]`
  - Mono/score: Geist Mono, `text-sm`, `tabular-nums`

## Motion

- **Library:** `motion/react` (formerly Framer Motion)
- **Philosophy (Emil Kowalski):** animate only what earns it. Every animation must communicate hierarchy, feedback, or state change.
- **Easing:** `cubic-bezier(0.23, 1, 0.32, 1)` — strong ease-out for entrances
- **Durations:** buttons 160ms, panels 200ms, cards 250ms, page transitions 300ms
- **Spring config:** `{ type: "spring", duration: 0.4, bounce: 0.15 }`
- **Reduced motion:** all motion wraps `useReducedMotion()` — collapses to opacity only

## Layout

- Max content width: `max-w-4xl mx-auto` (focused tool, not a wide dashboard)
- Page padding: `px-4 md:px-8`
- Section gap: `gap-6` between major UI blocks
- Corner radius system: `rounded-xl` for cards/panels, `rounded-lg` for inputs/buttons, `rounded-full` for badges/pills
- Grid: CSS Grid for 3-column post variants, single column for input flow

## Components

### InputSelector
Tab-style switcher: GitHub / Image / Text. Active tab highlighted with `--color-primary` bottom border + teal text. Inactive tabs muted.

### AudienceSelector
4-option pill grid: Founder / Engineer / Job Seeker / Recruiter. Selected pill gets `bg-[--color-primary]` with white text. Spring animation on selection.

### ToneSelector
4-option pill grid: Professional / Casual / Storytelling / Bold. Same pattern as AudienceSelector.

### PostVariants
3-column card grid (stacks to 1-col on mobile). Each card:
- Dark surface background
- Score badge (Geist Mono, teal accent)
- Improvement tip (muted, italic)
- Editable textarea (inline edit on click)
- Copy + Publish actions

### GenerateButton
Full-width primary CTA. Teal background, white text. `scale(0.97)` on `:active`. Loading state with skeleton shimmer.

### Score Badge
Pill: `oklch(0.820 0.080 210.0)` background, dark ink text. Geist Mono. e.g. "8/10"

## Iconography

Library: `@phosphor-icons/react` — weight `regular` (1.5 stroke equivalent). One family throughout.

## Anti-patterns (do not ship)

- No purple gradients
- No mesh/aurora backgrounds
- No three equal white cards
- No Inter as primary font
- No em-dashes anywhere
- No section-number eyebrows
- No fake product screenshots made of divs
