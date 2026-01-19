# MEKIKI Genius — Backlog (ID-based)

> Status values: DONE / NEXT / IN-PROGRESS / BLOCKED / DEFER

## A. Stabilization & UX (Phase 1 closeout)
- **B-001** (DONE) Remove duplicate Spreadsheet panel implementations; keep component-based SpreadsheetPanel only.
- **B-002** (DONE) Fix “Simulate” button to launch Unified Inspection Editor.
- **B-003** (DONE) Fix “Advanced Match” to run the correct unified pipeline.
- **B-004** (NEXT) Strengthen error handling so exceptions do not crash the app (graceful recovery + user-facing message).

## B. State Management (SSOT enforcement)
- **S-001** (DONE) Introduce ComparisonState / state model; migrate AdvancedComparisonView to use it.
- **S-002** (NEXT) Enforce “UI is a view only”: remove remaining ad-hoc UI patch methods; all updates derive from UnifiedMatchResult.
- **S-003** (NEXT) Add internal invariants:
  - No duplicate IDs
  - Every SyncPair references existing regions
  - Fusion Score/Sync Rate always recomputed from the same MatchResult snapshot

## C. Matching Engine (Hybrid pipeline)
- **M-001** (DONE) AnchorMatcher (Anchor & Grow) optimized.
- **M-002** (DONE) Optimization pipeline: Silent Sync → RangeOpt → Silent Sync → AnchorMatch.
- **M-003** (NEXT) Strategy Selector:
  - If anchors insufficient → fall back to bag-of-words / text-only matcher
  - Otherwise → Anchor alignment then text refinement
- **M-004** (DEFER) Isomorphic graph matching exploration (only if needed for hard cases).

## D. Template Propagation (Genius Edition)
- **P-001** (DONE) Implement StructurePropagator core logic.
- **P-002** (DONE) Integrate Propagate button in GUI (“✨ 類似検出”).
- **P-003** (DONE) Implement VisualPropagator (OpenCV template matching).
- **P-004** (NEXT / CRITICAL) Verify Template Propagation with “03 Sugawara Shrine” template (Kyushu Temple sample).
- **P-005** (NEXT) Add debug telemetry:
  - number of anchors found
  - number of projected boxes pre/post NMS
  - reasons for rejection (overlap, out-of-bounds, low score)

## E. Refactoring (Phase 2 recommended)
- **R-001** (NEXT) Model layer separation: comparison_model.py (WebRegions/PdfRegions/SyncPairs).
- **R-002** (NEXT) Logic layer separation: move _calculate_* methods into core/engine/matching_engine.py.
- **R-003** (NEXT) View layer slimming: AdvancedComparisonView handles input + render only.

## F. Quality & Regression Protection
- **Q-001** (NEXT) Golden Sample test set:
  - preserve known “good” pairs and expected Sync Rate / match count
  - automated check to prevent regression during refactor
- **Q-002** (NEXT) Performance baseline:
  - spreadsheet rendering O(N) without repeated lookups (cache previews/diffs)
  - smooth scrolling and no redundant refresh loops
