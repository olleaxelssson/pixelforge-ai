# D-010: Agent runtime & `PlanningBackend` interface

- **Status:** Proposed (Phase 1 design; pending review)
- **Date:** 2026-07-16
- **Deciders:** Agentic architecture review (Claude Code)
- **Related:** D-009 (Scene Graph — the shared artifact); mirrors D-004 (mock backend) and the
  `GenerationBackend` pattern; extends D-005 (registries); consumed by D-011–D-014.

## Context

The vision calls for many single-responsibility agents (Intent → Art Director → Composition →
Palette → Silhouette → Lighting/Material → Animation → QA/Critic) that communicate in structured
JSON — explicitly *"no giant monolithic prompt."* We need a runtime that (a) runs these agents,
(b) is provider-swappable like `GenerationBackend`, (c) stays fully offline-testable per D-004, and
(d) does not drag a heavy framework into the MIT core.

Phase 0 showed Texel Studio uses LangGraph/LangChain effectively but couples to it. We want the
same capability without the coupling — and without repeating that project's per-pixel-LLM
scalability wall (agents here *plan and critique*, they do not paint every pixel).

## Decision

**1. A `PlanningBackend` ABC** analogous to `GenerationBackend`:

```python
class PlanningBackend(ABC):
    name: str
    def is_available(self) -> bool: ...
    def complete_structured(
        self, request: AgentCall, schema: type[ModelT]
    ) -> ModelT: ...          # returns a validated pydantic instance (JSON / tool-calling)
```

Providers register in a `planning_backends/registry.py`:
`AnthropicPlanningBackend`, `OpenAIPlanningBackend`, `OllamaPlanningBackend` (local), and
**`MockPlanningBackend`** (deterministic, seeded — the CI/default choice, no API key). Selected via
settings (`PIXELFORGE_PLANNING_BACKEND`, `PIXELFORGE_` prefix), exactly like the diffusion backend.

**2. Agents are small typed units.** Each `Agent` declares an input schema, an output schema (a
**Scene-Graph patch** or a typed result), and the prompt/tooling to produce it. Agents never emit
free text into the pipeline — only validated pydantic objects. Invalid output triggers **one
bounded self-repair retry** (feed the validation error back); still invalid → typed error surfaced
to the orchestrator.

**3. Orchestration is a lightweight in-house DAG**, not an external framework. Agents declare
dependencies; the `runtime` topologically runs them, passing the evolving `SceneGraph`, validating
each patch, caching by scene-graph hash (D-009), and running independent agents concurrently. This
keeps the core light and MIT-clean. A LangGraph-style checkpoint/resume layer can be added later
*behind the same interface* if durable multi-worker agent threads become a requirement — the
interface does not presuppose it.

**4. A "fast path" toggle** skips planning entirely and uses today's `prompt_builder.py`, so the
current behavior/latency is always available and the agent layer is strictly opt-in.

## Alternatives considered

| Option | Verdict | Why |
|---|---|---|
| **A. LangGraph/LangChain as a core dependency** | Rejected as *required*, allowed as *optional* | Powerful, MIT-licensed (compatible), and proven by Texel Studio — but heavy, opinionated, and couples the core. We keep our interface framework-free; a LangGraph adapter can implement `PlanningBackend`/orchestration later for those who want checkpointing. |
| **B. In-house DAG + `PlanningBackend` (chosen)** | **Chosen** | Light, typed, mock-testable, matches the existing backend/registry idioms; no lock-in. |
| **C. Single monolithic planning prompt** | Rejected | Explicitly disallowed by the brief; poor separability, hard to test, no per-stage control. |
| **D. DSPy / structured-generation libraries** | Deferred | Attractive for prompt optimization; extra dependency; revisit once agents stabilize. |
| **E. Provider SDK hard-coded (e.g. Anthropic only)** | Rejected | Violates provider-swappability and offline-first; kills CI without keys. |

## Cross-cutting analysis

- **Complexity:** Moderate. The runtime (topo-sort + validate + cache + retry) is small and
  testable. Complexity is bounded by keeping agents pure functions of the Scene Graph.
- **Performance & budget:** N LLM calls per generation. Budgets: default planning ≤ **4** agent
  calls; independent agents run concurrently; results cached by scene-graph hash so re-runs and
  edits are cheap. Targets: mock backend adds < **50 ms**; cloud planning p50 target < **6 s** for
  the default agent set; the fast path adds **0**. Planning depth is a setting (off / light / full).
- **Scalability:** Agents are stateless given the Scene Graph → trivially parallel and movable onto
  the existing job queue (D-006) for batch generation. Cost per sprite is bounded by agent count,
  **not** by pixel/op count (the key improvement over Texel Studio).
- **Maintainability:** Registry-driven (D-005). A new agent = one module + a registry entry + I/O
  schemas. Providers are isolated behind `PlanningBackend`; swapping one touches one file.
- **Licensing:** Anthropic SDK (MIT), OpenAI SDK (Apache-2.0/MIT), Ollama client (MIT) — all
  permissive. LangGraph/LangChain (MIT) permitted but optional. No GPL. No new *required* dep beyond
  a provider SDK, which is only imported when that backend is selected.
- **Security/privacy:** Cloud backends send prompts/Scene-Graph text to third parties — off by
  default, opt-in via settings, documented. Local (Ollama) and mock keep everything on-device,
  preserving the local-first stance (D-001).

## Benchmarks & validation plan

- **Determinism:** `MockPlanningBackend` yields identical Scene-Graph patches for identical input +
  seed → golden-file tests for each agent (no keys, runs in CI).
- **Contract tests:** every agent's output validates against its declared schema; malformed-output
  path exercises the one-shot repair and the typed-error fallback.
- **Orchestration tests:** DAG runs in dependency order; independent agents run concurrently; cache
  hit on identical scene-graph hash; cycle detection errors clearly.
- **Equivalence:** fast-path generation reproduces today's output exactly (no regression).
- **Later empirical eval:** a small labeled prompt set scoring plan quality per provider (report,
  don't gate CI).

## Repo mapping

| Piece | Location |
|---|---|
| Backend interface + providers | new `agents/planning_backends/{base,mock,anthropic,openai,ollama}.py` + `registry.py` |
| Agent base + registry | new `agents/base.py`, `agents/registry.py` |
| Orchestrator | new `agents/runtime.py` |
| First agents | `agents/intent.py`, `agents/art_director.py` (more in later milestones) |
| Compile step | `generation/plan_compiler.py` (D-009) reads the finished Scene Graph |
| Settings | extend `config/settings.py` (`PLANNING_BACKEND`, planning depth, budgets) |
| API | new `api/routers/agents.py` (expose plan preview / re-plan) |

## Consequences & open questions

- **Positive:** structured, testable, provider-agnostic planning; no framework lock-in; bounded cost.
- **Negative:** we own the orchestrator (small) instead of reusing LangGraph's checkpointing; if
  durable resumable threads become a hard requirement we add a LangGraph adapter — accepted.
- **Open:** (1) How much tool-use (real function calling) vs. plain structured JSON per agent —
  start with structured JSON, add tools where an agent genuinely needs to inspect intermediate
  pixels (bridges to D-013's critic). (2) Prompt-optimization/versioning of agent prompts — treat
  agent prompts as versioned data (registry), evaluate later.
