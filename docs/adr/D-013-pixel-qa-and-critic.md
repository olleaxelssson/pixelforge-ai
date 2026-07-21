# D-013: Pixel QA engine & AI critic

- **Status:** Accepted — Layer 1 (M9): `qa/` deterministic detectors + safe repairs,
  `HeuristicCritic`, `QAEngine`, opt-in pipeline hook, API + CLI. Layer 2 (M15): the QA-gated
  **repair loop** (`qa/repair_loop.py`) — critique → regenerate only the failing regions, bounded
  and monotonic, via a swappable `RegionRegenerator` (deterministic inpaint + real-backend img2img).
  Semantic critic (M17): `VLMCritic` over a swappable `critic_backends/` (deterministic mock +
  gated real VLM) adds subject-match/appeal judgment to the score and feeds the repair loop.
- **Date:** 2026-07-16
- **Deciders:** Agentic architecture review (Claude Code)
- **Related:** extends `pixelize/cleanup.py`; consumes D-009 (writes findings into the Scene Graph),
  D-010 (critic runs on a `PlanningBackend`/VLM), D-011 (identity drift gate), D-012 (palette
  readability). Loop economics rely on D-002/§4 distilled sampling.

## Context

Today QA is two functions: `remove_orphan_pixels` and `binarize_alpha`. The brief wants automatic
**detection and repair** of banding, pillow shading, jaggies, floating pixels, broken clusters,
poor readability, poor silhouette, palette overflow, noisy dithering, and inconsistent light — plus
a **critic** that scores readability / palette / contrast / silhouette / animation-consistency /
commercial-quality and, below a threshold, **rejects and regenerates only the failing regions.**

## Decision

**Two-layer QA.**

**Layer 1 — deterministic defect detectors** (`qa/detectors/`, pure image ops, no ML, run in CI):
each detector inspects the sprite (and its Scene-Graph context) and returns typed `Finding`s
(kind, bounding region, severity, message) plus an optional deterministic **auto-repair**:

| Detector | Method | Auto-repair |
|---|---|---|
| Palette overflow | unique-color count vs. budget | snap to palette (Stage C) |
| Floating / orphan pixels | connected-component size = 1 | remove (existing op) |
| Broken clusters | components below min size | merge / prune |
| Jaggies | staircase/edge run-length analysis | optional edge smoothing within palette |
| Banding | gradient run-length uniformity | flag (repair is risky → advise) |
| Pillow shading | light appears from all edges (radial gradient heuristic) | flag → re-plan lighting |
| Silhouette readability | alpha coverage, convexity, bg contrast (D-012) | flag |
| Dither noise | isolated-pixel frequency | flag / denoise |
| Light-direction consistency | shading gradient vs. Scene-Graph `lighting` | flag → re-plan |

**Layer 2 — AI critic** (`qa/critic.py`, VLM via `PlanningBackend` + CLIP/SigLIP metrics): scores
each axis in [0, 1] — readability, palette, contrast, silhouette, consistency (incl. identity via
D-011 and cross-frame for animation), and an overall "commercial quality". If any axis is below its
threshold, the critic emits a **region mask** of the failing area.

**Bounded region-repair loop:** the mask is fed back to `plan_compiler` → Stage A regenerates
**only** the masked region (inpainting / img2img with shared seed/context) → Stages B–D → re-QA.
Capped at **K iterations** (default K ≤ 2) to prevent infinite loops; if still failing, surface the
findings to the user rather than looping. Region repair (not full regeneration) is what makes this
affordable, and distilled/consistency sampling (§4) makes each repair cheap.

Both layers are mockable: detectors are deterministic; a `MockCritic` returns fixed scores so the
loop is testable in CI with no VLM.

## Alternatives considered

| Option | Verdict | Why |
|---|---|---|
| **A. Deterministic detectors + VLM/embedding critic + region repair (chosen)** | **Chosen** | Detectors give immediate, testable value with no model; the critic adds judgment; region repair is cheap and targeted. |
| **B. Single end-to-end learned QA model** | Deferred | Needs a labeled dataset and training; deterministic detectors deliver most value now; a learned scorer can augment later. |
| **C. Full-image regeneration on failure** | Rejected | Wasteful and disruptive (changes passing regions); region repair preferred. |
| **D. Flag-only, no auto-repair** | Rejected as sole option | We do both: safe auto-repairs applied, risky ones (banding) advised, always under user control. |

## Cross-cutting analysis

- **Complexity:** Moderate–high, concentrated in the repair loop (mask handling, seed continuity,
  loop control). Detectors themselves are simple and independent.
- **Performance & budget:** Detectors are ms-scale (connected components / histograms on ≤ 256²).
  The critic adds one VLM call + embedding passes; repair adds ≤ K Stage-A region passes. Budget:
  default K ≤ 2; detectors always on; critic optional (settings). Loop must be bounded and
  progress-checked (abort if a repair doesn't improve the failing score).
- **Scalability:** Detectors scale trivially; critic/repair cost is bounded by K per image and
  parallelizable across a batch on the job queue (D-006).
- **Maintainability:** `qa/` with a **detector registry** (add a detector = module + registry entry,
  D-005). Thresholds and K are settings, not magic numbers in code.
- **Licensing:** CLIP (MIT), SigLIP (Apache-2.0), VLM providers permissive — consistent with D-001.
  Detectors are our own code.
- **Security/privacy:** critic (cloud VLM) sends the sprite off-device only when a cloud backend is
  enabled; deterministic detectors and `MockCritic` keep everything local.

## Benchmarks & validation plan

- **Synthetic-defect unit tests:** generate images with a known planted defect (one orphan pixel; a
  15-color sprite against a 8-color budget; a radial "pillow" gradient) and assert the matching
  detector fires with the right region — deterministic, no weights.
- **Auto-repair tests:** repair is idempotent and does not introduce new defects (re-run detectors
  after repair).
- **Loop tests:** with `MockCritic` scripted to fail-then-pass, the loop repairs and terminates
  within K; scripted to always fail, it stops at K and surfaces findings (no infinite loop).
- **Golden set (calibration):** a small labeled set of good/bad sprites to measure detector
  precision/recall and to **calibrate critic thresholds against false rejects** (the named risk from
  Phase 0). Thresholds are chosen from data and documented, not guessed.

## Repo mapping

| Piece | Location |
|---|---|
| Detectors + registry | new `qa/detectors/*.py`, `qa/registry.py` |
| Critic | new `qa/critic.py` (+ `MockCritic`) using `PlanningBackend` (D-010) + embeddings (D-011) |
| Repair loop | new `qa/repair.py`; integrates with `generation/plan_compiler.py` + Stage A region pass |
| Findings storage | `core/scene_graph.py` `qa: list[Finding]` (D-009) |
| Existing ops | reuse/extend `pixelize/cleanup.py` |
| Settings | thresholds, K, critic on/off in `config/settings.py` |
| API | expose QA report per image (jobs/results routers) |

## Consequences & open questions

- **Positive:** turns "commercial quality" into measured, enforced criteria; cheap targeted repair;
  detectors ship value before the critic exists.
- **Negative:** threshold calibration needs a labeled set (small effort, real dependency); repair
  loop must be carefully bounded — designed in.
- **Open:** (1) Which defects are safe to auto-repair vs. advise-only — start conservative (orphans,
  clusters, palette snap auto; banding, jaggies advise). (2) Animation-consistency scoring needs the
  animation milestone's frame set (cross-frame identity via D-011). (3) Whether the critic can also
  *suggest* Scene-Graph edits (e.g., "move light source") — yes, as structured suggestions, closing
  the plan→critique→re-plan loop.
