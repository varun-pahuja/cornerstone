# Dataset coverage report — `vidit031/isl-isolated-40words`

Status: 7 of the 10 SilentOS vocabulary classes covered. **PAIN, DOCTOR, TOILET
are absent from this dataset.** All numbers below were verified against the
downloaded files (sha256 spot-checked 8/8, disk↔metadata match 128/128).

## Dataset identity & provenance

| Field | Value |
|---|---|
| Repository | https://huggingface.co/datasets/vidit031/isl-isolated-40words |
| Revision (commit) | `255ce7fd10da5d05bc30d59668ba256e5f02531c` |
| Local copy | `data/external/isl-isolated-40words/` (git-ignored) |
| Fetched via | `huggingface_hub.snapshot_download` (README, metadata.csv + 7 target folders only) |
| Downloaded | 128 MP4 clips + 128 per-clip JSON sidecars + `sources.txt`, ~42 MB |
| Format | H.264 MP4, 30 FPS, 854×480 (113) or 480×480 (15), 1.87–6.67 s (mean 3.91 s) |

## License — multi-source aggregate, NOT one license

The dataset card declares `license: other`: it aggregates four upstream
datasets. Redistribution must respect each upstream license; for research use
the upstream terms below apply.

| Source | Target clips | Upstream license | Upstream |
|---|---|---|---|
| ISL500 | 90 | "see HF card" | ISL-DATA / ISL500 |
| INCLUDE | 21 | CC-BY-4.0 | INCLUDE (thank_you only) |
| CISLR | 15 | "research (see HF card)" | Exploration-Lab/CISLR (ACL EMNLP 2022) |
| ISLRTC_dictionary | 2 | Government open data / data.gov.in | ISLRTC dictionary entries |
| **Total** | **128** | | Intended use: research/education (not clinical certification) |

## Gloss → SilentOS label mapping (explicit, never assumed)

Source `word`/`normalized_word` values are lowercase; the folder slug replaces
spaces with underscores (`thank you` → `thank_you/`). Mapping used:

| Source gloss | SilentOS label | Clips |
|---|---|---|
| help | HELP | 16 |
| water | WATER | 18 |
| food | FOOD | 17 |
| yes | YES | 17 |
| no | NO | 17 |
| stop | STOP | 4 |
| thank you | THANK YOU | 39 |
| — | **PAIN, DOCTOR, TOILET** | **0 (absent from dataset)** |

SilentOS vocabulary has 10 labels; the dataset's other 33 glosses (hello,
sorry, mother, …) are out of vocabulary and were not downloaded.

## Class counts after ingestion (`data/manifests/isl40.json`)

| Label | Train | Val | Test | Total |
|---|---|---|---|---|
| HELP | 10 | 3 | 3 | 16 |
| WATER | 12 | 3 | 3 | 18 |
| FOOD | 11 | 3 | 3 | 17 |
| YES | 11 | 3 | 3 | 17 |
| NO | 11 | 3 | 3 | 17 |
| STOP | 4 | 0 | 0 | 4 |
| THANK YOU | 33 | 3 | 3 | 39 |
| **Total** | **92** | **18** | **18** | **128** |
| PAIN / DOCTOR / TOILET | — | — | — | 0 |

- Ingestion: 128/128 registered, 0 errors, 128/128 pass `probe_clip`
  validation (decode, duration, resolution, label, participant-id checks).
- All 128 recorded `duplicate_status=unique`; `sha256` matches metadata.
- One clip flagged upstream `review_status="Needs Manual Review"`
  (`stop__ISLRTC_dictionary__00631__Cease_Discontinue_Halt_Stop.mp4`,
  quality_score 1.0): **included** (its exclusion would drop STOP below the
  4-clip training minimum); flagged in its ClipRecord notes.

## Split policy (participant-based, seed 42, ratios 0.6/0.2/0.2)

- **ISL500 (90 clips)**: real signer IDs `User001`–`User015`; signers are
  shuffled into train/val/test → val/test contain only held-out signers
  (6 classes × 3 signers = 18 clips each).
- **CISLR / INCLUDE / ISLRTC (38 clips)**: no real signer identity
  (CISLR signer field holds category labels, INCLUDE holds per-clip IDs,
  ISLRTC holds dictionary IDs). These are **pinned train-only**
  (`pin={"src_cislr","src_include","src_islrtc_dictionary"}: train`) so val/test
  stay participant-held-out. Recorded in `manifest.splits.pin`.
- **Known limitation**: STOP has only 4 clips (2 CISLR + 2 ISLRTC), all with
  no signer identity → STOP is trained but **has 0 test support**; per-class
  STOP metrics cannot be computed honestly and are reported as support=0.
- Split assignment: `assign_splits`/`apply_splits` pure function, reproducible
  from (participants, seed, ratios, pin).

## Coverage-gap plan (PAIN, DOCTOR, TOILET)

Not in this dataset → collect via the existing local recording workflow:
consented signer, verified ISL glosses (never ASL substitutes), participant +
session metadata, `data/manifests` registration, then re-split. **No
synthesized or duplicated clips** will be used to inflate counts.

## Reproduce

```bash
# 1. fetch (git-ignored)
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('vidit031/isl-isolated-40words', repo_type='dataset', local_dir='data/external/isl-isolated-40words', allow_patterns=['README.md','metadata.csv','help/*','water/*','food/*','yes/*','no/*','stop/*','thank_you/*'])"
# 2. ingest (idempotent: verifies sha256, registers, splits)
.venv/bin/python scripts/ingest_isl.py
```
