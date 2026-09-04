# Methodology: three attempts at automated "verdict silently degrades" defect detection

This document covers a full investigation arc, written for someone who did not run any of it
themselves. The target defect class throughout: a function that computes a status, verdict, score,
or exit code that *looks* valid but silently misrepresents what actually happened (as opposed to
crashing loudly, which is a different, much easier-to-detect failure mode).

Three approaches were tried in sequence against real code in `google/adk-python`'s
`evaluation/` subsystem. All three are now closed avenues for this specific problem, with the
evidence trail below preserved so a future attempt starts from what's already known rather than
repeating it.

## Attempt 1 — AST-based syntactic pattern matching

**What it was:** `scripts/archive/scan_verdict_defects.py`, five hand-built detectors using Python's
`ast` module (not regex) to look for five specific code shapes: an enum-valued function that never
produces every member of its own enum (`D1`), a hardcoded `>=`/`<=` comparison against a
threshold with no polarity/direction variable in scope (`D2`), a loop or comprehension that writes
to a results accumulator only inside a conditional with no else/except placeholder (`D3`), a
success-like default that only gets reassigned conditionally before being returned (`D4`), and a
CLI command that can complete without ever calling `sys.exit` on a failure path (`D5`).

**Training-set result:** 3 of the 4 real bugs the detectors were hand-built from were correctly
re-flagged (75%).

**Why that number means nothing on its own:** measuring recall on the exact examples a detector was
designed to catch measures memorization of those examples, not generalization to new ones. This is
the single most important lesson from this whole investigation, repeated in a different form in
Attempt 2 below: **a detector's performance on its own design examples is not a validation
experiment — it needs a separate, held-out test set collected independently of the detector's
construction.**

**Held-out result:** against 30 real, independently-sourced bug-fix commits to the same subsystem
from the prior 12 months (chosen chronologically, not cherry-picked, authored by people other than
whoever built the detector), the scanner caught **0 of 30 (0%)**. Even restricted to the 3 commits
whose bug mechanism genuinely matched one of the 5 target shapes, it still caught **0 of 3**.

**Three documented near-misses, useful for anyone attempting a v2:**
1. A textbook `D3` (silent-drop) shape was missed because the loop's accumulator variable was named
   `rubric_scores` — outside the naming heuristic, which only matched `result`/`output`-containing
   names. **Lesson: naming heuristics for "this looks like a results collection" need to be much
   broader, or replaced with a data-flow check (does this variable eventually get returned/used as
   the function's output?) instead of pattern-matching its name.**
2. A function whose real defect was "never returns one specific enum member under a numerically
   degenerate input" was missed because that member only appeared in a *comparison* inside the
   function, never in an assignment or return statement — which is what the detector's AST walk was
   watching for. **Lesson: track a variable's possible *values* through the function (a lightweight
   abstract-interpretation pass), not just literal enum-member tokens appearing in specific AST node
   types.**
3. A wrongful exclusion happened inside a **list comprehension**, not a `for`/`while` loop — a
   different AST node shape than what the loop-body detector was watching. **Lesson: comprehensions
   and generator expressions need first-class handling, not just an afterthought case of "loops."**

**Conclusion:** syntactic pattern matching, at least in the form attempted here, cannot reliably
capture this class of *semantic* defect. The bug isn't in any single syntactic shape — it's in
whether a function's actual branch coverage matches its own intended contract, and recognizing that
requires understanding intent, which AST structure alone doesn't encode. The scanner is retired to
`scripts/archive/` with its full source preserved.

## Attempt 2 — Multi-model local LLM consensus

**What it was:** `scripts/llm_defect_detector.py`, sending each of 60 benchmark functions (30 real
bug-fix positives + 30 verified-untouched controls — see `benchmark/eval_defects.jsonl` and
`benchmark/README.md`) to three different local Ollama model families (Llama, Gemma, Qwen), blind
(function source only, no filename/commit/label), and taking a majority vote.

**Raw numbers, as first measured:** consensus recall 53.3% (16/30), consensus false-positive rate
43.3% (13/30).

**Why those numbers were themselves defective — three separate measurement flaws, not one:**

