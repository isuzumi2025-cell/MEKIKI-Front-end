# MEKIKI Genius - Decisions (ADR-lite)

## ADR-001 - Product goal: Beyond OCR via Fusion Architecture
**Decision:** Build a multimodal proofing system that integrates text + structure and outputs a fusion score.  
**Rationale:** Text-only OCR matching is insufficient; users expect one-click consistency and document-wide inference.

## ADR-002 - SSOT (Single Source of Truth) for all UI rendering
**Decision:** Canvas/Spreadsheet/SyncRate must all be derived from a single MatchResult (`UnifiedMatchResult`) snapshot.  
**Rationale:** Prevent contradictory UI states and regressions where a worse algorithm overwrites better results.

## ADR-003 - Hybrid matching pipeline (structure + text refinement)
**Decision:** Adopt a hybrid pipeline: anchor/structure alignment first, then text refinement; add strategy selection for anchor-sparse cases.  
**Rationale:** Pure text or pure structure approaches fail on different edge cases; hybrid improves robustness.

## ADR-004 - Incremental refactor instead of rewrite
**Decision:** Keep the application running while migrating logic out of `AdvancedComparisonView` into core/engine modules.  
**Rationale:** Full rewrite risk is high; incremental refactor reduces downtime and preserves working behavior.

## ADR-005 - UI simplification: single panel + unified editor
**Decision:** Revert to single-panel UI; "Simulate" launches Unified Inspection Editor; remove duplicate/legacy panels.  
**Rationale:** Users want clear workflow value without internal complexity; duplication caused confusion and crashes.

## ADR-006 - Template Propagation as a first-class workflow
**Decision:** Provide Propagate as a core interaction; implement text/coordinate propagation and extend with OpenCV visual propagation.  
**Rationale:** The core user value is "fix once, apply everywhere"; propagation must be reliable and verifiable.

## ADR-007 - Golden samples required for refactor safety
**Decision:** Maintain a golden sample set and automated checks across refactors.  
**Rationale:** Prevent regressions (for example, sync-rate drops due to overwrite bugs) and enable safe iteration.

## ADR-008 - Selection identity must be unique at UI ingress
**Decision:** Manual selection IDs are validated and reissued to guarantee uniqueness before region/pair creation.  
**Rationale:** Duplicate IDs caused map collisions and unstable sheet linkage.

## ADR-009 - Global coordinate contract for persisted rectangles
**Decision:** Persisted `EditableRegion.rect` and `SyncPair.*_bbox` use global coordinates; view conversion is render-time only.  
**Rationale:** Mixed coordinate models caused highlight/sheet mismatch and difficult debugging.

## ADR-010 - Heavy debug logging disabled by default
**Decision:** File-based deep debug logs are disabled unless explicitly enabled via runtime flag.  
**Rationale:** Uncontrolled logging degrades UI responsiveness and obscures performance regressions.

## ADR-011 - KPI/SLO contract aligned with normal web-load expectations
**Decision:** Use three quality KPIs (`Top-1 precision`, `false-match ratio`, `unmatched ratio`) and adopt latency SLO:
- 100x100 candidates: initial run <= 2.0s
- 100x100 candidates: rerun <= 0.5s  
**Constraint:** Keep responsiveness aligned with normal web-page load perception; recalibrate SLO when repeatedly violated in representative datasets.  
**Rationale:** Accuracy/speed improvements require measurable targets and a shared UX boundary.

## ADR-012 - ParagraphMatcher latency baseline uses Kyushu Temple fixed dataset
**Decision:** Default benchmark dataset is fixed to `exports/metadata_20260206_031356.csv` (Kyushu Temple sample), evaluated at `web=100`, `pdf=100`.  
**Constraint:** Synthetic mode remains available for algorithm micro-benchmarks, but KPI/SLO tracking uses Kyushu baseline by default.  
**Rationale:** Real-sample fixed inputs reduce drift and make speed decisions comparable across refactors.

## ADR-013 - CI enforces ParagraphMatcher latency SLO
**Decision:** GitHub Actions runs `benchmark_paragraph_matcher_latency.py --enforce-slo` on each relevant push/PR and fails the check on threshold breach.  
**Constraint:** Enforcement target is Kyushu Temple baseline (`100x100`, first <= 2.0s, rerun <= 0.5s).  
**Rationale:** Performance regression must be blocked automatically, not detected manually after merge.
