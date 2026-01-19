"""
統合アプリ起動スクリプト
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.unified_app import main

if __name__ == "__main__":
    main()
