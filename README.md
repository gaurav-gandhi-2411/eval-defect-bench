# eval-defect-bench

Three independent detection approaches — an AST scanner, a local multi-model LLM consensus, and
a single frontier-model judge — were each tried against this exact benchmark, and **none of them
passed a pre-registered viability gate.** This is the headline result, not a footnote: this
repository exists to make that negative result, and the benchmark that produced it, reusable by
the next attempt, rather than something that has to be rediscovered from scratch.

The benchmark's positive set has a verifiable, narrow date range: **all 30 positive commits have
fix dates between 2026-05-15 and 2026-08-26** (confirmed directly against `fix_date` in
`benchmark/eval_defects.jsonl`). Each record carries its own `fix_date`, so a reader evaluating any
specific model can check that model's own stated training cutoff against the exact dates that
matter to them, rather than relying on a blanket claim made on their behalf. **What was actually
checked here:** the frontier judge's stated training cutoff (January 2026), checked directly against
the fix-date range above — the frontier-judge baseline's positive set does postdate that cutoff.
**What was not checked:** the three local Ollama models' (`llama3.1:8b`, `gemma2:9b`, `qwen2.5:7b`)
actual training-data cutoffs were never determined or checked against these dates — this is an open
gap, not a settled fact, and no "contamination-free" claim is made for the local-consensus baseline.
This is a design property worth being precise about, not an incidental detail of one baseline run.

## Leaderboard

| Detector | Recall | Adjudicated FPR | Balanced accuracy | d-prime | EXACT localization | EXACT+REAL_OTHER |
|---|---|---|---|---|---|---|
| AST scanner (5 hand-built detectors) | 0% (0/30 held-out)\* | — | — | — | — | — |
| Local LLM consensus (llama3.1:8b + gemma2:9b + qwen2.5:7b, majority vote) | 53.3% | 36.7% | 58.3% | 0.42 | 0% | not re-scored |
| Frontier single judge (blind, isolated function body) | 13.3% | 6.7% | 53.3% | 0.39 | 6.7% | 13.3% |

\* The AST scanner's 0/30 is against this exact positive set (it predates and motivated this
benchmark's formalization); it was never run against the control set. Its training-set recall
(75%, on the 4 examples it was hand-built from) is not a valid comparison point — see
`METHODOLOGY.md`'s Attempt 1 for why measuring a detector against its own design examples proves
nothing about generalization.

**No detector so far has passed either the mechanism-naming gate** (EXACT >=40% AND adjudicated
FPR <=20%) **or the triage gate** (balanced accuracy >=70% AND adjudicated FPR <=15%) — both
pre-registered before the frontier-judge baseline was run. The field is open for a fourth
attempt; see `CONTRIBUTING.md` for how to submit one.

Numbers above are pulled from `METHODOLOGY.md`'s own summary table, not re-derived. Every
discrimination number (recall, raw/adjudicated FPR, balanced accuracy, d-prime) is independently
reproducible from `benchmark/eval_defects.jsonl` via `scripts/score.py` — the frontier-judge raw
row (13.3% / 10.0% raw FPR / 51.7% / 0.17) was reproduced exactly by transforming
`frontier_judge_answers.jsonl` into `scripts/score.py`'s input format and running it; see the
"Verification" section below.

## What's in this repository

- `benchmark/eval_defects.jsonl` — the frozen 60-record benchmark (30 real, merged bug-fix
  commits + 30 verified-untouched controls), copied verbatim from the source workspace. See
  `benchmark/SCHEMA.md` for the record schema and how to judge it blind.
- `scripts/score.py` — a standalone, stdlib-only Python script that scores a detector's output
  against the benchmark: recall, raw false-positive rate, balanced accuracy, d-prime. See the
  script's own docstring for its documented input format and for what it deliberately does *not*
  automate (adjudicated FPR, EXACT/REAL_OTHER/SPURIOUS localization — both require hand-checking
  against live source, as this benchmark's own baselines did).
- `METHODOLOGY.md` — the full investigation arc: three attempts, in order, with every
  measurement flaw found along the way (a degenerate LLM rater that silently poisoned a
  majority vote, an unfixed-but-not-defect-free control set, binary-scoring's inability to
  distinguish a lucky guess from a real hit) and how each was corrected before drawing a
  conclusion.
- `results/ast-scanner.md`, `results/local-llm-consensus.md`, `results/frontier-judge.md` — one
  short index entry per baseline, each pointing to the relevant `METHODOLOGY.md` section for
  full detail.
- `NOTICE` / `LICENSE-THIRD-PARTY` — attribution and license text for the `google/adk-python`
  source excerpts embedded in the benchmark (Apache License 2.0, Copyright 2026 Google LLC).
- `LICENSE` — MIT, covering this repository's own original contributions (benchmark
  construction, scoring script, methodology writeup) — chosen because a permissive license is
  the conventional choice for a research/benchmark artifact meant to be freely reused, and MIT
  imposes the least friction on a downstream user who just wants to run `scripts/score.py`
  against their own detector.
