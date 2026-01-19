import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from app.gui.windows.advanced_comparison_view import AdvancedComparisonView
    print(f"Class loaded: {AdvancedComparisonView}")
    if hasattr(AdvancedComparisonView, '_build_spreadsheet_panel'):
        print("Method '_build_spreadsheet_panel' EXISTS.")
    else:
        print("Method '_build_spreadsheet_panel' MISSING.")
        print("Available methods starting with _build:")
        for m in dir(AdvancedComparisonView):
            if m.startswith("_build"):
                print(f" - {m}")
except Exception as e:
    print(f"Import Error: {e}")
