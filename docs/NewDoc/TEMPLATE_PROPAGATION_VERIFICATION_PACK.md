# Template Propagation Verification Pack (Kyushu Temple)

## 0. Purpose
Verify that Template Propagation works end-to-end in the GUI and does not create duplicates or misaligned boxes.

## 1. Preconditions
- You are running the cleaned build (restart via run_unified.py).
- The “Kyushu Temple” sample can be loaded.
- The toolbar includes “✨ 類似検出 (Propagate)” and it is enabled only when exactly one region is selected.
- `raw_words` are available in AdvancedComparisonView (or state) for the current document.

## 2. Manual test script (authoritative)
1) Open the app and load the “Kyushu Temple” image.
2) Manually create/adjust a region around **“03 Sugawara Shrine”** so it is “perfect” (your template).
3) Select that single region.
4) Click **“✨ 類似検出”**.
5) Confirm that new boxes are created for **“01”, “02”, “04” … “09”** with:
   - Same size as template (within tolerance)
   - Same relative alignment to the item number
6) Confirm there are **no duplicates** (NMS worked).

## 3. Acceptance criteria (pass/fail)
PASS if all of the following are true:
- (A) Boxes appear for the expected set of items (01,02,04..09).
- (B) No duplicate boxes exist for the same target.
- (C) Alignment is visually correct; onion-skin overlay shows consistent relative placement.

FAIL if any of the following occurs:
- Missing boxes for expected items
- Multiple overlapping boxes for the same target
- Boxes drift (inconsistent offsets) or attach to wrong anchors

## 4. Debug telemetry to capture on failure
Please capture these values (log to console or a debug panel):
- Detected header/anchor regex
- Count of raw_words
- Count of anchors detected
- Number of projected boxes before NMS
- Number of boxes after NMS
- For each candidate rejected by NMS: overlap score / rejection reason

## 5. LLM “no-forget” prompt (Gemini/antigravity)
Use this prompt when asking the agent to implement or fix propagation:

---
ROLE: You are the implementation engineer. The Verification Pack is the acceptance test.

RULES:
1) Do not claim “done” until the Manual test script passes (Section 2) and you have a pass/fail statement for each acceptance criterion (Section 3).
2) Before coding, produce a TODO ledger with IDs: [P-004], [P-005] etc.
3) After coding, produce a Coverage Matrix: requirement -> file/function touched -> how it is verified.
4) If something is ambiguous, mark it as BLOCKED in the ledger and ask a single targeted question.

INPUTS:
- SSOT: MEKIKI_SSOT.md
- Backlog: MEKIKI_BACKLOG.md
- This Verification Pack

OUTPUT FORMAT:
- TODO ledger
- Patch summary
- Coverage matrix
- Remaining risks

--- 
