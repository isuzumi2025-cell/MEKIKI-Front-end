"""
Main Entry Point
アプリケーションのエントリーポイント
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Windows UTF-8対応
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# PIL画像サイズ制限を解除
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

# メインウィンドウ V2を起動
from app.gui.main_window_v2 import MainWindow

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 OCR 比較ツール 起動中...")
    print("=" * 50)
    
    app = MainWindow()
    app.mainloop()
