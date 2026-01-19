"""
ダッシュボードビュー
プロファイル管理、ジョブ履歴、システム状態を表示
"""
import customtkinter as ctk
from typing import Optional, Dict, List, Callable
from datetime import datetime


class DashboardView(ctk.CTkFrame):
    """ダッシュボード - メインナビゲーション画面"""
    
    def __init__(self, parent, api_client, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.api_client = api_client
        
        self._build_ui()
        self._refresh_data()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="📊 ダッシュボード",
            font=("Meiryo", 18, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=20, pady=15)
        
        refresh_btn = ctk.CTkButton(
            header,
            text="🔄 更新",
            command=self._refresh_data,
            width=80,
            height=35,
            fg_color="#616161"
        )
        refresh_btn.pack(side="right", padx=20, pady=12)
        
        # コンテンツ (2カラム)
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 左カラム: プロファイル
        left_col = ctk.CTkFrame(content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self._build_profiles_section(left_col)
        
        # 右カラム: ジョブ履歴
        right_col = ctk.CTkFrame(content, fg_color="transparent")
        right_col.pack(side="left", fill="both", expand=True, padx=(10, 0))
        
        self._build_jobs_section(right_col)
    
    def _build_profiles_section(self, parent):
        """プロファイルセクション"""
        section = ctk.CTkFrame(parent, fg_color="#2D2D2D", corner_radius=10)
        section.pack(fill="both", expand=True)
        
        # ヘッダー
        header = ctk.CTkFrame(section, fg_color="#383838", corner_radius=10)
        header.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            header,
            text="👤 プロファイル",
            font=("Meiryo", 14, "bold")
        ).pack(side="left", padx=15, pady=10)
        
        ctk.CTkButton(
            header,
            text="➕ 新規",
            width=60,
            height=30,
            fg_color="#4CAF50",
            command=self._add_profile
        ).pack(side="right", padx=10, pady=8)
        
        # リスト
        self.profiles_frame = ctk.CTkScrollableFrame(
            section,
            fg_color="transparent",
            scrollbar_fg_color="#3A3A3A"
        )
        self.profiles_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _build_jobs_section(self, parent):
        """ジョブ履歴セクション"""
        section = ctk.CTkFrame(parent, fg_color="#2D2D2D", corner_radius=10)
        section.pack(fill="both", expand=True)
        
        # ヘッダー
        header = ctk.CTkFrame(section, fg_color="#383838", corner_radius=10)
        header.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(
            header,
            text="📋 ジョブ履歴",
            font=("Meiryo", 14, "bold")
        ).pack(side="left", padx=15, pady=10)
        
        # リスト
        self.jobs_frame = ctk.CTkScrollableFrame(
            section,
            fg_color="transparent",
            scrollbar_fg_color="#3A3A3A"
        )
        self.jobs_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _refresh_data(self):
        """データを更新"""
        self._load_profiles()
        self._load_jobs()
    
    def _load_profiles(self):
        """プロファイル一覧を読み込み"""
        # クリア
        for widget in self.profiles_frame.winfo_children():
            widget.destroy()
        
        profiles = self.api_client.get_profiles()
        
        if not profiles:
            ctk.CTkLabel(
                self.profiles_frame,
                text="プロファイルがありません\nサーバーに接続できないか、\nプロファイルが未作成です",
                font=("Meiryo", 11),
                text_color="gray"
            ).pack(pady=30)
            return
        
        for profile in profiles:
            self._create_profile_card(profile)
    
    def _create_profile_card(self, profile: Dict):
        """プロファイルカードを作成"""
        card = ctk.CTkFrame(self.profiles_frame, fg_color="#3A3A3A", corner_radius=8)
        card.pack(fill="x", pady=5)
        
        # 左側: 情報
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        ctk.CTkLabel(
            info,
            text=profile.get("name", "無名"),
            font=("Meiryo", 13, "bold"),
            anchor="w"
        ).pack(fill="x")
        
        url = profile.get("root_url", "")
        if len(url) > 50:
            url = url[:50] + "..."
        ctk.CTkLabel(
            info,
            text=url,
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w"
        ).pack(fill="x")
        
        # 認証バッジ
        auth = profile.get("auth_user")
        if auth:
            ctk.CTkLabel(
                info,
                text=f"🔐 {auth}",
                font=("Meiryo", 10),
                text_color="#FF9800",
                anchor="w"
            ).pack(fill="x")
        
        # 右側: アクション
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(side="right", padx=10, pady=10)
        
        ctk.CTkButton(
            actions,
            text="▶️ 実行",
            width=60,
            height=28,
            fg_color="#FF6F00",
            command=lambda: self._run_profile(profile)
        ).pack(side="left", padx=2)
    
    def _load_jobs(self):
        """ジョブ一覧を読み込み"""
        # クリア
        for widget in self.jobs_frame.winfo_children():
            widget.destroy()
        
        jobs = self.api_client.get_jobs(limit=20)
        
        if not jobs:
            ctk.CTkLabel(
                self.jobs_frame,
                text="ジョブ履歴がありません",
                font=("Meiryo", 11),
                text_color="gray"
            ).pack(pady=30)
            return
        
        for job in jobs:
            self._create_job_card(job)
    
    def _create_job_card(self, job: Dict):
        """ジョブカードを作成"""
        card = ctk.CTkFrame(self.jobs_frame, fg_color="#3A3A3A", corner_radius=8)
        card.pack(fill="x", pady=5)
        
        # ステータスに応じた色
        status = job.get("status", "unknown")
        status_colors = {
            "completed": "#4CAF50",
            "running": "#2196F3",
            "failed": "#F44336",
            "pending": "#FFC107"
        }
        color = status_colors.get(status, "gray")
        
        # 左側: ステータスインジケーター
        indicator = ctk.CTkLabel(
            card,
            text="●",
            font=("Meiryo", 16),
            text_color=color,
            width=30
        )
        indicator.pack(side="left", padx=10)
        
        # 中央: 情報
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=10)
        
        # タイトル (ID + 状態)
        title = f"Job #{job.get('id', '?')} - {status}"
        ctk.CTkLabel(
            info,
            text=title,
            font=("Meiryo", 12, "bold"),
            anchor="w"
        ).pack(fill="x")
        
        # 詳細
        pages = job.get("pages_crawled", 0)
        errors = job.get("errors_count", 0)
        detail = f"📄 {pages} ページ"
        if errors > 0:
            detail += f"  ⚠️ {errors} エラー"
        
        ctk.CTkLabel(
            info,
            text=detail,
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w"
        ).pack(fill="x")
        
        # 右側: アクション
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(side="right", padx=10, pady=10)
        
        if status == "completed":
            ctk.CTkButton(
                actions,
                text="📊 表示",
                width=60,
                height=28,
                fg_color="#2196F3",
                command=lambda: self._view_job(job)
            ).pack(side="left", padx=2)
    
    def _add_profile(self):
        """プロファイル追加"""
        # TODO: プロファイル作成ダイアログ
        from tkinter import messagebox
        messagebox.showinfo("プロファイル追加", "sitemap_pro Web UIで追加してください\nhttp://localhost:8000")
    
    def _run_profile(self, profile: Dict):
        """プロファイルを実行"""
        profile_id = profile.get("id")
        if profile_id:
            result = self.api_client.create_job(profile_id)
            if result:
                from tkinter import messagebox
                messagebox.showinfo("ジョブ開始", f"Job #{result.get('id')} を開始しました")
                self._refresh_data()
    
    def _view_job(self, job: Dict):
        """ジョブを表示"""
        # TODO: サイトマップビューワーで表示
        from tkinter import messagebox
        messagebox.showinfo("ジョブ表示", f"Job #{job.get('id')} の詳細表示はサイトマップビューワーで実装予定")
