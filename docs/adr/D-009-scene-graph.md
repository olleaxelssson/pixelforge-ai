# D-009: Scene Graph — schema & lifecycle

- **Status:** Accepted — foundation implemented in M7 (`core/scene_graph.py`,
  `generation/plan_compiler.py`); parts/QA/animation slots and editor lifecycle land in later
  milestones.
- **Date:** 2026-07-16
- **Deciders:** Agentic architecture review (Claude Code)
- **Related:** `docs/research/agentic-pixel-art-research.md`; builds on D-002 (hybrid pipeline),
  D-004 (mock testability), D-005 (data-driven registries); consumed by D-010–D-014.

## Context

Today a `GenerationRequest` is turned into a `DiffusionSpec` by string concatenation in
`generation/prompt_builder.py`, and the sprite is produced. Nothing structured survives: there is
no machine-readable record of *what was drawn* (which parts, materials, colors, light direction,
pose). This is the root cause of three limitations identified in Phase 0:

1. **No edit-without-regeneration** — changing "helmet color" means re-prompting the whole image.
2. **Identity drift** — the weakness we saw in Agent Sprite Forge; each generation is independent.
3. **No target for the planning agents** — the multi-agent layer (D-010) needs a shared artifact
   to read and write; a prompt string is not one.

The Scene Graph is the central data contract for the entire agentic layer. Every other ADR depends
on it, so it must be designed first, be strictly typed, and evolve without breaking consumers.

## Decision

Introduce a **versioned pydantic model `SceneGraph`** (`core/scene_graph.py`) as the single source
of truth for one generation. It is populated by the Intent agent, mutated by planning agents via
**typed patches**, compiled into a `DiffusionSpec` + control maps, annotated by QA, edited by the
UI, and persisted with the project.

Shape (illustrative, not final — full schema lands with implementation):

```
SceneGraph
├─ schema_version: int                      # additive evolution + migrations
├─ id: str                                   # stable, referenced by memory/provenance
├─ entity: Entity                            # kind (character/item/tile/...), subject, intent
├─ parts: list[Part]                         # name, geometry hint, z-order, material_ref,
│                                            #   palette_index_refs, bbox hint
├─ materials: list[Material]                 # metal/cloth/skin/... → shading behavior
├─ palette: PaletteRef | InlinePalette       # id or inline; colors referenced by index
├─ lighting: Lighting                        # direction, intensity, key/fill, single-source flag
├─ pose: Pose | None                         # character pose / orientation
├─ camera: Camera                            # perspective (front/iso/top-down), framing
├─ animation: AnimationState | None          # action, frame index, direction
├─ constraints: Constraints                  # size, max_colors, transparent_bg, no-AA flags
├─ qa: list[Finding]                         # populated by D-013
└─ provenance: Provenance                    # prompts, seeds, model+adapter versions, agent trace
```

**Design commitments**

- **Colors are palette indices, not RGB**, mirroring the palette-indexed canvas that gives Texel
  Studio its artifact-free output. RGB is resolved only at compile time from the referenced palette.
- **Canonical serialization** (sorted keys, normalized floats) so a scene graph hashes
  deterministically — the hash is the cache key for planning results (D-010) and the identity of a
  provenance record.
- **Additive, versioned evolution.** `schema_version` + explicit `migrate_v{n}_to_v{n+1}` functions;
  never repurpose a field. Old project files always load.
- **JSON Schema is exported** from the pydantic model and is the source the frontend mirrors
  (satisfies the CONTRIBUTING rule that FE types mirror BE pydantic — generated, not hand-copied).

**Lifecycle:** `Intent agent seeds → planning agents patch → compiler reads → pipeline generates →
QA annotates → (repair loop) → editor edits → project store persists`. Editing the graph and
recompiling is the "edit without regeneration" path; reusing an entity's graph fragment across
generations is the anti-drift mechanism (D-011).

## Alternatives considered

| Option | Verdict | Why |
|---|---|---|
| **A. Keep the prompt string (status quo)** | Rejected | Lossy; blocks planning, editing, memory. |
| **B. Freeform `dict` / untyped JSON** | Rejected | No validation; violates "no `Any` across boundaries"; agents would emit unvalidated garbage. |
| **C. pydantic `SceneGraph` (chosen)** | **Chosen** | Typed, validated, free JSON-Schema export, matches the codebase's pydantic-everywhere norm, cheap. |
| **D. Protobuf / JSON-Schema-first IDL** | Deferred | Better for polyglot/cross-process contracts, but heavier tooling; pydantic already gives us JSON Schema for the frontend. Revisit if a non-Python consumer appears. |
| **E. ECS / graph database** | Rejected | Over-engineered for single-asset scope; a scene is a small tree, not a world state store. (Reconsider only for the World Asset Generator's multi-entity scenes — see open questions.) |

## Cross-cutting analysis

- **Complexity:** Moderate but concentrated. It is a *central* type touched by many modules, so the
  risk is coupling, not algorithmic difficulty. Mitigation: strict versioning + patch API + a stable
  public surface; consumers depend on the schema, not on each other.
- **Performance & budget:** In-memory pydantic; construction and validation are microseconds.
  Canonical serialization is O(size) and only runs at cache/persist boundaries. No hot-path cost.
- **Scalability:** `parts`/`materials`/`entities` are lists, so multi-part and (later) multi-entity
  scenes and animation-frame sequences fit without schema surgery. Nested scene graphs cover
  tileset/world composition later.
- **Maintainability:** One file, one concept. JSON-Schema export removes hand-sync drift with the
  frontend. Migrations are unit-tested, so evolution is safe.
- **Licensing:** None — our own schema. No dependencies beyond pydantic (already used).
- **Security/privacy:** Provenance may embed user prompts; treat project files as user data (already
  the case). No secrets in the graph.

## Benchmarks & validation plan

- **Round-trip tests:** `SceneGraph → JSON → SceneGraph` is identity for representative graphs.
- **Determinism tests:** canonical serialization stable across processes/runs; hash reproducible.
- **Migration tests:** a v1 fixture loads and upgrades to vN with expected values.
- **Golden scene graphs:** for a handful of prompts (e.g., "red knight", "health potion"), the
  Intent agent on the **mock** planning backend produces a fixed graph checked into tests — proves
  the whole seed step deterministically, no API keys.
- **Compile equivalence:** a scene graph compiled with the "fast path" reproduces today's
  `DiffusionSpec` for the same request (guarantees no regression to current output).

## Repo mapping

| Piece | Location |
|---|---|
| Model + migrations | new `core/scene_graph.py` |
| Compile to `DiffusionSpec` | extend `generation/prompt_builder.py` → `generation/plan_compiler.py` |
| Persistence | `projects/store.py` (embed graph in project JSON) |
| JSON-Schema export | build step → `frontend/src/renderer/api/sceneGraph.schema.json` → generated TS types |
| QA annotations | `qa/` writes `SceneGraph.qa` (D-013) |

## Consequences & open questions

- **Positive:** unlocks D-010–D-014; makes generations auditable and re-derivable; decouples "what
  to draw" from "how it was prompted".
- **Negative:** a central type is a coordination point; schema changes need care. Accepted via
  versioning discipline.
- **Open:** (1) Single-entity vs. multi-entity graphs — start single-entity with a `list[Entity]`
  left open for the World Asset Generator. (2) How much geometry to encode (bbox hints vs. full
  region masks) — start with hints; masks arrive with the silhouette agent (D-010) and QA (D-013).
