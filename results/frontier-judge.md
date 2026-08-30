# Result: Single frontier-model judge, blind, localization-scored (Attempt 3)

**What was run:** the same 60-item benchmark, judged by a single frontier-capability model
(Claude), genuinely blind — fresh dispatch, zero prior context, shuffled/anonymized function
bodies only, no commit/file/label metadata, split into four independent 15-item batches. Scored
primarily on localization (EXACT / REAL_OTHER / SPURIOUS), not raw YES/NO recall.

Reproduce the raw discrimination numbers below with `scripts/score.py` against
`benchmark/eval_defects.jsonl` (verified reproduction — see this repo's top-level `README.md`
"Verification" note and the session report that built this repo).

**Numbers:**

| Metric | Value |
|---|---|
| Recall, raw | 13.3% (4/30) |
| False-positive rate, raw | 10.0% (3/30) |
| False-positive rate, adjudicated | 6.7% (2/30 — 1 of the 3 raw flags was a genuine, independently-corroborated defect) |
| Balanced accuracy, adjudicated FPR | 53.3% |
| d-prime, adjudicated FPR | 0.39 |
| EXACT localization | 6.7% (2/30) |
| EXACT + REAL_OTHER localization | 13.3% (4/30 — every flagged positive corresponded to a real, verified defect, even when it wasn't the specific paired commit) |
| Gate 1 (mechanism-naming: EXACT >=40% AND adjudicated FPR <=20%) | NOT VIABLE |
| Gate 2 (triage: balanced accuracy >=70% AND adjudicated FPR <=15%) | CLOSED |

**Contamination check, scoped to this baseline only:** every one of the 30 positive commits has a
`fix_date` between 2026-05-15 and 2026-08-26 (confirmed against `benchmark/eval_defects.jsonl`).
**Verified:** this judge's own stated training cutoff (January 2026) predates that entire range —
checked directly, not assumed. **Not verified, and not claimed here:** anything about the local
Ollama models used in the separate `local-llm-consensus.md` baseline — their training cutoffs were
never checked against these dates. Per-record `fix_date` values are available in the schema for a
reader to check against whatever specific model they care about.

**Full detail:** `METHODOLOGY.md`, "Attempt 3 — Single frontier-model judge, scored on
localization not YES/NO" (covers the two re-adjudicated EXACT->REAL_OTHER reclassifications, the
fair discrimination comparison against Attempt 2, and both pre-registered decision gates).
