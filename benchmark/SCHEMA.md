# `eval_defects.jsonl` record schema

See `METHODOLOGY.md` in this repo for the full construction methodology (positive-set selection
criteria, control-set zero-touch verification method, and the exclusions applied to each).

```json
{
  "commit_sha": "... | null (control)",
  "parent_sha": "... | null (control)",
  "repo": "google/adk-python",
  "file": "src/google/adk/evaluation/...",
  "function_name": "ClassName.method | bare_function_name | ClassName",
  "fix_date": "YYYY-MM-DD | null (control)",
  "defect_description": "one line | null (control)",
  "defect_class": "D1_..|D2_..|D3_..|D4_..|D5_..|OTHER | null (control)",
  "pre_fix_source": "the actual function/class source, pre-fix",
  "label": "positive | control"
}
```

Controls additionally carry `verified_zero_touch_at` (the pinned SHA the zero-touch check
was run against).

## Field notes

- **`label`** — `positive` (30 records): a real, merged bug-fix commit's pre-fix function/
  method/class body. `control` (30 records): a function verified to have zero commits
  touching it in the 12 months prior to the pinned SHA (see `METHODOLOGY.md` for why "no
  fix landed" is not the same claim as "defect-free" — several controls in this benchmark's
  own baselines turned out to hide genuine, unfixed defects on hand-adjudication).
- **`pre_fix_source`** is the field a detector should be given — it is the code to judge.
  For positives, it is the function's source *before* the historical fix commit. For
  controls, it is the function's current source (there is no fix to be "before").
- **`defect_class`** — a five-value taxonomy (`D1_ENUM_UNDER_COVERAGE`,
  `D2_HARDCODED_POLARITY`, `D3_SILENT_DROP`, `D4_DEFAULT_SUCCESS_SURVIVES`,
  `D5_EXIT_CODE_UNSET`) plus `OTHER` for real bugs that don't match any of the five
  named shapes. Only 3 of the 30 positives match a named class; the remaining 27 are
  `OTHER` — real, shipped bugs, not shaped like any of the five.
- **A note on 5 "class-level" positives:** five of the 30 real bugs are not method-body
  logic errors but Pydantic-model field defaults / class-level shared mutable state. For
  these, `function_name` is the class name and `pre_fix_source` is the class's full
  pre-fix body, because a bare field annotation cannot be meaningfully evaluated as
  standalone Python outside the class that gives it Pydantic semantics.
- **Judging blind:** `label`, `defect_class`, `defect_description`, `commit_sha`, `file`,
  and `fix_date` exist for scoring only — never pass them to whatever is doing the
  judging. Only `pre_fix_source` should reach the detector.

## Provenance

- **Source repo:** `google/adk-python` (`https://github.com/google/adk-python`)
- **Subsystem:** `src/google/adk/evaluation/` (one positive lives in
  `src/google/adk/optimization/local_eval_sampler.py`, which directly wires into this
  subsystem — see `METHODOLOGY.md` for the full provenance note).
- **Licensing:** all 60 records derive from `google/adk-python`, licensed Apache License
  2.0. See `NOTICE` and `LICENSE-THIRD-PARTY` at this repo's root.
