# MEKIKI Genius — SSOT (Single Source of Truth)
**Version:** 1.0 (compiled)
**Date:** 2026-01-09

## 0. Purpose
MEKIKI Genius is a **multimodal proofing system** that goes *beyond text-only OCR matching* by **integrating text extraction and structure extraction to produce a final fusion score**, enabling reliable, one-click, document-wide consistency adjustments.

## 1. Vision
- Move beyond “text match” proofing toward **visual intelligence**.
- If a user corrects one place, the system should infer the same correction elsewhere (“1箇所直せば全て直る”).

## 2. Scope (What this system does)
### 2.1 Primary workflow
1. Ingest Web OCR results and PDF OCR results.
2. Compare and align regions using a **hybrid pipeline** (structure first; text refinement second).
3. Present:
   - Canvas (spatial view),
   - Spreadsheet (diff/rows view),
   - Sync Rate / Fusion Score,
   all driven from a **single internal match result (SSOT)**.
4. Allow user edits in a unified editor; propagate fixes; update all views immediately.

### 2.2 Supported document types
- Web screenshot / rendered page images
- PDF page images
- Mixed layouts, including list-like repeated blocks

## 3. Non-Goals (Explicitly out of scope for now)
- Full autonomous correction without user input
- Model training / fine-tuning (Phase 3 work only)
- Perfect handling of all exotic PDF tables without per-template tuning

## 4. Core pillars (Definitive Features)
### A. Visual Anchor Engine (VAE)
**Goal:** Recognize anchors using images/icons/layout features (not only text).
**Key functions (Phase 2):**
- OpenCV-based image matching to align anchors when OCR is weak.
- Style recognition features (bold/box/ratio/density) to group similar blocks.

**Acceptance criteria (Phase 2 minimum):**
- Given an anchor/icon area selected as template, detect the same anchor across pages with stable coordinates within tolerance.
- In anchor-only pages with limited text, still produce matches using visual features.

### B. Structure Propagator (Template Propagation)
**Goal:** User defines one “correct region” template; system detects similar structures and normalizes them.
Two modes:
1) **Text/coordinate-based propagation** (existing)
2) **Visual propagation** via OpenCV template matching (Phase 2)

**Acceptance criteria (Genius Edition baseline):**
- UI exposes “✨ 類似検出 (Propagate)” and enables it only when exactly one region is selected.
- Propagate produces a non-duplicated set of boxes using NMS overlap removal.
- Manual test: Using Kyushu Temple sample, selecting “03 Sugawara Shrine” as template and running Propagate creates aligned boxes for “01, 02, 04 … 09” with matching size/alignment.

### C. Unified Comparison Matrix
**Goal:** Manage Web/PDF comparison as meaningful pairs; compute Fusion Score; guarantee real-time sync.
**Core rules:**
- **Single Source of Truth:** all UI renders derive from one unified match result (e.g., UnifiedMatchResult / MatchResult).
- UI is passive; logic lives in core/engine modules.
- Any action that recalculates matching must update the SSOT object first; then UI re-renders from that SSOT (no ad-hoc patches).

**Acceptance criteria:**
- Canvas, Spreadsheet, and Sync Rate never disagree.
- “Advanced Match” must never reduce accuracy by overwriting a better result with a worse algorithm; pipeline is unified.

### D. Visual Match Simulator / Unified Inspection Editor
**Goal:** Provide a debug/verification environment implementing onion-skin overlay and optional LLM semantic checks.
**Acceptance criteria:**
- “Simulate” launches the unified editor reliably.
- Onion-skin overlay supports visual verification of alignment.
- The editor supports quick iteration: inspect, adjust, propagate, verify.

## 5. Architecture principles (Hard constraints)
1. **SSOT state management**: Comparison state and match result must be centralized.
2. **Hybrid pipeline**: Anchor alignment + text refinement; strategy selection when anchors unavailable.
3. **Incremental refactor**: keep the system running while migrating logic out of the monolithic view.
4. **Golden samples**: maintain test cases to prevent regressions during refactor.

## 6. Current phase & priorities
- Phase 1 (Foundation): complete / near-complete.
- Phase 2 (Visual Intelligence): active; prioritize OpenCV integration and robust visual propagation.
- Immediate priority: Verify Template Propagation end-to-end on the Kyushu Temple sample.
