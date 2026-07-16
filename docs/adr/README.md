# Architecture Decision Records (ADR)

Full ADRs for the **agentic pixel-art layer** (Phase 1 design). Each ADR expands a one-line entry
in the repo's decision log (`../../DECISIONS.md`) with the depth the project brief requires:
alternatives considered, complexity, performance/budget, scalability, maintainability, licensing
implications, and a validation plan.

`DECISIONS.md` remains the quick index (D-001…D-014); these files are the long form for the
decisions that need it. Short foundational decisions (D-001…D-008) stay inline in `DECISIONS.md`.

## Status legend

- **Proposed** — designed, under review; no implementation yet.
- **Accepted** — approved; implementation may proceed (behind a flag, mock-tested).
- **Superseded** — replaced by a later ADR (linked).

## Index (Phase 1 — agentic layer)

| ADR | Subsystem | Status |
|---|---|---|
| [D-009](D-009-scene-graph.md) | Scene Graph — schema & lifecycle (the central data contract) | Proposed |
| [D-010](D-010-agent-runtime-planning-backend.md) | Agent runtime & `PlanningBackend` interface | Proposed |
| [D-011](D-011-character-memory.md) | Character Memory (identity persistence, no drift) | Proposed |
| [D-012](D-012-palette-intelligence.md) | Palette Intelligence (ranking, contrast, CVD, readability) | Proposed |
| [D-013](D-013-pixel-qa-and-critic.md) | Pixel QA engine & AI critic | Proposed |
| [D-014](D-014-agent-tool-plugin-sdk.md) | Agent / Tool Plugin SDK | Proposed |

Context and the comparative research that motivates these ADRs live in
[`../research/agentic-pixel-art-research.md`](../research/agentic-pixel-art-research.md).

## Template

Each ADR follows this structure:

```
# D-0NN: <title>
- Status / Date / Deciders / Related
## Context
## Decision
## Alternatives considered   (with trade-offs)
## Cross-cutting analysis     (complexity, performance & budget, scalability,
                               maintainability, licensing, security/privacy)
## Benchmarks & validation plan
## Repo mapping               (exactly where it plugs into backend/src/pixelforge)
## Consequences & open questions
```

## Guiding constraints (inherited)

These ADRs must not violate the existing foundation:
- **Additive, never regressive** — the deterministic Stage B–D pipeline (D-002) and CI stay green.
- **Mock-testable** — every new subsystem runs in CI with no GPU, no weights, no API keys (D-004).
- **Registry-driven** — extend by adding entries, not editing consumers (D-005).
- **Permissive licensing** — MIT core (D-008); Apache/MIT-only bundled models/deps (D-001).
- **Typed** — pydantic models, no `Any` across boundaries; frontend types mirror backend schemas.
