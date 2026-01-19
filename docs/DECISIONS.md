# MEKIKI Genius — Decisions (ADR-lite)

## ADR-001 — Product goal: Beyond OCR via Fusion Architecture
**Decision:** Build a multimodal proofing system that integrates text + structure and outputs a fusion score.
**Rationale:** Text-only OCR matching is insufficient; users expect one-click consistency and document-wide inference.

## ADR-002 — SSOT (Single Source of Truth) for all UI rendering
**Decision:** Canvas/Spreadsheet/SyncRate must all be derived from a single MatchResult (UnifiedMatchResult) snapshot.
**Rationale:** Prevent contradictory UI states and regressions where a worse algorithm overwrites better results.

## ADR-003 — Hybrid matching pipeline (structure → text refinement)
**Decision:** Adopt a hybrid pipeline: anchor/structure alignment first, then text refinement; add strategy selection for anchor-sparse cases.
**Rationale:** Pure text or pure structure approaches fail on different edge cases; hybrid improves robustness.

## ADR-004 — Incremental refactor instead of rewrite
**Decision:** Keep the application running while migrating logic out of AdvancedComparisonView into core/engine modules.
**Rationale:** Full rewrite risk is high; incremental refactor reduces downtime and preserves working behavior.

## ADR-005 — UI simplification: Single panel + unified editor
**Decision:** Revert to single-panel UI; “Simulate” launches Unified Inspection Editor; remove duplicate/legacy panels.
**Rationale:** Users want “button makes it better” without internal complexity; duplication caused confusion and crashes.

## ADR-006 — Template Propagation as a first-class workflow
**Decision:** Provide “✨ 類似検出 (Propagate)” as a core interaction; implement text/coordinate propagation and extend with OpenCV visual propagation.
**Rationale:** The core user value is “fix once, apply everywhere”; propagation must be reliable and verifiable.

## ADR-007 — Golden samples required for refactor safety
**Decision:** Maintain a golden sample set and automated checks across refactors.
**Rationale:** Prevent regressions (e.g., sync rate drop due to result overwrites) and enable safe iteration.
