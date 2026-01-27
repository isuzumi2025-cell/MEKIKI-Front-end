"""
Main Entry Point
アプリケーションのエントリーポイント

統合版: UnifiedApp (フル機能GUI + 比較マトリクス)
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

# UnifiedApp を起動 (フル機能版)
from app.gui.unified_app import UnifiedApp

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MEKIKI Proofing System 起動中...")
    print("   Unified GUI (比較マトリクス含む)")
    print("=" * 60)
    
    app = UnifiedApp()
    app.mainloop()
