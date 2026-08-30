# Contributing a new detector result

This benchmark is a leaderboard, not a one-shot report: three approaches were tried
(`results/ast-scanner.md`, `results/local-llm-consensus.md`, `results/frontier-judge.md`) and
all three failed both pre-registered viability gates (see `METHODOLOGY.md`). The benchmark stays
useful as long as new approaches keep getting measured against it honestly — including ones that
also fail. A negative result is a valid, welcome contribution; do not hold back a submission
because your detector didn't beat the existing baselines.

## Process

1. **Get the benchmark.** `benchmark/eval_defects.jsonl` — 60 records (30 `label: positive`, 30
   `label: control`). Read `benchmark/SCHEMA.md` for the record schema before writing any code
   against it.

2. **Run your detector blind.** Feed your detector only the `pre_fix_source` field from each
   record — never `label`, `defect_class`, `defect_description`, `commit_sha`, `file`,
   `fix_date`, or `verified_zero_touch_at`. If your detector is an LLM, strip those fields before
   constructing any prompt. Judging with access to the label defeats the entire point of the
   benchmark; a submission found to have leaked label information into the judging step will not
   be accepted onto the leaderboard.

3. **Record every raw answer before consulting any label.** Save your detector's raw verdict and
   (if it produces one) a free-text explanation of the mechanism/trigger it believes it found,
   for every one of the 60 items, before you compare anything to `eval_defects.jsonl`'s `label`
   field. Recording answers after seeing the label risks post-hoc rationalization creeping into
   what gets reported.

4. **Format your output** as a JSONL file matching `scripts/score.py`'s documented input format
   (see the script's module docstring): one record per benchmark item, each with `commit_sha`
   (or `file` + `function_name` for controls), `verdict` (`"YES"` or `"NO"`), and optionally
   `mechanism` (free text).

5. **Score it.**

   ```bash
   python scripts/score.py --benchmark benchmark/eval_defects.jsonl --detector <your_output.jsonl>
   ```

   This prints recall, raw false-positive rate, balanced accuracy, and d-prime.

6. **Hand-adjudicate every control your detector flagged YES.** The raw false-positive rate
   `score.py` prints is not the number to report as final — this benchmark's own baselines found
   real, previously-unfixed defects hiding among the controls every time this step was skipped
   (see `METHODOLOGY.md`, Attempts 2 and 3). Read each flagged control against the live
   `google/adk-python` source and reclassify any genuine, verifiable defect as a true positive
   the control set simply hadn't caught up to yet, not a false alarm.

7. **Hand-score localization** for every item your detector flagged YES: does the stated
   mechanism match the historical commit's actual fix (EXACT), a different but genuine, verified
   defect in the same function (REAL_OTHER), or nothing real on inspection (SPURIOUS)?
   `scripts/score.py` deliberately does not automate this — see its docstring for why free-text
   mechanism matching isn't reliably automatable, and `METHODOLOGY.md` for how the existing three
   baselines did it by hand.

8. **Write `results/<detector-name>.md`**, following the shape of the existing three files: what
   was run, the exact numbers (recall, raw FPR, adjudicated FPR, balanced accuracy, d-prime,
   EXACT, EXACT+REAL_OTHER), and one or two sentences on what the numbers mean. Keep it short —
   it's an index entry, not a full methodology writeup. If your approach's investigation arc has
   real substance (multiple attempts, real measurement flaws found and fixed, like the existing
   three), add a corresponding section to `METHODOLOGY.md` and link to it from your `results/`
   file, following the existing sections' shape.

9. **Add a leaderboard row** to the table in this repo's top-level `README.md`, in the same
   column order as the existing rows.

10. **Open a PR** with: the new `results/<detector-name>.md` file, the new `README.md`
    leaderboard row, and (if applicable) a new `METHODOLOGY.md` section. Do not modify
    `benchmark/eval_defects.jsonl` — it is a frozen, shared ground truth; if you believe a
    specific record is mislabeled or wrong, open an issue describing the specific record and the
    evidence, rather than editing the file directly.

## What counts as a valid submission

- Scored against the full 60-item benchmark, not a subset.
- Judged blind (no label leakage into the judging step — see step 2).
- Raw answers recorded before label consultation (see step 3).
- Reports both raw and adjudicated false-positive rate, not just whichever is lower.
- Reports localization (EXACT and EXACT+REAL_OTHER as two separate numbers, per
  `METHODOLOGY.md`'s explanation of why collapsing them misrepresents what was measured) if your
  detector produces any mechanism/explanation text at all — a bare YES/NO with no explanation is
  acceptable but should say so explicitly rather than omitting the localization rows.
- Includes enough detail in `results/<detector-name>.md` for someone who did not run it to
  understand what was tried and reproduce the discrimination numbers via `scripts/score.py`.
