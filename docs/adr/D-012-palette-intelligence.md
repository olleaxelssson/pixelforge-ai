# D-012: Palette Intelligence

- **Status:** Proposed (Phase 1 design; pending review)
- **Date:** 2026-07-16
- **Deciders:** Agentic architecture review (Claude Code)
- **Related:** extends `palettes/service.py`, `palettes/quantize.py`; feeds the Palette Planner
  agent (D-010) and the QA critic (D-013); aligns with D-004 (deterministic, mock-free tests).

## Context

`palettes/` already does extraction (median-cut/octree), quantization, dithering, and import/export.
The brief wants *intelligence* on top: rank colors, detect contrast, simulate color blindness,
check readability, remove duplicates, suggest improvements, and compress palettes. None of this
exists yet, and — importantly — **none of it needs a model**. It is well-understood color math, so
it can be pure, deterministic, and fully unit-tested, which fits the project's testability stance
better than anything else in the agentic layer.

## Decision

Add a **`PaletteAnalysis` service** (`palettes/analysis.py`) of pure functions over a `Palette`:

1. **Ranking** — order colors by usage share, luminance, and hue; expose ramps (shadow→midtone→
   highlight) detected within the palette.
2. **Contrast** — WCAG-style relative-luminance ratios *and* perceptual **ΔE (CIEDE2000 in CIELAB)**
   between colors and against background; flag pairs too close to read.
3. **Color-vision-deficiency (CVD) simulation** — protanopia / deuteranopia / tritanopia via
   established transforms (Machado 2009 / Brettel matrices); re-run contrast under each to catch
   palettes that collapse for color-blind players.
4. **Readability** — foreground/background separation, adjacent-cluster ΔE, silhouette contrast
   (ties into D-013's silhouette check).
5. **Dedup** — merge near-identical colors below a ΔE threshold (idempotent).
6. **Compression** — reduce to a target N with minimal perceptual loss (k-means / median-cut in
   CIELAB, not RGB), preserving ramps.
7. **Suggestions** — actionable, structured: "raise highlight contrast", "add a mid-tone to this
   ramp", "two colors indistinguishable under deuteranopia".

All functions are deterministic and return typed results (pydantic), so they run in CI with no
weights and surface directly in the API and the palette panel.

## Alternatives considered

| Option | Verdict | Why |
|---|---|---|
| **A. Deterministic color-math core (chosen)** | **Chosen** | No model, deterministic, testable, instant; covers every listed requirement. |
| **B. ML aesthetic/harmony scoring** | Deferred | Needs data + a model, non-deterministic; a possible *additional* signal later, never the core. |
| **C. RGB-distance dedup/compression** | Rejected | Perceptually wrong (RGB distance ≠ perceived difference); use CIEDE2000 in CIELAB. |
| **D. Depend on `colour-science` (BSD-3) for color math** | Optional | Permissive and high-quality; acceptable as a dependency for CIEDE2000/CVD precision. Default: implement the small subset in-house with numpy to avoid a dep; adopt the library if precision/coverage warrants. |

## Cross-cutting analysis

- **Complexity:** Low–moderate. Standard, well-documented color science; the only care needed is
  correct color-space conversions (sRGB↔linear↔XYZ↔Lab) and validated CVD matrices.
- **Performance & budget:** Palettes are ≤ 256 colors; every operation is trivial (sub-millisecond).
  Analysis can run live on every palette edit in the UI without a perceptible delay.
- **Scalability:** Constant/small work regardless of image size (operates on the palette, not the
  image), except readability checks that sample the sprite — still cheap at ≤ 256².
- **Maintainability:** Extends the existing palette module; new analyses are additive pure functions
  and can be registry-listed so the UI/API enumerate them (D-005 idiom).
- **Licensing:** In-house math = none. If adopted, `colour-science` is BSD-3 (compatible). Any
  borrowed CVD matrices are from published papers — cite the source; the numeric matrices themselves
  are facts, not copyrightable, but we attribute.
- **Security/privacy:** None — operates on color data only.

## Benchmarks & validation plan

- **Golden tests:** known palettes with known WCAG ratios / ΔE values → assert exact numbers.
- **CVD sanity:** a red/green pair that is high-contrast for typical vision collapses under
  deuteranopia simulation (asserts the transform is wired correctly).
- **Property tests:** dedup is idempotent; compression to N is monotonic in perceptual loss and
  preserves detected ramps; sRGB↔Lab↔sRGB round-trips within tolerance.
- **Cross-check:** a couple of values verified against `colour-science` even if we ship the in-house
  implementation, to catch conversion bugs.

## Repo mapping

| Piece | Location |
|---|---|
| Analysis functions | new `palettes/analysis.py` |
| Service wiring | extend `palettes/service.py` |
| Color-space helpers | `palettes/color_math.py` (sRGB/linear/XYZ/Lab, ΔE, CVD) |
| API | extend the palettes router with analysis endpoints |
| Agent use | Palette Planner (D-010) calls analysis to choose/repair palettes |
| UI | `frontend/.../features/palettes/` surfaces scores, CVD preview, suggestions |

## Consequences & open questions

- **Positive:** high-value, low-risk, fully deterministic — a good early milestone that ships user
  value before the heavier agent/QA work; gives the Palette Planner and critic real signals.
- **Negative:** must get color-space conversions exactly right; mitigated by cross-checks.
- **Open:** (1) Which CVD model (Machado 2009 severity-parameterized vs. Brettel dichromat) — plan
  to ship Machado with a severity slider. (2) Whether to auto-apply suggestions or only advise —
  advise by default, one-click apply, never silently mutate a user's palette.