1. **A degenerate rater poisons a majority vote silently.** One of the three models answered "NO"
   on all 60 items with zero exceptions — it contributed no information at all. This didn't show up
   as an obvious failure in the raw recall/FPR numbers; those looked plausible. It only became
   visible by computing **Fleiss' kappa across all three raters, which came out at -0.128** — worse
   than chance agreement. A "3-model consensus" with one inert rater is actually a 2-rater AND
   between two other models, and if those two share a correlated bias (here, both leaned heavily
   toward YES on almost everything — one alone had a 70% false-positive rate by itself), the
   resulting "consensus" looks like agreement but is actually two biased opinions dressed up as
   independent confirmation. **Lesson: always compute inter-rater agreement before trusting a
   consensus number, and treat a rater that never varies its answer as a red flag requiring
   removal or investigation, not as one vote among equals.**

2. **The control set measured the wrong thing.** "No bug fix landed against this function in 12
   months" is not the same claim as "this function has no defects" — it only means nobody happened
   to find and fix one in that window, for any reason (nobody looked, it's rarely exercised, the
   defect is real but nobody hit it yet). Adjudicating the 13 controls that got flagged by hand
   (reading each against the live repository) found that 2 of the 13 were **genuine, real defects**
   that simply hadn't been fixed yet — not false positives at all. Recomputing the false-positive
   rate using only the confirmed genuine false alarms (11, not 13) brought it down from 43.3% to
   36.7% — a real but modest correction, and nowhere near enough to rescue the local-model result on
   its own. **Lesson: an "unfixed" control set will always contain some real defects; a spot-check
   adjudication of anything flagged as a false positive is not optional if you plan to report a
   false-positive rate as if it were ground truth.**

3. **Binary YES/NO scoring on a task that's 50% guessable can't distinguish signal from bias.** A
   detector that says YES to almost everything gets a high recall number "for free," and the
   headline recall (53.3%) looked almost respectable in isolation — until the actual content of the
   "correct" answers was read. **Zero of the 32 individual YES votes on real bugs named the actual
   historical defect mechanism** (0/32 exact localization); most named a plausible-sounding but
   unrelated concern. A YES/NO score cannot tell the difference between "found the real bug" and
   "guessed YES and happened to be scored as a hit." **Lesson: for this kind of task, localization
   quality (did it name the actual mechanism, not just get the binary label right) is the metric
   that matters; treat bare recall/precision as secondary, easily-gamed numbers.**

**Corrected conclusion:** balanced accuracy 55%, d-prime ≈0.25 (near-chance; for reference, d′=0
is pure guessing) — this licenses the narrow claim "these three small local models produced no
usable discriminative signal on this task." It does **not** license "LLM-based detection of this
defect class is closed" — the raters tested were small (7-9B parameter), locally hosted, and one
was fully non-participating; a materially stronger single judge had not yet been tried at the point
this conclusion would otherwise have been drawn.

## Attempt 3 — Single frontier-model judge, scored on localization not YES/NO

**What it was:** the same 60-item benchmark, but judged by a single frontier-capability model
(Claude), genuinely blind — a fresh dispatch with zero access to any of this investigation's prior
context, given only shuffled, anonymized function bodies with no commit/file/label metadata, split
into four independent batches of 15 so no batch's answers could inform another's. Scored primarily
on **localization** (did the stated trigger match the real historical defect's actual mechanism:
EXACT / ADJACENT / WRONG), not on raw YES/NO recall, per the lesson above.

**Results:** of 30 positives, 4 were flagged YES (13.3% raw recall). Confusion matrix over all 60:
TP=4, FN=26, FP=3, TN=27 (raw); FP=2, TN=28 after control adjudication (below).

**A first pass scored localization strictly against "the mechanism the specific historical commit
fixed"** and found 2 EXACT matches (a `zip()`-without-`strict` truncation, and a silently-empty
rubric-score list feeding an average as if it were a complete evaluation), 1 ADJACENT, and 1 WRONG
— **EXACT localization: 2/30 = 6.7%.**

**That strict ground truth turned out to be mis-specified, and re-adjudicating the 2 non-EXACT
positives against the actual code (not just the one commit each was paired with) changed the
count.** Reading both flagged functions at their exact benchmarked parent commit:
- The "ADJACENT" item (`AgentEvaluator.evaluate_eval_set`) — the judge's stated trigger (an empty
  `eval_results_by_eval_id` mapping causing `assert not failures` to pass vacuously) is **verified
  present** in the function's actual source at that parent commit, and remains present, unfixed, on
  the current `origin/main` tip (line 289 of the current file, same `for ... items(): ... assert
  not failures` shape). It shares the exact downstream failure mode as the commit's real fix (a
  crashed inference case emptying one entry vs. an empty eval set emptying the whole mapping) but
  is a genuinely different, independently reproducible trigger.
