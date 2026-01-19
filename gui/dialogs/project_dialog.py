"""
Project Dialog Module
新規プロジェクト作成ダイアログ
"""
import customtkinter as ctk
from tkinter import filedialog
from typing import Optional, Callable, Dict


class ProjectDialog(ctk.CTkToplevel):
    """
    新規プロジェクト作成ダイアログ
    URLとPDF指定、分析設定を行う
    """
    
    def __init__(
        self,
        master,
        on_start: Optional[Callable] = None,
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            on_start: 分析開始時のコールバック
        """
        super().__init__(master, **kwargs)
        
        self.on_start = on_start
        self.result: Optional[Dict] = None
        
        # ウィンドウ設定
        self.title("➕ 新規プロジェクト作成")
        self.geometry("700x650")
        self.resizable(False, False)
        
        # モーダルに設定
        self.transient(master)
        self.grab_set()
        
        self._build_ui()
        
        # 中央に配置
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (700 // 2)
        y = (self.winfo_screenheight() // 2) - (650 // 2)
        self.geometry(f"+{x}+{y}")
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="➕ 新規プロジェクト作成",
            font=("Meiryo", 20, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=20, pady=20)
        
        ctk.CTkLabel(
            header,
            text="URLとPDFを指定して分析を開始します",
            font=("Meiryo", 11),
            text_color="gray"
        ).pack(side="left", padx=20)
        
        # スクロール可能なコンテンツエリア
        content = ctk.CTkScrollableFrame(self)
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # === Web設定 ===
        self._build_web_section(content)
        
        # セパレーター
        ctk.CTkFrame(content, height=2, fg_color="gray").pack(fill="x", pady=15)
        
        # === PDF設定 ===
        self._build_pdf_section(content)
        
        # セパレーター
        ctk.CTkFrame(content, height=2, fg_color="gray").pack(fill="x", pady=15)
        
        # === 詳細設定 ===
        self._build_advanced_section(content)
        
        # ボタンエリア
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(
            button_frame,
            text="✖ キャンセル",
            command=self._on_cancel,
            width=150,
            height=40,
            fg_color="gray"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="🚀 分析開始",
            command=self._on_start_analysis,
            width=200,
            height=40,
            font=("Meiryo", 13, "bold"),
            fg_color="#4CAF50"
        ).pack(side="right", padx=5)
    
    def _build_web_section(self, parent):
        """Web設定セクション"""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=10)
        
        # セクションヘッダー
        ctk.CTkLabel(
            section,
            text="🌐 Web設定",
            font=("Meiryo", 14, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 10))
        
        # URL入力
        url_frame = ctk.CTkFrame(section, fg_color="transparent")
        url_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            url_frame,
            text="対象URL:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://example.com",
            font=("Meiryo", 11),
            height=35
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # デフォルト値を設定
        self.url_entry.insert(0, "https://www.portcafe.net/demo/jrkyushu/jisha-meguri/")
        
        # 深さ設定
        depth_frame = ctk.CTkFrame(section, fg_color="transparent")
        depth_frame.pack(fill="x", pady=15)
        
        ctk.CTkLabel(
            depth_frame,
            text="クロール深さ:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.depth_slider = ctk.CTkSlider(
            depth_frame,
            from_=1,
            to=5,
            number_of_steps=4,
            command=self._on_depth_change
        )
        self.depth_slider.set(2)
        self.depth_slider.pack(side="left", fill="x", expand=True, padx=5)
        
        self.depth_label = ctk.CTkLabel(
            depth_frame,
            text="2階層",
            font=("Meiryo", 11, "bold"),
            width=80,
            text_color="#4CAF50"
        )
        self.depth_label.pack(side="left", padx=5)
        
        # 最大ページ数
        max_pages_frame = ctk.CTkFrame(section, fg_color="transparent")
        max_pages_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            max_pages_frame,
            text="最大ページ数:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.max_pages_entry = ctk.CTkEntry(
            max_pages_frame,
            font=("Meiryo", 11),
            width=100,
            height=35
        )
        self.max_pages_entry.insert(0, "10")
        self.max_pages_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(
            max_pages_frame,
            text="ページ",
            font=("Meiryo", 11),
            text_color="gray"
        ).pack(side="left", padx=5)
        
        # Basic認証設定
        auth_frame = ctk.CTkFrame(section, fg_color="transparent")
        auth_frame.pack(fill="x", pady=15)
        
        self.use_auth_checkbox = ctk.CTkCheckBox(
            auth_frame,
            text="Basic認証を使用する",
            font=("Meiryo", 11),
            command=self._toggle_auth_fields
        )
        self.use_auth_checkbox.pack(anchor="w", padx=5, pady=5)
        
        # プロファイル選択ドロップダウン
        profile_frame = ctk.CTkFrame(section, fg_color="transparent")
        profile_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            profile_frame,
            text="プロファイル:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
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
            text="💾 保存",
            command=self._save_current_profile,
            width=60,
            height=35,
            state="disabled"
        )
        self.save_profile_btn.pack(side="left", padx=2)
        
        self.delete_profile_btn = ctk.CTkButton(
            profile_frame,
            text="🗑️",
            command=self._delete_current_profile,
            width=40,
            height=35,
            fg_color="gray",
            state="disabled"
        )
        self.delete_profile_btn.pack(side="left", padx=2)
        
        # ユーザー名
        username_frame = ctk.CTkFrame(section, fg_color="transparent")
        username_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            username_frame,
            text="ユーザー名:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.auth_username_entry = ctk.CTkEntry(
            username_frame,
            placeholder_text="username",
            font=("Meiryo", 11),
            height=35,
            state="disabled"
        )
        self.auth_username_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # パスワード
        password_frame = ctk.CTkFrame(section, fg_color="transparent")
        password_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            password_frame,
            text="パスワード:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.auth_password_entry = ctk.CTkEntry(
            password_frame,
            placeholder_text="password",
            font=("Meiryo", 11),
            height=35,
            show="*",
            state="disabled"
        )
        self.auth_password_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        # プロファイル一覧を読み込み
        self._load_profile_list()
    
    def _build_pdf_section(self, parent):
        """PDF設定セクション"""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=10)
        
        # セクションヘッダー
        ctk.CTkLabel(
            section,
            text="📁 PDF設定",
            font=("Meiryo", 14, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 10))
        
        # ファイル選択
        file_frame = ctk.CTkFrame(section, fg_color="transparent")
        file_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            file_frame,
            text="PDFファイル:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.pdf_path_label = ctk.CTkLabel(
            file_frame,
            text="ファイルが選択されていません",
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w"
        )
        self.pdf_path_label.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(
            file_frame,
            text="📂 選択",
            command=self._select_pdf_file,
            width=100,
            height=35
        ).pack(side="left", padx=5)
        
        # フォルダ選択
        folder_frame = ctk.CTkFrame(section, fg_color="transparent")
        folder_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(
            folder_frame,
            text="PDFフォルダ:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.pdf_folder_label = ctk.CTkLabel(
            folder_frame,
            text="フォルダが選択されていません",
            font=("Meiryo", 10),
            text_color="gray",
            anchor="w"
        )
        self.pdf_folder_label.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(
            folder_frame,
            text="📂 選択",
            command=self._select_pdf_folder,
            width=100,
            height=35
        ).pack(side="left", padx=5)
        
        # 注意書き
        ctk.CTkLabel(
            section,
            text="※ ファイルまたはフォルダのどちらかを選択してください",
            font=("Meiryo", 9),
            text_color="gray"
        ).pack(fill="x", pady=(5, 0))
        
        # 保存用変数
        self.pdf_file_path = None
        self.pdf_folder_path = None
    
    def _build_advanced_section(self, parent):
        """詳細設定セクション"""
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=10)
        
        # セクションヘッダー
        ctk.CTkLabel(
            section,
            text="⚙️ 詳細設定",
            font=("Meiryo", 14, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 10))
        
        # OCR設定
        ocr_frame = ctk.CTkFrame(section, fg_color="transparent")
        ocr_frame.pack(fill="x", pady=5)
        
        self.use_ocr_checkbox = ctk.CTkCheckBox(
            ocr_frame,
            text="Google Cloud Vision API を使用する",
            font=("Meiryo", 11)
        )
        self.use_ocr_checkbox.select()
        self.use_ocr_checkbox.pack(side="left", padx=5)
        
        # マッチング閾値
        threshold_frame = ctk.CTkFrame(section, fg_color="transparent")
        threshold_frame.pack(fill="x", pady=15)
        
        ctk.CTkLabel(
            threshold_frame,
            text="類似度閾値:",
            font=("Meiryo", 11),
            width=120,
            anchor="w"
        ).pack(side="left", padx=5)
        
        self.threshold_slider = ctk.CTkSlider(
            threshold_frame,
            from_=0.1,
            to=0.9,
            number_of_steps=8,
            command=self._on_threshold_change
        )
        self.threshold_slider.set(0.3)
        self.threshold_slider.pack(side="left", fill="x", expand=True, padx=5)
        
        self.threshold_label = ctk.CTkLabel(
            threshold_frame,
            text="30%",
            font=("Meiryo", 11, "bold"),
            width=80,
            text_color="#4CAF50"
        )
        self.threshold_label.pack(side="left", padx=5)
    
    def _on_depth_change(self, value):
        """深さスライダーの変更"""
        depth = int(value)
        self.depth_label.configure(text=f"{depth}階層")
    
    def _on_threshold_change(self, value):
        """閾値スライダーの変更"""
        threshold = int(value * 100)
        self.threshold_label.configure(text=f"{threshold}%")
    
    def _toggle_auth_fields(self):
        """Basic認証フィールドの有効/無効を切り替え"""
        if self.use_auth_checkbox.get():
            # 有効化
            self.auth_username_entry.configure(state="normal")
            self.auth_password_entry.configure(state="normal")
            self.profile_dropdown.configure(state="normal")
            self.save_profile_btn.configure(state="normal")
            self.delete_profile_btn.configure(state="normal")
        else:
            # 無効化
            self.auth_username_entry.configure(state="disabled")
            self.auth_password_entry.configure(state="disabled")
            self.profile_dropdown.configure(state="disabled")
            self.save_profile_btn.configure(state="disabled")
            self.delete_profile_btn.configure(state="disabled")
    
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
            # フィールドをクリア
            self.auth_username_entry.delete(0, "end")
            self.auth_password_entry.delete(0, "end")
            return
        
        try:
            from app.core.auth_manager import get_auth_manager
            manager = get_auth_manager()
            profile = manager.get_profile(selected)
            
            if profile:
                # フィールドに値を設定
                self.auth_username_entry.delete(0, "end")
                self.auth_username_entry.insert(0, profile.username)
                self.auth_password_entry.delete(0, "end")
                self.auth_password_entry.insert(0, profile.password)
                
                # URLも設定（空の場合のみ）
                if profile.url and not self.url_entry.get().strip():
                    self.url_entry.delete(0, "end")
                    self.url_entry.insert(0, profile.url)
        except Exception as e:
            print(f"⚠️ プロファイル読み込みエラー: {e}")
    
    def _save_current_profile(self):
        """現在の認証情報をプロファイルとして保存"""
        from tkinter import simpledialog, messagebox
        
        username = self.auth_username_entry.get().strip()
        password = self.auth_password_entry.get().strip()
        url = self.url_entry.get().strip()
        
        if not username or not password:
            messagebox.showwarning("入力エラー", "ユーザー名とパスワードを入力してください")
            return
        
        # プロファイル名を入力
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
                # 既存の場合は更新
                if messagebox.askyesno("確認", f"「{profile_name}」は既に存在します。上書きしますか？"):
                    manager.update_profile(profile_name, profile)
                    messagebox.showinfo("完了", f"プロファイル「{profile_name}」を更新しました")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗しました: {e}")
    
    def _delete_current_profile(self):
        """選択中のプロファイルを削除"""
        from tkinter import messagebox
        
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
                self.auth_username_entry.delete(0, "end")
                self.auth_password_entry.delete(0, "end")
        except Exception as e:
            messagebox.showerror("エラー", f"削除に失敗しました: {e}")
    
    def _select_pdf_file(self):
        """PDFファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="PDFファイルを選択",
            filetypes=[
                ("PDFファイル", "*.pdf"),
                ("全てのファイル", "*.*")
            ]
        )
        
        if file_path:
            self.pdf_file_path = file_path
            self.pdf_folder_path = None  # フォルダをクリア
            
            # ファイル名を表示
            from pathlib import Path
            file_name = Path(file_path).name
            self.pdf_path_label.configure(
                text=file_name,
                text_color="white"
            )
            self.pdf_folder_label.configure(
                text="フォルダが選択されていません",
                text_color="gray"
            )
    
    def _select_pdf_folder(self):
        """PDFフォルダを選択"""
        folder_path = filedialog.askdirectory(
            title="PDFフォルダを選択"
        )
        
        if folder_path:
            self.pdf_folder_path = folder_path
            self.pdf_file_path = None  # ファイルをクリア
            
            # フォルダ名を表示
            from pathlib import Path
            folder_name = Path(folder_path).name
            self.pdf_folder_label.configure(
                text=folder_name,
                text_color="white"
            )
            self.pdf_path_label.configure(
                text="ファイルが選択されていません",
                text_color="gray"
            )
    
    def _validate_inputs(self) -> bool:
        """入力値を検証"""
        # URL検証
        url = self.url_entry.get().strip()
        if not url:
            from tkinter import messagebox
            messagebox.showwarning("入力エラー", "URLを入力してください")
            return False
        
        if not url.startswith("http"):
            from tkinter import messagebox
            messagebox.showwarning("入力エラー", "有効なURLを入力してください（http://またはhttps://）")
            return False
        
        # PDF検証
        if not self.pdf_file_path and not self.pdf_folder_path:
            from tkinter import messagebox
            messagebox.showwarning("入力エラー", "PDFファイルまたはフォルダを選択してください")
            return False
        
        return True
    
    def _on_start_analysis(self):
        """分析開始ボタン"""
        if not self._validate_inputs():
            return
        
        # 結果を設定
        self.result = {
            "url": self.url_entry.get().strip(),
            "depth": int(self.depth_slider.get()),
            "max_pages": int(self.max_pages_entry.get()),
            "pdf_file": self.pdf_file_path,
            "pdf_folder": self.pdf_folder_path,
            "use_ocr": self.use_ocr_checkbox.get(),
            "threshold": self.threshold_slider.get(),
            "use_auth": self.use_auth_checkbox.get(),
            "auth_user": self.auth_username_entry.get().strip() if self.use_auth_checkbox.get() else None,
            "auth_pass": self.auth_password_entry.get().strip() if self.use_auth_checkbox.get() else None
        }
        
        # コールバック実行
        if self.on_start:
            self.on_start(self.result)
        
        # ダイアログを閉じる
        self.destroy()
    
    def _on_cancel(self):
        """キャンセルボタン"""
        self.result = None
        self.destroy()
    
    def get_result(self) -> Optional[Dict]:
        """結果を取得"""
        return self.result

