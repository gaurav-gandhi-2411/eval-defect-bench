# Result: AST-based syntactic pattern matching (Attempt 1)

**What was run:** `scripts/archive/scan_verdict_defects.py` (source workspace, not included in
this repo's `scripts/` — retired), five hand-built Python `ast`-module detectors targeting five
specific code shapes (enum under-coverage, hardcoded polarity, silent-drop accumulator, default-
success-survives, unset exit code), run against this benchmark's 30 held-out positives.

**Numbers:**

| Metric | Value |
|---|---|
| Training-set recall (4 hand-picked design examples) | 75% (3/4) — not a valid generalization measurement, see below |
| Held-out recall (this benchmark's 30 positives) | 0% (0/30) |
| Held-out recall, restricted to the 3 positives matching a named defect shape | 0% (0/3) |
| False-positive rate | not measured — never run against the control set |
| Verdict | NOT VIABLE |

**Why the training-set number is not comparable:** 75% recall was measured on the exact 4
examples the detectors were hand-built from — it measures memorization of the design set, not
generalization. The held-out 0/30 (including 0/3 on shape-matching cases) is the only number
that reflects real detection capability.

**Full detail:** `METHODOLOGY.md`, "Attempt 1 — AST-based syntactic pattern matching" (includes
three documented near-misses: a naming-heuristic gap, a values-not-tokens gap, and a list-
comprehension AST-shape gap — useful starting points for a v2 attempt).
