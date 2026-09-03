# Defect taxonomy — 30 benchmark positives + 5 external PRs + 1 filed issue

Pinned SHA used for all `git show <SHA>:<path>` line lookups below:
`6d145180611956b2065704189517fd6a0ff1a063` (`google/adk-python`, `origin/main`, re-verified via
`git fetch origin && git rev-parse origin/main` in `adk-python-verify/` on 2026-08-30). Line
numbers for historical commits are taken from `git show <parent_sha>:<file> | grep -n <def ...>`
against each record's own `parent_sha` (the commit immediately before the fix landed), not the
current tip, except where explicitly noted as "still present at current tip." Line numbers cited
against *current* `origin/main` in the "Out-of-class" section below are re-verified at
`c506ddf3bc34a6312ffc81899221bfa3f2da3b1d` (2026-09-03).

## Method (revised 2026-09-03)

The original 11-shape version of this document (built 2026-08-30) was a description, not a
taxonomy: 7 of 11 shapes had n≤2, one hypothesis ("hardcoded polarity") matched 0/30, and the
document mixed loud crashes in with the benchmark's actual target class — silent, wrong-but-
plausible verdict degradation — as if they were peer shapes. This revision:

1. Collapses the 7 low-count shapes into 3 mechanism-honest, n≥4 primary shapes (no shape is
   merged into another without a stated shared mechanism — count convenience alone was never a
   sufficient reason).
2. Moves the crash family (loud `Exception`s, the opposite of "wrong but plausible") to a clearly
   separate **out-of-class** section and recomputes in-class coverage without it.
3. Re-examines whether "missing numeric floor" (old Shape 10) actually belongs in the crash family
   by directly testing the runtime mechanism of every candidate "floor-less parameter" raised in
   issue #6951's investigation, rather than assuming the natural-language similarity ("an unbounded
   count reachable at 0") implies a shared *mechanism*.
4. Leaves "hardcoded polarity" exactly where it already was — unconfirmed, prose-only, never
   presented as a counted shape — since that was already correct.
5. Leaves the 6 no-fit positives and the two remaining real-but-underpowered shapes (n=3, n=2)
   honestly flagged rather than padded into the primary taxonomy.

