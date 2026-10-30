# SilentOS — Skills Inventory

Created: 2026-10-30. There is **no `/skills` directory** in this workspace; skills come
from the agent's installed skill registry (`~/.agents/skills/`, surfaced in the agent's
available-skills list). Only skills whose instructions were actually opened are marked
**read**; the rest are listed by registry description for future use.

## Relevant skills

| Skill | Purpose | Supports project tasks | Status |
|---|---|---|---|
| `super-code/python` | Idiomatic Python (comprehensions, typing, anti-patterns) | Backend modules, training code, ingest script | **read** (this audit) |
| `systematic-debugging` | Root-cause-first debugging protocol | MediaPipe SIGKILL investigation (T-ML-01) | **read** (this audit) |
| `fastapi-pro` | FastAPI/Pydantic best practices | API routes, settings validation, worker threads | **read** (this audit) |
| `typescript` (`super-code/typescript`) | TS language guidelines | Frontend pages/services | not read |
| `testing-patterns` / `pytest-skill` | Test structure, fixtures, parametrize | Backend pytest suite | not read (suite already green) |
| `frontend-design` / `impeccable` | UI/UX design quality review | Dashboard redesign (already complete — do not re-open) | not read (redesign frozen by directive) |
| `ml-engineer` / `rag-engineering` | ML pipeline guidance | Training pipeline (Phase 10) | not read |
| `scikit-learn` | sklearn workflows | Not applicable — training uses a custom `LogisticBaseline` | not read |
| `computer-vision-expert` | CV model guidance | Landmark/feature work | not read |
| `documentation` / `readme` | Docs generation | README fix (T-DOC-01) | not read |
| `git-pushing` / `commit` | Commit conventions | Only when user approves a commit | not read (no commit approved) |
| `debugger` / `diagnosing-bugs` | Debugging workflows | Overlaps `systematic-debugging` | not read |

## Graphify instructions

- `AGENTS.md` contains the `graphify init` rules block (use Graphify before grep) — **read**.
- No Graphify-specific skill file exists under a `/skills` directory.

## Skills actually used this session

1. `super-code/python` — style reference while auditing backend/ingest code.
2. `systematic-debugging` — governed the MediaPipe probe approach (root-cause before fix;
   probes were read-only, single-purpose, and no fix was applied without evidence).
3. `fastapi-pro` — reference while auditing the training route/worker design.

Not loaded: anything design/UI (redesign is frozen), anything that would trigger
implementation before the audit was delivered.
