"""
MEKIKI OCR - Main Entry Point

業務配布用のエントリーポイント:
- ログ初期化
- エラーハンドリング
- GUI起動

Usage:
    python app/main.py
    # or after packaging:
    MEKIKI.exe
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ログ初期化
from app.core.logger import get_logger
logger = get_logger(__name__)

def main():
    """
    メインエントリーポイント
    """
    try:
        logger.info("=" * 60)
        logger.info("MEKIKI OCR Starting")
        logger.info("=" * 60)

        # GUI起動
        from app.gui.main_window_v2 import MainWindow
        import customtkinter as ctk

        # CustomTkinter設定
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # メインウィンドウ起動
        app = MainWindow()

        logger.info("Main window initialized successfully")

        # イベントループ開始
        app.mainloop()

        logger.info("MEKIKI OCR Exiting normally")

    except Exception as e:
        # クリティカルエラー
        logger.critical(f"Fatal error: {e}", exc_info=True)

        # ユーザーに通知
        try:
            import tkinter.messagebox as messagebox
            messagebox.showerror(
                "起動エラー",
                f"MEKIKI OCRの起動中にエラーが発生しました:\n\n{e}\n\n"
                f"ログファイルを確認してください:\nlogs/mekiki_error.log"
            )
        except:
            # メッセージボックスも表示できない場合はコンソールに出力
            print(f"❌ FATAL ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

        sys.exit(1)


if __name__ == "__main__":
    main()
