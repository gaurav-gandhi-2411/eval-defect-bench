#!/usr/bin/env python3
"""Score a detector's output against the eval_defects benchmark.

Usage
-----
    python scripts/score.py --benchmark benchmark/eval_defects.jsonl --detector <your_output.jsonl>

Input format (the file you pass to --detector)
-----------------------------------------------
A JSONL file, one record per benchmark item, containing:

    {
      "commit_sha": "<sha> | null",      # required if the item is a positive (has a commit_sha
                                          # in eval_defects.jsonl); null/absent for controls
      "file": "src/google/adk/...",      # required for matching control items (commit_sha is
                                          # null for every control in eval_defects.jsonl, so file +
                                          # function_name together are the only way to identify one)
      "function_name": "ClassName.method",  # required for matching control items
      "verdict": "YES" | "NO",           # required: did the detector flag this item as defective?
      "mechanism": "free text, optional" # optional: what the detector says the trigger/bug is
    }

Matching key: for each benchmark record, the canonical key is `commit_sha` if it is not null,
else `f"{file}::{function_name}"`. Your detector output must supply enough fields to reconstruct
the same key for every item it scored. A detector output missing a required benchmark item, or
containing an id this benchmark doesn't recognize, is reported as an error rather than silently
ignored (fail closed, not open).

What this script computes
--------------------------
- **Recall** = (positives the detector flagged YES) / 30
- **False-positive rate (raw)** = (controls the detector flagged YES) / 30
- **Balanced accuracy** = (recall + (1 - FPR)) / 2
- **d-prime** = Phi^-1(recall) - Phi^-1(FPR), via `statistics.NormalDist().inv_cdf` (stdlib,
  Python >= 3.8; no scipy/numpy dependency). d' near 0 means no better than guessing; d' >= 1 is
  a conventional floor for "a real, if weak, signal."

What this script deliberately does NOT compute
-------------------------------------------------
- **Adjudicated FPR.** This benchmark's own baselines found that "no bug fix landed in 12
  months" is not the same claim as "defect-free" -- several controls turned out to hide genuine,
  unfixed defects only visible on hand inspection against the live repository (see
  METHODOLOGY.md, Attempts 2 and 3). The *raw* FPR this script reports over-counts false alarms
  whenever a "false positive" turns out to be a real, previously-unfixed bug. Hand-adjudicate
  every control your detector flags YES against the live `google/adk-python` source before
  reporting an FPR number as if it were ground truth -- this script only gives you the raw
  starting point, not the final answer.
- **EXACT / REAL_OTHER / SPURIOUS localization scoring.** Whether a detector's stated
  `mechanism` text actually names the real historical defect (EXACT), names a different but
  genuine defect in the same function (REAL_OTHER), or names nothing real (SPURIOUS) is NOT
  reliably automatable -- free-text mechanism descriptions vary too much in phrasing, framing,
  and level of detail for a string/keyword match to be trustworthy (this benchmark's own
  baselines were localization-scored entirely by hand, reading the detector's stated mechanism
  against the live source at the relevant commit -- see METHODOLOGY.md). This script prints a
  reminder of this every run and does not attempt to compute EXACT/REAL_OTHER/SPURIOUS numbers
  itself. If you pass --check-mechanism-present, it will only report how many YES verdicts
  included a non-empty `mechanism` field -- a coverage check, not a correctness check.

This script has no third-party dependencies (stdlib only): argparse, json, statistics, sys.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass


@dataclass
class BenchmarkItem:
    """One labeled item from eval_defects.jsonl, reduced to what scoring needs."""

    key: str
    label: str  # "positive" | "control"


def canonical_key(commit_sha: str | None, file: str | None, function_name: str | None) -> str:
    """Compute the matching key used to align a detector's output with a benchmark record.

    Positives (non-null commit_sha) are keyed by their commit SHA. Controls (null commit_sha
    in eval_defects.jsonl) are keyed by "<file>::<function_name>", since every control record
    shares the same null commit_sha and file+function_name is the only unique identifier left.
    """
    if commit_sha:
        return commit_sha
    if not file or not function_name:
        raise ValueError(
            "Cannot compute a canonical key: commit_sha is null/absent and file/function_name "
            "are not both present. Every control-set record needs file + function_name."
        )
    return f"{file}::{function_name}"


def load_benchmark(path: str) -> dict[str, BenchmarkItem]:
    """Load eval_defects.jsonl and index every record by its canonical key.

    Fails loudly (raises) on a duplicate key or a record missing required fields -- a benchmark
    file that silently collapses two distinct items onto the same key would corrupt every
    downstream metric without any visible symptom, which is exactly the failure mode to avoid.
    """
    items: dict[str, BenchmarkItem] = {}
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            key = canonical_key(
                record.get("commit_sha"), record.get("file"), record.get("function_name")
            )
            if key in items:
                raise ValueError(f"Duplicate benchmark key {key!r} at {path}:{line_no}")
            label = record["label"]
            if label not in ("positive", "control"):
                raise ValueError(f"Unexpected label {label!r} at {path}:{line_no}")
            items[key] = BenchmarkItem(key=key, label=label)
    return items


def load_detector_output(path: str) -> dict[str, tuple[str, str]]:
    """Load a detector's output file and index every verdict by its canonical key.

    Returns a mapping of key -> (verdict, mechanism_text_or_empty). Raises on a malformed
    verdict (must be exactly "YES" or "NO", case-sensitive, to avoid silently coercing an
    ambiguous answer into a binary label the detector never actually gave).
    """
    verdicts: dict[str, tuple[str, str]] = {}
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            key = canonical_key(
                record.get("commit_sha"), record.get("file"), record.get("function_name")
            )
            verdict = record.get("verdict")
            if verdict not in ("YES", "NO"):
                raise ValueError(
                    f"Malformed verdict {verdict!r} at {path}:{line_no} "
                    '(must be exactly "YES" or "NO")'
                )
            if key in verdicts:
                raise ValueError(f"Duplicate detector-output key {key!r} at {path}:{line_no}")
            verdicts[key] = (verdict, record.get("mechanism") or "")
    return verdicts


def compute_metrics(
    benchmark: dict[str, BenchmarkItem], detector: dict[str, tuple[str, str]]
) -> dict[str, float]:
    """Compute recall, raw FPR, balanced accuracy, and d-prime.

    Fails closed: any benchmark item missing from the detector output is an error, not a
    silently-skipped item -- a partial run must not produce a metric that looks like it covers
    the full 60-item set when it doesn't.
    """
    missing = [k for k in benchmark if k not in detector]
    if missing:
        raise ValueError(
            f"Detector output is missing {len(missing)} benchmark item(s), e.g. {missing[:3]!r}. "
            "Score against the full benchmark, not a subset."
        )
    unknown = [k for k in detector if k not in benchmark]
    if unknown:
        raise ValueError(
            f"Detector output contains {len(unknown)} key(s) not present in the benchmark, "
            f"e.g. {unknown[:3]!r}."
        )

    positives = [k for k, v in benchmark.items() if v.label == "positive"]
    controls = [k for k, v in benchmark.items() if v.label == "control"]

    true_positives = sum(1 for k in positives if detector[k][0] == "YES")
    false_positives = sum(1 for k in controls if detector[k][0] == "YES")

    recall = true_positives / len(positives)
    fpr = false_positives / len(controls)
    balanced_accuracy = (recall + (1.0 - fpr)) / 2.0

    normal_dist = statistics.NormalDist()
    # d-prime is undefined (infinite) at recall/fpr of exactly 0 or 1; clamp to the nearest
    # representable value half a "count" away, the standard signal-detection-theory convention,
    # rather than let inv_cdf raise or return +/-inf.
    epsilon = 1.0 / (2.0 * len(positives))
    clamped_recall = min(max(recall, epsilon), 1.0 - epsilon)
    clamped_fpr = min(max(fpr, epsilon), 1.0 - epsilon)
    d_prime = normal_dist.inv_cdf(clamped_recall) - normal_dist.inv_cdf(clamped_fpr)

    return {
        "n_positives": len(positives),
        "n_controls": len(controls),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "recall": recall,
        "false_positive_rate_raw": fpr,
        "balanced_accuracy": balanced_accuracy,
        "d_prime": d_prime,
    }


def check_mechanism_coverage(
    benchmark: dict[str, BenchmarkItem], detector: dict[str, tuple[str, str]]
) -> tuple[int, int]:
    """Count how many YES verdicts included a non-empty `mechanism` field.

    This is a coverage check only -- it says nothing about whether the mechanism text is
    correct (see the module docstring for why that isn't automated here).
    """
    yes_items = [k for k in benchmark if detector[k][0] == "YES"]
    with_mechanism = sum(1 for k in yes_items if detector[k][1].strip())
    return with_mechanism, len(yes_items)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 success, 1 on any scoring error)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--benchmark",
        default="benchmark/eval_defects.jsonl",
        help="Path to the benchmark's eval_defects.jsonl (default: benchmark/eval_defects.jsonl)",
    )
    parser.add_argument(
        "--detector",
        required=True,
        help="Path to your detector's output JSONL file (see module docstring for format).",
    )
    parser.add_argument(
        "--check-mechanism-present",
        action="store_true",
        help="Also report how many YES verdicts included a non-empty `mechanism` field.",
    )
    args = parser.parse_args(argv)

    try:
        benchmark = load_benchmark(args.benchmark)
        detector = load_detector_output(args.detector)
        metrics = compute_metrics(benchmark, detector)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"n positives:              {metrics['n_positives']}")
    print(f"n controls:               {metrics['n_controls']}")
    print(f"true positives:           {metrics['true_positives']}")
    print(f"false positives (raw):    {metrics['false_positives']}")
    print(f"recall:                   {metrics['recall']:.4f} ({metrics['recall']:.1%})")
    print(
        f"false positive rate (raw):{metrics['false_positive_rate_raw']:.4f} "
        f"({metrics['false_positive_rate_raw']:.1%})"
    )
    print(f"balanced accuracy:        {metrics['balanced_accuracy']:.4f} "
          f"({metrics['balanced_accuracy']:.1%})")
    print(f"d-prime:                  {metrics['d_prime']:.4f}")
    print()
    print(
        "NOTE: false_positive_rate_raw is NOT adjudicated. This benchmark's own baselines found "
        "real, previously-unfixed defects hiding among the controls every time an adjudication "
        "step was skipped -- hand-check every control your detector flagged YES against the "
        "live google/adk-python source before reporting a final FPR. See METHODOLOGY.md."
    )
    print(
        "NOTE: EXACT/REAL_OTHER/SPURIOUS localization scoring is NOT computed by this script -- "
        "it was done by hand-adjudication against live source in this benchmark's own "
        "baselines, and the same is recommended for new detectors. See METHODOLOGY.md and "
        "results/*.md for how each baseline's localization numbers were produced."
    )

    if args.check_mechanism_present:
        with_mechanism, n_yes = check_mechanism_coverage(benchmark, detector)
        print()
        print(
            f"mechanism-field coverage: {with_mechanism}/{n_yes} YES verdicts included a "
            "non-empty `mechanism` field (coverage only, not a correctness check)."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
