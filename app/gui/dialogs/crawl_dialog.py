"""
Crawl Dialog Module
新規クロールダイアログ（洗練版）
"""
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Callable, Dict


class CrawlDialog(ctk.CTkToplevel):
    """
    新規クロールダイアログ
    URL指定、認証設定、プロファイル管理
    """
    
    def __init__(
        self,
        master,
        on_crawl: Optional[Callable] = None,
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            on_crawl: クロール開始時のコールバック
        """
        super().__init__(master, **kwargs)
        
        self.on_crawl = on_crawl
        self.result: Optional[Dict] = None
        
        # ウィンドウ設定
        self.title("🌐 新規クロール")
        self.geometry("500x600")
        self.resizable(False, False)
        
        # モーダルに設定
        self.transient(master)
        self.grab_set()
        
        self._build_ui()
        
        # 中央に配置
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f"+{x}+{y}")
    
    def _build_ui(self):
        """UI構築"""
        # メインコンテンツ
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # URL入力
        ctk.CTkLabel(
            content,
            text="開始URL:",
            font=("Meiryo", 11),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        self.url_entry = ctk.CTkEntry(
            content,
            placeholder_text="https://example.com",
            font=("Meiryo", 11),
            height=40
        )
        self.url_entry.pack(fill="x", pady=(0, 15))
        
        # クロール設定
        settings_frame = ctk.CTkFrame(content, fg_color="transparent")
        settings_frame.pack(fill="x", pady=10)
        
        # 最大ページ数
        page_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        page_frame.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        ctk.CTkLabel(page_frame, text="最大ページ:", font=("Meiryo", 10)).pack(anchor="w")
        self.max_pages_entry = ctk.CTkEntry(page_frame, width=80, height=35)
        self.max_pages_entry.insert(0, "10")
        self.max_pages_entry.pack(side="left")
        
        # 最大深度
        depth_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        depth_frame.pack(side="left", expand=True, fill="x", padx=(5, 0))
        
        ctk.CTkLabel(depth_frame, text="最大深度:", font=("Meiryo", 10)).pack(anchor="w")
        self.max_depth_entry = ctk.CTkEntry(depth_frame, width=80, height=35)
        self.max_depth_entry.insert(0, "2")
        self.max_depth_entry.pack(side="left")
        
        # === Basic認証セクション ===
        auth_section = ctk.CTkFrame(content, fg_color="#2D2D2D", corner_radius=10)
        auth_section.pack(fill="x", pady=15, padx=0)
        
        self.use_auth_checkbox = ctk.CTkCheckBox(
            auth_section,
            text="Basic認証を使用",
            font=("Meiryo", 11),
            command=self._toggle_auth_fields
        )
        self.use_auth_checkbox.pack(anchor="w", padx=15, pady=10)
        
        # プロファイル選択
        profile_frame = ctk.CTkFrame(auth_section, fg_color="transparent")
        profile_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(profile_frame, text="プロファイル:", font=("Meiryo", 10), width=80).pack(side="left")
        
        self.profile_dropdown = ctk.CTkComboBox(
            profile_frame,
            values=["(新規入力)"],
            font=("Meiryo", 11),
            height=35,
            state="disabled",
            command=self._on_profile_select
        )
        self.profile_dropdown.pack(side="left", fill="x", expand=True, padx=5)
        
        self.save_profile_btn = ctk.CTkButton(
            profile_frame,
            text="💾",
            command=self._save_current_profile,
            width=40,
            height=35,
            fg_color="#4CAF50",
            state="disabled"
        )
        self.save_profile_btn.pack(side="left", padx=2)
        
        self.delete_profile_btn = ctk.CTkButton(
            profile_frame,
            text="🗑️",
            command=self._delete_current_profile,
            width=40,
            height=35,
            fg_color="#EF4444",
            state="disabled"
        )
        self.delete_profile_btn.pack(side="left", padx=2)
        
        # ユーザー名
        username_frame = ctk.CTkFrame(auth_section, fg_color="transparent")
        username_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(username_frame, text="ユーザー名:", font=("Meiryo", 10), width=80).pack(side="left")
        
        self.username_entry = ctk.CTkEntry(
            username_frame,
            placeholder_text="username",
            font=("Meiryo", 11),
            height=35,
            state="disabled"
        )
        self.username_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # パスワード
        password_frame = ctk.CTkFrame(auth_section, fg_color="transparent")
        password_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkLabel(password_frame, text="パスワード:", font=("Meiryo", 10), width=80).pack(side="left")
        
        self.password_entry = ctk.CTkEntry(
            password_frame,
            placeholder_text="password",
            font=("Meiryo", 11),
            height=35,
            show="*",
            state="disabled"
        )
        self.password_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        self.show_password_btn = ctk.CTkButton(
            password_frame,
            text="👁",
            command=self._toggle_password_visibility,
            width=40,
            height=35,
            fg_color="gray",
            state="disabled"
        )
        self.show_password_btn.pack(side="left", padx=2)
        
        self._password_visible = False
        
        # プロファイル読み込み
        self._load_profile_list()
        
        # プログレス表示
        self.progress_label = ctk.CTkLabel(
            content,
            text="",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.progress_label.pack(fill="x", pady=10)
        
        # ボタン
        button_frame = ctk.CTkFrame(content, fg_color="transparent")
        button_frame.pack(fill="x", pady=20)
        
        ctk.CTkButton(
            button_frame,
            text="🚀 クロール開始",
            command=self._on_start_crawl,
            width=200,
            height=45,
            font=("Meiryo", 13, "bold"),
            fg_color="#FF6B35"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="キャンセル",
            command=self._on_cancel,
            width=120,
            height=45,
            fg_color="gray"
        ).pack(side="left", padx=5)
    
    def _toggle_auth_fields(self):
        """認証フィールドの有効/無効を切り替え"""
        if self.use_auth_checkbox.get():
            self.username_entry.configure(state="normal")
            self.password_entry.configure(state="normal")
            self.profile_dropdown.configure(state="normal")
            self.save_profile_btn.configure(state="normal")
            self.delete_profile_btn.configure(state="normal")
            self.show_password_btn.configure(state="normal")
        else:
            self.username_entry.configure(state="disabled")
            self.password_entry.configure(state="disabled")
            self.profile_dropdown.configure(state="disabled")
            self.save_profile_btn.configure(state="disabled")
            self.delete_profile_btn.configure(state="disabled")
            self.show_password_btn.configure(state="disabled")
    
    def _toggle_password_visibility(self):
        """パスワード表示/非表示切り替え"""
        self._password_visible = not self._password_visible
        if self._password_visible:
            self.password_entry.configure(show="")
            self.show_password_btn.configure(text="🔒")
        else:
            self.password_entry.configure(show="*")
            self.show_password_btn.configure(text="👁")
    
    def _load_profile_list(self):
        """プロファイル一覧を読み込み"""
        try:
            from app.core.auth_manager import get_auth_manager
            manager = get_auth_manager()
            names = manager.get_profile_names()
            
            values = ["(新規入力)"] + names
            self.profile_dropdown.configure(values=values)
            self.profile_dropdown.set("(新規入力)")
        except Exception as e:
            print(f"⚠️ プロファイル読み込みエラー: {e}")
    
    def _on_profile_select(self, selected):
        """プロファイル選択時"""
        if selected == "(新規入力)":
            self.username_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            return
        
        try:
            from app.core.auth_manager import get_auth_manager
            manager = get_auth_manager()
            profile = manager.get_profile(selected)
            
            if profile:
                self.username_entry.delete(0, "end")
                self.username_entry.insert(0, profile.username)
                self.password_entry.delete(0, "end")
                self.password_entry.insert(0, profile.password)
                
                if profile.url and not self.url_entry.get().strip():
                    self.url_entry.delete(0, "end")
                    self.url_entry.insert(0, profile.url)
        except Exception as e:
            print(f"⚠️ プロファイル読み込みエラー: {e}")
    
    def _save_current_profile(self):
        """現在の認証情報をプロファイルとして保存"""
        from tkinter import simpledialog
        
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        url = self.url_entry.get().strip()
        
        if not username or not password:
            messagebox.showwarning("入力エラー", "ユーザー名とパスワードを入力してください")
            return
        
        profile_name = simpledialog.askstring(
            "プロファイル保存",
            "プロファイル名を入力してください:",
            parent=self
        )
        
        if not profile_name:
            return
        
        try:
            from app.core.auth_manager import get_auth_manager, AuthProfile
            manager = get_auth_manager()
            
            profile = AuthProfile(
                name=profile_name,
                url=url,
                username=username,
                password=password,
                auth_type="basic"
            )
            
            if manager.add_profile(profile):
                messagebox.showinfo("完了", f"プロファイル「{profile_name}」を保存しました")
                self._load_profile_list()
                self.profile_dropdown.set(profile_name)
            else:
                if messagebox.askyesno("確認", f"「{profile_name}」は既に存在します。上書きしますか？"):
                    manager.update_profile(profile_name, profile)
                    messagebox.showinfo("完了", f"プロファイル「{profile_name}」を更新しました")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました: {e}")
    
    def _delete_current_profile(self):
        """選択中のプロファイルを削除"""
        selected = self.profile_dropdown.get()
        if selected == "(新規入力)":
            return
        
        if not messagebox.askyesno("確認", f"プロファイル「{selected}」を削除しますか？"):
            return
        
        try:
            from app.core.auth_manager import get_auth_manager
            manager = get_auth_manager()
            
            if manager.delete_profile(selected):
                messagebox.showinfo("完了", f"プロファイル「{selected}」を削除しました")
                self._load_profile_list()
                self.username_entry.delete(0, "end")
                self.password_entry.delete(0, "end")
        except Exception as e:
            messagebox.showerror("エラー", f"削除に失敗しました: {e}")
    
    def _on_start_crawl(self):
        """クロール開始"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("入力エラー", "URLを入力してください")
            return
        
        try:
            max_pages = int(self.max_pages_entry.get() or "10")
            max_depth = int(self.max_depth_entry.get() or "2")
        except ValueError:
            messagebox.showerror("エラー", "数値の形式が正しくありません")
            return
        
        use_auth = self.use_auth_checkbox.get()
        
        self.result = {
            "url": url,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "use_auth": use_auth,
            "username": self.username_entry.get().strip() if use_auth else None,
            "password": self.password_entry.get().strip() if use_auth else None
        }
        
        if self.on_crawl:
            self.on_crawl(self.result)
        
        self.destroy()
    
    def _on_cancel(self):
        """キャンセル"""
        self.result = None
        self.destroy()
    
    def update_progress(self, text: str):
        """プログレス更新"""
        self.progress_label.configure(text=text)
        self.update()
