# MEKIKI Proofing System - System Context (Cursor Handoff)

## 1. System Identity

- **Name**: MEKIKI Proofing System (Orchestra v2.0)
- **Purpose**: High-precision visual/text proofing tool comparing Web pages vs PDFs.
- **Core Engine**: HybridOCR (Local Tesseract + Cloud Gemini 2.0 Flash).
- **Architecture**: "Orchestra" (Multi-Agent/Multi-Modality System).

## 2. Directory Structure

```
26/
├── OCR/                  # Main Application Code
│   ├── app/
│   │   ├── gui/          # CustomTkinter GUI (UnifiedApp)
│   │   ├── core/         # Core Logic (Crawler, OCR, Auth)
│   │   └── sdk/          # Modern SDK Layers (OpenClaw, AgentOps)
│   ├── main.py           # Entry Point
│   └── .env              # Configuration
└── Vault/                # Knowledge Base (Obsidian)
    ├── 00_Runbook/       # Operational Procedures
    └── 10_Projects/      # Specifications & Architecture
```

## 3. Critical Implementation Rules (DO NOT BREAK)

### A. "Stitch-Localism" (Image Handling)

- **Rule**: Stitched images (long vertical screenshots) are expensive.
- **Implementation**: They MUST be cached (`_web_stitch_cache`). **Never** re-stitch on every frame or scroll event.
- **Reference**: `app/gui/windows/advanced_comparison_view.py`

### B. "Robust Async" (Thumbnail Generation)

- **Rule**: UI responsiveness is important, but **Data Integrity is King**.
- **Implementation**:
  - Use **Robust Batching** (e.g., process 3 items per frame in `after` loop).
  - **DO NOT use Threading** for Tkinter/ImageTk operations (causes crashes/blank images).
  - **DO NOT use Time-Limits** (e.g., `if time > 10ms break`) inside the loop, as it drops items on slow machines.
- **Reference**: `app/gui/panels/spreadsheet_panel.py`

### C. Text Fidelity

- **Rule**: **NEVER truncate text** for display or comparison.
- **Implementation**: Always pass the full string (e.g., `text`, NOT `text[:200]`) to Diff algorithms.
- **Reason**: Truncation destroys sync accuracy and prevents proper proofing.

## 4. Key Components

- **SpreadsheetPanel**:
  - Virtualized list view.
  - Handles async thumbnail generation.
  - Manages "Live Sync" between Web and PDF rows.
- **ComparisonMatrixWindow**:
  - 2x3 Grid View.
  - Performs **Async Diff Calculation** (threaded `SequenceMatcher` to avoid UI freeze).
- **UnifiedApp**:
  - Main container.
  - manages `CrawlDialog` and data flow to sub-windows.

## 5. Recent Status (2026-02-04)

- **Status**: Stable / Business Standard.
- **Recent Fixes**:
    1. **Thumbnail Fix**: Reverted aggressive async optimization to stable batching.
    2. **Accuracy Fix**: Removed legacy text truncation code.
    3. **Performance**: Implemented non-blocking Matrix comparison.

## 6. How to Develop

1. **Read the Vault**: Check `Vault/00_Runbook` before starting complex tasks.
2. **Use Task Mode**: Maintain `task.md` for tracking.
3. **Run Main**: `python main.py` triggers the full GUI.
