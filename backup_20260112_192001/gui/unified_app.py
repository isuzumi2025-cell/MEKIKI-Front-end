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
        # ステータスバー
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color="#1A1A1A")
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="🔄 初期化中...",
            font=("Meiryo", 11),
            anchor="w"
        )
        self.status_label.pack(side="left", padx=10)
        
        self.server_indicator = ctk.CTkLabel(
            self.status_bar,
            text="● サーバー: 確認中",
            font=("Meiryo", 11),
            text_color="gray"
        )
        self.server_indicator.pack(side="right", padx=10)
        
        # メインコンテナ
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True)
        
        # 左サイドバー (Dashboard)
        self.sidebar = ctk.CTkFrame(self.main_container, width=250, fg_color="#1E1E1E")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        self._build_sidebar()
        
        # 右コンテンツエリア
        self.content = ctk.CTkFrame(self.main_container, fg_color="#2B2B2B")
        self.content.pack(side="left", fill="both", expand=True)
        
        self._show_welcome()
    
    def _build_sidebar(self):
        """サイドバー構築"""
        # ロゴ/タイトル
        header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=20)
        
        ctk.CTkLabel(
            header,
            text="🎯 MEKIKI",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack()
        
        ctk.CTkLabel(
            header,
            text="Multimodal Comparison Tool",
            font=("Meiryo", 10),
            text_color="gray"
        ).pack()
        
        # セパレーター
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray").pack(fill="x", padx=10, pady=10)
        
        # ナビゲーションボタン
        nav_buttons = [
            ("📊 ダッシュボード", self._show_dashboard),
            ("🗺️ サイトマップ", self._show_sitemap_viewer),
            ("⚖️ 比較マトリクス", self._show_comparison_matrix),
            ("🔬 詳細検査", self._show_detail_inspector),
            ("📝 レポート編集", self._show_report_editor),
        ]
        
        for text, command in nav_buttons:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                command=command,
                anchor="w",
                height=40,
                font=("Meiryo", 12),
                fg_color="transparent",
                hover_color="#3A3A3A",
                text_color="white"
            )
            btn.pack(fill="x", padx=10, pady=2)
        
        # セパレーター
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray").pack(fill="x", padx=10, pady=20)
        
        # アクションボタン
        ctk.CTkButton(
            self.sidebar,
            text="➕ 新規クロール",
            command=self._start_new_crawl,
            height=45,
            font=("Meiryo", 13, "bold"),
            fg_color="#FF6F00"
        ).pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(
            self.sidebar,
            text="📂 PDF読込",
            command=self._load_pdf,
            height=40,
            font=("Meiryo", 12),
            fg_color="#2196F3"
        ).pack(fill="x", padx=10, pady=5)
        
        # セパレーター
        ctk.CTkFrame(self.sidebar, height=2, fg_color="gray").pack(fill="x", padx=10, pady=10)
        
        # ワークフローアクションボタン (Phase 4 UI統合)
        ctk.CTkButton(
            self.sidebar,
            text="🔄 OCR実行",
            command=self._run_ocr_from_sidebar,
            height=35,
            font=("Meiryo", 11),
            fg_color="#FF6F00"
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            self.sidebar,
            text="🔍 全文比較",
            command=self._run_text_comparison_from_sidebar,
            height=35,
            font=("Meiryo", 11),
            fg_color="#00BCD4"
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            self.sidebar,
            text="📊 比較シート",
            command=self._open_comparison_sheet_from_sidebar,
            height=35,
            font=("Meiryo", 11),
            fg_color="#9C27B0"
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            self.sidebar,
            text="📊 Excel出力",
            command=self._export_excel_from_sidebar,
            height=35,
            font=("Meiryo", 11),
            fg_color="#4CAF50"
        ).pack(fill="x", padx=10, pady=3)
        
        # サーバー制御 (下部)
        server_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        server_frame.pack(side="bottom", fill="x", padx=10, pady=20)
        
        ctk.CTkButton(
            server_frame,
            text="🌐 サーバー起動",
            command=self._toggle_server,
            height=35,
            font=("Meiryo", 11),
            fg_color="#616161"
        ).pack(fill="x", pady=2)
        
        ctk.CTkButton(
            server_frame,
            text="🔗 Web UI を開く",
            command=self._open_web_ui,
            height=35,
            font=("Meiryo", 11),
            fg_color="#37474F"
        ).pack(fill="x", pady=2)
    
    def _show_welcome(self):
        """ウェルカム画面"""
        self._clear_content()
        
        welcome = ctk.CTkFrame(self.content, fg_color="transparent")
        welcome.pack(fill="both", expand=True)
        
        center = ctk.CTkFrame(welcome, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(
            center,
            text="🎯 MEKIKI Proofing System",
            font=("Meiryo", 28, "bold"),
            text_color="#4CAF50"
        ).pack(pady=20)
        
        ctk.CTkLabel(
            center,
            text="Web × PDF 高精度比較ツール",
            font=("Meiryo", 14),
            text_color="gray"
        ).pack(pady=10)
        
        ctk.CTkLabel(
            center,
            text="左のメニューから操作を選択するか、\n「新規クロール」で分析を開始してください",
            font=("Meiryo", 12),
            text_color="gray"
        ).pack(pady=30)
    
    def _clear_content(self):
        """コンテンツエリアをクリア"""
        for widget in self.content.winfo_children():
            widget.destroy()
    
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
        """新規クロール開始 - スタンドアローン版"""
        # クロールダイアログ
        dialog = ctk.CTkToplevel(self)
        dialog.title("🌐 新規クロール")
        dialog.geometry("500x620")  # 高さを増加 (プロファイル管理UI追加のため)
        dialog.transient(self)
        dialog.grab_set()
        
        # URL入力
        ctk.CTkLabel(dialog, text="開始URL:", font=("Meiryo", 12)).pack(pady=(20, 5))
        url_entry = ctk.CTkEntry(dialog, width=400, placeholder_text="https://example.com")
        url_entry.pack(pady=5)
        
        # 設定フレーム
        settings_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        settings_frame.pack(pady=20)
        
        # 最大ページ数
        ctk.CTkLabel(settings_frame, text="最大ページ:").grid(row=0, column=0, padx=10)
        max_pages_var = ctk.StringVar(value="10")
        ctk.CTkEntry(settings_frame, width=80, textvariable=max_pages_var).grid(row=0, column=1)
        
        # 最大深度
        ctk.CTkLabel(settings_frame, text="最大深度:").grid(row=0, column=2, padx=10)
        max_depth_var = ctk.StringVar(value="2")
        ctk.CTkEntry(settings_frame, width=80, textvariable=max_depth_var).grid(row=0, column=3)
        
        # Basic認証 (プロファイル管理付き)
        auth_frame = ctk.CTkFrame(dialog, fg_color="#2D2D2D", corner_radius=10)
        auth_frame.pack(pady=10, padx=20, fill="x")
        
        use_auth_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(auth_frame, text="Basic認証を使用", variable=use_auth_var).pack(anchor="w", padx=10, pady=5)
        
        # プロファイル選択
        from app.core.auth_manager import get_auth_manager
        auth_manager = get_auth_manager()
        
        profile_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        profile_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(profile_frame, text="プロファイル:").pack(side="left")
        profile_names = ["-- 新規 --"] + auth_manager.get_profile_names()
        profile_var = ctk.StringVar(value="-- 新規 --")
        profile_dropdown = ctk.CTkOptionMenu(
            profile_frame, 
            values=profile_names, 
            variable=profile_var,
            width=150
        )
        profile_dropdown.pack(side="left", padx=5)
        
        def on_profile_select(choice):
            if choice != "-- 新規 --":
                profile = auth_manager.get_profile(choice)
                if profile:
                    url_entry.delete(0, "end")
                    url_entry.insert(0, profile.url)
                    username_entry.delete(0, "end")
                    username_entry.insert(0, profile.username)
                    password_entry.delete(0, "end")
                    password_entry.insert(0, profile.password)
                    use_auth_var.set(True)
        
        profile_dropdown.configure(command=on_profile_select)
        
        # プロファイル保存/削除ボタン
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
            # ドロップダウン更新
            profile_dropdown.configure(values=["-- 新規 --"] + auth_manager.get_profile_names())
            profile_var.set(username)
        
        def delete_profile():
            name = profile_var.get()
            if name == "-- 新規 --":
                return
            if messagebox.askyesno("確認", f"プロファイル「{name}」を削除しますか？"):
                auth_manager.delete_profile(name)
                profile_dropdown.configure(values=["-- 新規 --"] + auth_manager.get_profile_names())
                profile_var.set("-- 新規 --")
                username_entry.delete(0, "end")
                password_entry.delete(0, "end")
        
        # プロファイルボタン（シンメトリーレイアウト、同サイズ）
        btn_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        btn_frame.pack(pady=5)
        
        btn_width = 50
        btn_height = 40
        icon_font = ("Segoe UI Emoji", 20)
        ctk.CTkButton(btn_frame, text="💾", width=btn_width, height=btn_height, 
                     command=save_profile, fg_color="#4CAF50", hover_color="#388E3C",
                     anchor="center", font=icon_font).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🗑️", width=btn_width, height=btn_height,
                     command=delete_profile, fg_color="#F44336", hover_color="#D32F2F",
                     anchor="center", font=icon_font).pack(side="left", padx=5)
        
        ctk.CTkLabel(auth_frame, text="ユーザー名:").pack(anchor="w", padx=10)
        username_entry = ctk.CTkEntry(auth_frame, width=300)
        username_entry.pack(padx=10, pady=2)
        
        # パスワード入力 (表示/非表示トグル付き)
        pass_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        pass_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(pass_frame, text="パスワード:").pack(anchor="w")
        
        pass_input_frame = ctk.CTkFrame(auth_frame, fg_color="transparent")
        pass_input_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        password_entry = ctk.CTkEntry(pass_input_frame, width=260, show="*")
        password_entry.pack(side="left")
        
        show_pass_var = ctk.BooleanVar(value=False)
        def toggle_password():
            if show_pass_var.get():
                password_entry.configure(show="")
                pass_toggle_btn.configure(text="🙈")
            else:
                password_entry.configure(show="*")
                pass_toggle_btn.configure(text="👁️")
            show_pass_var.set(not show_pass_var.get())
        
        pass_toggle_btn = ctk.CTkButton(pass_input_frame, text="👁️", width=btn_width, height=btn_height,
                                        command=toggle_password, fg_color="#616161", hover_color="#757575",
                                        anchor="center", font=icon_font)
        pass_toggle_btn.pack(side="left", padx=5)
        
        # 進捗表示
        progress_label = ctk.CTkLabel(dialog, text="", font=("Meiryo", 10), text_color="gray")
        progress_label.pack(pady=10)
        
        def run_crawl():
            url = url_entry.get().strip()
            if not url:
                messagebox.showwarning("警告", "URLを入力してください")
                return
            
            max_pages = int(max_pages_var.get() or 10)
            max_depth = int(max_depth_var.get() or 2)
            username = username_entry.get() if use_auth_var.get() else None
            password = password_entry.get() if use_auth_var.get() else None
            
            # Debug: 認証情報確認
            print(f"[Crawl] use_auth_var: {use_auth_var.get()}")
            print(f"[Crawl] username: {username}, password: {'***' if password else 'None'}")
            
            progress_label.configure(text="🚀 クロール中...")
            dialog.update()
            
            def crawl_thread():
                try:
                    from app.core.standalone_scraper import StandaloneScraper
                    
                    scraper = StandaloneScraper(headless=True)
                    
                    def progress_cb(current_url, current, total):
                        self.after(0, lambda: progress_label.configure(
                            text=f"📄 {current}/{total}: {current_url[:40]}..."
                        ))
                    
                    results = scraper.crawl(
                        start_url=url,
                        max_pages=max_pages,
                        max_depth=max_depth,
                        username=username,
                        password=password,
                        progress_callback=progress_cb
                    )
                    
                    # 結果を比較キューに追加
                    for r in results:
                        if not r.error:
                            self.comparison_queue.append({
                                'type': 'web',
                                'url': r.url,
                                'text_content': r.text_content,
                                'screenshot_base64': r.screenshot_base64,
                                'title': r.title,
                                'status_code': r.status_code,
                                'depth': r.depth
                            })
                    
                    # ローカルページデータとして保存
                    self.local_pages = scraper.get_results_as_dict_list(results)
                    
                    self.after(0, lambda: self._on_crawl_complete(len(results)))
                    self.after(0, dialog.destroy)
                    
                except Exception as e:
                    err_msg = str(e)  # Capture before lambda
                    self.after(0, lambda m=err_msg: messagebox.showerror("エラー", f"クロールエラー: {m}"))
                    self.after(0, lambda m=err_msg: progress_label.configure(text=f"❌ エラー: {m}"))
            
            import threading
            threading.Thread(target=crawl_thread, daemon=True).start()
        
        # ボタン
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame, text="🚀 クロール開始", fg_color="#FF6F00", width=150,
            command=run_crawl
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, text="キャンセル", fg_color="#616161", width=100,
            command=dialog.destroy
        ).pack(side="left", padx=10)
    
    def _on_crawl_complete(self, page_count: int):
        """クロール完了時"""
        self.status_label.configure(text=f"✅ クロール完了: {page_count} ページ")
        messagebox.showinfo("完了", f"クロール完了: {page_count} ページ\n\n比較キューに追加しました。\n「⚖️ 比較マトリクス」を開いてください。")
    
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
        
        file_name = Path(file_path).name
        self.status_label.configure(text=f"📄 PDF読込中: {file_name}...")
        self.update()
        
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            
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
                
                self.status_label.configure(
                    text=f"📄 PDF読込中: {page_num + 1}/{page_count}ページ"
                )
                self.update()
            
            doc.close()
            
            # 最初のページをcurrent_pdf_imageに設定
            if self.selected_pdf_pages:
                self.current_pdf_image = self.selected_pdf_pages[0]
            
            self.status_label.configure(
                text=f"✅ PDF読込完了: {file_name} ({page_count}ページ)"
            )
            messagebox.showinfo(
                "PDF読込完了", 
                f"{page_count}ページを読み込みました。\n\n「⚖️ 比較マトリクス」を開いて確認してください。"
            )
            
        except Exception as e:
            self.status_label.configure(text=f"❌ PDF読込エラー: {e}")
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


def main():
    """エントリーポイント"""
    print("=" * 60)
    print("🚀 MEKIKI Proofing System 起動中...")
    print("=" * 60)
    
    app = UnifiedApp()
    app.mainloop()


if __name__ == "__main__":
    main()
