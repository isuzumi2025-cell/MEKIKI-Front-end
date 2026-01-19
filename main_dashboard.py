"""
新しいアーキテクチャのエントリーポイント
Phase 2: Dashboard画面から起動
"""
import customtkinter as ctk
from app.gui.dashboard import Dashboard


def main():
    """メインエントリーポイント"""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # ダミールートウィンドウ（非表示）
    root = ctk.CTk()
    root.withdraw()
    
    # Dashboard画面を表示
    dashboard = Dashboard(root)
    
    root.mainloop()


if __name__ == "__main__":
    main()

