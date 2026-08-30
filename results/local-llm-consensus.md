# Result: Multi-model local LLM consensus (Attempt 2)

**What was run:** `scripts/llm_defect_detector.py` (source workspace, not included in this
repo's `scripts/`), sending each of the benchmark's 60 items (30 positives + 30 controls) to
three local Ollama models (Llama 3.1 8B, Gemma 2 9B, Qwen 2.5 7B) blind (function source only,
no metadata), majority vote across the three.

**Numbers:**

| Metric | Value |
|---|---|
| Recall | 53.3% (16/30) |
| False-positive rate, raw | 43.3% (13/30) |
| False-positive rate, adjudicated | 36.7% (11/30 — 2 of the 13 raw flags were genuine, unfixed defects, not false alarms) |
| Balanced accuracy (adjudicated FPR) | 58.3% |
| d-prime (adjudicated FPR) | 0.42 |
| Fleiss' kappa across the 3 raters | -0.128 (worse than chance agreement) |
| EXACT localization | 0% (0/32 individual YES votes named the actual historical defect mechanism) |
| Verdict | NOT VIABLE (degenerate rater; near-chance discrimination) |

**Why the headline recall is misleading:** one of the three models answered "NO" on all 60
items — it contributed zero information, and the other two shared a correlated bias toward YES.
The apparent "3-model consensus" was actually two positively-correlated raters dressed up as
independent confirmation, only visible via the negative Fleiss' kappa.

**Full detail:** `METHODOLOGY.md`, "Attempt 2 — Multi-model local LLM consensus" (covers all
three measurement flaws found: the degenerate rater, the control-set adjudication gap, and why
binary YES/NO scoring can't distinguish a real hit from a lucky guess).