- The "WRONG" item (`LlmAsJudge.evaluate_invocations`) — the judge's stated trigger (a zero-sample
  invocation silently dropped via a bare `continue`, never entering the results list) is **verified
  present**, verbatim, in the function's actual source at that exact parent commit (`if not
  invocation_result_samples: continue`) — a real defect, just not the "deprecated threshold source"
  bug the paired commit happened to be fixing. This is the same underlying gap already tracked and
  fixed by a separate, already-open PR in this same investigation (not a new finding).

**Reclassifying both as REAL_OTHER (a genuine, verified, different defect in the same function,
with a stated triggering input and wrong output) rather than ADJACENT/WRONG: corrected localization
is EXACT=2, REAL_OTHER=2, SPURIOUS=0 — every single positive this judge flagged YES on corresponded
to a real, verifiable defect (4/4, 100%), even though only half matched the specific commit it was
paired with. Both numbers are reported, not just the more favorable one: strict EXACT is 6.7%
(2/30); EXACT+REAL_OTHER is 13.3% (4/30) — identical to raw recall, because zero flagged positives
were spurious.**

**The central methodological lesson of this whole arc:** ground-truthing "the defect" as "whatever
the paired historical commit happened to fix" conflates two different questions — *did the judge
explain why this specific commit exists* (a narrow, commit-level question) versus *did the judge
correctly discriminate a genuinely buggy function from a clean one* (the actual capability being
measured). A judge that finds a real, different bug in the same function is not wrong about the
function — it's wrong about which bug the benchmark happens to be pointing at. Any future benchmark
for this defect class should score at the function level ("is there a genuine defect here, matching
what was found, yes/no") as the primary metric, with "does it match the specific paired commit" as
a secondary, stricter statistic — not the other way around, and never as the only number reported.

Of 30 controls, 3 were flagged YES (10% raw false-positive rate). Hand-adjudicating those 3 the same
way as Attempt 2's controls: 1 was a genuine defect (independently corroborating, via an entirely
different mechanism — a tie-breaking edge case — a function already known from Attempt 2's own
control adjudication to be defective), and 2 were confirmed false alarms after checking the actual
code semantics (one rested on a Google Cloud Storage API behavior that doesn't actually occur the
way the model assumed; one rested on calling a properly `@abstractmethod`-enforced method in a way
Python's `abc` module already prevents — verified directly against the class declaration).
**Adjudicated false-positive rate: 2/30 = 6.7%.**

**Discrimination, computed both ways and compared fairly against Attempt 2 (this is the number a
prior pass omitted, making the "better discrimination" claim unsupported in either direction):**

| | Recall | FPR | Balanced accuracy | d-prime |
|---|---|---|---|---|
| Local consensus, raw | 53.3% | 43.3% | 55.0% | 0.25 |
| Local consensus, adjudicated FPR | 53.3% | 36.7% | 58.3% | 0.42 |
| Frontier judge, raw | 13.3% | 10.0% | 51.7% | 0.17 |
| Frontier judge, adjudicated FPR | 13.3% | 6.7% | 53.3% | 0.39 |

**Once fairly compared, the frontier judge does not clearly out-discriminate the local-model
consensus** — its d-prime (0.39 adjudicated) is not higher than the local consensus's own adjudicated
d-prime (0.42); both sit in the same "barely above chance" band (for reference, d′=0 is pure
guessing, d′=1 is often treated as a weak-but-real floor in signal detection theory — neither
approach clears it). What changed between the two attempts is not net discrimination but where each
sits on the recall/precision tradeoff: the frontier judge traded most of its recall for a much lower
false-alarm rate. Both are honestly "does not meaningfully discriminate at the whole-population
level," independent of the mechanism-naming question addressed above.

**Contamination check, scoped honestly:** every one of the 30 positive commits has a `fix_date`
between 2026-05-15 and 2026-08-26 (confirmed directly against `benchmark/eval_defects.jsonl`).
**What was actually verified:** this frontier judge's own stated training cutoff (January 2026)
predates that entire range, checked directly — for this specific baseline, the positive set does
postdate the judge's cutoff. **What was not verified:** nothing here establishes anything about the
Attempt 2 local Ollama models (`llama3.1:8b`, `gemma2:9b`, `qwen2.5:7b`) — their actual training-data
cutoffs were never checked against these dates, in this section or anywhere else in this
investigation. A reader evaluating a different model against this benchmark should check that
model's own stated cutoff against each record's individual `fix_date`, rather than assume a
blanket "contamination-free" claim extends to it.

**Decision gate 1 (mechanism-naming), applied as pre-registered:** EXACT localization ≥40% AND
adjudicated FPR ≤20% → VIABLE, otherwise NOT VIABLE.
```
EXACT localization: 6.7% >= 40%  → FALSE
Adjudicated FPR:      6.7% <= 20%  → TRUE
Gate: FALSE AND TRUE → NOT VIABLE
```

**Decision gate 2 (triage — ranking functions for human review, not explaining them), applied
separately:** balanced accuracy ≥70% AND adjudicated FPR ≤15% → TRIAGE_VIABLE, otherwise CLOSED.
```
Balanced accuracy: 53.3% >= 70%  → FALSE
Adjudicated FPR:     6.7% <= 15%  → TRUE
Gate: FALSE AND TRUE → CLOSED
```
Both gates fail, for different and complementary reasons: mechanism-naming fails because EXACT
matches are rare even when the judge is right about something being wrong; triage fails because
recall is far too low (13.3%) for a tool meant to flag most real issues for a human to review, even
though its false-alarm rate when it does flag something is excellent.

**What this attempt licenses concluding:** a single frontier-capability judge, given an isolated
function body and asked directly, is highly precise but very conservative — when it says YES, it
was right about a real defect existing 100% of the time in this sample (n=4, too small to trust as
a stable rate, but directionally clean); when it says NO, it is very often wrong (it missed 26 of
30 real defects). It does not meaningfully out-discriminate a multi-model local consensus in
aggregate signal-detection terms, and it cannot reliably name the *specific* mechanism a real
historical bug fix addressed, even genuinely blind and (for this specific judge's own verified
cutoff, per the contamination check above) contamination-free. What's foreclosed by
this result is the narrow claim "a frontier model, given an isolated function body and asked
directly, reliably identifies or names this defect class's real cause, or catches most instances of
it." What remains untested and open: whether more context (full file/class rather than an isolated
function), a different prompt, or an ensemble of frontier judges would move the recall number,
since the one clean signal here (zero spurious YES votes) suggests the model's precision is
trustworthy even if its coverage isn't.

## Summary for future reference

| Approach | Recall (raw) | Adjudicated FPR | EXACT localization | EXACT+REAL_OTHER | Verdict |
|---|---|---|---|---|---|
| AST scanner, training-set | 75% (3/4) | — | — | — | Invalid measurement (overfit to design set) |
| AST scanner, held-out | 0% (0/30) | — | — | — | NOT VIABLE |
| Local LLM consensus (3 small models) | 53.3%* | 36.7% | 0% (0/32 votes) | not re-scored | NOT VIABLE (kappa -0.128, degenerate rater) |
| Frontier single judge, blind | 13.3% | 6.7% | 6.7% (2/30) | 13.3% (4/30) | NOT VIABLE (both gates — mechanism-naming and triage) |

\* Local-model recall is not comparable to the frontier judge's — it reflects a majority vote
dominated by two positively-correlated, high-false-alarm raters, not genuine discrimination; see
Attempt 2's kappa finding.

Two artifacts remain independently useful regardless of the closed detector question: the benchmark
itself (`benchmark/eval_defects.jsonl`, 30 verified positives + 30 verified controls, reusable
against any future approach — see `benchmark/README.md` for schema and how to run/score a new
detector against it), and the concrete list of real, verified findings this arc turned up in
currently-live code while adjudicating the judges' answers, not from the detectors themselves:
- Two are known-and-already-being-fixed (the `num_samples=0`/`get_eval_status` polarity and
  `aggregate_per_invocation_samples` bucketing gaps from Attempt 2's control adjudication) — one has
  an open PR already; neither is reachable via any real shipped call path, so neither was filed as a
  new issue.
- One is **new, live, and reachable via a real call path, found during Attempt 3's re-adjudication**:
  `AgentEvaluator.evaluate_eval_set` (`src/google/adk/evaluation/agent_evaluator.py`, confirmed
  still present at line 289 of `origin/main` as of this writing) silently reports overall success
  when `eval_results_by_eval_id` is empty for any reason (an eval set with zero eval cases is the
  most direct trigger) — `assert not failures` passes vacuously since the loop that would populate
  `failures` never runs. Not filed or patched; flagged here as a genuine contribution candidate
  pending the pre-flight recency/churn check documented elsewhere in this workspace's `CLAUDE.md`.

## Near-miss: a candidate that was investigated and correctly rejected

Not every function that produces `NaN`/`inf` with no exception is this benchmark's target defect
class. One candidate from adjacent OSS work (`keras-team/keras`, outside this benchmark's own
`google/adk-python` scope, recorded here purely as a methodology artifact) is worth writing down
precisely because it looked like a fit and was investigated to the same evidentiary standard as a
real finding before being rejected — this is what "what does NOT count as silent degradation"
looks like in practice, not just in the abstract.

**Candidate:** `R2Score.result` (`keras/src/metrics/regression_metrics.py:535`, pinned
`origin/master` `15a11018cff3670dd5746800fcce2b31b253b25a`) —
`raw_scores = 1 - (self.total_mse / total)` is a tensor division with no exception path. Verified
directly (not reasoned about) that a `NaN` in `y_pred` (e.g. a diverged model) propagates all the
way to `R2Score.result() == NaN` with no exception, on a **normal-variance** input
(`total = 2.0`, nonzero) — mechanically distinct from `keras-team/keras#23420`'s own target
(the zero-variance `total == 0` case). Re-ran the identical repro against `#23420`'s own PR branch
and confirmed the patch does **not** close this path either — same `NaN` result, no exception,
both before and after.

