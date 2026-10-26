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

---

# Visual redesign research — 2026-10-27

Mandated full-research redesign pass. The eight specified sources were re-fetched live
(this session) plus additional template/typography research. Findings below drove the
implementation that follows this document's Phase-1 section.

## Sources actually inspected this pass

| Source | Live inspection | What was taken |
|---|---|---|
| reactbits.dev | Fetched: component catalog (text animations, backgrounds, micro-interactions, components) | **Nothing installed.** Decorative/animated-page vocabulary (beams, gradient text) conflicts with the spec's AI-slop bans. Listed as rejected evidence. |
| 21st.dev | Fetched: registry model — shadcn-registry-format, "one command installs source you own", themes/templates catalog | Confirms shadcn CLI as the integration route (official install method, source lands in repo, adapts to existing tokens). No premium/paid components used. |
| ui.shadcn.com | Fetched: docs, components list, dashboard examples (light+dark reference) | **Adopted for primitives**: official `shadcn` CLI used to install component *source* (tabs, tooltip, dialog, progress, select, switch, slider, table, skeleton, sonner) — then re-tokenized to the SilentOS palette. |
| radix-ui.com | Fetched: Themes 3.0, Primitives, Icons, Colors docs | Primitives come in via shadcn (Radix under the hood) for accessible tabs/dialogs/selects/tooltips. **Radix Themes not installed** — it would impose its own visual system. |
| ui.aceternity.com | Fetched: 118+ components, 183 blocks (shaders, 3D cards, glass, marquee, sparkles) | **Rejected wholesale** — landing-page flash aesthetic; spec explicitly bans glassmorphism, gradient blobs, glow, sparkles. Evidence of what NOT to do. |
| motion.dev | Fetched: docs, Motion UI components, 14.x changelog | **Not installed.** Core interactions are achievable with CSS transitions (spec: motion only for state/feedback). Re-evaluate only if a real state transition needs choreography. Keeps bundle lean for the Pi. |
| lucide.dev | Fetched: v1.61.0, 1908 icons, customization, ISC license | **Single icon family** (already installed). Stroke-width/size standardized for the new shell. |
| iconify.design | Fetched: 300k icons, multi-set API | **Not used** — aggregator invites mixed icon styles; offline-first favours bundled Lucide. |

## Additional research (dark tool UIs, typography, templates)

- **Linear's design system write-ups** (linear.app/now/how-we-redesigned-the-linear-ui and
  published DESIGN.md breakdowns): layered graphite surfaces, hairline borders instead of
  shadows, serif reserved for rare editorial moments, dense-but-quiet navigation.
- **Vercel Geist / dashboard analyses** (shadcn.io/design/vercel, blakecrosley.com guide):
  monospace for measurements and status, ruthless information density, functional empty
  states, restraint in color.
- **Stripe/Linear/Vercel craft article** (mantlr.com): typography-as-brand, interaction
  density, crafted microstates — the invariant "premium tool" decisions.
- **Tabler UI kit docs** (docs.tabler.io): dashboard structure reference (kept at pattern
  level only; Bootstrap kit not usable in a Tailwind v4 app).
- **Assistive-technology framing**: camera/computer-vision products (vision workstations)
  put the brightest element on screen = the video frame → dark canvas is the correct
  hierarchy for a vision console, not a stylistic whim.
- **Fonts**: Google Fonts (OFL) fetched as static woff2 and bundled under
  `frontend/src/assets/fonts/` — no runtime CDN (offline deployment on the Pi).
  Newsreader (variable 400–600, serif display), IBM Plex Sans (variable, UI),
  IBM Plex Mono (400/500, data). Total ≈ 190 KB after dedup.

## Three directions compared (Step 3)

**A — Obsidian Instrument.** Warm charcoal canvas (#0d0e10), layered graphite panels with
hairline borders, warm off-white ink, single teal-mint accent (continuity with SilentOS's
Phase-1 teal), semantic amber/coral/blue, Newsreader serif page titles, Plex Sans UI,
Plex Mono data. Instrument-like meters, restrained lime-free status color.

**B — Warm Clinical Editorial.** Ivory ground, ink type, forest-green accent, stone
surfaces, serif display + sans UI. Elegant and calm, but a light ground competes with
video frames for brightness (wrong hierarchy for a camera product), and the direction
drifts toward "wellness brand" rather than "communication instrument".

**C — Modern Research Console.** Graphite-blue ground, cool neutrals, cobalt accent,
all-mono numerics. Technical but reads as a generic developer/GitHub-adjacent tool —
lowest differentiation against the "unmodified admin template" failure mode.

**Chosen: A — Obsidian Instrument.**
Why: (1) the camera frame must be the brightest thing in a vision product — dark canvas
gives it primacy; (2) the instrument metaphor matches the product language already in the
code ("communication console", telemetry, calibration); (3) the teal-mint accent preserves
brand continuity instead of introducing an arbitrary new color; (4) serif titles + mono
data give the required editorial/technical contrast and a differentiating anchor that a
default shadcn admin never has.
DFII (frontend-design skill): Impact 4, Fit 5, Feasibility 5, Performance 4,
Consistency risk 2 → **16** (execute fully).

## Design system summary (tokens live in `frontend/src/styles/globals.css`)

- Surfaces: canvas `#0d0e10` → rail `#101113` → panel `#141619` → elevated `#1a1d21`;
  hairlines `#24272c` / `#33373d` (no shadows except overlays).
- Text: ink `#e8e6e1`, ink-soft `#a4a6ab`, ink-faint `#828791` (≥4.5:1 on panel).
- Accent: teal `#2dd4bf` (hover `#14b8a6`) — primary actions, active nav, live state.
- Semantic: ok `#4ec98a`, warn `#e5b454`, danger `#f07167`, info `#8aa4f0`, each with a
  dark tinted soft background; never color-only signaling (dot + text always present).
- Type: Newsreader (page titles/display), IBM Plex Sans 400/500/600 (UI), IBM Plex Mono
  (measurements, IDs, timestamps, tabular-nums). Scale: 11/12/13/14/16/20/28/36.
- Geometry: radius 4/6/10 (sharp instrument feel — not the rounded-lg template look);
  4px spacing rhythm; borders over shadows; max content width 1480px.
- Motion: 120–160 ms ease-out for state changes; global `prefers-reduced-motion` guard.

## Deliberately rejected (evidence-backed)

- Aceternity/React Bits decorative effects: gradient blobs, beams, glassmorphism, sparkles,
  marquee, 3D cards — all named as AI-slop bans in the redesign spec.
- Radix Themes kit and shadcn default theme: would replace, not adapt, our tokens.
- Inter/system defaults: flagged as generic by the frontend-design skill; replaced with
  bundled Newsreader + IBM Plex.
- A second accent color family: spec requires one primary neutral + one accent family;
  lime was dropped so teal-mint stays the single accent.
- Fake charts for CPU/memory: the backend reports point-in-time metrics only — sparklines
  would imply a history that does not exist. Charts appear only for real training curves
  parsed from job logs.
