import sys
import os
from pathlib import Path
import tkinter as tk
from PIL import Image

# Add project root to path
root_dir = Path(__file__).resolve().parent
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / 'app'))

# Disable PIL max image size limit
Image.MAX_IMAGE_PIXELS = None

# Import legacy MainWindow
from app.gui.main_window import MainWindow

if __name__ == "__main__":
    print("=" * 50)
    print("🕰️ Running Legacy MEKIKI (Backup Version)...")
    print("=" * 50)
    
    app = MainWindow()
    app.mainloop()