**Why this was rejected, not filed:** `#23420`'s own diff adds
`test_r2_nan_total_mse_propagates`, asserting `reference_result=float("nan")` for exactly this
input — the PR's author explicitly locked in `NaN`-passthrough as the *intended* behavior for a
`NaN`-contaminated input, not an oversight. And this isn't `R2Score`-specific: every Keras metric
built on IEEE754 tensor ops passes `NaN` through the same way (a `NaN` numerator anywhere in a
computation graph propagates as `NaN`, full stop, across every backend). Filing this as a
`R2Score`-specific "silent degradation" defect would be indistinguishable from filing "floating
point division doesn't raise `ZeroDivisionError`" as a bug — technically true of the mechanism,
but not a defect in this function relative to its own contract or its neighbors' behavior.

**The distinguishing test, stated generally:** this benchmark's target class is a function that
produces a *plausible-looking, wrong* verdict with no signal that anything went wrong — not a
function whose output faithfully reflects genuinely-invalid input via a well-understood, universal
convention (`NaN` in → `NaN` out is IEEE754, not a bug). A `NaN` result is not "plausible" the way
a spuriously-passing exit code or a silently-dropped enum member is — most downstream consumers
either propagate it visibly or crash on the first comparison/format operation that touches it. The
zero-variance `0/0` case `#23420` actually fixes is different in exactly this respect: pre-patch,
it silently returned a **plausible, wrong, finite** score (`NaN` formatted and logged as if it
were a real number, or worse — see `#23420`'s own before-state, which the PR's title names
directly) for a case sklearn's own reference implementation defines a specific finite answer for
(`force_finite=True`, defaulting to `1.0`). That gap between "a defined correct finite answer
exists and this function doesn't produce it" versus "the input was genuinely invalid and `NaN` is
the standard, expected propagation" is the actual line this benchmark's target class sits on.

