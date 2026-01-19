"""
統合マルチウィンドウGUI - メインエントリーポイント
sitemap_proバックエンドとの統合、5ウィンドウ構成

ウィンドウ構成:
1. Dashboard - ナビゲーション、プロファイル管理
2. Sitemap Viewer - ツリー表示、404エラーアラート
3. Comparison Matrix - 2x3 Web/PDF比較
4. Detail Inspector - 拡大表示、Sync率、OCR再実行
5. Report Editor - 比較結果編集、GSheets/Excel出力
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import sys
import io
import subprocess
import threading
import time
import requests
from pathlib import Path
from typing import Optional, Dict, List
import json
import base64
from PIL import Image

# プロジェクトルートをsys.pathに追加 (app.coreなどのインポートを可能にする)
_project_root = Path(__file__).resolve().parent.parent.parent  # OCR directory
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from PIL import Image

# Windows UTF-8対応
if sys.platform == 'win32' and not isinstance(sys.stdout, io.TextIOWrapper):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except AttributeError:
        pass

# PIL画像サイズ制限を解除
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

# テーマ設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class SitemapProClient:
    """sitemap_pro APIクライアント"""
    
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def is_server_running(self) -> bool:
        """サーバーが起動しているか確認"""
        try:
            response = self.session.get(f"{self.base_url}/profiles", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def get_profiles(self) -> List[Dict]:
        """プロファイル一覧を取得"""
        try:
            response = self.session.get(f"{self.base_url}/profiles")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ プロファイル取得エラー: {e}")
            return []
    
    def get_jobs(self, limit: int = 50) -> List[Dict]:
        """ジョブ一覧を取得"""
        try:
            response = self.session.get(f"{self.base_url}/jobs?limit={limit}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ ジョブ取得エラー: {e}")
            return []
    
    def get_job_pages(self, job_id: str) -> List[Dict]:
        """ジョブのページ一覧を取得"""
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/pages")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ ページ取得エラー: {e}")
            return []
    
    def create_job(self, profile_id: int, start_url: Optional[str] = None) -> Optional[Dict]:
        """ジョブを作成"""
        try:
            data = {"profile_id": profile_id}
            if start_url:
                data["start_url"] = start_url
            response = self.session.post(f"{self.base_url}/jobs", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"⚠️ ジョブ作成エラー: {e}")
            return None


class BackendManager:
    """sitemap_proバックエンドの起動/管理"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.sitemap_pro_path = Path(__file__).parent.parent.parent.parent / "sitemap_pro"
    
    def start_server(self) -> bool:
        """サーバーを起動"""
        if self.is_running():
            print("✅ サーバーは既に起動中")
            return True
        
        if not self.sitemap_pro_path.exists():
            print(f"❌ sitemap_proが見つかりません: {self.sitemap_pro_path}")
            return False
        
        try:
            print(f"🚀 サーバー起動中: {self.sitemap_pro_path}")
            self.process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=str(self.sitemap_pro_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # 起動待機
            for _ in range(10):
                time.sleep(1)
                if self.is_running():
                    print("✅ サーバー起動完了")
                    return True
            
            print("⚠️ サーバー起動タイムアウト")
            return False
            
        except Exception as e:
            print(f"❌ サーバー起動エラー: {e}")
            return False
    
    def is_running(self) -> bool:
        """サーバーが起動しているか確認"""
        try:
            response = requests.get("http://localhost:8000/api/v1/profiles", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def stop_server(self):
        """サーバーを停止"""
        if self.process:
            self.process.terminate()
            self.process = None
            print("🛑 サーバー停止")


class WindowManager:
    """ウィンドウの分離/結合管理"""
    
    def __init__(self):
        self.windows: Dict[str, ctk.CTkToplevel] = {}
        self.docked_frames: Dict[str, ctk.CTkFrame] = {}
    
    def register_window(self, name: str, window: ctk.CTkToplevel):
        """ウィンドウを登録"""
        self.windows[name] = window
    
    def register_frame(self, name: str, frame: ctk.CTkFrame):
        """ドッキングフレームを登録"""
        self.docked_frames[name] = frame
    
    def detach_window(self, name: str, parent: ctk.CTk) -> Optional[ctk.CTkToplevel]:
        """ウィンドウを分離"""
        if name in self.docked_frames:
            frame = self.docked_frames[name]
            # 新しいトップレベルウィンドウを作成
            window = ctk.CTkToplevel(parent)
            window.title(name)
            window.geometry("800x600")
            # TODO: フレームの内容をウィンドウに移動
            self.windows[name] = window
            return window
        return None
    
    def attach_window(self, name: str, container: ctk.CTkFrame):
        """ウィンドウを結合"""
        if name in self.windows:
            window = self.windows[name]
            window.destroy()
            del self.windows[name]
            # TODO: 内容をコンテナに戻す


class UnifiedApp(ctk.CTk):
    """
    統合アプリケーション
    5ウィンドウ構成のマルチウィンドウGUI
    """
    
    def __init__(self):
        super().__init__()
        
        # ウィンドウ設定
        self.title("🎯 MEKIKI Proofing System")
        self.geometry("1400x900")
        
        # バックエンド管理
        self.backend = BackendManager()
        self.api_client = SitemapProClient()
        self.window_manager = WindowManager()
        
        # 状態
        self.server_status = "unknown"
        self.current_job = None
        self.current_profile = None
        
        # 共有データ (ビュー間でページデータを共有)
        self.selected_web_page: Optional[Dict] = None  # サイトマップから選択したWebページ
        self.selected_pdf_pages: List = []  # 読み込んだPDFページ
        self.comparison_queue: List[Dict] = []  # 比較待ちのページリスト
        
        # UI構築
        self._setup_ui()
        
        # サーバー状態確認
        self.after(1000, self._check_server_status)
    
    def add_web_page_to_comparison(self, page_data: Dict):
        """Webページを比較キューに追加 (サイトマップから呼ばれる)"""
        self.comparison_queue.append({
            'type': 'web',
            'url': page_data.get('url', ''),
            'text': page_data.get('text_content', ''),
            'screenshot_base64': page_data.get('screenshot_base64'),
            'title': page_data.get('title', ''),
            'status_code': page_data.get('status_code', 200)
        })
        self.status_label.configure(text=f"✅ 比較に追加: {page_data.get('url', '')[:40]}...")
        print(f"📥 比較キューに追加: {page_data.get('url', '')} (キュー: {len(self.comparison_queue)}件)")
    
    def _setup_ui(self):
        """UI構築"""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Right Panel (Container for Content + Status Bar)
        self.right_panel = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True)

        # Content (Dynamic View Area)
        self.content = ctk.CTkFrame(self.right_panel, corner_radius=0, fg_color="transparent")
        self.content.pack(side="top", fill="both", expand=True)

        # Status Bar
        self.status_bar = ctk.CTkFrame(self.right_panel, height=25)
        self.status_bar.pack(side="bottom", fill="x")
        
        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", font=("Meiryo", 10), anchor="w")
        self.status_label.pack(side="left", padx=10, fill="x")
        
        self.server_indicator = ctk.CTkLabel(self.status_bar, text="● Server", font=("Meiryo", 10))
        self.server_indicator.pack(side="right", padx=10)

        self._build_sidebar()
        self._show_welcome()

    def _build_sidebar(self):
        """サイドバー構築"""
        # Header
        ctk.CTkLabel(self.sidebar, text="MEKIKI\nProofing System", font=("Meiryo", 18, "bold")).pack(pady=(20, 10))
        
        # Navigation
        buttons = [
            ("📊 ダッシュボード", self._show_dashboard),
            ("🗺️ サイトマップ", self._show_sitemap_viewer),
            ("⚖️ 比較マトリクス", self._show_comparison_matrix),
            ("🔍 詳細検査", self._show_detail_inspector),
            ("📝 レポート", self._show_report_editor),
        ]
        
        for text, command in buttons:
            ctk.CTkButton(
                self.sidebar,
                text=text,
                command=command,
                height=35,
                anchor="w",
                font=("Meiryo", 12),
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30")
            ).pack(fill="x", padx=10, pady=2)
            
        ctk.CTkLabel(self.sidebar, text="アクション", font=("Meiryo", 12, "bold")).pack(anchor="w", padx=10, pady=(20, 5))

        # ボタンスタイル定数（マット配色）
        BTN_HEIGHT = 40
        BTN_CORNER = 8
        BTN_FONT = ("Meiryo", 12, "bold")

        # Web読み込みボタン（青系）
        self.web_btn = ctk.CTkButton(
            self.sidebar,
            text="🌐 Web読み込み",
            command=self._start_new_crawl,
            height=BTN_HEIGHT,
            corner_radius=BTN_CORNER,
            font=BTN_FONT,
            fg_color="#3B82F6",
            hover_color="#2563EB"
        )
        self.web_btn.pack(fill="x", padx=10, pady=5)

        # PDF読み込みボタン（赤系）
        self.pdf_btn = ctk.CTkButton(
            self.sidebar,
            text="📄 PDF読み込み",
            command=self._load_pdf,
            height=BTN_HEIGHT,
            corner_radius=BTN_CORNER,
            font=BTN_FONT,
            fg_color="#EF4444",
            hover_color="#DC2626"
        )
        self.pdf_btn.pack(fill="x", padx=10, pady=5)

        # ハイブリッドOCRボタン（紫系）
        self.hybrid_btn = ctk.CTkButton(
            self.sidebar,
            text="🔀 ハイブリッドOCR",
            command=self._run_ai_analysis_mode,
            height=BTN_HEIGHT,
            corner_radius=BTN_CORNER,
            font=BTN_FONT,
            fg_color="#8B5CF6",
            hover_color="#7C3AED"
        )
        self.hybrid_btn.pack(fill="x", padx=10, pady=(15, 5))
        
        self._build_footer_tools()
    
    def _build_footer_tools(self):
        """フッターツール"""
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=10, pady=20)
        
        ctk.CTkLabel(footer, text="ツール", font=("Meiryo", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        tools = [
            ("テキスト比較", self._run_text_comparison_from_sidebar),
            ("比較シート", self._open_comparison_sheet_from_sidebar),
            ("Excel出力", self._export_excel_from_sidebar),
        ]
        
        for text, cmd in tools:
            ctk.CTkButton(
                footer,
                text=text,
                command=cmd,
                height=30,
                font=("Meiryo", 11),
                fg_color="transparent",
                border_width=1,
                text_color=("gray10", "gray90")
            ).pack(fill="x", pady=2)

        ctk.CTkButton(
            footer,
            text="サーバー起動/停止",
            command=self._toggle_server,
            height=30,
            font=("Meiryo", 11),
            fg_color="transparent",
            text_color="gray"
        ).pack(fill="x", pady=(10, 0))

    def _show_welcome(self):
        """ウェルカム画面"""
        self._clear_content()
        
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(frame, text="MEKIKI Proofing System", font=("Meiryo", 32, "bold"), text_color="gray60").pack(pady=10)
        ctk.CTkLabel(frame, text="サイドバーからアクションを選択してください", font=("Meiryo", 14), text_color="gray60").pack()
    
    def _clear_content(self):
        """コンテンツエリアをクリア"""
        for widget in self.content.winfo_children():
            widget.destroy()

    def _set_button_loading(self, button, loading: bool):
        """ボタンのローディング状態を設定"""
        # 元のテキストを取得（初回は保存）
        if not hasattr(button, '_original_text'):
            button._original_text = button.cget("text")

        if loading:
            button.configure(state="disabled", text="⏳ 処理中...")
        else:
            button.configure(state="normal", text=button._original_text)

    def _check_server_status(self):
        """サーバー状態を確認 (スタンドアローンモードでは無効化)"""
        # スタンドアローンモードではサーバーチェックをスキップ
        # 手動でサーバー起動ボタンを押した場合のみチェック
        if not getattr(self, '_server_check_enabled', False):
            self.server_status = "standalone"
            self.server_indicator.configure(
                text="● スタンドアローン",
                text_color="#2196F3"
            )
            self.status_label.configure(text="✅ スタンドアローンモード")
            return
        
        # バックグラウンドスレッドでチェック (UIブロックを防ぐ)
        def check():
            try:
                running = self.api_client.is_server_running()
                self.after(0, lambda: self._update_server_indicator(running))
            except:
                self.after(0, lambda: self._update_server_indicator(False))
        
        threading.Thread(target=check, daemon=True).start()
        
        # 定期チェック (サーバーチェック有効時のみ)
        if getattr(self, '_server_check_enabled', False):
            self.after(10000, self._check_server_status)  # 10秒間隔に変更
    
    def _update_server_indicator(self, running: bool):
        """サーバーインジケーター更新"""
        if running:
            self.server_status = "running"
            self.server_indicator.configure(
                text="● サーバー: 起動中",
                text_color="#4CAF50"
            )
        else:
            self.server_status = "stopped"
            self.server_indicator.configure(
                text="● サーバー: 停止",
                text_color="#F44336"
            )
    
    def _toggle_server(self):
        """サーバーの起動/停止"""
        if self.server_status == "running":
            self.backend.stop_server()
            self._server_check_enabled = False
            self.server_status = "standalone"
            self.server_indicator.configure(
                text="● スタンドアローン",
                text_color="#2196F3"
            )
        else:
            # サーバー起動時のみチェックを有効化
            self._server_check_enabled = True
            def start():
                success = self.backend.start_server()
                if success:
                    self.after(0, self._check_server_status)
            threading.Thread(target=start, daemon=True).start()
            self.status_label.configure(text="🚀 サーバー起動中...")
    
    def _open_web_ui(self):
        """Web UIをブラウザで開く"""
        import webbrowser
        webbrowser.open("http://localhost:8000")
    
    # ===== ビュー切り替え =====
    
    def _show_dashboard(self):
        """ダッシュボード表示"""
        self._clear_content()
        from app.gui.windows.dashboard import DashboardView
        view = DashboardView(self.content, self.api_client)
        view.pack(fill="both", expand=True)
    
    def _show_sitemap_viewer(self):
        """サイトマップビューワー表示"""
        self._clear_content()
        from app.gui.windows.sitemap_viewer import SitemapViewerFrame
        view = SitemapViewerFrame(self.content, self.api_client)
        view.pack(fill="both", expand=True)
    
    def _show_comparison_matrix(self):
        """比較マトリクス表示 - 高度な校正ワークスペース"""
        self._clear_content()
        from app.gui.windows.advanced_comparison_view import AdvancedComparisonView
        self.comparison_view = AdvancedComparisonView(self.content)
        self.comparison_view.pack(fill="both", expand=True)
    
    def _show_detail_inspector(self):
        """詳細インスペクター表示"""
        self._clear_content()
        from app.gui.windows.detail_inspector import DetailInspectorFrame
        view = DetailInspectorFrame(self.content)
        view.pack(fill="both", expand=True)
    
    def _show_report_editor(self):
        """レポートエディター表示"""
        self._clear_content()
        from app.gui.windows.report_editor import ReportEditorFrame
        view = ReportEditorFrame(self.content)
        view.pack(fill="both", expand=True)
    
    def _start_new_crawl(self):
        """新規クロール開始"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("新規クロール開始")
        dialog.geometry("500x650")
        dialog.attributes("-topmost", True)
        
        main_frame = ctk.CTkFrame(dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame, 
            text="🌐 新規Webサイトクロール", 
            font=("Meiryo", 20, "bold")
        ).pack(pady=(0, 20), anchor="w")
        
        # URL Input
        ctk.CTkLabel(main_frame, text="ターゲットURL", font=("Meiryo", 12)).pack(anchor="w", pady=(0, 5))
        url_entry = ctk.CTkEntry(
            main_frame, 
            width=460, 
            height=35,
            placeholder_text="https://example.com"
        )
        url_entry.pack(fill="x", pady=(0, 15))
        
        # Settings
        settings_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        settings_frame.pack(fill="x", pady=5)
        
        # Max Pages
        f1 = ctk.CTkFrame(settings_frame, fg_color="transparent")
        f1.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(f1, text="最大ページ数", font=("Meiryo", 11)).pack(anchor="w")
        max_pages_var = ctk.StringVar(value="10")
        ctk.CTkEntry(f1, textvariable=max_pages_var, height=30).pack(fill="x", pady=2)
        
        # Max Depth
        f2 = ctk.CTkFrame(settings_frame, fg_color="transparent")
        f2.pack(side="left", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(f2, text="最大階層深さ", font=("Meiryo", 11)).pack(anchor="w")
        max_depth_var = ctk.StringVar(value="2")
        ctk.CTkEntry(f2, textvariable=max_depth_var, height=30).pack(fill="x", pady=2)
        
        # Basic認証 (プロファイル管理付き)
        # Basic認証 (プロファイル管理付き)
        use_auth_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(main_frame, text="Basic認証を使用", variable=use_auth_var, font=("Meiryo", 12)).pack(anchor="w", pady=(20, 5))

        auth_frame = ctk.CTkFrame(main_frame)
        auth_frame.pack(fill="x", pady=5)

        # Profile Selection - with error handling
        auth_manager = None
        profile_names = ["(profiles unavailable)"]
        try:
            from app.core.auth_manager import AuthProfileManager
            auth_manager = AuthProfileManager()
            profile_names = ["-- New Profile --"] + auth_manager.get_profile_names()
        except Exception as e:
            print(f"[Auth] Import error: {e}")
        
        ctk.CTkLabel(auth_frame, text="プロファイル選択", font=("Meiryo", 11)).pack(anchor="w")
        profile_var = ctk.StringVar(value="-- New Profile --")
        
        # Define callbacks before creating widgets that use them
        def on_profile_select(choice):
            if choice == "-- New Profile --":
                url_entry.delete(0, "end")
                username_entry.delete(0, "end")
                password_entry.delete(0, "end")
            else:
                try:
                    profile = auth_manager.get_profile(choice)
                    if profile:
                        url_entry.delete(0, "end")
                        url_entry.insert(0, profile.url or "")
                        username_entry.delete(0, "end")
                        username_entry.insert(0, profile.username)
                        password_entry.delete(0, "end")
                        password_entry.insert(0, profile.password)
                        use_auth_var.set(True)  # Enable auth checkbox
                except AttributeError:
                    # Fallback for dicts if AuthManager changed
                    pass

        profile_dropdown = ctk.CTkOptionMenu(
            auth_frame,
            variable=profile_var,
            values=profile_names,
            command=on_profile_select,
            width=300
        )
        profile_dropdown.pack(fill="x", pady=(0, 10))

        # Username / Password Inputs
        ctk.CTkLabel(auth_frame, text="ユーザー名", font=("Meiryo", 11)).pack(anchor="w")
        username_entry = ctk.CTkEntry(auth_frame, width=300)
        username_entry.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(auth_frame, text="パスワード", font=("Meiryo", 11)).pack(anchor="w")
        password_entry = ctk.CTkEntry(auth_frame, show="*", width=300)
        password_entry.pack(fill="x", pady=(0, 15))

        def save_profile():
            from app.core.auth_manager import AuthProfile
            url = url_entry.get().strip()
            username = username_entry.get().strip()
            password = password_entry.get()
            
            if not username:
                messagebox.showwarning("警告", "ユーザー名を入力してください")
                return

            profile = AuthProfile(name=username, url=url, username=username, password=password)
            auth_manager.add_profile(profile)
            messagebox.showinfo("保存完了", f"プロファイル「{username}」を保存しました")
            profile_dropdown.configure(values=["-- New Profile --"] + auth_manager.get_profile_names())
            profile_var.set(username)

        action_row = ctk.CTkFrame(auth_frame, fg_color="transparent")
        action_row.pack(fill="x", pady=5)
        
        ctk.CTkButton(
            action_row, 
            text="💾 保存", 
            command=save_profile,
            height=30,
            font=("Meiryo", 11),
            width=80
        ).pack(side="left", padx=(0, 10)) 

        
        def delete_profile():
            name = profile_var.get()
            if name == "-- New Profile --":
                return
            if messagebox.askyesno("確認", f"プロファイル「{name}」を削除しますか？"):
                auth_manager.delete_profile(name)
                profile_dropdown.configure(values=["-- New Profile --"] + auth_manager.get_profile_names())
                profile_var.set("-- New Profile --")
                username_entry.delete(0, "end")
                password_entry.delete(0, "end")
        
        ctk.CTkButton(
            action_row, 
            text="🗑️ 削除", 
            command=delete_profile,
            height=30,
            font=("Arial", 11),
            fg_color="#EF4444", 
            hover_color="#DC2626",
            text_color="white",
            width=80
        ).pack(side="left")

        # --- Main Action Button & Progress ---
        progress_label = ctk.CTkLabel(main_frame, text="", font=("Meiryo", 11), text_color="#A1A1AA")
        progress_label.pack(pady=(10, 0))

        def run_crawl():
            url = url_entry.get().strip()
            if not url:
                messagebox.showwarning("警告", "URLを入力してください")
                return
            
            try:
                max_pages = int(max_pages_var.get() or 10)
                max_depth = int(max_depth_var.get() or 2)
            except ValueError:
                messagebox.showerror("エラー", "数値の形式が正しくありません")
                return

            use_auth = use_auth_var.get()
            username = username_entry.get() if use_auth else None
            password = password_entry.get() if use_auth else None
            
            if use_auth and (not username or not password):
                messagebox.showwarning("警告", "認証を使用する場合はユーザー名とパスワードが必要です")
                return

            progress_label.configure(text="🚀 クロールを開始します...")
            dialog.update()
            
            def crawl_thread():
                dialog_alive = True
                try:
                    from app.core.standalone_scraper import StandaloneScraper
                    # Force headless to avoid extra windows unless debugging
                    scraper = StandaloneScraper(headless=True)
                    
                    def progress_cb(current_url, current, total):
                        nonlocal dialog_alive
                        if dialog_alive:
                            try:
                                self.after(0, lambda: progress_label.configure(
                                    text=f"📄 {current}/{total}: {current_url[:40]}..."
                                ) if progress_label.winfo_exists() else None)
                            except:
                                dialog_alive = False
                    
                    results = scraper.crawl(
                        start_url=url,
                        max_pages=max_pages,
                        max_depth=max_depth,
                        username=username,
                        password=password,
                        progress_callback=progress_cb
                    )
                    
                    def on_crawl_complete():
                        nonlocal dialog_alive
                        dialog_alive = False
                        try:
                            dialog.destroy()
                        except:
                            pass
                        try:
                            self._handle_crawl_results(results)
                        except Exception as ex:
                            print(f"Error handling crawl results: {ex}")
                        messagebox.showinfo("完了", f"{len(results)} ページのクロールが完了しました！")
                    
                    self.after(0, on_crawl_complete)
                    
                except Exception as e:
                    def show_error():
                        nonlocal dialog_alive
                        dialog_alive = False
                        messagebox.showerror("エラー", f"クロールに失敗しました: {str(e)}")
                    self.after(0, show_error)

            import threading
            threading.Thread(target=crawl_thread, daemon=True).start()

        ctk.CTkButton(
            main_frame, 
            text="🚀 クロール開始", 
            command=run_crawl,
            height=50,
            font=("Meiryo", 14, "bold"),
            fg_color="#3B8ED0", # Legacy Blue
            hover_color="#1E40AF",
            corner_radius=25,
            text_color="white"
        ).pack(fill="x", pady=20)
    def _handle_crawl_results(self, results):
        """クロール結果の処理"""
        try:
            count = 0
            for r in results:
                if not r.error:
                    count += 1
                    self.comparison_queue.append({
                        'type': 'web',
                        'url': r.url,
                        'text_content': r.text_content,
                        'screenshot_base64': r.screenshot_base64,
                        'title': r.title,
                        'status_code': r.status_code,
                        'depth': r.depth
                    })
            
            # Save local pages
            self.local_pages = [r.to_dict() for r in results]
            
            # Safe status update
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.configure(text=f"✅ クロール完了: {count} ページ")
            
            print(f"✅ クロール結果処理完了: {count} ページ")
            
        except Exception as e:
            print(f"Error handling results: {e}")
    
    def _load_pdf(self):
        """PDF読込 - ページを画像に変換してcomparison_queueに追加"""
        from tkinter import filedialog
        import fitz  # PyMuPDF
        
        file_path = filedialog.askopenfilename(
            title="PDFファイルを選択",
            filetypes=[("PDFファイル", "*.pdf"), ("全てのファイル", "*.*")]
        )
        
        if not file_path:
            return
        
        def safe_status(text):
            """安全にステータスを更新"""
            if hasattr(self, 'status_label') and self.status_label.winfo_exists():
                self.status_label.configure(text=text)
            print(text)
        
        file_name = Path(file_path).name
        safe_status(f"📄 PDF読込中: {file_name}...")
        self.update()
        
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            
            print(f"📄 PDF読込開始: {file_name} ({page_count}ページ)")
            
            # PDFページをリセット
            self.selected_pdf_pages = []
            
            for page_num in range(page_count):
                page = doc[page_num]
                
                # ページを画像にレンダリング (高解像度 3x for better OCR)
                mat = fitz.Matrix(3.0, 3.0)  # 3x scale for OCR quality
                pix = page.get_pixmap(matrix=mat)
                
                # PIL Imageに変換
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # OCR精度向上のための前処理
                from PIL import ImageEnhance, ImageFilter
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.3)  # コントラスト強調
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(1.5)  # シャープネス強調
                
                self.selected_pdf_pages.append(img)
                
                # Base64エンコード
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # テキスト抽出
                text = page.get_text()
                
                # comparison_queueに追加
                self.comparison_queue.append({
                    'type': 'pdf',
                    'url': f"file://{file_path}#page={page_num+1}",
                    'title': f"{file_name} - ページ {page_num + 1}",
                    'text_content': text,
                    'image_base64': img_b64,
                    'page_number': page_num + 1
                })
                
                safe_status(f"📄 PDF読込中: {page_num + 1}/{page_count}ページ")
                self.update()
            
            doc.close()
            
            # 最初のページをcurrent_pdf_imageに設定
            if self.selected_pdf_pages:
                self.current_pdf_image = self.selected_pdf_pages[0]
            
            safe_status(f"✅ PDF読込完了: {file_name} ({page_count}ページ)")
            
            # 比較ビューが開いていれば更新
            if hasattr(self, 'comparison_view') and self.comparison_view:
                try:
                    self.comparison_view._load_pdf_data()
                    print("📄 比較ビューにPDFデータを反映しました")
                except Exception as e:
                    print(f"⚠️ 比較ビュー更新エラー: {e}")
            
            messagebox.showinfo(
                "PDF読込完了", 
                f"{page_count}ページを読み込みました。\n\n「⚖️ 比較マトリクス」を開いて確認してください。"
            )
            
        except Exception as e:
            safe_status(f"❌ PDF読込エラー: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("エラー", f"PDF読込に失敗しました:\n{e}")
    
    # ===== サイドバーアクションハンドラ (Phase 4 UI統合) =====
    
    def _run_ocr_from_sidebar(self):
        """サイドバーからOCR実行を呼び出し"""
        if hasattr(self, 'comparison_view') and self.comparison_view:
            self.comparison_view._run_ocr_analysis()
        else:
            self._show_comparison_matrix()
            self.after(500, lambda: self.comparison_view._run_ocr_analysis() if hasattr(self, 'comparison_view') else None)
    
    def _run_text_comparison_from_sidebar(self):
        """サイドバーから全文比較を呼び出し"""
        if hasattr(self, 'comparison_view') and self.comparison_view:
            self.comparison_view._run_text_comparison()
        else:
            self.status_label.configure(text="⚠️ 先に比較マトリクスを開いてください")
    
    def _open_comparison_sheet_from_sidebar(self):
        """サイドバーから比較シートを呼び出し"""
        if hasattr(self, 'comparison_view') and self.comparison_view:
            self.comparison_view._open_comparison_spreadsheet()
        else:
            self.status_label.configure(text="⚠️ 先に比較マトリクスを開いてください")
    
    def _export_excel_from_sidebar(self):
        """サイドバーからExcel出力を呼び出し"""
        if hasattr(self, 'comparison_view') and self.comparison_view:
            self.comparison_view._export_to_excel()
        else:
            self.status_label.configure(text="⚠️ 先に比較マトリクスを開いてください")
    
    def _run_llm_segmentation_from_sidebar(self):
        """Phase 5: マルチモーダルLLMパラグラフ生成"""
        if not hasattr(self, 'comparison_view') or not self.comparison_view:
            self.status_label.configure(text="⚠️ 先に比較マトリクスを開いてください")
            return
        
        try:
            from app.pipeline.llm_segmenter import MultimodalLLMSegmenter, find_common_segments, LLMParagraph
            
            self.status_label.configure(text="🧠 Phase 5: 既存OCR結果からLLMパラグラフ生成...")
            self.update()
            
            view = self.comparison_view
            
            # 複数のデータソースを試行
            web_clusters = getattr(view, 'web_clusters', [])
            pdf_clusters = getattr(view, 'pdf_clusters', [])
            web_regions = getattr(view, 'web_regions', [])
            pdf_regions = getattr(view, 'pdf_regions', [])
            sync_pairs = getattr(view, 'sync_pairs', [])
            
            # データソースを選択
            if web_clusters and pdf_clusters:
                print("[Phase 5] Using clusters as data source")
                web_data = web_clusters
                pdf_data = pdf_clusters
            elif web_regions and pdf_regions:
                print("[Phase 5] Using regions as data source")
                web_data = web_regions
                pdf_data = pdf_regions
            elif sync_pairs:
                print("[Phase 5] Using sync_pairs as data source")
                # sync_pairsから直接テキストを抽出
                web_full_text = "\n".join([getattr(p, 'web_text', p.web_id if hasattr(p, 'web_id') else '') for p in sync_pairs])
                pdf_full_text = "\n".join([getattr(p, 'pdf_text', p.pdf_id if hasattr(p, 'pdf_id') else '') for p in sync_pairs])
                web_data = None
                pdf_data = None
            else:
                self.status_label.configure(text="⚠️ 先にOCRを実行してください")
                return
            
            # クラスタ/リージョンからテキスト抽出
            if web_data and pdf_data:
                web_full_text = "\n".join([
                    c.get('text', '') if isinstance(c, dict) else getattr(c, 'text', '')
                    for c in web_data
                ])
                pdf_full_text = "\n".join([
                    c.get('text', '') if isinstance(c, dict) else getattr(c, 'text', '')
                    for c in pdf_data
                ])
            
            data_source_len = len(web_data) if web_data else len(sync_pairs)
            print(f"[Phase 5] Web text: {len(web_full_text)} chars from {data_source_len} items")
            print(f"[Phase 5] PDF text: {len(pdf_full_text)} chars")
            
            # 全文比較
            match_segments = find_common_segments(web_full_text, pdf_full_text)
            print(f"[Phase 5] Match segments: {len(match_segments)}")
            
            # LLMパラグラフ生成
            web_image = getattr(view, 'web_image', None)
            pdf_image = getattr(view, 'pdf_image', None)
            
            segmenter = MultimodalLLMSegmenter()
            if web_image and pdf_image:
                paragraphs = segmenter.generate_paragraphs(
                    web_image, pdf_image,
                    web_full_text, pdf_full_text,
                    match_segments
                )
            else:
                # 画像がない場合はフォールバック
                paragraphs = segmenter._fallback_paragraphs(match_segments, web_full_text, pdf_full_text)
            
            # LiveComparisonSheetに反映するためsync_pairsを更新
            if paragraphs:
                # LLMParagraphをSyncPair互換オブジェクトに変換
                class LLMSyncPair:
                    def __init__(self, p: LLMParagraph):
                        self.web_id = p.id
                        self.pdf_id = p.id
                        self.similarity = p.sync_score
                        self.web_text = p.web_text
                        self.pdf_text = p.pdf_text
                
                # web_regionsとpdf_regionsを作成
                class LLMRegion:
                    def __init__(self, p: LLMParagraph, source: str):
                        self.area_code = p.id
                        self.text = p.web_text if source == 'web' else p.pdf_text
                        self.rect = [0, 0, 100, 100]  # ダミー座標
                        self.similarity = p.sync_score
                
                llm_sync_pairs = [LLMSyncPair(p) for p in paragraphs]
                llm_web_regions = [LLMRegion(p, 'web') for p in paragraphs]
                llm_pdf_regions = [LLMRegion(p, 'pdf') for p in paragraphs]
                
                # comparison_viewのデータを更新
                view.sync_pairs = llm_sync_pairs
                view.web_regions = llm_web_regions
                view.pdf_regions = llm_pdf_regions
                
                # SpreadsheetPanelを更新
                if hasattr(view, 'spreadsheet_panel'):
                    view.spreadsheet_panel.update_data(
                        llm_sync_pairs,
                        llm_web_regions,
                        llm_pdf_regions,
                        web_image,
                        pdf_image
                    )
                
                # Sync Rate更新
                if hasattr(view, 'sync_rate_label'):
                    avg_sync = sum(p.sync_score for p in paragraphs) / len(paragraphs) if paragraphs else 0
                    view.sync_rate_label.configure(text=f"Sync: {avg_sync:.1%}")
            
            # 結果表示
            self.status_label.configure(
                text=f"✅ Phase 5完了: {len(paragraphs)}パラグラフ, {len(match_segments)}マッチ"
            )
            
            print(f"[Phase 5] Generated: {len(paragraphs)} paragraphs")
            for p in paragraphs[:5]:
                print(f"   {p.id}: Web[{p.web_text[:25]}...] ⇔ PDF[{p.pdf_text[:25]}...]")
                
        except Exception as e:
            self.status_label.configure(text=f"❌ エラー: {str(e)}")
            print(f"Phase 5 Error: {e}")
            import traceback
            traceback.print_exc()
    
    def _normalize_japanese_text(self, text: str) -> str:
        """
        日本語テキストの正規化
        - 日本語文字間のスペースを削除
        - 句読点前後のスペースを削除
        - 英単語間のスペースは維持
        """
        import re

        if not text:
            return text

        # 日本語文字の範囲
        # ひらがな: \u3040-\u309F
        # カタカナ: \u30A0-\u30FF
        # 漢字: \u4E00-\u9FFF
        # 全角記号・句読点: \u3000-\u303F
        jp_char = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
        jp_punct = r'[。、．，！？｡､]'

        # 1. 日本語文字同士の間のスペース（半角・全角）を削除
        text = re.sub(f'({jp_char})[ 　]+({jp_char})', r'\1\2', text)

        # 2. 句読点の前後のスペースを削除
        text = re.sub(f'[ 　]+({jp_punct})', r'\1', text)
        text = re.sub(f'({jp_punct})[ 　]+', r'\1', text)

        # 3. 日本語文字と句読点の間のスペースを削除
        text = re.sub(f'({jp_char})[ 　]+({jp_punct})', r'\1\2', text)
        text = re.sub(f'({jp_punct})[ 　]+({jp_char})', r'\1\2', text)

        # 4. 連続するスペースを1つに
        text = re.sub(r'[ 　]{2,}', ' ', text)

        return text.strip()

    def _run_ai_analysis_mode(self):
        """
        🤖 AI分析モード: ハイブリッドアーキテクチャ版

        1. Web: engine_cloud.py のクラスタリングで長文パラグラフ抽出
        2. PDF: PyMuPDF 埋め込みテキスト優先（5px padding で文字欠け防止）
        3. テキスト正規化（日本語スペース削除）
        4. パラグラフ間マッチング → LiveComparisonSheet表示
        """
        if not hasattr(self, 'comparison_view') or not self.comparison_view:
            self.status_label.configure(text="⚠️ 先に比較マトリクスを開いてください")
            return

        try:
            from app.core.engine_cloud import CloudOCREngine
            from app.core.paragraph_detector import Paragraph
            from app.core.hybrid_ocr import HybridOCREngine  # 🔥 Hybrid OCR
            import fitz  # PyMuPDF
            import os
            
            # 🔥 ハイブリッドOCRモード (Cloud Vision + Gemini補正)
            USE_HYBRID_OCR = True

            view = self.comparison_view

            # ★★★ 状態初期化（State Management Fix）★★★
            # 結果データのみクリア（入力画像は保持）
            view.sync_pairs = []
            view.web_regions = []
            view.pdf_regions = []
            # Note: view.web_image/pdf_image は入力ソースとして使われるため、ここではクリアしない
            # 最後に新しい結果で上書きされる

            # spreadsheet_panelの結果状態のみクリア
            if hasattr(view, 'spreadsheet_panel'):
                view.spreadsheet_panel.sync_pairs = []
                view.spreadsheet_panel.web_map = {}
                view.spreadsheet_panel.pdf_map = {}
                # サムネイル参照もクリア（GC対策）
                if hasattr(view.spreadsheet_panel, '_thumbnail_refs'):
                    view.spreadsheet_panel._thumbnail_refs = []
                # Note: 画像参照は最後に update_data で新しいものが渡される
            print("[AI Mode] ✓ State initialized (clean slate)")

            # Step 1: データ取得
            self.status_label.configure(text="🤖 AI分析モード: データ取得中...")
            self.update()

            # ローカル変数も明示的に初期化
            web_images = []
            pdf_images = []
            pdf_file_path = None
            web_paragraphs = []
            pdf_paragraphs = []

            # Web画像
            if hasattr(view, 'web_pages') and view.web_pages:
                for page in view.web_pages:
                    if isinstance(page, dict) and page.get('image'):
                        web_images.append(page['image'])
                print(f"[AI Mode] web_pages から {len(web_images)} 画像取得")
            if not web_images and hasattr(view, 'web_image') and view.web_image:
                web_images = [view.web_image]
                print(f"[AI Mode] web_image から 1 画像取得")

            # PDF: ファイルパスを取得
            if hasattr(self, 'comparison_queue') and self.comparison_queue:
                for item in self.comparison_queue:
                    if item.get('type') == 'pdf':
                        url = item.get('url', '')
                        if url.startswith('file://'):
                            pdf_file_path = url.replace('file://', '').split('#')[0]
                            break

            # PDF画像（OCRフォールバック用）
            if hasattr(view, 'pdf_pages_list') and view.pdf_pages_list:
                for page in view.pdf_pages_list:
                    if isinstance(page, dict) and page.get('image'):
                        pdf_images.append(page['image'])
                print(f"[AI Mode] pdf_pages_list から {len(pdf_images)} 画像取得")
            if not pdf_images and hasattr(view, 'pdf_image') and view.pdf_image:
                pdf_images = [view.pdf_image]
                print(f"[AI Mode] pdf_image から 1 画像取得")

            print(f"[AI Mode] Found - Web: {len(web_images)}, PDF path: {pdf_file_path}, PDF images: {len(pdf_images)}")

            if not web_images or (not pdf_file_path and not pdf_images):
                self.status_label.configure(text="⚠️ Web/PDF画像を読み込んでください")
                return

            # Step 2: パラグラフ抽出
            self.status_label.configure(text="🤖 AI分析モード: パラグラフ検出中...")
            self.update()

            # === Web: engine_cloud.py クラスタリング ===
            ocr_engine = CloudOCREngine()
            
            # 🔥 ハイブリッドOCRエンジン (Gemini補正用)
            hybrid_engine = None
            if USE_HYBRID_OCR:
                try:
                    hybrid_engine = HybridOCREngine()
                    if hybrid_engine._is_initialized:
                        print("[AI Mode] 🔥 Hybrid OCR Engine initialized")
                    else:
                        hybrid_engine = None
                        print("[AI Mode] ⚠️ Hybrid OCR Engine failed, using standard OCR")
                except Exception as e:
                    print(f"[AI Mode] ⚠️ Hybrid OCR init error: {e}")
                    hybrid_engine = None
            
            web_y_offset = 0  # 複数画像の縦連結用オフセット

            for i, img in enumerate(web_images[:5]):
                try:
                    # 🔥 Hybrid OCR: Gemini補正を適用
                    if hybrid_engine:
                        self.status_label.configure(text=f"🔥 Hybrid OCR (Web {i+1}/{len(web_images[:5])})...")
                        self.update()
                    
                    clusters, raw_words = ocr_engine.extract_text(img)

                    for cluster in clusters:
                        # テキスト正規化（日本語スペース削除）
                        raw_text = cluster.get('text', '')
                        
                        # 🔥 Hybrid補正（長文のみ適用）
                        if hybrid_engine and len(raw_text) >= 20:
                            try:
                                corrected = hybrid_engine._call_gemini_correction(raw_text)
                                if corrected:
                                    raw_text = corrected
                            except:
                                pass
                        
                        normalized_text = self._normalize_japanese_text(raw_text)


                        if len(normalized_text) >= 5:
                            rect = cluster.get('rect', [0, 0, 100, 100])
                            # ★ 縦連結オフセットを追加
                            adjusted_rect = [
                                rect[0],
                                rect[1] + web_y_offset,
                                rect[2],
                                rect[3] + web_y_offset
                            ]
                            cluster_id = cluster.get('id', 0)
                            para_id = cluster.get('paragraph_id', f'P-{cluster_id}')
                            p = Paragraph(
                                id=f"W{i+1}_{para_id}",
                                text=normalized_text,
                                bbox=adjusted_rect,
                                page=i + 1,
                                column=0,
                                line_count=normalized_text.count("\n") + 1
                            )
                            web_paragraphs.append(p)

                    print(f"   Web page {i+1}: {len(clusters)} clusters → {len([c for c in clusters if len(self._normalize_japanese_text(c.get('text', ''))) >= 5])} paragraphs (engine_cloud, y_offset={web_y_offset})")

                    # 次ページ用のオフセット更新
                    web_y_offset += img.height

                except Exception as e:
                    print(f"   Web page {i+1} error: {e}")
                    import traceback
                    traceback.print_exc()

            # === PDF: 埋め込みテキスト優先 ===
            pdf_embedded_success = False
            BBOX_PADDING = 5  # 文字欠け防止用パディング (px)
            PDF_DPI = 300  # PDFローダーと同じDPI
            DPI_SCALE = PDF_DPI / 72.0  # PyMuPDF座標 → 画像座標の変換係数

            if pdf_file_path and os.path.exists(pdf_file_path):
                try:
                    doc = fitz.open(pdf_file_path)
                    total_chars = 0

                    # 縦オフセット（複数ページの縦連結対応）
                    y_offset = 0

                    for page_num in range(min(len(doc), 5)):
                        page = doc.load_page(page_num)
                        text_dict = page.get_text("dict")

                        # このページの画像サイズを計算
                        page_height_scaled = int(page.rect.height * DPI_SCALE)

                        # ★ PDFページを画像としてレンダリング（サムネイル用）
                        # DPI_SCALE (300/72 ≈ 4.17) に合わせてレンダリング
                        mat = fitz.Matrix(DPI_SCALE, DPI_SCALE)
                        pix = page.get_pixmap(matrix=mat)
                        img_data = pix.tobytes("png")
                        page_img = Image.open(io.BytesIO(img_data))
                        pdf_images.append(page_img)
                        print(f"   PDF page {page_num+1}: rendered {page_img.size}")

                        page_paragraphs = []
                        para_idx = 1

                        for block in text_dict.get("blocks", []):
                            if block.get("type") != 0:
                                continue

                            bbox = block.get("bbox", [])
                            if len(bbox) != 4:
                                continue

                            # bbox 拡張（文字欠け防止）
                            original_rect = fitz.Rect(bbox)
                            expanded_rect = fitz.Rect(
                                original_rect.x0 - BBOX_PADDING,
                                original_rect.y0 - BBOX_PADDING,
                                original_rect.x1 + BBOX_PADDING,
                                original_rect.y1 + BBOX_PADDING
                            )
                            clip_rect = expanded_rect & page.rect

                            block_text = page.get_text("text", clip=clip_rect).strip()

                            if len(block_text) >= 5:
                                # ★ bbox を画像座標系にスケーリング
                                scaled_bbox = [
                                    int(bbox[0] * DPI_SCALE),
                                    int(bbox[1] * DPI_SCALE + y_offset),  # 縦連結オフセット追加
                                    int(bbox[2] * DPI_SCALE),
                                    int(bbox[3] * DPI_SCALE + y_offset)
                                ]

                                p = Paragraph(
                                    id=f"P{page_num+1}_emb_{para_idx}",
                                    text=block_text,
                                    bbox=scaled_bbox,
                                    page=page_num + 1,
                                    column=0,
                                    line_count=block_text.count("\n") + 1
                                )
                                page_paragraphs.append(p)
                                total_chars += len(block_text)
                                para_idx += 1

                        pdf_paragraphs.extend(page_paragraphs)
                        print(f"   PDF page {page_num+1}: {len(page_paragraphs)} paragraphs (埋め込みテキスト, y_offset={y_offset})")

                        # 次ページ用の縦オフセットを更新
                        y_offset += page_height_scaled

                    doc.close()

                    if total_chars > 100:
                        pdf_embedded_success = True
                        print(f"[AI Mode] ✅ PDF埋め込みテキスト使用: {total_chars} chars, {len(pdf_paragraphs)} paragraphs (DPI scale: {DPI_SCALE:.2f})")

                except Exception as e:
                    print(f"[AI Mode] ⚠️ PDF埋め込みテキスト抽出エラー: {e}")
                    import traceback
                    traceback.print_exc()

            # === PDF: OCRフォールバック ===
            if not pdf_embedded_success:
                print("[AI Mode] 📸 PDF埋め込みテキストなし → OCRフォールバック")
                pdf_paragraphs = []
                pdf_ocr_y_offset = 0  # 複数画像の縦連結用オフセット

                for i, img in enumerate(pdf_images[:5]):
                    try:
                        clusters, _ = ocr_engine.extract_text(img)

                        for cluster in clusters:
                            raw_text = cluster.get('text', '')
                            if len(raw_text) >= 5:
                                rect = cluster.get('rect', [0, 0, 100, 100])
                                # ★ 縦連結オフセットを追加
                                adjusted_rect = [
                                    rect[0],
                                    rect[1] + pdf_ocr_y_offset,
                                    rect[2],
                                    rect[3] + pdf_ocr_y_offset
                                ]
                                cluster_id = cluster.get('id', 0)
                                para_id = cluster.get('paragraph_id', f'P-{cluster_id}')
                                p = Paragraph(
                                    id=f"P{i+1}_{para_id}",
                                    text=raw_text,
                                    bbox=adjusted_rect,
                                    page=i + 1,
                                    column=0,
                                    line_count=raw_text.count("\n") + 1
                                )
                                pdf_paragraphs.append(p)

                        print(f"   PDF page {i+1}: {len(clusters)} paragraphs (OCR, y_offset={pdf_ocr_y_offset})")

                        # 次ページ用のオフセット更新
                        pdf_ocr_y_offset += img.height

                    except Exception as e:
                        print(f"   PDF page {i+1} error: {e}")

            print(f"[AI Mode] Extracted - Web: {len(web_paragraphs)}, PDF: {len(pdf_paragraphs)}")

            # Step 3: パラグラフ間マッチング（テキスト類似度）
            self.status_label.configure(text="🤖 AI分析モード: マッチング中...")
            self.update()

            import difflib

            # ★★★ ID生成を単一関数に集約（根本原因修正）★★★
            def make_area_code(p: Paragraph) -> str:
                """パラグラフからarea_codeを生成する共通関数"""
                return f"Col{p.column}-{p.id}"

            sync_pairs = []
            used_pdf_ids = set()

            for wp in web_paragraphs:
                best_match = None
                best_score = 0.0

                for pp in pdf_paragraphs:
                    if pp.id in used_pdf_ids:
                        continue

                    # テキスト類似度計算
                    score = difflib.SequenceMatcher(None, wp.text, pp.text).ratio()

                    if score > best_score and score >= 0.2:  # 閾値20%
                        best_score = score
                        best_match = pp

                if best_match:
                    used_pdf_ids.add(best_match.id)

                    # SyncPair風オブジェクト作成（bbox含む）
                    class ParaSyncPair:
                        def __init__(self, web_p: Paragraph, pdf_p: Paragraph, sim: float):
                            # ★ 共通関数でID生成
                            self.web_id = make_area_code(web_p)
                            self.pdf_id = make_area_code(pdf_p)
                            self.similarity = sim
                            self.web_text = web_p.text
                            self.pdf_text = pdf_p.text
                            self.web_column = web_p.column
                            self.pdf_column = pdf_p.column
                            # ★ bbox追加（サムネイル用）
                            self.web_bbox = web_p.bbox
                            self.pdf_bbox = pdf_p.bbox

                    sync_pairs.append(ParaSyncPair(wp, best_match, best_score))

            # マッチしなかったものも追加（bbox含む）
            for wp in web_paragraphs:
                found = any(p.web_id.endswith(wp.id) for p in sync_pairs)
                if not found:
                    class UnmatchedPair:
                        def __init__(self, p: Paragraph, source: str):
                            # ★ 共通関数でID生成
                            self.web_id = make_area_code(p) if source == 'web' else ""
                            self.pdf_id = "" if source == 'web' else make_area_code(p)
                            self.similarity = 0.0
                            self.web_text = p.text if source == 'web' else ""
                            self.pdf_text = "" if source == 'web' else p.text
                            self.web_column = p.column if source == 'web' else -1
                            self.pdf_column = -1 if source == 'web' else p.column
                            # ★ bbox追加
                            self.web_bbox = p.bbox if source == 'web' else None
                            self.pdf_bbox = None if source == 'web' else p.bbox
                    sync_pairs.append(UnmatchedPair(wp, 'web'))

            for pp in pdf_paragraphs:
                if pp.id not in used_pdf_ids:
                    class UnmatchedPair:
                        def __init__(self, p: Paragraph, source: str):
                            # ★ 共通関数でID生成
                            self.web_id = make_area_code(p) if source == 'web' else ""
                            self.pdf_id = "" if source == 'web' else make_area_code(p)
                            self.similarity = 0.0
                            self.web_text = p.text if source == 'web' else ""
                            self.pdf_text = "" if source == 'web' else p.text
                            # ★ bbox追加
                            self.web_bbox = p.bbox if source == 'web' else None
                            self.pdf_bbox = None if source == 'web' else p.bbox
                    sync_pairs.append(UnmatchedPair(pp, 'pdf'))

            # 類似度降順ソート
            sync_pairs.sort(key=lambda x: x.similarity, reverse=True)

            print(f"[AI Mode] Matched: {len([p for p in sync_pairs if p.similarity > 0])} pairs")

            # Step 4: Region オブジェクト作成
            class ParaRegion:
                def __init__(self, p: Paragraph, source: str, sync_number: int = None, similarity: float = 0.0):
                    # ★ 共通関数でID生成（sync_pairs.web_id/pdf_idと同じ形式）
                    self.area_code = make_area_code(p)
                    self.id = make_area_code(p)  # ★ idもarea_codeと同じにして整合性確保
                    self.text = p.text
                    self.rect = p.bbox  # [x1, y1, x2, y2] - 画像座標系
                    self.similarity = similarity
                    self.column = p.column
                    self.source = source  # "web" or "pdf"
                    self.sync_number = sync_number  # マッチペアの番号
                    self.original_id = p.id  # 元のパラグラフID（デバッグ用）

            # ParaSyncPairからsimilarityとsync_numberを取得するマップ作成
            web_similarity_map = {}
            pdf_similarity_map = {}
            for i, pair in enumerate(sync_pairs):
                if pair.web_id and pair.similarity > 0:
                    web_similarity_map[pair.web_id] = (pair.similarity, i)
                if pair.pdf_id and pair.similarity > 0:
                    pdf_similarity_map[pair.pdf_id] = (pair.similarity, i)

            # Regionオブジェクト作成（similarityとsync_numberを紐付け）
            web_regions = []
            for p in web_paragraphs:
                area_code = f"Col{p.column}-{p.id}"
                sim, sync_num = web_similarity_map.get(area_code, (0.0, None))
                web_regions.append(ParaRegion(p, 'web', sync_num, sim))

            pdf_regions = []
            for p in pdf_paragraphs:
                # ★ 共通関数でarea_code生成
                area_code = make_area_code(p)
                sim, sync_num = pdf_similarity_map.get(area_code, (0.0, None))
                pdf_regions.append(ParaRegion(p, 'pdf', sync_num, sim))

            print(f"[AI Mode] Regions created - Web: {len(web_regions)}, PDF: {len(pdf_regions)}")

            # Step 5: LiveComparisonSheet表示
            view.sync_pairs = sync_pairs
            view.web_regions = web_regions
            view.pdf_regions = pdf_regions

            # ★ 画像を縦連結してサムネイル用に使用
            def stitch_images_vertically(images):
                """複数画像を縦連結"""
                if not images:
                    return None
                if len(images) == 1:
                    return images[0]

                # 最大幅を取得
                max_width = max(img.width for img in images)
                total_height = sum(img.height for img in images)

                # 新しい画像を作成
                stitched = Image.new('RGB', (max_width, total_height), (255, 255, 255))
                y_pos = 0
                for img in images:
                    stitched.paste(img, (0, y_pos))
                    y_pos += img.height

                return stitched

            stitched_web = stitch_images_vertically(web_images) if web_images else None
            stitched_pdf = stitch_images_vertically(pdf_images) if pdf_images else None

            # ★ view に画像を設定（他の機能との互換性のため）
            if stitched_web:
                view.web_image = stitched_web
            if stitched_pdf:
                view.pdf_image = stitched_pdf

            print(f"[AI Mode] Images - Web: {stitched_web.size if stitched_web else 'None'}, PDF: {stitched_pdf.size if stitched_pdf else 'None'}")
            print(f"[AI Mode] Regions - Web: {len(web_regions)}, PDF: {len(pdf_regions)}")
            print(f"[AI Mode] View state check:")
            print(f"  - web_canvas exists: {hasattr(view, 'web_canvas') and view.web_canvas is not None}")
            print(f"  - pdf_canvas exists: {hasattr(view, 'pdf_canvas') and view.pdf_canvas is not None}")
            print(f"  - spreadsheet_panel exists: {hasattr(view, 'spreadsheet_panel') and view.spreadsheet_panel is not None}")

            # デバッグ: 最初のいくつかのregionの座標を出力
            for i, r in enumerate(web_regions[:3]):
                print(f"  Web[{i}]: {r.area_code} rect={r.rect} sim={r.similarity:.2f}")
            for i, r in enumerate(pdf_regions[:3]):
                print(f"  PDF[{i}]: {r.area_code} rect={r.rect} sim={r.similarity:.2f}")

            # ★ 先にスプレッドシートを更新（これがキャンバスに影響しないように）
            if hasattr(view, 'spreadsheet_panel'):
                view.spreadsheet_panel.update_data(
                    sync_pairs,
                    web_regions,
                    pdf_regions,
                    stitched_web,
                    stitched_pdf
                )
                print(f"[AI Mode] Spreadsheet updated")

            # ★ タブを先に切り替え（キャンバスが表示状態でないと描画が反映されない可能性）
            try:
                if hasattr(view, 'view_tabs'):
                    view.view_tabs.set("Web Source")
                    view.update_idletasks()
                    view.update()
                    print(f"[AI Mode] Pre-switched to Web Source tab")
            except Exception as e:
                print(f"[AI Mode] Pre-tab switch warning: {e}")

            # ★ 全体マップに画像と領域を描画（スプレッドシート更新後）
            try:
                if hasattr(view, 'web_canvas') and view.web_canvas and stitched_web:
                    view._display_image(view.web_canvas, stitched_web)
                    # ★ PhotoImage参照をviewにも保持（GC防止）
                    view._web_photo_ref = view.web_canvas.image
                    print(f"[AI Mode] Web canvas displayed, scale={getattr(view.web_canvas, 'scale_x', 'N/A')}")

                # PDF描画前にタブ切り替え
                if hasattr(view, 'view_tabs'):
                    view.view_tabs.set("PDF Source")
                    view.update_idletasks()
                    view.update()

                if hasattr(view, 'pdf_canvas') and view.pdf_canvas and stitched_pdf:
                    view._display_image(view.pdf_canvas, stitched_pdf)
                    # ★ PhotoImage参照をviewにも保持（GC防止）
                    view._pdf_photo_ref = view.pdf_canvas.image
                    print(f"[AI Mode] PDF canvas displayed, scale={getattr(view.pdf_canvas, 'scale_x', 'N/A')}")

                # 最後にWebタブに戻す
                if hasattr(view, 'view_tabs'):
                    view.view_tabs.set("Web Source")
                    view.update_idletasks()
            except Exception as e:
                print(f"[AI Mode] Canvas display error: {e}")
                import traceback
                traceback.print_exc()

            # ★ 領域を再描画（ユニーク番号とシンクロカラー付き）
            try:
                if hasattr(view, '_redraw_regions'):
                    view._redraw_regions()
                    print(f"[AI Mode] Regions redrawn on canvas")
            except Exception as e:
                print(f"[AI Mode] Redraw error: {e}")
                import traceback
                traceback.print_exc()

            # ★ GUI強制更新（描画を確実に反映）
            view.update_idletasks()
            view.update()

            # ★ 描画中フラグを設定してConfigureイベント干渉を防止（Case2修正）
            view._display_in_progress = True

            # ★ 最終タブ切り替えとキャンバス更新
            try:
                if hasattr(view, 'view_tabs'):
                    view.view_tabs.set("Web Source")
                    view.update_idletasks()
                    if view.web_canvas:
                        view.web_canvas.update()
                        # キャンバスアイテム最終確認
                        all_items = view.web_canvas.find_all()
                        print(f"[AI Mode] Final web_canvas items: {len(all_items)}")
                    print(f"[AI Mode] Final tab switch to Web Source")
            except Exception as e:
                print(f"[AI Mode] Final tab switch warning: {e}")

            # ★ 300ms後に描画中フラグをクリア（Configureイベントのデバウンス100msより長い時間待つ）
            def _clear_display_flag():
                view._display_in_progress = False
                print(f"[AI Mode] Display in progress flag cleared")
            view.after(300, _clear_display_flag)

            if hasattr(view, 'sync_rate_label'):
                matched = [p for p in sync_pairs if p.similarity > 0]
                avg_sync = sum(p.similarity for p in matched) / len(matched) if matched else 0
                sync_percent = avg_sync * 100
                # 色分け: 50%以上=緑, 30%以上=橙, それ以下=赤
                color = "#4CAF50" if sync_percent >= 50 else "#FF9800" if sync_percent >= 30 else "#F44336"
                view.sync_rate_label.configure(text=f"Sync Rate: {sync_percent:.1f}%", text_color=color)

            # 完了
            matched_count = len([p for p in sync_pairs if p.similarity > 0])
            col0_web = len([p for p in web_paragraphs if p.column == 0])
            col1_web = len([p for p in web_paragraphs if p.column == 1])
            col0_pdf = len([p for p in pdf_paragraphs if p.column == 0])
            col1_pdf = len([p for p in pdf_paragraphs if p.column == 1])

            self.status_label.configure(
                text=f"✅ AI分析完了: Web[Col0:{col0_web}/Col1:{col1_web}] PDF[Col0:{col0_pdf}/Col1:{col1_pdf}] Match:{matched_count}"
            )

            print(f"[AI Mode] Done - Web columns: 0={col0_web}, 1={col1_web} | PDF columns: 0={col0_pdf}, 1={col1_pdf}")

            # ★ 遅延デバッグ: 500ms後にキャンバス状態を再確認
            def delayed_canvas_check():
                try:
                    if view.web_canvas:
                        all_items = view.web_canvas.find_all()
                        image_items = view.web_canvas.find_withtag("image")
                        region_items = view.web_canvas.find_withtag("region")
                        scroll_y = view.web_canvas.yview()
                        scroll_x = view.web_canvas.xview()
                        scrollregion = view.web_canvas.cget("scrollregion")
                        print(f"[AI Mode +500ms] web_canvas: total={len(all_items)}, images={len(image_items)}, regions={len(region_items)}")
                        print(f"[AI Mode +500ms] web_canvas scroll: xview={scroll_x}, yview={scroll_y}")
                        print(f"[AI Mode +500ms] web_canvas scrollregion={scrollregion}")
                        if hasattr(view.web_canvas, 'scale_x'):
                            print(f"[AI Mode +500ms] web_canvas scale_x={view.web_canvas.scale_x:.4f}")
                    if view.pdf_canvas:
                        all_items = view.pdf_canvas.find_all()
                        image_items = view.pdf_canvas.find_withtag("image")
                        region_items = view.pdf_canvas.find_withtag("region")
                        print(f"[AI Mode +500ms] pdf_canvas: total={len(all_items)}, images={len(image_items)}, regions={len(region_items)}")
                except Exception as e:
                    print(f"[AI Mode +500ms] Debug error: {e}")
            view.after(500, delayed_canvas_check)

        except Exception as e:
            self.status_label.configure(text=f"❌ AI分析エラー: {str(e)}")
            print(f"AI Analysis Error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """エントリーポイント"""
    print("=" * 60)
    print("🚀 MEKIKI Proofing System 起動中...")
    print("=" * 60)
    
    app = UnifiedApp()
    app.mainloop()


if __name__ == "__main__":
    main()
