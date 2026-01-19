# Implementation Plan - Template Propagation

## Goal
Implement "Template Propagation" (Find Similar Patterns) feature to allow users to unify cluster layouts based on a manual selection.

## User Review Required
None (Consensus already built).

## Proposed Changes

### Core Logic
#### [NEW] [structure_propagator.py](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/app/core/structure_propagator.py)
- Implements `StructurePropagator` class.
- Logic:
    1. Detect header pattern (Regex) from template text.
    2. Scan all raw words for anchors matching the pattern.
    3. Project the template box onto detected anchors.
    4. NMS (Non-Maximum Suppression) to remove overlaps.

### UI Integration
#### [MODIFY] [advanced_comparison_view.py](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/app/gui/windows/advanced_comparison_view.py)
- In `_setup_toolbar`: Add "✨ 類似検出 (Propagate)" button.
    - Enable only when 1 region is selected.
- Add `_on_propagate_click` handler:
    - Get selected region as Template.
    - Get all raw words (from `self.raw_words` - need to ensure this is stored).
    - Call `StructurePropagator.propagate`.
    - Update `self.web_regions` (or pdf_regions) with new result.
    - Refresh UI.

#### [MODIFY] [engine_cloud.py](file:///c:/Users/raiko/OneDrive/Desktop/26/OCR/app/core/engine_cloud.py)
- Ensure `extract_text` returns `raw_words` and it is stored in `AdvancedComparisonView`. (Already seems to return it).

## Verification Plan

### Manual Verification
1. Open the App and load the "Kyushu Temple" image.
2. Select the "03 Sugawara Shrine" box manually (adjust it perfectly).
3. Select that box.
4. Click "✨ 類似検出".
5. Verify that "01", "02", "04"... "09" boxes are automatically created with the same size and alignment relative to their numbers.
6. Verify no duplicate boxes.