## Near-miss: Windows MAX_PATH surfacing as a Python `ModuleNotFoundError`

Not every convincing-looking "defect" traced during this project's adjacent verification work
(`adk-tracegauge`, outside this benchmark's own `google/adk-python`-subsystem scope, recorded here
purely as a methodology artifact — same category as the `R2Score` near-miss above) turns out to be
a real code defect anywhere. This one is worth recording precisely because the investigator's own
first-pass conclusion was wrong, corrected only by a second, controlled re-test — a live
demonstration of the exact failure mode this entry documents, not just a description of it.

**What was observed:** installing `google-adk[eval]` (editable, from a pinned
`google/adk-python` checkout, no version overrides) into a fresh venv located under a long path
(`...\AppData\Local\Temp\claude\...\scratchpad\.venv-pinned-adk\...`) and then importing
`adk_tracegauge` (which unconditionally imports `google.adk.evaluation.metric_evaluator_registry`,
which transitively imports the Vertex AI eval facade) failed with:

```
File "...\transports\__init__.py", line 21, in <module>
    from .grpc_asyncio import FeatureOnlineStoreAdminServiceGrpcAsyncIOTransport
ModuleNotFoundError: No module named 'google.cloud.aiplatform_v1.services.feature_online_store_admin_service.transports.grpc_asyncio'
```

