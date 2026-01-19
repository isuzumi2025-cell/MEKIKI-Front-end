# Task: Advanced Cluster Matching System

## Completed
- [x] Create cluster_matcher module
- [x] LayoutPatternDetector, SyntaxPatternMatcher
- [x] CrossDocumentAligner, ImageRegionComparator
- [x] SelectionSimulator, UI integration

## In Progress
- [x] RangeOptimizationSimulator (5% step, 20% threshold) - Reduced redundant syncs
- [x] AnchorMatcher (Anchor & Grow Strategy) - O(N) optimized
- [x] Optimization Pipeline (Silent Sync -> RangeOpt -> Silent Sync -> AnchorMatch)
- [x] Fix AttributeError: '_build_spreadsheet_panel'
- [x] Fix Sync Visualization (Duplicate Code Removal)
- [x] Fix Sync Label/Spreadsheet Update (Manual Refresh logic)
- [x] Fix SyncPair AttributeError (ID-based text lookup)
- [x] Fix Advanced Match SyncPairs Update (Consistency with Auto Sync)
- [x] **Debugging UI Issues**
    - [x] Investigate "Simulate" Button mapping (mapped to old simulator)
    - [x] Fix "Advanced Match" Button logic (missing method)
    - [x] Resolve Duplicate Comparison Sheet (Deleted duplicate code)
    - [x] Verify Unified Editor Launch via Simulator Button
- [x] Fix Spreadsheet Design (Grid Layout + Header)
- [x] Fix Advanced Match Logic (Redirect to Anchor Pipeline)
- [x] Define Genius Edition Roadmap (Model/Logic Separation)
- [x] Initialize Core Engine (state_model.py, semantic_matcher.py)
- [x] Phase 2: Migrate AdvancedComparisonView to use ComparisonState (Logic moved to SemanticMatcher)
- [x] Integrate Genius Engine (SemanticMatcher) into Auto Sync
- [x] Extract SpreadsheetPanel to app.gui.panels
- [x] Extract OverviewPanel to app.gui.panels (Page Selection Logic)
- [x] Activated Comparison Matrix Window (Accessible via Toolbar)
- [x] Implemented Manual Page Split (Right-click menu)
- [x] Enhanced Comparison Spreadsheet (Diff Highlight + Sorting)
- [x] Fixed Missing Comparison Screen Bug
- [x] Fixed UI Crash (pack(height) error) preventing Matrix View load
- [x] Fixed OCR Error (AttributeError: overview_scroll) by removing legacy code
- [x] Fixed Logic Error (NameError: anchor_matches) to enable Spreadsheet update

### Template Propagation (Genius Edition)
- [x] Implement StructurePropagator logic
- [x] Integrate Propagate Button in GUI
- [x] Implement VisualPropagator (OpenCV Template Matching)
- [ ] Verify Template Propagation with "03 Sugawara Shrine" template
