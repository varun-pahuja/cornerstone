"""Ingest target classes of vidit031/isl-isolated-40words into SilentOS.

Reads metadata.csv + target-class clips from data/external/isl-isolated-40words
(fetched separately via HF tooling; git-ignored), verifies every clip against
its recorded sha256, maps glosses to the canonical SilentOS vocabulary,
copies files under data/raw/{participant}/{session}/, registers ClipRecords
with source/license provenance in notes, then applies participant-based splits.

Split policy: participants with real signer metadata (ISL500 User001..) are
shuffled into train/val/test; sources without real signer identity (CISLR,
INCLUDE, ISLRTC) are pinned train-only so val/test stay participant-held-out.

Run from the repo root:  .venv/bin/python scripts/ingest_isl.py
Idempotent: clips already in the manifest are skipped.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from silentos.config import load_settings  # noqa: E402
from silentos.dataset import (  # noqa: E402
    apply_splits,
    load_manifest,
    manifest_path,
    register_clip,
    validate_dataset,
)
from silentos.schemas import ClipMeta  # noqa: E402

EXTERNAL = ROOT / "data" / "external" / "isl-isolated-40words"
DATASET_ID = "isl40"
# explicit gloss -> canonical SilentOS label (never assumed elsewhere)
WORD_TO_LABEL = {
    "help": "HELP",
    "water": "WATER",
    "food": "FOOD",
    "yes": "YES",
    "no": "NO",
    "stop": "STOP",
    "thank you": "THANK YOU",
}
SEED = 42
TRAIN_RATIO = 0.6
VAL_RATIO = 0.2


def slug(value: str) -> str:
    return value.lower().replace(" ", "_")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    os.chdir(ROOT)
    settings = load_settings(os.environ.get("SILENTOS_CONFIG"))  # same load path as main.py
    vocab = list(settings.vocabulary.labels)
    data_dir = settings.paths.data_dir
    for p in (settings.paths.raw_dir, settings.paths.manifests_dir, settings.paths.splits_dir):
        p.mkdir(parents=True, exist_ok=True)

    meta_csv = EXTERNAL / "metadata.csv"
    if not meta_csv.is_file():
        print(f"ERROR: {meta_csv} missing — download the dataset first")
        return 1

    rows = list(csv.DictReader(meta_csv.open()))
    target = [r for r in rows if r["normalized_word"] in WORD_TO_LABEL]

    mp = manifest_path(settings.paths.manifests_dir, DATASET_ID)
    existing = set()
    if mp.is_file():
        existing = {c.file for c in load_manifest(mp).clips}

    report: dict = {"registered": 0, "skipped_existing": 0, "errors": []}
    per_class: dict[str, Counter] = defaultdict(Counter)

    for r in sorted(target, key=lambda x: (x["normalized_word"], x["video_path"])):
        word = r["normalized_word"]
        label = WORD_TO_LABEL[word]
        source = r["dataset"]
        fn = os.path.basename(r["video_path"])
        rel_src = f"{slug(word)}/{fn}"
        src = EXTERNAL / rel_src
        participant = (
            r["signer"] if source == "ISL500" and r["signer"] else f"src_{slug(source)}"
        )
        session = slug(source)
        rel_dest = f"raw/{participant}/{session}/{fn}"
        if rel_dest in existing:
            report["skipped_existing"] += 1
            per_class[label]["skipped_existing"] += 1
            continue
        if not src.is_file():
            report["errors"].append(f"{rel_src}: file missing on disk")
            continue
        digest = sha256(src)
        if digest != r["sha256"]:
            report["errors"].append(f"{rel_src}: sha256 mismatch (corrupt download?)")
            continue
        dest = data_dir / rel_dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file() or sha256(dest) != digest:
            shutil.copy2(src, dest)
        notes = (
            f"source={source}; license={r['license']}; review={r['review_status']}; "
            f"quality={r['quality_score']}; orig={fn}"
        )
        try:
            record = register_clip(
                settings.paths.manifests_dir,
                data_dir,
                ClipMeta(
                    label=label,
                    modality="sign",
                    participant_id=participant,
                    session_id=session,
                    notes=notes,
                    dataset_id=DATASET_ID,
                ),
                dest,
                vocab,
            )
        except ValueError as e:
            report["errors"].append(f"{rel_src}: {e}")
            continue
        report["registered"] += 1
        per_class[label]["registered"] += 1

    if report["registered"] == 0 and report["skipped_existing"] == 0:
        print("nothing to register — errors:\n  " + "\n  ".join(report["errors"]))
        return 1

    # participant-based splits: pin signer-less sources train-only
    m = load_manifest(mp)
    participants = sorted({c.participant_id for c in m.clips})
    pin = {p: "train" for p in participants if p.startswith("src_")}
    split = apply_splits(
        settings.paths.manifests_dir,
        settings.paths.splits_dir,
        DATASET_ID,
        seed=SEED,
        train_ratio=TRAIN_RATIO,
        val_ratio=VAL_RATIO,
        pin=pin,
    )

    vreport = validate_dataset(settings.paths.manifests_dir, data_dir, DATASET_ID, vocab)
    (settings.paths.manifests_dir / f"{DATASET_ID}_validation.json").write_text(
        json.dumps(vreport.model_dump(mode="json"), indent=2)
    )

    # summary
    m = load_manifest(mp)
    by_split: dict[str, Counter] = defaultdict(Counter)
    for c in m.clips:
        by_split[c.split or "none"][c.label] += 1
    print(f"registered={report['registered']} skipped_existing={report['skipped_existing']} "
          f"errors={len(report['errors'])}")
    for e in report["errors"]:
        print(f"  ERROR {e}")
    print(f"validation: checked={vreport.checked} valid={vreport.valid} invalid={vreport.invalid}")
    for issue in vreport.issues[:20]:
        print(f"  issue {issue.file}: {issue.errors or issue.warnings}")
    labels = sorted({c.label for c in m.clips})
    print(f"split seed={split.seed} ratios={split.ratios} pin={pin}")
    print(f"clip counts: {split.clip_counts}")
    for name in ("train", "val", "test"):
        print(f"  {name:5s} {dict(sorted(by_split[name].items()))}")
    missing = [l for l in vocab if l not in labels]
    if missing:
        print(f"vocabulary classes with NO clips: {missing}")
    return 0 if vreport.invalid == 0 and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
