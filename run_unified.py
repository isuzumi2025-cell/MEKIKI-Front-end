"""
統合アプリ起動スクリプト
"""
import sys
import os
import io

# Force UTF-8 stdout/stderr to prevent UnicodeEncodeError on cp932 terminals.
# Several modules (scroll_sync.py, api_manager.py, etc.) print emoji (✅🚀⚠️)
# that crash on Japanese Windows where the default encoding is cp932.
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.gui.unified_app import main

if __name__ == "__main__":
    main()
