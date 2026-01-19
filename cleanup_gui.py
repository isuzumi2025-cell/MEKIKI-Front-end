import os

file_path = r"c:\Users\raiko\OneDrive\Desktop\26\OCR\app\gui\windows\advanced_comparison_view.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Verify markers (0-indexed, so line 489 is index 488)
# Line 489 in 1-based is index 488.
idx_start = 488
idx_end = 968

print(f"Line {idx_start+1}: {lines[idx_start].strip()}")
print(f"Line {idx_end+1}: {lines[idx_end].strip()}")

check1 = "def _build_spreadsheet_panel(self, parent):" in lines[idx_start]
check2 = "def _build_spreadsheet_panel(self, parent):" in lines[idx_end]

if check1 and check2:
    print("Markers confirmed. Deleting block.")
    # Keep 0 to 487 (lines 1-488)
    # Skip 488 to 967 (lines 489-968)
    # Keep 968 to end (lines 969+)
    
    new_lines = lines[:idx_start] + lines[idx_end:]
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Success: File updated.")
else:
    print("Error: Markers did not match expectations.")
