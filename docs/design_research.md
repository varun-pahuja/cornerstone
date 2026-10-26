# SilentOS — Design Research

Record of the design research mandated before implementation: sources inspected,
components and libraries evaluated, and the decisions taken. Date: 2026-10-26.

## Skills inspected and applied

Inspected the agent skill registry (`~/.agents/skills`, `~/.config/opencode/skills`;
no `/skills` directory exists on this machine). Read and applied:

| Skill | Where | Applied as |
|---|---|---|
| `frontend-design` | `~/.agents/skills/frontend-design` | Design-direction discipline (named aesthetic, anti-generic checks) |
| `design-system` | `~/.agents/skills/design-system` | Token architecture, typography hierarchy, no hard-coded hex in components, focus/chrome stability rules |
| `super-code/typescript` | `~/.agents/skills/super-code/typescript` | Idiomatic TS patterns, no `any`, inference-first typing |
| `super-code/python` | `~/.agents/skills/super-code/python` | Idiomatic Python patterns for the backend |
| `fastapi-pro` | `~/.agents/skills/fastapi-pro` | Pydantic-first API contracts, async-aware design, lifespan handling |
| `pytest-skill` | `~/.agents/skills/pytest-skill` | Fixture/parametrize patterns used in `backend/tests` |
| `impeccable` | `~/.config/opencode/skills/impeccable` | Read (not invoked) — "Operate" mode confirmed as the right mode for a dashboard |

Not claimed: no skill was listed as applied unless it was actually read.

## Component library research

All eight mandated sources were fetched and reviewed (official sites):

| Source | What it offers | Verdict for SilentOS |
|---|---|---|
| **React Bits** (reactbits.dev) | Animated decorative components (text animations, backgrounds) | **Not used.** Effects target marketing pages; spec forbids decorative animation on a device console. |
| **21st.dev** (21st.dev) | Community registry, shadcn-compatible, copy-in components | **Reference only.** Useful as a pattern source (sidebar/command-menu structures), but components were not installed — the needed primitives are small and written locally in shadcn style. |
| **shadcn/ui** (ui.shadcn.com) | Composable, accessible primitives you own as source; Radix + Tailwind | **Adopted as the pattern.** `frontend/src/components/ui/` holds locally-owned components in the shadcn style (no runtime dependency on an external kit, works offline). |
| **Radix UI** (radix-ui.com) | Unstyled accessible primitives (dialogs, popovers, selects, tabs) + Themes | **Adopted incrementally.** Primitives will be added per component when a page needs them (dialog/tabs in Phase 2+). Radix Themes is *not* used — it would impose its own visual system over ours. |
| **Lucide** (lucide.dev) | 1900+ tree-shakable icons, ISC license, React package | **Selected as the single icon family** (see below). |
| **Motion** (motion.dev, formerly Framer Motion) | Animation library, free core, 3.2 kB mini entry | **Not installed (yet).** Current UI communicates state with CSS transitions only; `prefers-reduced-motion` is honored globally. Re-evaluate only if a state transition genuinely needs choreography — spec allows motion only for state/feedback/navigation. |
| **Iconify** (iconify.design) | 300k+ icons from many sets, one API | **Not used.** A multi-set aggregator invites icon-style mixing; spec requires one consistent icon family. Offline operation also favours bundled Lucide SVGs over an icon API. |
| **Aceternity UI** (ui.aceternity.com) | 200+ animated landing-page components (gradients, shaders, 3D) | **Not used.** Explicitly a landing-page/flash aesthetic; spec bans neon gradients, glow and glassmorphism. |

### Licensing notes

- Lucide: **ISC** license — permissive, compatible.
- Radix primitives: **MIT**.
- shadcn/ui components: **MIT**, and the model is "source lands in your repo" — no lock-in.
- Motion: **MIT** (core library).
- Aceternity: MIT for free components (commercial use allowed), but not applicable to this product.
- Iconify: code MIT/Apache; *individual icon sets carry their own licenses* — a reason to prefer one bundled family.

## Components selected and why