**Wrong-but-plausible first attribution:** the `[eval]` extra's own `google-cloud-aiplatform`
version bound (`>=1.148`, no upper bound — see `adk-tracegauge`'s own session notes) resolved to
`2.1.0`, a major version bump from what every OTHER extra referencing the same package caps at
(`<2`). This looked like a completely sufficient explanation — a genuinely newer, larger, more
deeply-nested major version plausibly breaking on import — and installing with an explicit
`google-cloud-aiplatform<2` pin (resolving `1.165.1`) appeared, at the time, to fix it. **That
conclusion was never actually isolated as a controlled experiment** (both the "broken" and
allegedly-"fixed" runs happened at the same long path), and it was wrong: re-tested cleanly in a
later session with the two variables properly separated —

- short install path + `google-cloud-aiplatform==2.1.0` (unpinned) → `import
  google.cloud.aiplatform_v1.services.feature_online_store_admin_service.transports.grpc_asyncio`
  **succeeds**.
- long install path (the original scratchpad location) + the identical unpinned `2.1.0` → the
  identical shape of failure reproduces immediately, this time on a *different* service module
  (`deployment_resource_pool_service`, alphabetically earlier in `aiplatform_v1/__init__.py`'s own
  import order — confirming this is a function of which generated submodule's path happens to
  cross the limit first, not a fixed, version-specific failure point). The failing file's exact
  path length: **261 characters** — one over Windows' legacy `MAX_PATH` (260).

**Root cause, confirmed, not assumed:** `google-cloud-aiplatform`'s generated gRPC client tree
nests deeply enough (`.../services/<long_service_name>/transports/grpc_asyncio.py`) that a
sufficiently long install-path *prefix* — not any property of the package's version or code —
pushes some generated file's absolute path past 260 characters. `CPython`'s import machinery
reports this exact case as `ModuleNotFoundError` for the missing-looking submodule, not as an
`OSError`/`FileNotFoundError` naming the real cause, and not as anything that mentions path length
at all — indistinguishable, from the traceback alone, from a genuinely absent module or a broken
package install. The version-bound inconsistency (the `[eval]` extra's missing `<2` cap) is real
and independently verifiable in `pyproject.toml`, but it is not what caused this failure — the
identical unpinned `2.1.0` imports cleanly at a short path.

**Why this belongs in the near-miss collection:** this is precisely the "wrong-but-plausible error
attribution" shape the collection exists to document — the error message names a specific,
plausible-sounding cause (a missing module) that is not the real cause, and a careful
investigator (in this case, this project's own prior session) was actually misled by it before a
second, controlled test corrected the record. The class of defect this benchmark actually targets
is a function *silently* producing a wrong verdict with no error at all; this is close kin but
distinct — a LOUD error whose *attribution* is wrong, not a silent one.

**Why it is a near-miss, not a benchmark positive:** it is an environment/tooling limitation (a
Windows filesystem API constraint interacting with an install path this investigator chose), not a
code defect in `google/adk-python`, `google-cloud-aiplatform`, or any target repo this benchmark
scopes to. Nothing about the target code's own contract or branch coverage is at fault — the exact
same code imports correctly given a shorter install path. Filing this against either upstream
project would misattribute an environment property as a code defect, the same class of mistake the
entry itself documents at one level up.

## Cross-cutting lesson: an uncontrolled comparison variable, three times

The MAX_PATH near-miss above was not an isolated slip — it is the third documented instance, in
this same project, of the identical failure shape: a comparison or measurement that changed (or
implicitly held fixed) more than the one variable it was actually trying to isolate, produced a
specific, confident, WRONG conclusion, and that conclusion shipped until a second, deliberately
controlled re-run caught it. Written down together because the pattern is more useful as a
repeated shape than as three unconnected anecdotes.

1. **MAX_PATH near-miss (above).** The "fix" — pinning `google-cloud-aiplatform<2` — was concluded
   from two runs that differed in BOTH the package version AND the install-path length at once,
   never isolated as a controlled pair. The wrong conclusion (that the version bound caused the
   failure) shipped into a prior session's own report and was corrected only by a later run that
   held install path fixed while varying version, and vice versa.

2. **Frontier-judge localization grading (Attempt 3 above).** The first pass graded EXACT/ADJACENT/
   WRONG localization strictly against "the mechanism the one paired historical commit happened to
   fix" — a single, narrow reference point, implicitly treated as ground truth and never separately
   checked against the function's own actual, current-state code. Re-adjudicating the two non-EXACT
   positives directly against the real source (see "That strict ground truth turned out to be
   mis-specified..." above) found both were genuine, independently-verified defects — one still
   present, unfixed, on the current `origin/main` tip — that the first pass had scored as the judge
   being *wrong*, purely because they didn't match the one commit paired with that function. The
   reference point that defined "correct" was never itself validated as the right thing to compare
   against; the correction came only from a second, controlled read against the real code, not from
   scrutinizing the first pass's own plausibility (which looked entirely reasonable on its face).

3. **AST scanner train-on-test recall (Attempt 1 above).** The reported 75% (3/4) recall measured
   the detectors against the exact examples they were hand-built from — the "held-out" and
   "training" sets were the same set, an uncontrolled overlap rather than a deliberately separated
   comparison. That number meant nothing until a genuinely independent, chronologically-selected,
   author-disjoint 30-commit set (never touched during detector construction) was run against the
   identical, unmodified detectors — producing 0/30, the number that actually mattered.

**The general lesson, stated once:** in all three cases, the WRONG result was not vague or
obviously implausible — each looked like a clean, confident answer on its own terms, and each
took a second, deliberately controlled re-run (not closer scrutiny of the first result) to catch.
Before trusting any "before vs. after," "with vs. without X," or "measured on Y" comparison in this
project's own future work: name every variable that differs between the two things being compared,
explicitly, before trusting the delta between them. If more than the one variable under test
differs — or the "test" and "training"/reference set are not actually independent — the comparison
has not isolated anything, no matter how clean the resulting story reads.

## Licensing position on the benchmark's contents

`benchmark/eval_defects.jsonl` stores raw, unmodified function-body excerpts extracted directly from
`google/adk-python`, which is licensed Apache License 2.0 (confirmed: every source file in that
repository carries a `Copyright 2026 Google LLC` / `Licensed under the Apache License, Version 2.0`
header). Each benchmark record carries `repo`, `commit_sha`, and `file` provenance fields, so the
origin of any given excerpt is traceable — but **no copyright notice, license text, or NOTICE file
is currently embedded in the benchmark itself**, and the extracted excerpts do not carry the
originating file's own license header (only the function body, not the file, was extracted).

**This is not neutral, and should not be assumed fine by default.** Apache-2.0 §4 conditions
redistribution of the Work (or Derivative Works) on: (a) providing recipients a copy of the License,
(c) retaining all copyright, patent, trademark, and attribution notices from the Source form of the
Work, and (d) if the Work's distribution includes a NOTICE file, reproducing its attribution notices
in any Derivative Works distributed. A private, local research artifact used only within this
workspace is very unlikely to constitute "distribution" in the sense the license means. **If this
benchmark is ever published, shared outside this workspace, or committed to a public repository,
it does not currently satisfy §4 as constructed** — the fix is straightforward: add a top-level
`NOTICE`/`LICENSE-THIRD-PARTY` file citing `google/adk-python`'s copyright and Apache-2.0 license,
and either embed the same short attribution per-record or point to the single top-level notice. This
should happen before any public redistribution, not be assumed already covered by the existing
per-record `commit_sha`/`file` provenance fields, which establish origin but do not themselves
satisfy the license's notice-retention requirement.