- `CONTRIBUTING.md` — the process for submitting a new detector's result to the leaderboard.

## Quick start

```bash
# Score your own detector's output against the benchmark
python scripts/score.py --benchmark benchmark/eval_defects.jsonl --detector your_output.jsonl
```

See `scripts/score.py`'s module docstring for the exact input format, and `CONTRIBUTING.md` for
the full blind-judging and adjudication process this benchmark requires before a result is
comparable to the existing leaderboard rows.

## Verification

`scripts/score.py` was tested by transforming `benchmark/raw/frontier_judge_answers.jsonl` into
the script's documented input format, using `benchmark/raw/blinding_key.jsonl` to map anonymized
item IDs back to `commit_sha`/`file`/`function_name`, and running it against
`benchmark/eval_defects.jsonl`. It reproduced the frontier judge's raw discrimination numbers
exactly:

```
n positives:              30
n controls:               30
true positives:           4
false positives (raw):    3
recall:                   0.1333 (13.3%)
false positive rate (raw):0.1000 (10.0%)
balanced accuracy:        0.5167 (51.7%)
d-prime:                  0.1708
```

This matches `METHODOLOGY.md`'s "Frontier judge, raw" row (13.3% / 10.0% / 51.7% / 0.17)
exactly. The adjudicated-FPR numbers in the leaderboard above (6.7%, not the raw 10.0%) come
from `METHODOLOGY.md`'s hand-adjudication step, which `scripts/score.py` deliberately does not
automate (see the script's docstring).

## Defect taxonomy

The 30 positive commits, plus 5 of the author's own external OSS PRs and one filed issue, were
classified by underlying mechanism (not surface symptom) into 11 shapes. Full detail, canonical
`file:line` examples, and per-shape detector performance: [`TAXONOMY.md`](./TAXONOMY.md). The
external cross-references, for independent verification:
[adk-python#6740](https://github.com/google/adk-python/pull/6740),
[#6739](https://github.com/google/adk-python/pull/6739),
[#6710](https://github.com/google/adk-python/pull/6710)→[#6939](https://github.com/google/adk-python/pull/6939),
[#6682](https://github.com/google/adk-python/pull/6682),
[keras#23420](https://github.com/keras-team/keras/pull/23420),
[adk-python#6951](https://github.com/google/adk-python/issues/6951).

| Shape | Benchmark count (/30) | External match |
|---|---|---|
| 1. Empty-collection silent degrade | 2 | issue #6951 |
| 2. Silent drop | 3 | PR #6710 → #6939 |
| 3. Config field loss (Pydantic schema) | 2 | — |
| 4. Stale threshold source | 2 | PR #6739; superseded PR #6678 |
| 5. Missing null-guard crash (loud, not silent) | 3 | — |
| 6. Unsanitized input injection | 3 | — |
| 7. Unwired config / dead setting | 3 | PR #6740 (generalized) |
| 8. Text normalization blind spot | 2 | — |
| 9. Type narrowing drops wrapper | 2 | — |
| 10. Missing numeric floor | 1 | keras PR #23420 (clean match) |
| 11. Status precedence / unconditional overwrite | 1 (weak/generalized fit) | PR #6682 (clean match) |
| **No fit** | **6 (20%)** | — |

"Hardcoded polarity" (one of five seed hypotheses tested against the data) was **not confirmed** —
zero matches among the 30, zero among the 5 PRs. 20% no-fit is under the "more than a third" weak-
taxonomy threshold, but two shapes (10, 11) have only one benchmark member each and only read as
real shapes because of the external PR cross-reference — see `TAXONOMY.md`'s closing caveats for
the honest limitations of this classification.

## Known limitations

- **n=30 per class is small.** Point estimates computed on 30 items each have wide confidence
  intervals; a handful of flipped verdicts materially moves the headline numbers. Treat any
  single percentage from this benchmark as a rough signal, not a precise measurement.
- **Single repo, single subsystem.** Everything is drawn from one Python codebase's
  agent-evaluation framework (`google/adk-python`'s `src/google/adk/evaluation/`).
  Generalization to other languages, domains, or even other subsystems of the same repo is
  untested.
- See `METHODOLOGY.md`'s own "Known limitations"-equivalent notes throughout for per-attempt
  caveats (the degenerate-rater risk in any small-model consensus, the "unfixed is not the same
  as defect-free" control-set risk, and why raw recall/FPR alone can't be trusted without
  adjudication).
