# D-011: Character Memory — identity persistence without drift

- **Status:** Proposed (Phase 1 design; pending review)
- **Date:** 2026-07-16
- **Deciders:** Agentic architecture review (Claude Code)
- **Related:** D-009 (Scene Graph), D-010 (agent runtime), D-013 (QA loop enforces the drift gate);
  extends `projects/store.py`; informed by Phase 0 §4 (IP-Adapter, DreamBooth, LoRA, CLIP/SigLIP).

## Context

The brief's motivating example: generate "Captain Elias", then later "Captain Elias winter armor",
then "Captain Elias without helmet" — with **no identity drift** across face, hair, equipment,
palette, proportions, and silhouette. Today nothing persists between generations except a `seed`,
so this is impossible. Phase 0 identified identity drift as Agent Sprite Forge's core weakness and
recommended solving it *structurally* (memory + Scene Graph) rather than with prompt tricks.

**Approved direction (reviewer):** IP-Adapter-first (inference-time reference conditioning, no
per-character training), with per-character LoRA as a later, optional tier.

## Decision

**1. A persisted `Character` entity** (in the project store, stable id) holding:
- a **canonical Scene-Graph fragment** — the reusable identity slots (face, hair, proportions,
  equipment defaults, silhouette descriptors), reused verbatim on every subsequent generation;
- a **locked palette** (the character's colors, enforced at Stage C);
- a set of **reference frames** — a canonical "passport" view + accepted variants (image paths,
  never committed to git);
- **identity embeddings** (CLIP/SigLIP) computed from the reference frames, for drift measurement;
- a **character bible** — short structured text notes (personality, canon constraints).

**2. Tiered consistency strategy:**
- **Tier 1 — default, no training:** IP-Adapter-style reference-image conditioning at Stage A +
  palette lock (Stage C) + Scene-Graph fragment reuse. "Winter armor" varies only the equipment /
  palette slots; identity slots stay fixed. Cheap, immediate, on-device.
- **Tier 2 — optional, per production:** a per-character LoRA (or DreamBooth) trained via the
  training milestone when a studio needs maximum identity lock across many poses/scenes.

**3. Drift gate (enforced by D-013):** every candidate generation gets an identity embedding;
cosine similarity to the character's canonical embedding must exceed a calibrated threshold. Below
threshold → reject and regenerate (optionally region-repair only the drifted area). This makes "no
identity drift" a *measured, enforced* property, not a hope.

**4. Editing preserves identity:** because equipment/pose/palette are Scene-Graph slots (D-009),
"without helmet" is a graph edit (drop the helmet part) + recompile — not a fresh prompt that could
redraw the face.

## Alternatives considered

| Option | Verdict | Why |
|---|---|---|
| **A. IP-Adapter-first + palette + graph reuse (chosen)** | **Chosen** | Inference-time, no training cost, immediate, on-device; strong enough for most cases; upgradeable. |
| **B. LoRA/DreamBooth-first** | Deferred to Tier 2 | Strongest identity but per-character training cost (minutes–hours, GPU), heavy for casual use; belongs behind the training pipeline. |
| **C. Prompt-only ("same character…")** | Rejected | This is the Agent Sprite Forge failure mode — drifts, unmeasured. |
| **D. Textual inversion** | Optional | Cheaper than DreamBooth, weaker identity; a possible middle tier, not the default. |
| **E. Full fine-tune per character** | Rejected | Absurd cost, no benefit over LoRA at this scale. |

## Cross-cutting analysis

- **Complexity:** Moderate. Storage + embedding compute + threshold calibration. IP-Adapter wiring
  lives in the Stage-A backend; the memory store and drift metric are straightforward.
- **Performance & budget:** IP-Adapter adds modest Stage-A overhead (an image encoder pass +
  cross-attention conditioning); embedding comparison is a dot product (microseconds). Tier-2 LoRA
  cost is offline/one-time per character. Target: Tier-1 adds < ~15% to Stage-A latency.
- **Scalability:** Memory grows with number of characters; embeddings are tiny; reference frames are
  images stored on disk (paths in the project, bytes outside git per existing artifact policy).
  Thousands of characters are fine.
- **Maintainability:** New `memory/` package; the embedding model sits behind an interface
  (swap CLIP ↔ SigLIP without touching callers); persistence reuses `projects/store.py`.
- **Licensing:** IP-Adapter (Apache-2.0), CLIP (MIT), SigLIP (Apache-2.0) — all permissive and
  consistent with D-001/D-008. Tier-2 LoRA weights trained on licensed/owned data (bundled) or
  user data (user's responsibility), per existing model-research posture.
- **Security/privacy:** Character data (including reference images) is user content; stays local
  unless a cloud backend is explicitly enabled. No cross-project leakage — memory is project-scoped
  (open question: optional global character library).

## Benchmarks & validation plan

- **Deterministic tests:** with the mock diffusion + a **mock embedding** provider, the drift gate
  logic (threshold compare, accept/reject) is unit-tested with no weights.
- **Identity metric:** on a small labeled set (same-character vs. different-character pairs),
  measure similarity separation and pick the threshold from the ROC — documented, not hard-coded
  blindly. Guard against false rejects (a named risk).
- **Scenario test:** "Elias → Elias winter armor → Elias without helmet" — assert identity slots are
  byte-identical across the three Scene Graphs and only the intended slots changed.
- **Caveat to validate:** IP-Adapter support/quality **for FLUX** is still maturing; if a
  cleanly-licensed FLUX IP-Adapter is unavailable at build time, fall back to (a) img2img reference
  conditioning with high structure preservation, or (b) the optional SDXL backend's mature
  IP-Adapter — both already contemplated by the pipeline's backend abstraction. This fallback is an
  explicit part of the design, not an afterthought.

## Repo mapping

| Piece | Location |
|---|---|
| Character model + store | new `memory/` package; persistence via `projects/store.py` |
| Identity slots | `core/scene_graph.py` character fragment (D-009) |
| Reference conditioning | Stage-A hook in `generation/backends/` (IP-Adapter / img2img) |
| Embeddings | `memory/embeddings.py` behind an interface (CLIP/SigLIP/mock) |
| Drift gate | consumed by `qa/` (D-013) |
| Palette lock | reuse `palettes/service.py` (Stage C) |
| API | `api/routers/characters.py` (create/list/reference-frame management) |

## Consequences & open questions

- **Positive:** "no identity drift" becomes measurable and enforced; character edits are structural;
  starts cheap (no training) and scales up to LoRA when needed.
- **Negative:** IP-Adapter-for-FLUX maturity risk (mitigated by the documented fallbacks).
- **Open:** (1) Project-scoped vs. a global cross-project character library — start project-scoped.
  (2) When to auto-promote a character to Tier-2 LoRA (manual trigger first). (3) Multi-character
  scenes and per-character palettes in one image — depends on multi-entity Scene Graph (D-009 open
  question).
