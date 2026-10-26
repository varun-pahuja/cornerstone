# Dataset Studio (Phase 4)

How SilentOS records, imports, validates, splits and exports training clips.
Engine: `backend/src/silentos/dataset/` (one module, `__init__.py`).

## Facts, never assumptions

Every clip that enters a dataset is **decoded with OpenCV and measured**: frame
count, fps, resolution, duration, SHA-256. Metadata that fails validation is
rejected with the specific reason — a clip with a label outside the canonical
vocabulary, an unsafe participant id, or an undecodable file never reaches the
manifest.

## Layout

```
data/
  raw/{participant_id}/{session_id}/…   real video files (recorded or imported)
  manifests/{dataset_id}.json           clip records + split assignment
  splits/{dataset_id}.json              generated split file (mirrors manifest)
```

## Endpoints

| Endpoint | What it really does |
|---|---|
| `POST /api/v1/datasets/record` | Records N seconds (0.5–10) from the **running** camera into an MJPG `.avi`, then validates + registers. 503 when the camera is off or frames go stale mid-record. |
| `POST /api/v1/datasets/import` | Multipart upload (≤200 MB, `.mp4/.mov/.webm/.avi/.mkv`), saved under `data/raw/{participant}/{session}/`, validated, registered. Invalid files are deleted, not left behind. |
| `POST /api/v1/datasets/clips` | Registers a file that already lives under `data/` (script-generated clips). Paths outside the data root are refused. |
| `GET /api/v1/datasets/{id}` | Full manifest (raw JSON). |
| `POST /api/v1/datasets/{id}/validate` | Re-checks every registered clip against disk: existence, decodability, duration window, vocabulary, safe names. Returns per-clip errors/warnings. |
| `POST /api/v1/datasets/{id}/splits` | Deterministic participant-based split generation. |
| `GET /api/v1/datasets/{id}/splits` | Current split assignment. |
| `GET /api/v1/datasets/{id}/export` | Zip: manifest + splits (+ clips unless `include_clips=false`). |
| `GET /api/v1/datasets`, `GET /api/v1/datasets/stats` | Listing + counts **computed from real files** (by class, modality, split). |

## Validation rules

- file exists, non-empty, decodable by OpenCV; ≥1 decodable frame
- duration ∈ [0.2, 30.0] s (a sign/silent-lip utterance window)
- `label` must be in the canonical vocabulary (`configs/default.yaml`)
- `modality` ∈ {sign, lip}
- `participant_id` / `session_id` match `^[A-Za-z0-9_-]{1,64}$` (they become
  path components — unsafe names are a traversal risk)
- resolution < 64 px → warning, not rejection

## Splits

Participant-based, never random row splits:

```python
assign_splits(participants, seed, train_ratio, val_ratio)
```

- Pure function of `(participants, seed, ratios)` — same inputs, same output
  (sorted then seeded-shuffled, so input order does not matter).
- Each participant lands in **exactly one** split; all of a participant's clips
  follow them. No participant leakage across train/val/test.
- test ratio = `1 − train − val` (default 70/15/15).
- Fewer than 3 participants → everything goes to `train` with an explicit
  warning ("record more participants for val/test") instead of a silent
  degenerate split.

## Manifest format (per clip)

```json
{
  "clip_id": "clip_a1b2c3d4e5f6",
  "file": "raw/p01/s1/rec-20261027-001822-sign.avi",
  "label": "WATER", "modality": "sign",
  "participant_id": "p01", "session_id": "s1",
  "duration_s": 0.367, "frames": 11, "width": 640, "height": 480, "fps": 30.0,
  "sha256": "ebe8…", "split": "train", "created_at": "…"
}
```

## Dashboard

Dataset Studio wires all of it: record form (needs a running camera — it shows
the live camera state), import form, validation report, split generation with
seed, export download, and stats that only ever display counts derived from
disk.

## Tests

`backend/tests/test_dataset.py` (17 tests): probe facts on a real written
clip, rejection of missing/empty/corrupt files, vocabulary/unsafe-name/path
escape rejections, manifest round-trip, split determinism + disjointness +
seed sensitivity + n<3 warning, record-from-mock-camera end-to-end,
multipart import round-trip + rejects, validate-when-file-missing, splits
endpoint + determinism, export zip contents (with and without clips), 404s.
