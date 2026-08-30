# Defect taxonomy — 30 benchmark positives + 5 external PRs + 1 filed issue

Pinned SHA used for all `git show <SHA>:<path>` line lookups below:
`6d145180611956b2065704189517fd6a0ff1a063` (`google/adk-python`, `origin/main`, re-verified via
`git fetch origin && git rev-parse origin/main` in `adk-python-verify/` on 2026-08-30). Line
numbers for historical commits are taken from `git show <parent_sha>:<file> | grep -n <def ...>`
against each record's own `parent_sha` (the commit immediately before the fix landed), not the
current tip, except where explicitly noted as "still present at current tip."

## Method

This taxonomy was built by reading every one of the 30 `label: "positive"` records'
`defect_description` field in `benchmark/eval_defects.jsonl` (not by starting from the five
hypotheses and filtering the data to match them), then grouping by underlying mechanism. The five
seed hypotheses from the task were tested against the resulting groups, not assumed. Two were
confirmed as-is, one was **not confirmed at all** (zero matches among the 30, zero matches among
my 5 PRs), one was confirmed but only via a generalization broader than its original wording, and
six additional shapes emerged from the data that none of the five hypotheses anticipated.

Cross-references to 5 external PRs — [adk-python#6740](https://github.com/google/adk-python/pull/6740),
[#6739](https://github.com/google/adk-python/pull/6739),
[#6710](https://github.com/google/adk-python/pull/6710)→[#6939](https://github.com/google/adk-python/pull/6939),
[#6682](https://github.com/google/adk-python/pull/6682),
[keras#23420](https://github.com/keras-team/keras/pull/23420) — and one filed issue,
[adk-python#6951](https://github.com/google/adk-python/issues/6951), are based on their titles/
mechanisms as recorded by the author at the time this taxonomy was built (no `gh`/network access
was used in this task; PR body/diff details beyond what's already summarized here are not
independently re-verified in this document — a reader can check the linked URLs directly).

---

## Shape 1 — EMPTY_COLLECTION_SILENT_DEGRADE

**Definition:** A field or verdict is populated only inside a guard/loop that executes conditional
on a collection being non-empty; if the collection is empty for any reason, the guard body never
runs and the pre-existing default (an already-vacuous-true assertion, an unset string) is what
silently ships, with no explicit handling of the empty case.

**Count:** 2 of 30 (`#3` `69c909000f73e47272fcab508e96f184c5cd81b3`, `#5`
`efeec703dad61357ad1d79860a4696d4801ce487`). Also fits **issue #6951** (filed by me) and is
plausibly related to my PR **#6740** only at the level of "a verdict computed under one condition
silently doesn't happen under another" — but #6740's actual mechanism (below, Shape 7) is a
better fit for #6740 specifically.

**Canonical example:** `src/google/adk/evaluation/agent_evaluator.py`, `AgentEvaluator.evaluate_eval_set`,
line 124 at parent `308c818867ecefdf68b13eca73a11e5b618b6746` (record `#5`; `assert not failures`
line is 191 lines further down in that same function body). The record's real trigger: a crashed
inference case contributes nothing to `failures`, so the loop that would normally populate
`failures` runs but adds nothing for that case — `assert not failures` still passes. **A second,
independently-reachable trigger for the identical vacuous-pass shape in this exact function is
issue #6951** (filed 2026-08-30): an eval set with zero eval cases (or `num_runs=0`) makes
`eval_results_by_eval_id` itself empty, so the for-loop body never executes at all. Confirmed still
present, unfixed, at the pinned SHA:
```
$ git show 6d145180611956b2065704189517fd6a0ff1a063:src/google/adk/evaluation/agent_evaluator.py | grep -n "def evaluate_eval_set\|assert not failures"
129:  async def evaluate_eval_set(
289:    assert not failures, failure_message
```

**Why wrong-but-plausible, not a loud failure:** `assert not failures` on an empty list is valid
Python and raises nothing — the function returns normally, exactly as it would on a real, clean
pass. There is no code-level signal distinguishing "zero cases evaluated" from "every case passed."

**Detector performance — this shape was CAUGHT, not missed, by the frontier judge:** the frontier
judge flagged record `#5` (blinded ID `Q20`) **YES**, but its stated mechanism was the empty-mapping
trigger — i.e., it independently found the *#6951* trigger while judging the *`#5`* record, not
the crashed-inference trigger `#5` was actually fixed for. This is `METHODOLOGY.md`'s "ADJACENT →
REAL_OTHER" reclassification, and it's the direct origin of issue #6951: verified via
`benchmark/frontier_judge_answers.jsonl` line 20 ("mechanism": "failures is only populated inside
the for-loop over eval_results_by_eval_id.items(); if that mapping is empty the loop body never
runs..."). Local LLM consensus also flagged `#5` majority YES (llama3.1:8b YES, gemma2:9b YES,
qwen2.5:7b NO — `benchmark/llm_detector_results.jsonl`), but per `METHODOLOGY.md`'s Attempt 2
finding, 0/32 YES votes overall named the real mechanism, so this YES cannot be credited as a real
catch the way the frontier judge's can. The AST scanner never had a detector shape that could
express "guard only fires when a collection is non-empty" — none of D1-D5 model this pattern, so
it was structurally out of scope, not inaccurate.

---

## Shape 2 — SILENT_DROP

**Definition:** An accumulator (list, running sum, or aggregate result) is written to only along
one branch of a conditional/zip/comprehension with no `else`/placeholder on the other branch, so
items that should count toward the population are excluded with no trace, shrinking the effective
sample the final verdict is computed from.

**Count:** 3 of 30 (`#18` `0b7355baa385270cf0be59e601dc7c1e898980c4` — already tagged
`D3_SILENT_DROP`; `#20` `8ca9128a6397389c171625fb6ac0475c516ccfae`; `#27`
`5b16a867d06c222e6eacbddfe03894336d5a0bc5` — already tagged `D3_SILENT_DROP`). Also fits my PR
**#6710 → #6939** (`JudgeModelOptions(num_samples=0)` silently dropping an invocation) directly —
same file, same function family (`llm_as_judge.py` / `LlmAsJudge.evaluate_invocations`).

**Canonical example:** `src/google/adk/evaluation/llm_as_judge.py`,
`LlmAsJudge.evaluate_invocations`, line 131 at parent `b9625bfd709282b96c259f3c8136beb4c79955eb`
(wait — corrected: this is `#20`'s own parent). Verified:
```
$ git show b9625bfd709282b96c259f3c8136beb4c79955eb:src/google/adk/evaluation/llm_as_judge.py | grep -n "def evaluate_invocations"
131:  async def evaluate_invocations(
```
Mechanism (`#20`): `zip(actual_invocations, expected_invocations)` with no `strict=True` silently
truncates to the shorter list — extra actual turns beyond a shorter expected list never enter
`per_invocation_results` at all.

**Why wrong-but-plausible, not a loud failure:** the truncated `zip()` raises nothing; the returned
`EvaluationResult` looks like a complete evaluation of the whole conversation while silently having
scored only a prefix of it.

**Detector performance — this is the ONE shape the frontier judge got exactly right, twice:** per
`benchmark/frontier_judge_answers.jsonl`, both of the judge's two **EXACT** localizations
(`METHODOLOGY.md`'s 6.7%/2-of-30 figure) are Shape-2 instances: `Q10` (`#20`, zip-truncation,
verdict YES, mechanism text verbatim matches "no validation that len(expected_invocations) ==
len(actual_invocations) before zip()...") and `Q56` (`#18`, verdict YES, mechanism text: "if
rubric: rubric_scores.append(...) inside a loop, no else"). **This directly contradicts a
"detectors always miss this shape" narrative — for the frontier judge, Shape 2 is the only shape
it ever named correctly.** The AST scanner's `D3` detector was hand-built specifically for this
shape and still scored 0/3 held-out (`#18`, `#20`, `#27` all missed) — `#18` was missed because its
accumulator variable is named `rubric_scores`, outside the scanner's `result|output` naming regex;
`#27` was missed because the drop happens inside a list comprehension, a node shape `D3`'s loop-body
walk never inspects; `#20`'s zip-truncation was never a form `D3` could catch at all (no
conditional-write-to-accumulator shape exists here — the "drop" is `zip()`'s own semantics, not a
branch the scanner's AST walk visits). Local LLM consensus flagged both `#18` and `#20` majority
YES (2 of 3 raters), but per Attempt 2's own audit, the *explanations* were unrelated hallucinated
narratives (e.g. gemma2:9b's answer for `#20` invents a "compromised `convert_auto_rater_response_to_score`"
attacker-manipulation story, never mentioning `zip()` at all) — a right binary label for the wrong
reason, which is exactly why `METHODOLOGY.md` treats raw recall as untrustworthy for this class.

---

## Shape 3 — CONFIG_FIELD_LOSS

**Definition:** A Pydantic model is missing a schema-level annotation (`SerializeAsAny`, `extra=
"allow"`) that controls whether subclass-only fields or caller-supplied extra fields survive
(de)serialization; the model still parses/serializes successfully, just silently without the
fields the caller actually cared about.

**Count:** 2 of 30 (`#14` `623da4930a43cbaa5386a096c5a54266bae02522`, `#26`
`780b0ab1595c0c74025aea2b4bd8084bc6c1d19a`). No PR/issue match found among my 5.

**Canonical example:** `src/google/adk/evaluation/eval_metrics.py`, `EvalMetric` class, line 277 at
parent `625ef1aa693ebb1980620be39c02d3ddd5154672`:
```
277:class EvalMetric(EvalBaseModel):
```
`criterion: Optional[BaseCriterion]` had no `SerializeAsAny`, so a subclass of `BaseCriterion` with
extra fields loses those fields the moment the model is serialized (e.g. to JSON for persistence).

**Why wrong-but-plausible:** the round-tripped object is a valid, loadable `EvalMetric` — it just
silently reverts to the base class's field set. Nothing errors; a reader of the persisted JSON has
no signal that fields were ever dropped.

**Detector performance:** this shape lives entirely in Pydantic model *declarations* (a class-body
annotation, not a function body with branches), which is completely outside all three detectors'
target surface — the AST scanner's five detectors only inspect `FunctionDef`/`AsyncFunctionDef`
bodies; a bare `class ... (EvalBaseModel):` field declaration with no method body has no branches
for D1-D5 to walk. The frontier judge and local LLM consensus were both given isolated function
bodies per `benchmark/blinded_for_judging.jsonl`'s schema (per `SCHEMA.md`) — a class-level field
declaration with no logic gives an LLM judge nothing to reason about beyond "does this parse," so
a miss here reflects a benchmark-construction/prompting gap (isolated-function framing losing
class-level context), not a reasoning failure specific to either judge.

---

## Shape 4 — STALE_THRESHOLD_SOURCE

**Definition:** A pass/fail decision reads a deprecated or superseded field (a legacy top-level
`threshold` attribute) instead of the newer, correctly-resolved source of truth (a `criterion`-based
threshold), so the decision silently uses stale/wrong data whenever the two sources have diverged.

**Count:** 2 of 30 (`#6` `bcce415ee80fa008dee796d8a6f24ebb77d6f6f8`, `#8`
`83f79123aae4d2473f1fe374a696250cca60de5d`). This is the same underlying family as my PR **#6739**
("honor each metric's own eval_status in `AgentEvaluator.evaluate()`" — the aggregator recomputed
pass/fail from a stale/generic comparison rather than trusting each metric's own already-resolved
status) and my self-closed/superseded PR **#6678** (`LlmAsJudge.__init__` reading
`EvalMetric.threshold` instead of resolving via `criterion` — closed because record `#6`'s own fix
commit, `bcce415e`, independently landed the identical behavior first).

**Canonical example:** `src/google/adk/evaluation/llm_as_judge.py`,
`LlmAsJudge.evaluate_invocations`, line 131 at parent `b66cba28097e5922786571bc46224030a9c08d57`:
```
131:  async def evaluate_invocations(
```
(Note: this is the *same file and method name* as Shape 2's canonical example, at an *earlier*
commit in the function's history — the function accreted both defects at different points in
time, which is itself a small data point that this file/function pair is a recurring hotspot.)

**Why wrong-but-plausible:** `self._eval_metric.threshold` is a real, typed, non-crashing field —
just the wrong one once `criterion.threshold` is the field callers actually set. The eval status
computed against it looks like a normal, valid PASS/FAIL, only computed against a number that may
be `None` or stale.

**Detector performance:** no D1-D5 detector expresses "reads field X instead of field Y" — this
requires knowing which of two similarly-typed fields is the semantically current one, which is a
naming/domain-knowledge judgment no AST shape encodes. The frontier judge was given record `#6`
directly (blinded `Q47`) and answered **YES**, but named a *different, also-real* mechanism (the
zero-sample-invocation `continue` drop — Shape 2 — verified verbatim present in that same function)
rather than the stale-threshold bug `#6` was actually fixing; reclassified REAL_OTHER, not EXACT,
per the same audit as Shape 1's `Q20`. So the judge saw this exact defective function twice
(paired with two different historical commits, `#6` here and `#20` in Shape 2) and both times
found a real Shape-2 bug in it rather than the record's own paired mechanism — a consistent miss on
Shape 4 specifically, not a fluke. Local LLM consensus: `#6` majority YES (llama, gemma YES; qwen
NO) but, per the same 0/32-exact-localization finding, with no confirmed correct mechanism named.

---

## Shape 5 — MISSING_NULL_GUARD_CRASH

**Definition:** A function calls a method or built-in (`.strip()`, `len(...)`) on a value that can
be `None` along a real path, with no guard beforehand, raising `TypeError`/`AttributeError`/
`ValidationError` instead of handling the `None` case explicitly.

**Count:** 3 of 30 (`#21` `c9bacd40ee4f8ad9951d543b240ce3f2f59ebb42`, `#28`
`9a6cf60fa8d54523e95943ebdb49d4f35341aed0`, `#30` `eed9bd319ffc398fae14c2362c93f986ffe25f67`). No
PR/issue match among my 5.

**Canonical example:** `src/google/adk/evaluation/simulation/per_turn_user_simulator_quality_v1.py`,
`PerTurnUserSimulatorQualityV1._evaluate_first_turn`, line 294 at parent
`c03f333769feaeaa9fe8910fbe95cb9f2d513f54`:
```
294:  def _evaluate_first_turn(
```
`get_text_from_content(first_invocation.user_content).strip()` crashes when `user_content` has no
text.

**Why this shape does *not* fit the "wrong-but-plausible" theme — flagged explicitly rather than
forced:** all three instances are **loud failures** (an uncaught exception), the opposite of the
silent-verdict-degradation pattern this whole benchmark was built around. I'm reporting it as a
real, recurring mechanism in the data (10% of the 30) because the task asks for shapes actually
present, but it does not answer "why does it produce a wrong-but-plausible output" — it doesn't;
it crashes, which is the easier-to-detect failure mode `METHODOLOGY.md`'s introduction explicitly
distinguishes from the target class.

**Detector performance:** not meaningfully applicable — none of the three detection approaches
were built to find latent-crash bugs (the AST scanner's D1-D5 are verdict-shape detectors; the LLM
judges were prompted specifically for "wrong but plausible," per `SCHEMA.md`, so a crash-only bug
is arguably out of scope for what they were asked to find, not a capability gap).

---

## Shape 6 — UNSANITIZED_INPUT_INJECTION

**Definition:** A caller-controlled string (an ID, a persona field) flows directly into a
path/blob-name/template construction with no sanitization, enabling path traversal, GCS blob-name
injection, or (via an un-sandboxed Jinja2 `Template`) server-side template injection.

**Count:** 3 of 30 (`#7` `a56f6e13ae38296b608808c7a3b37efe4b8c862e`, `#22`
`7b87f910cd69b22d8a7d6ea2a0ec5fcd403fb000`, `#24` `30493bae56f62dddb8adde249e9cd0654882bd05`). No
PR/issue match among my 5 (my own PRs are all in the evaluation-verdict space, not this
path/template-injection space).

**Canonical example:** `src/google/adk/evaluation/gcs_eval_sets_manager.py`,
`GcsEvalSetsManager._get_eval_set_blob_name`, line 66 at parent
`6ed484dc8762efe42cdaf6286c20fbab177ba5e8`:
```
66:  def _get_eval_set_blob_name(self, app_name: str, eval_set_id: str) -> str:
```

**Why wrong-but-plausible:** an attacker-controlled `app_name`/`eval_set_id` containing `../`
produces a syntactically valid blob name/path that resolves outside the intended directory — no
error, just a read/write against the wrong object, which looks like normal successful I/O.

**Detector performance:** none of D1-D5 model taint-flow from an untrusted parameter to a path/
string-construction sink — this is a security-injection shape, a different problem class from
verdict-degradation, and the AST scanner was never designed for it. The frontier judge and local
consensus, given isolated function bodies with no caller context, could plausibly reason about this
(it doesn't require multi-function context the way Shape 3 does) but per the raw verdict data none
of `#7`, `#22`, `#24` were flagged YES by the frontier judge (not in the YES list checked above),
and local consensus also skewed NO on `#7` (all three raters NO) — a genuine miss by all three, not
an out-of-scope non-finding the way Shape 3 is.

---

## Shape 7 — UNWIRED_CONFIG (dead setting / uncalled hook)

**Definition:** A parameter, config flag, or setup call exists in the code and is threaded through
signatures correctly, but the one call site that would actually make it take effect is never
invoked (or a field is populated using a general-purpose formatter that never receives it),
so a documented/plausible-looking piece of behavior silently has no effect.

**Count:** 3 of 30 (`#2` `b0cdecfc3f846e8124f0a964e64174c12a696a2e`, `#19`
`79a879f5833a223d3d3f0e78abc2fc6c5da8c1fa`, `#29` `8519602116d2217ed4347aed1e3ca546b81d8948`).
Generalizes to fit my PR **#6740** ("`adk eval` process exit code now reflects PASSED/FAILED"): the
CLI computed a correct pass/fail verdict internally but never wired that computed value into the
actual process exit code — the identical "the value exists, the consumer that should act on it
never receives it" shape, just at the level of a CLI exit code rather than a metric/prompt field.

**Canonical example:** `src/google/adk/optimization/local_eval_sampler.py`,
`LocalEvalSampler.__init__`, line 150 at parent `7c5008f2ba14375e0ae03648cd91b614b84b9592`:
```
150:  def __init__(
```
`__init__` never calls `register_custom_metrics_from_config`, so any custom metric defined in
config is silently never registered — no error, the sampler just runs with fewer metrics than
configured.

**Why wrong-but-plausible:** the object constructs successfully; nothing in its public surface
indicates a registration step was skipped. A user who configured a custom metric sees the sampler
run to completion and gets a result set that's simply missing scores for the metric they thought
they'd added.

**Detector performance:** "a function that should be called somewhere but isn't" requires
cross-function call-graph reasoning (does *anything* call `register_custom_metrics_from_config`
reachably from `__init__`?) — none of D1-D5 do inter-procedural analysis; all five are single-
function AST walks. Neither LLM judge was given more than one isolated function body at a time
(per `SCHEMA.md`), which makes this shape close to undetectable by construction for both of them —
you cannot notice a missing call to a sibling function you were never shown. This is a benchmark-
design limitation as much as a detector weakness.

---

## Shape 8 — TEXT_NORMALIZATION_BLIND_SPOT

**Definition:** A text-processing/scoring function silently mishandles a subset of otherwise-valid
inputs (markdown-decorated text, non-Latin scripts) because its normalization/tokenization step
was written and tested against a narrower input distribution than what actually reaches it in
production, producing a numerically valid but systematically wrong score for that subset.

**Count:** 2 of 30 (`#10` `bf8388aaed968c11552977799899b242df1fdab2`, `#15`
`8200faec6d42c10e5c3cf5f9613bcb6bd5d51240`). No PR/issue match among my 5.

**Canonical example:** `src/google/adk/evaluation/final_response_match_v1.py`,
`_calculate_rouge_1_scores`, line 99 at parent `d31b5e7dcec3b1c8da8c35ad9a1d14d046f56cc3`:
```
99:def _calculate_rouge_1_scores(candidate: str, reference: str):
```
The default `rouge_scorer.RougeScorer` tokenizer strips everything outside `[a-z0-9]` before
scoring, so any candidate/reference pair in a non-Latin script tokenizes to an empty string on both
sides and scores exactly `0.0` — indistinguishable, at the number level, from a genuinely bad
response.

**Why wrong-but-plausible:** `0.0` is a completely valid ROUGE score. There's no sentinel, no
exception, nothing that flags "this input wasn't actually scorable" — it looks identical to "this
response was terrible."

**Detector performance:** requires knowing the *semantics* of an external library's default
tokenizer (`rouge_scorer.RougeScorer([...], use_stemmer=True)`), not anything visible in this
function's own AST — no D1-D5 detector inspects third-party call arguments for locale/charset
assumptions. Neither LLM judge flagged `#15` YES (not in the YES-verdict list above) nor `#10` YES
in the majority vote (llama YES, gemma/qwen NO on `#10` — no majority) — a genuine miss requiring
domain knowledge about a specific library's tokenizer defaults that an isolated-function read
doesn't surface.

---

## Shape 9 — TYPE_NARROWING_DROPS_WRAPPER

**Definition:** An `isinstance`/type-narrowing check written for one concrete type (or one
`hasattr` check) is stricter than the actual set of valid runtime types, so a legitimately valid
wrapping object (an `App` around an agent) or a legitimately valid root-agent subtype is rejected
or silently unwrapped/discarded even though it was a correct input.

**Count:** 2 of 30 (`#9` `3eae315d367e1679fb712f78312a6170c36ea62b`, `#11`
`73ecb5b535a7fde3e604eeb1148442f9cc5699c4`). No PR/issue match among my 5 (though it's in the same
`agent_evaluator.py`/`evaluation_generator.py` file pair as several of my PRs).

**Canonical example:** `src/google/adk/evaluation/agent_evaluator.py`,
`AgentEvaluator._get_agent_for_eval`, line 513 at parent
`eebdf22c07d66b35d41b3307b964c2f37d237a57`:
```
513:  async def _get_agent_for_eval(
```
The function returns the bare `root_agent`, dropping the wrapping `App` object entirely — so any
downstream code path that depends on `App.plugins`, context-cache, or resumability config silently
runs without them, using only the raw agent.

**Why wrong-but-plausible:** the returned object is a fully valid `BaseAgent` — every call that
only needs the agent itself works correctly. Only the omitted `App`-level configuration is silently
absent, and nothing in the return type signals that anything was dropped.

**Detector performance:** this is a data-flow/return-value question (what got dropped between the
wrapper being constructed and the value actually returned), not a syntactic pattern any of D1-D5
model. Local LLM consensus: `#11` majority NO (llama, qwen NO — 2 of 2 sampled; gemma2:9b's row is
missing/failed for this item per the raw log, so only 2 raters' worth of signal exists here) — a
miss. `#9` majority NO as well (llama YES but gemma/qwen NO — no majority). Neither judge flagged
either instance.

---

## Shape 10 — MISSING_NUMERIC_FLOOR (unguarded zero/degenerate denominator)

**Definition:** An aggregate computation divides by a count/variance/denominator that is
reachable at exactly zero (or another degenerate value) along a real input path, with no
special-cased floor/guard for that case — unlike Shape 1 (which silently *passes*), this shape
crashes loudly (`ZeroDivisionError`) rather than silently mis-scoring, because the missing guard
is arithmetic, not a bypassed control-flow branch.

**Count:** 1 of 30 (`#25` `5cfef0173d359ee907bc09099fafdde61098299b`, already tagged
`D1_ENUM_UNDER_COVERAGE` by the AST scanner's own categorization — reclassified here on mechanism
grounds, see below). **Confirmed match to keras PR #23420** (`R2Score.result` returning `NaN`
instead of `1.0` for a perfect prediction on zero-variance data) — this is the cleanest, most
literal instance of the "missing numeric floor" hypothesis across everything reviewed in this task,
better fitting the hypothesis's own wording ("an unbounded count/limit parameter reachable at 0")
than the benchmark's own single example does.

**Canonical example:** `src/google/adk/evaluation/final_response_match_v2.py`,
`FinalResponseMatchV2Evaluator.aggregate_invocation_results`, line 229 at parent
`a546bcf743ab8ccd10fbbb893e54bb4d27d2c917`:
```
229:  def aggregate_invocation_results(
```
`overall_score = num_valid / num_evaluated` with no check for `num_evaluated == 0`; the fix returns
`NOT_EVALUATED` instead of dividing.

**Why this shape sits between the two others:** unlike Shapes 1/2/3/7 (which produce a plausible
wrong *value*), this one crashes — same category concern as Shape 5. I kept it as its own shape
rather than merging into Shape 5 because the *cause* is categorically different (missing floor on
an arithmetic aggregate vs. missing null-check before a method call) and because it's the direct
match for the task's named hypothesis, which explicitly frames it as a distinct concern worth
tracking on its own even where it manifests as a crash rather than a silent pass.

**Detector performance — AST scanner near-miss, documented in `METHODOLOGY.md`:** the scanner's
`D1` (`ENUM_UNDER_COVERAGE`) detector was designed to catch exactly this shape (a function that
never produces one specific enum member, here `NOT_EVALUATED`, under a reachable input) but missed
it because `NOT_EVALUATED` appears in this function only via *comparison* elsewhere in the file,
never as a literal assigned/returned value inside `aggregate_invocation_results` itself — the
detector's AST walk only tracked assignment/return-statement tokens, not values reachable through
comparisons. Neither LLM judge flagged `#25` YES (not in the frontier judge's 7-item YES list) —
local consensus did flag it majority YES (llama, gemma YES; qwen NO), but per the same
no-mechanism-named caveat as other local-consensus YES votes.

---

## Shape 11 — STATUS_PRECEDENCE / UNCONDITIONAL_OVERWRITE

**Definition:** A later, unconditional write into an aggregation variable overwrites an earlier,
valid (and sometimes more informative) value with no precedence check, so the final result depends
on iteration/event order rather than on which value should actually win.

**Count:** 1 of 30 (`#23` `6bc9c9fb78ae0edeecde02fe24e2879f9a96c676`) — **noted as a generalized,
weaker fit**: `#23`'s overwritten value is a `Content` object (`user_content`), not an enum status,
so it instantiates the *mechanism* (unconditional overwrite loses a valid prior value) without
instantiating the *status*-specific framing the hypothesis names. **My PR #6682** ("NOT_EVALUATED
metric no longer masked by a passing one" in `_generate_final_eval_status`) is the clean, literal
match for the hypothesis as stated — an aggregation loop where a `PASSED` status processed after a
`NOT_EVALUATED` one could overwrite it, masking the fact that a metric was never evaluated. I am
keeping the benchmark match and the PR match as one shape rather than splitting them, because the
underlying code-level cause (an unconditional write inside a loop that should instead check
"is the new value more informative than what's already there before overwriting") is identical in
both — only the payload type (content vs. enum) differs.

**Canonical example (benchmark):** `src/google/adk/evaluation/evaluation_generator.py`,
`EvaluationGenerator.convert_events_to_eval_invocations`, line 626 at parent
`c08debc93fa540a1c181918da9d19825470d02a3`:
```
626:  def convert_events_to_eval_invocations(
```
`user_content = event.content` runs unconditionally inside the `if current_author == _USER_AUTHOR:`
branch even when `event.content` is `None`, silently overwriting a valid `user_content` value set
by an earlier user-authored event in the same invocation.

**Why wrong-but-plausible:** the resulting `Invocation` is a fully valid object; `user_content`
being `None` (or stale) doesn't crash anything downstream that tolerates `Optional[Content]` — it
just silently loses information a human would expect to see.

**Detector performance:** no D1-D5 detector models "does this write check whether the new value is
more/less informative than the old one before overwriting" — that requires knowing an ordering
relation between values (which status precedes which), not just detecting a write. Both LLM judges
were given `#23` in isolation; local consensus flagged it majority YES (llama, gemma YES; qwen NO),
but again with the same no-verified-mechanism caveat noted throughout — I did not independently
re-verify whether either rater's YES *explanation* named the actual overwrite bug versus a
different, hallucinated concern, and flag that gap explicitly here rather than assume it matches
the pattern seen on other items.

---

## Hypothesis dispositions (explicit)

| Seed hypothesis | Disposition |
|---|---|
| Missing numeric floor | **Confirmed**, 1/30 (`#25`), plus a strong external match (keras #23420) → Shape 10 |
| Empty-collection-defaults-to-pass | **Confirmed, broadened**: not just "defaults to pass" but "defaults to whatever the unguarded default already was" (a blank string, a vacuous assert) → Shape 1, 2/30, plus issue #6951 |
| Hardcoded polarity | **NOT CONFIRMED.** Zero of 30 positives, zero of the 5 cross-referenced PRs, and the one filed issue (#6951) do not match this mechanism either. The one candidate ever investigated for it (`llm_as_judge_utils.py`'s hardcoded `>=`) was ruled a `FEATURE_GAP` in an earlier, unpublished stage of this investigation — unreachable, since no shipped ADK object can currently declare lower-is-better polarity — not a live defect, and was never filed. Dropped from the taxonomy; the benchmark's actual "threshold-related" defects are Shape 4 (stale field source), a different mechanism entirely. |
| Silent drop | **Confirmed as-is**, 3/30 (`#18`, `#20`, `#27`) → Shape 2, plus my PR #6710/#6939 |
| Status-precedence | **Confirmed but weak within the benchmark itself** (1/30, `#23`, and only via generalizing "status" to "any aggregated value"); strongly confirmed by my own PR #6682, which is the clean literal instance → Shape 11 |

Seven additional shapes emerged from the data that none of the five seed hypotheses anticipated:
Shape 3 (config field loss), Shape 4 (stale threshold source), Shape 5 (missing null guard crash —
explicitly not a "silent" shape), Shape 6 (unsanitized input injection), Shape 7 (unwired
config/dead setting), Shape 8 (text normalization blind spot), Shape 9 (type narrowing drops
wrapper) — **11 shapes total** (Shapes 1-11 above), covering the 4 confirmed/adapted hypotheses
(numeric floor, empty-collection, silent drop, status-precedence) plus these 7 data-driven
additions, with "hardcoded polarity" dropped as unconfirmed.

## No-fit count

**6 of 30 positives (20%) fit no shape above:**

| # | commit | function | description | why no fit |
|---|---|---|---|---|
| `#1` | `72a87a2eb9da19f73828c2f1a22272712183ec49` | `AgentEvaluator._print_details` | `from pandas import pandas as pd` typo → `ModuleNotFoundError` | pure import typo, loud crash, no other instance in the 30 shares this mechanism |
| `#4` | `2e878ed4120b1009080ec4bd189cf8b436d03ccf` | `load_json` | `open()` missing `encoding="utf-8"` | platform-default-dependent bug, singleton |
| `#12` | `d24c84cdd90d8b2cc78f4162c42d14b53b8f37d6` | `parse_sample_rate` | regex `rate=(\d+)` also matches `bitrate=` | regex over-matching, singleton |
| `#13` | `5d2aca08eb47e78d5915cd27c41db1541d9b18f8` | `MetricEvaluatorRegistry` | `_registry: dict = {}` shared mutable class-level default | classic Python mutable-default gotcha, singleton |
| `#16` | `67ab27f2547db48f7248b1689aab4c18502aee17` | `RubricBasedEvaluator.__init__` | premature `assert self._criterion.rubrics` before invocation-level rubrics merged in | ordering/premature-validation bug, singleton |
| `#17` | `b549ab41c906a1746e316788c2bd9366efb1cc0d` | `InvocationEvent` | `content: Optional[Content]` had no `= None` default | narrow schema-declaration bug, singleton |

**20% is under the "more than a third" threshold the task flags as a hard weak-taxonomy signal,
so I am not declaring this taxonomy invalid — but I am not overstating it as comprehensive either.**
Two honest caveats: (1) two of the eleven confirmed shapes (Shape 10, Shape 11) have exactly **one**
benchmark member each, and only become "shapes" rather than one-off oddities because of the
cross-reference to my own PRs outside the 30-item sample — within the benchmark alone, they'd be
indistinguishable from the six no-fit singletons above; (2) `METHODOLOGY.md`'s own account of how
these 30 were selected ("chosen chronologically... not cherry-picked... only 3 of 30 had a bug
mechanism that conceptually matches one of the [AST scanner's] 5 detector shapes at all") already
tells you most of these 30 were never going to cluster into a tight verdict-degradation taxonomy —
they're a representative sample of *all* bug-fix commits to this subsystem in the window, not a
sample pre-filtered for the "wrong-but-plausible" theme this whole investigation cares about. This
taxonomy is real structure in real data, not a comprehensive account of every defect family in
`google/adk-python`'s evaluation subsystem.