| Component | Source/pattern | Reason |
|---|---|---|
| App shell (dark nav rail + light work area + status header) | shadcn-style local component | Persistent navigation with clear current-page indicator (active state = inset accent bar), responsive (icon-only rail below `md`). |
| `StatusBadge` | Local (shadcn style) | One semantic pill (`ok/warn/danger/info/neutral`) so status colors stay consistent and meaningful across all 9 pages. |
| Cards / rows for data | Local | Thin 1px borders, no shadows, label-cased section headers — the industrial-console voice. |
| Typed API client | Local (`services/api.ts`) | Single `fetch` boundary with timeouts and typed errors; no component fetches raw URLs. |
| Tabs, dialogs, tooltips, selects, command menu | Radix primitives (future, per page need) | Accessible-by-default keyboard/focus behavior; added only when a page actually needs them. |
| Charts | Recharts (installed, unused so far) | Spec allows Recharts; will be used only with real measured data (training metrics, latency history). |

**Deliberately minimal dependency set so far:** `react`, `react-dom`, `react-router-dom`,
`lucide-react`, `recharts`, `tailwindcss` + `@tailwindcss/vite`. No animation library, no state
library, no UI kit runtime.

## Icon library

**Lucide** (`lucide-react` v1.61.0, ISC). One family only. Icons used for navigation
(LayoutDashboard, Camera, FlaskConical, Layers, GraduationCap, History, Target, Settings,
Activity) with `aria-hidden` (labels carry meaning). No emoji as icons; no manually drawn SVGs;
no Iconify aggregation.

## Logo search outcome

Searched the web for an existing legitimate "SilentOS" project logo. Results were unrelated
projects with similar names (Silent Speakers/FingerSpeak, silencespeaks.io, Silent SOS, etc.) —
**no verified logo belonging to this project was found**. Per requirements: the header uses a
plain typographic wordmark **"SilentOS"** (white "Silent" + teal "OS" from the palette — type
coloring, not an invented symbol). No symbol or generated logo was created; the wordmark is a
single span and can be replaced in `AppShell.tsx` when a real logo exists.

## Typography and color system

**Direction: "Industrial Utilitarian"** — a calm assistive-tech console, not a template admin
and not an AI landing page.

- **Fonts:** a deliberate system stack (`system-ui, Segoe UI, Roboto, …`) for body, and a
  monospace stack for all measurements/IDs/timestamps (`.data` class with
  `font-variant-numeric: tabular-nums`). Rationale: zero font downloads (offline-first),
  no FOUT on the Pi, and tabular numerals give the technical-instrument character. A
  self-hosted display face (e.g. IBM Plex) can be added later as WOFF2 if desired — it must
  not come from a third-party CDN.
- **Color tokens** (`frontend/src/styles/globals.css`, `@theme` block — components only use
  token utilities, never raw hex):
  - Surfaces: warm `paper` background, `panel` white cards, near-black `rail` nav.
  - Text: `ink` / `ink-soft` / `ink-faint` three-step hierarchy.
  - Lines: `line` and `line-strong` (1px borders instead of shadows).
  - Single accent: deep teal `accent #0f766e` for primary actions and active navigation.
  - Status: `ok/warn/danger/info` with soft backgrounds — used **only** for real states.
- **Spacing/rhythm:** consistent 4px-based Tailwind spacing, fixed 14-unit header height
  (chrome never resizes — status text truncates instead of wrapping).

## Accessibility and performance decisions

- Keyboard: visible `:focus-visible` ring (accent, 2px) globally; nav is real
  `<nav>/<ul>/<a>` with `NavLink` active semantics; `aria-hidden` on decorative icons.
- Contrast: near-black ink on warm white ≈ 15:1; teal accent on white ≈ 5.9:1 — both clear
  WCAG AA (4.5:1). Status pills use dark semantic text on soft backgrounds.
- Motion: CSS transitions only; a global `prefers-reduced-motion` media query zeroes
  animation/transition durations.
- Performance: production build is **274 kB JS (87 kB gzip) + 17 kB CSS** total; no
  animation/state libraries; polling uses 5–10 s intervals (never frame-rate updates);
  no WebSocket event yet, and when added it will be bounded and rate-limited so charts and
  lists never re-render per camera frame.
- Honest states: every metric renders `Unavailable` when the backend returns `null`;
  placeholder pages state their phase instead of rendering fake controls; `DEMO/SIMULATED`
  will be used only when simulation is genuinely active.