Cross-references to 5 external PRs — [adk-python#6740](https://github.com/google/adk-python/pull/6740),
[#6739](https://github.com/google/adk-python/pull/6739),
[#6710](https://github.com/google/adk-python/pull/6710)→[#6939](https://github.com/google/adk-python/pull/6939),
[#6682](https://github.com/google/adk-python/pull/6682),
[keras#23420](https://github.com/keras-team/keras/pull/23420) — and one filed issue,
[adk-python#6951](https://github.com/google/adk-python/issues/6951), are as recorded by the author.

---

## In-class taxonomy (silent verdict/value degradation) — primary shapes, all n≥4

**In-class coverage: 15/30 (50%).** This is the number that matters for "does this taxonomy
describe the benchmark's actual target class" — not the 63% figure from the first merge pass,
which counted the crash family as a peer in-class shape. It shouldn't have: a crash is loud and
trivially detectable, the opposite of what this benchmark measures.

### Shape A — SILENT_ACCUMULATION_LOSS (merges old Shapes 1, 2, 11)

**n = 6** (`#3`, `#5`, `#18`, `#20`, `#23`, `#27`)

**Definition:** An aggregate that should reflect every input silently ends up incomplete — an item
never enters it (a guard/loop body that only runs when a collection is non-empty; a branch with no
`else` on the accumulating side) or a valid earlier value is lost to a later unconditional
overwrite with no precedence check. All three sub-mechanisms share the same shape at the level that
matters: *something that should have contributed to the final verdict silently didn't, and nothing
in the return value signals that anything is missing.*

**Members and canonical examples (preserved from the pre-merge shapes):**

- **Empty-collection-guard non-execution** (`#3` `69c909000f73e47272fcab508e96f184c5cd81b3`, `#5`
  `efeec703dad61357ad1d79860a4696d4801ce487`) — `src/google/adk/evaluation/agent_evaluator.py`,
  `AgentEvaluator.evaluate_eval_set`, line 124 at parent `308c818867ecefdf68b13eca73a11e5b618b6746`
  (`#5`; `assert not failures` is 191 lines further down). A crashed inference case contributes
  nothing to `failures`, so the loop runs but adds nothing for that case — `assert not failures`
  still passes on an empty list. **Also directly reachable via issue #6951's two triggers** (empty
  `EvalSet`, `num_runs=0`) in the identical function, confirmed still present at
  `6d145180611956b2065704189517fd6a0ff1a063:src/google/adk/evaluation/agent_evaluator.py:289`
  (`assert not failures, failure_message`), and **confirmed fixed on PR #6952's branch (`798d4beb`)**
  by a direct, non-mocked repro through the real public API — see the "Out-of-class" section below
  for why `num_runs=0` itself is NOT a Shape 10 (numeric-floor) member despite surface similarity.

- **Silent drop via unstrict zip / no-else branch** (`#18` `0b7355baa385270cf0be59e601dc7c1e898980c4`,
  `#20` `8ca9128a6397389c171625fb6ac0475c516ccfae`, `#27` `5b16a867d06c222e6eacbddfe03894336d5a0bc5`)
  — `src/google/adk/evaluation/llm_as_judge.py`, `LlmAsJudge.evaluate_invocations`, line 131 at
  parent `b9625bfd709282b96c259f3c8136beb4c79955eb`. `zip(actual_invocations, expected_invocations)`
  with no `strict=True` silently truncates to the shorter list. **Directly matches PR #6710→#6939**
  (`JudgeModelOptions(num_samples=0)`): re-verified at `c506ddf3` (current `origin/main`),
  `llm_as_judge.py:228-231` — `for _ in range(num_samples): tasks.append(...)` with `num_samples=0`
  appends zero tasks for that invocation, so its index never enters `invocation_indices`, so the
  downstream `defaultdict`-keyed aggregation loop never sees that invocation at all. **Verified this
  is a silent drop, not a crash**, by reading the full aggregation loop (`llm_as_judge.py:236-254`):
  the invocation is simply absent from `per_invocation_results`, no exception anywhere.

- **Unconditional overwrite, no precedence check** (`#23` `6bc9c9fb78ae0edeecde02fe24e2879f9a96c676`)
  — `src/google/adk/evaluation/evaluation_generator.py`,
  `EvaluationGenerator.convert_events_to_eval_invocations`, line 626 at parent
  `c08debc93fa540a1c181918da9d19825470d02a3`. `user_content = event.content` runs unconditionally,
  silently overwriting a valid earlier value when the later `event.content` is `None`. **Directly
  matches PR #6682** ("NOT_EVALUATED metric no longer masked by a passing one") — the clean, literal
  instance of this mechanism, at `_generate_final_eval_status`.

**Why wrong-but-plausible:** in every member, the function returns a normally-typed, valid-looking
result. `assert not failures` on `[]` raises nothing; a truncated `zip()` raises nothing; an
overwritten `Optional[Content]` is still a valid field. Nothing in the return value distinguishes
"everything was checked and passed" from "some of it was silently never checked."

**Detector performance:** the frontier judge is the only approach that ever named a correct
mechanism for this shape, and it did so twice, both `#18` and `#20` (`METHODOLOGY.md`'s 6.7%/2-of-30
EXACT-localization figure) — this is the one shape where "detectors always miss this" is directly
contradicted. It also independently discovered the #6951 trigger while judging `#5` (paired to a
different historical mechanism), which is the direct origin of the filed issue. The AST scanner's
`D3` detector was hand-built for the zip/no-else sub-mechanism and still scored 0/3 on held-out data
(naming-regex miss on `#18`, comprehension-blind-spot miss on `#27`, `zip()`-semantics miss on
`#20` — none of these are node shapes `D3`'s AST walk visits).

---

### Shape B — VALUE_NOT_CONSULTED (merges old Shapes 4, 7)

**n = 5** (`#2`, `#6`, `#8`, `#19`, `#29`)

**Definition:** The correct/current value exists somewhere in the system, but the decision-making
code doesn't use it — either because it reads a deprecated/stale field instead of the resolved
current one (two sources exist, the wrong one is consulted), or because a computed/configured value
is never wired to the one call site that would actually apply it (no consumer at all). Both are the
same failure at the level that matters: *the right answer was available and the decision path
didn't reach it.*

**Members and canonical examples:**

- **Stale threshold source** (`#6` `bcce415ee80fa008dee796d8a6f24ebb77d6f6f8`, `#8`
  `83f79123aae4d2473f1fe374a696250cca60de5d`) — `src/google/adk/evaluation/llm_as_judge.py`,
  `LlmAsJudge.evaluate_invocations`, line 131 at parent `b66cba28097e5922786571bc46224030a9c08d57`
  (same file/method as Shape A's zip example, an earlier point in the function's history — a
  recurring hotspot). `self._eval_metric.threshold` is read instead of the resolved
  `criterion.threshold`. **Directly matches PR #6739** ("honor each metric's own eval_status in
  `AgentEvaluator.evaluate()`") and the self-closed/superseded PR **#6678** (same mechanism, one
  level up — `LlmAsJudge.__init__` reading `EvalMetric.threshold` directly).

- **Unwired config / dead setting** (`#2` `b0cdecfc3f846e8124f0a964e64174c12a696a2e`, `#19`
  `79a879f5833a223d3d3f0e78abc2fc6c5da8c1fa`, `#29` `8519602116d2217ed4347aed1e3ca546b81d8948`) —
  `src/google/adk/optimization/local_eval_sampler.py`, `LocalEvalSampler.__init__`, line 150 at
  parent `7c5008f2ba14375e0ae03648cd91b614b84b9592`. `__init__` never calls
  `register_custom_metrics_from_config`, so a configured custom metric is silently never registered.
  **Generalizes to PR #6740** ("`adk eval` process exit code now reflects PASSED/FAILED"): the CLI
  computes a correct pass/fail verdict internally but (pre-#6740) never wired it into the process
  exit code — the value existed, the consumer that should act on it never received it.

**Why wrong-but-plausible:** the object/function returns successfully in every case; nothing in the
public surface indicates a wrong field was read or a call was skipped. A user sees a complete,
successful run that's simply computed against the wrong number, or missing a feature they
configured.

**Detector performance:** neither sub-mechanism is expressible by any D1-D5 AST detector — "reads
field X instead of field Y" requires domain knowledge of which of two similarly-typed fields is
current; "nothing calls this function" requires call-graph reasoning no single-function AST walk
does. The frontier judge saw `#6`'s function twice (paired with two different historical commits)
and both times found a real Shape-A (zip-truncation) bug in it instead of the stale-threshold bug
each record was actually fixed for — a consistent miss on this shape specifically. Local consensus:
majority YES on `#6` with no confirmed correct mechanism named (same caveat as elsewhere).

---

### Shape C — BOUNDARY_STRIPS_ATTACHED_DATA (merges old Shapes 3, 9)

**n = 4** (`#9`, `#11`, `#14`, `#26`)

**Definition:** Data attached beyond a value's base/primary type — subclass-only fields, or a
wrapping container's own configuration — is silently discarded when the value crosses a type or
schema boundary: a missing serialization annotation drops extra fields on round-trip, or an
overly-strict `isinstance`/type-narrowing check accepts only the base type and unwraps/drops the
wrapper. Both lose *attached* data at a boundary, as opposed to Shape A's loss of *collection
membership* during accumulation — a structurally different failure site, which is why this isn't
folded into Shape A despite both being "silent loss."

**Members and canonical examples:**

- **Config field loss via missing schema annotation** (`#14` `623da4930a43cbaa5386a096c5a54266bae02522`,
  `#26` `780b0ab1595c0c74025aea2b4bd8084bc6c1d19a`) — `src/google/adk/evaluation/eval_metrics.py`,
  `EvalMetric` class, line 277 at parent `625ef1aa693ebb1980620be39c02d3ddd5154672`.
  `criterion: Optional[BaseCriterion]` had no `SerializeAsAny`, so a `BaseCriterion` subclass's
  extra fields vanish on serialization.

- **Type-narrowing drops the wrapper** (`#9` `3eae315d367e1679fb712f78312a6170c36ea62b`, `#11`
  `73ecb5b535a7fde3e604eeb1148442f9cc5699c4`) — `src/google/adk/evaluation/agent_evaluator.py`,
  `AgentEvaluator._get_agent_for_eval`, line 513 at parent `eebdf22c07d66b35d41b3307b964c2f37d237a57`.
  The function returns the bare `root_agent`, dropping the wrapping `App` — any code depending on
  `App.plugins`/context-cache/resumability silently runs without them.

**Why wrong-but-plausible:** the round-tripped/returned object is fully valid at its own type —
every caller that only needs the base type works correctly. Only the omitted wrapper-level data is
silently absent, with nothing in the return type signaling a drop occurred.

**Detector performance:** Shape C's first sub-mechanism lives entirely in Pydantic class-body field
declarations, not function bodies — outside all three detectors' target surface (D1-D5 only walk
`FunctionDef`/`AsyncFunctionDef`; the LLM judges were given isolated function bodies with no
class-level context, per `SCHEMA.md` — a benchmark-construction gap, not a reasoning failure). The
second sub-mechanism is a cross-statement return-value data-flow question no AST shape models.
Local consensus: `#11` majority NO (2 of 2 usable raters), `#9` no majority. Neither judge flagged
either instance.

---

## In-class, real but underpowered — not merged, not padded

These two shapes are genuine, single mechanisms found in the data. Neither shares a mechanism with
anything else in the 30, so forcing either into Shape A/B/C above would misrepresent what's
actually there. They stay in-class (neither is a crash) but are reported honestly below the n≥4 bar
rather than folded in for a rounder number.

### Shape D — UNSANITIZED_INPUT_INJECTION

**n = 3** (`#7`, `#22`, `#24`)

**Definition:** A caller-controlled string flows directly into a path/blob-name/template
construction with no sanitization, enabling path traversal, GCS blob-name injection, or (via an
un-sandboxed Jinja2 `Template`) server-side template injection.

**Canonical example:** `src/google/adk/evaluation/gcs_eval_sets_manager.py`,
`GcsEvalSetsManager._get_eval_set_blob_name`, line 66 at parent
`6ed484dc8762efe42cdaf6286c20fbab177ba5e8`. An attacker-controlled `app_name`/`eval_set_id`
containing `../` produces a syntactically valid blob name resolving outside the intended directory
— no error, just I/O against the wrong object.

**Detector performance:** none of D1-D5 model taint-flow to a path/string-construction sink — a
security-injection shape, categorically different from the verdict-degradation problem class. None
of `#7`, `#22`, `#24` were flagged YES by the frontier judge; local consensus also skewed NO on `#7`
(3 of 3 raters) — a genuine miss by all three approaches, not an out-of-scope non-finding.

### Shape E — TEXT_NORMALIZATION_BLIND_SPOT

**n = 2** (`#10`, `#15`)

**Definition:** A text-scoring function silently mishandles a subset of otherwise-valid inputs
(markdown-decorated text, non-Latin scripts) because its normalization/tokenization step was
written and tested against a narrower input distribution than production actually sees, producing a
numerically valid but systematically wrong score for that subset.

**Canonical example:** `src/google/adk/evaluation/final_response_match_v1.py`,
`_calculate_rouge_1_scores`, line 99 at parent `d31b5e7dcec3b1c8da8c35ad9a1d14d046f56cc3`. The
default `rouge_scorer.RougeScorer` tokenizer strips everything outside `[a-z0-9]`, so any non-Latin
candidate/reference pair scores exactly `0.0` — indistinguishable from a genuinely bad response.

**Detector performance:** requires knowing a third-party library's default tokenizer semantics, not
visible in this function's own AST. Neither judge flagged `#15` YES; `#10` had no majority
(llama YES, gemma/qwen NO) — a genuine miss requiring domain knowledge an isolated-function read
doesn't surface.

**Tested and rejected as a merge candidate:** `#4` (missing `open(..., encoding="utf-8")`) from the
no-fit bucket superficially resembles "narrower input assumption than production," but its actual
mechanism (platform-default text encoding) is not a scoring-normalization bug — merging it here
would be the same kind of dishonest padding this revision exists to remove.

---

## Out-of-class: loud failures present in the set

**n = 4** (`#21`, `#25`, `#28`, `#30`). This benchmark's target class is silent verdict degradation
— a wrong-but-plausible result with no error signal. A crash is the opposite failure mode: loud,
and (unlike every shape above) trivially detectable by anyone running the code once. These four
positives are real, recurring bug-fix commits in the same subsystem, but they don't belong in the
in-class coverage number and are reported separately rather than presented as a peer shape.

### UNGUARDED_DEGENERATE_INPUT_CRASH (merges old Shapes 5, 10)

- **Missing null guard** (`#21` `c9bacd40ee4f8ad9951d543b240ce3f2f59ebb42`, `#28`
  `9a6cf60fa8d54523e95943ebdb49d4f35341aed0`, `#30` `eed9bd319ffc398fae14c2362c93f986ffe25f67`) —
  `src/google/adk/evaluation/simulation/per_turn_user_simulator_quality_v1.py`,
  `PerTurnUserSimulatorQualityV1._evaluate_first_turn`, line 294 at parent
  `c03f333769feaeaa9fe8910fbe95cb9f2d513f54`.
  `get_text_from_content(first_invocation.user_content).strip()` raises `TypeError`/
  `AttributeError` when `user_content` has no text. Loud, uncaught.

- **Missing numeric floor** (`#25` `5cfef0173d359ee907bc09099fafdde61098299b`) —
  `src/google/adk/evaluation/final_response_match_v2.py`,
  `FinalResponseMatchV2Evaluator.aggregate_invocation_results`, line 229 at parent
  `a546bcf743ab8ccd10fbbb893e54bb4d27d2c917`. `overall_score = num_valid / num_evaluated` with no
  `num_evaluated == 0` guard raises `ZeroDivisionError`. **Re-verified this crashes, not degrades**:
  the fix (present on current `origin/main` at `final_response_match_v2.py:241-248`) explicitly
  guards `if num_evaluated == 0: return EvaluationResult(overall_score=None, ...NOT_EVALUATED)`
  before the division — confirming the unguarded parent state raised, since pure-Python `/` on an
  `int` zero denominator always raises rather than returning `inf`/`nan`.

**Correction to the previous version of this document:** the keras PR #23420 cross-reference
previously attached to this shape (as the "cleanest, most literal instance" of missing-numeric-floor)
has been **removed** — it does not belong here. Directly verified: `R2Score.result`'s division
(`keras/src/metrics/regression_metrics.py:536`, `raw_scores = 1 - (self.total_mse / total)`) is a
tensor/array op, not a Python-native division. Confirmed via a direct numpy test
(`np.float32(0.0) / np.float32(0.0)` → `nan`, no exception raised) that this class of division
silently returns `NaN` rather than crashing — the PR's own title ("returns NaN instead of 1.0") says
exactly this. **This is a silent wrong-value bug, not a crash**, so filing it under a crash-family
shape was itself a mechanism error in the pre-revision document. It doesn't cleanly join Shape A
either — no collection membership is lost, an arithmetic op just produces a non-crashing garbage
value — so it's reported here, unfiled, as a genuinely distinct third mechanism worth naming in a
future pass rather than being forced into whichever bucket is nearest.

**Also directly tested and confirmed NOT members of this shape, despite surface resemblance to
"floor-less numeric parameter":**

- `num_runs=0` (`AgentEvaluator.evaluate_eval_set`) — **silent vacuous pass**, not a crash. Verified
  by direct, non-mocked repro against `origin/main` (`c506ddf3`): `AgentEvaluator.evaluate_eval_set`
  returns `None` with no exception. Correctly a Shape A member (already so classified), not Shape 10.
- `asyncio.Semaphore(value=0)` (`EvaluateConfig.parallelism` / `InferenceConfig.parallelism`,
  `base_eval_service.py:46,72`, feeding `local_eval_service.py:186,216`) — **hangs indefinitely on
  `.acquire()`, does not raise**. Verified directly: `asyncio.wait_for(sem.acquire(), timeout=2.0)`
  times out. This is a third, distinct failure mode — neither a crash nor a wrong-but-plausible
  silent value — and is not currently a member of any shape in this taxonomy; flagged here rather
  than force-fit.
- Pre-#6939 `num_samples=0` (`JudgeModelOptions`, `llm_as_judge.py:228-231`) — **silently drops the
  invocation from aggregation**, not a crash. Already covered under Shape A above. Note:
  `JudgeModelOptions.parallelism_limit` (`eval_metrics.py:110`), previously flagged as a sibling
  floor-less parameter in issue #6951's investigation, is **no longer floor-less** — re-verified at
  `c506ddf3` that it now carries `ge=1` and rejects `parallelism_limit=0` with a `ValidationError`.

**Net effect of this re-examination:** Shape 10 (`#25`) correctly stays in the out-of-class crash
family — its own benchmark member is a verified crash. What changes is that its previously-attached
external annotation was wrong, and none of the three "does it belong in Shape A instead" test cases
raised by this re-examination actually turned out to be Shape 10 members at all — they were already
correctly classified elsewhere (or, for the semaphore case, correctly left unclassified).

---

## No-fit count

**6 of 30 positives (20%) fit no shape above** — unchanged from the prior version; re-examined for
a possible new shape and none emerged (see below).

| # | commit | function | description | why no fit |
|---|---|---|---|---|
| `#1` | `72a87a2eb9da19f73828c2f1a22272712183ec49` | `AgentEvaluator._print_details` | `from pandas import pandas as pd` typo → `ModuleNotFoundError` | pure import typo, loud crash, no other instance in the 30 shares this mechanism |
| `#4` | `2e878ed4120b1009080ec4bd189cf8b436d03ccf` | `load_json` | `open()` missing `encoding="utf-8"` | platform-default-dependent bug, singleton; tested against Shape E above and rejected as a merge |
| `#12` | `d24c84cdd90d8b2cc78f4162c42d14b53b8f37d6` | `parse_sample_rate` | regex `rate=(\d+)` also matches `bitrate=` | regex over-matching, singleton |
| `#13` | `5d2aca08eb47e78d5915cd27c41db1541d9b18f8` | `MetricEvaluatorRegistry` | `_registry: dict = {}` shared mutable class-level default | classic Python mutable-default gotcha, singleton; tested against `#17` below (both declaration-level gotchas) — the pair would only reach n=2, doesn't clear the bar, not proposed |
| `#16` | `67ab27f2547db48f7248b1689aab4c18502aee17` | `RubricBasedEvaluator.__init__` | premature `assert self._criterion.rubrics` before invocation-level rubrics merged in | ordering/premature-validation bug, singleton |
| `#17` | `b549ab41c906a1746e316788c2bd9366efb1cc0d` | `InvocationEvent` | `content: Optional[Content]` had no `= None` default | narrow schema-declaration bug, singleton |

No coherent new shape emerges: every pairwise combination was checked for a shared mechanism (not
just a shared vocabulary word), and the closest candidate (`#13`/`#17`, both declaration-level
Python/Pydantic default gotchas) still only reaches n=2 — reported, not proposed as a shape.

---

## Hypothesis dispositions (explicit)

| Seed hypothesis | Disposition |
|---|---|
| Missing numeric floor | **Confirmed, out-of-class.** 1/30 (`#25`), a verified crash (`ZeroDivisionError`). The keras #23420 cross-reference previously attached here has been removed — verified it's a silent-NaN mechanism, not a crash, and doesn't belong in this shape. |
| Empty-collection-defaults-to-pass | **Confirmed, broadened, in-class.** Not just "defaults to pass" but "defaults to whatever the unguarded default already was" → Shape A, plus issue #6951 (both triggers now closed by PR #6952, verified by direct repro). |
| Hardcoded polarity | **NOT CONFIRMED.** Zero of 30 positives, zero of the 5 cross-referenced PRs, zero for issue #6951. Unchanged from the prior version — never presented as a counted shape, no revision needed. |
| Silent drop | **Confirmed as-is, in-class.** 3/30 (`#18`, `#20`, `#27`) → Shape A, plus PR #6710/#6939 (verified: `num_samples=0` silently drops the invocation, does not crash). |
| Status-precedence | **Confirmed, in-class, folded into Shape A** (not a standalone shape) — 1/30 (`#23`) plus PR #6682, the clean literal instance. |

## Coverage summary

| Bucket | n | share |
|---|---|---|
| In-class primary (Shapes A, B, C — all n≥4) | 15 | 50% |
| In-class, real but underpowered (Shapes D, E) | 5 | 17% |
| Out-of-class: loud failures (crash family) | 4 | 13% |
| No fit | 6 | 20% |
| **Total** | **30** | **100%** |

**Headline number: in-class coverage is 15/30 (50%)**, not the 63% figure from the first merge
pass — that figure wrongly counted the out-of-class crash family as a fourth peer in-class shape.
