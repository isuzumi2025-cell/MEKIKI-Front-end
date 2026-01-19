import sys
import os
import customtkinter as ctk
import tkinter as tk

# Fix path
sys.path.append(os.getcwd())

def debug_test():
    print("--- START DEBUG TEST ---")
    ctk.set_appearance_mode("Dark")
    
    root = ctk.CTk()
    root.geometry("800x600")
    
    try:
        print("[1] Importing ComparisonMatrixWindow...")
        from app.gui.windows.comparison_matrix import ComparisonMatrixWindow
        print("Import Success.")
        
        print("[2] Creating Matrix Window...")
        matrix = ComparisonMatrixWindow(root)
        print("Created Success.")
        
        print("[3] Loading Data...")
        try:
            # Create Dummy data
            matrix.set_web_data(None, "Dummy Web Text")
            matrix.set_pdf_data(None, "Dummy PDF Text")
            print("Data Load Success.")
        except Exception as e:
            print(f"Data Load Error: {e}")
            import traceback
            traceback.print_exc()
            
        print("[4] Mainloop...")
        root.mainloop()
        
    except ImportError as e:
        print(f"IMPORT ERROR: {e}")
        print("Tip: Check if 'pymupdf' (fitz) is installed.")
    except tk.TclError as e:
        print(f"TKINTER ERROR: {e}")
        print("Tip: Check for invalid pack/grid options.")
    except Exception as e:
        print(f"GENERAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_test()
