"""
サイトマップビューワー
ツリー表示、404エラーアラート、ページサムネイル
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Callable
from PIL import Image, ImageTk
import io
import base64


class SitemapViewerWindow(ctk.CTkToplevel):
    """
    サイトマップビューワー - 分離可能なウィンドウ
    ツリー構造でサイトマップを表示、404エラーを赤でハイライト
    スタンドアローンモード対応
    """
    
    def __init__(self, parent, api_client=None, job_id: Optional[int] = None, 
                 on_add_to_comparison: Optional[Callable[[Dict], None]] = None,
                 local_pages: Optional[List[Dict]] = None, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.parent_app = parent
        self.api_client = api_client
        self.job_id = job_id
        self.pages_data: List[Dict] = local_pages or []
        self.selected_page = None
        self.on_add_to_comparison = on_add_to_comparison
        self.standalone_mode = (local_pages is not None) or (api_client is None)
        
        # ウィンドウ設定
        self.title("🗺️ サイトマップビューワー")
        self.geometry("900x700")
        self.minsize(600, 400)
        
        self._build_ui()
        
        # ローカルデータがあれば即表示
        if self.pages_data:
            self._build_page_tree()
            self._update_status()
        elif job_id and api_client:
            self._load_job_pages(job_id)
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🗺️ サイトマップビューワー",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        # ジョブ選択
        self.job_selector = ctk.CTkComboBox(
            header,
            values=["ジョブを選択..."],
            width=200,
            command=self._on_job_select
        )
        self.job_selector.pack(side="right", padx=15, pady=10)
        
        ctk.CTkButton(
            header,
            text="🔄",
            width=35,
            command=self._refresh_jobs
        ).pack(side="right", padx=5)
        
        # メインコンテンツ (ペインウィンドウで分割)
        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5, bg="#3A3A3A")
        self.paned.pack(fill="both", expand=True)
        
        # 左ペイン: ツリービュー
        left_frame = ctk.CTkFrame(self.paned, fg_color="#2D2D2D")
        self.paned.add(left_frame, width=350)
        
        self._build_tree_view(left_frame)
        
        # 右ペイン: プレビュー/詳細
        right_frame = ctk.CTkFrame(self.paned, fg_color="#2B2B2B")
        self.paned.add(right_frame, width=550)
        
        self._build_preview_panel(right_frame)
        
        # ステータスバー
        self.status_bar = ctk.CTkFrame(self, height=25, fg_color="#1A1A1A")
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="ジョブを選択してください",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.status_label.pack(side="left", padx=10)
        
        # ジョブ一覧を読み込み
        self._refresh_jobs()
    
    def _build_tree_view(self, parent):
        """ツリービュー構築"""
        # ヘッダー
        header = ctk.CTkFrame(parent, fg_color="#383838", height=40)
        header.pack(fill="x", padx=5, pady=5)
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="📂 ページ一覧",
            font=("Meiryo", 12, "bold")
        ).pack(side="left", padx=10, pady=8)
        
        # 凡例
        legend = ctk.CTkFrame(header, fg_color="transparent")
        legend.pack(side="right", padx=10)
        
        ctk.CTkLabel(legend, text="●", text_color="#4CAF50", font=("", 12)).pack(side="left")
        ctk.CTkLabel(legend, text="正常", font=("Meiryo", 9), text_color="gray").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(legend, text="●", text_color="#F44336", font=("", 12)).pack(side="left")
        ctk.CTkLabel(legend, text="エラー", font=("Meiryo", 9), text_color="gray").pack(side="left")
        
        # ツリービュー (ttk.Treeview with custom style)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Sitemap.Treeview",
                        background="#2D2D2D",
                        foreground="white",
                        fieldbackground="#2D2D2D",
                        rowheight=30)
        style.configure("Sitemap.Treeview.Heading",
                        background="#383838",
                        foreground="white")
        style.map("Sitemap.Treeview",
                  background=[("selected", "#4A4A4A")])
        
        tree_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tree = ttk.Treeview(
            tree_frame,
            style="Sitemap.Treeview",
            columns=("status", "depth"),
            show="tree headings"
        )
        
        self.tree.heading("#0", text="URL")
        self.tree.heading("status", text="状態")
        self.tree.heading("depth", text="階層")
        
        self.tree.column("#0", width=250, stretch=True)
        self.tree.column("status", width=60, anchor="center")
        self.tree.column("depth", width=40, anchor="center")
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 選択イベント
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        
        # タグ設定 (色分け)
        self.tree.tag_configure("error", foreground="#F44336")
        self.tree.tag_configure("ok", foreground="#4CAF50")
        self.tree.tag_configure("warning", foreground="#FF9800")
    
    def _build_preview_panel(self, parent):
        """プレビューパネル構築"""
        # タブビュー
        self.preview_tabs = ctk.CTkTabview(parent, fg_color="#2B2B2B")
        self.preview_tabs.pack(fill="both", expand=True, padx=5, pady=5)
        
        # サムネイルタブ
        self.thumbnail_tab = self.preview_tabs.add("🖼️ プレビュー")
        
        self.thumbnail_label = ctk.CTkLabel(
            self.thumbnail_tab,
            text="ページを選択してください",
            font=("Meiryo", 12),
            text_color="gray"
        )
        self.thumbnail_label.pack(fill="both", expand=True)
        
        # 詳細タブ
        self.detail_tab = self.preview_tabs.add("📋 詳細")
        
        self.detail_text = ctk.CTkTextbox(
            self.detail_tab,
            font=("Meiryo", 11),
            fg_color="#1E1E1E"
        )
        self.detail_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # アクションボタン
        actions = ctk.CTkFrame(parent, fg_color="transparent", height=50)
        actions.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(
            actions,
            text="⚖️ 比較に追加",
            fg_color="#2196F3",
            command=self._add_to_comparison
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            actions,
            text="🔗 ブラウザで開く",
            fg_color="#616161",
            command=self._open_in_browser
        ).pack(side="left", padx=5)
    
    def _refresh_jobs(self):
        """ジョブ一覧を更新"""
        # スタンドアローンモードではAPIを使用しない
        if self.standalone_mode or self.api_client is None:
            self.job_selector.configure(values=["(ローカルモード)"])
            self._job_map = {}
            return
        
        jobs = self.api_client.get_jobs(limit=20)
        
        if jobs:
            job_values = [f"Job #{j['id']} ({j.get('status', '?')})" for j in jobs]
            self.job_selector.configure(values=job_values)
            self._job_map = {f"Job #{j['id']} ({j.get('status', '?')})": j for j in jobs}
        else:
            self.job_selector.configure(values=["ジョブがありません"])
            self._job_map = {}
    
    def _on_job_select(self, selection):
        """ジョブ選択時"""
        if selection in self._job_map:
            job = self._job_map[selection]
            self._load_job_pages(job['id'])
    
    def _load_job_pages(self, job_id: int):
        """ジョブのページを読み込み"""
        self.job_id = job_id
        self.pages_data = self.api_client.get_job_pages(str(job_id))
        
        # ツリーをクリア
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not self.pages_data:
            self.status_label.configure(text="ページが見つかりません")
            return
        
        # ツリー構築
        self._build_page_tree()
        
        # ステータス更新
        self._update_status()
    
    def _update_status(self):
        """ステータスバー更新"""
        total = len(self.pages_data)
        errors = sum(1 for p in self.pages_data if p.get('status_code', 200) >= 400)
        mode_text = "(ローカル)" if self.standalone_mode else ""
        self.status_label.configure(
            text=f"📄 {total} ページ {mode_text} |  ✅ {total - errors} 正常  |  ❌ {errors} エラー"
        )
    
    def _build_page_tree(self):
        """ページツリーを構築"""
        from urllib.parse import urlparse
        
        # アイテム→ページマッピングを初期化
        self._item_to_page = {}
        
        # ツリーをクリア
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # URLをパス階層でグループ化
        url_tree = {}
        
        for page in self.pages_data:
            url = page.get('url', '')
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            
            # ルートノードを作成
            domain = parsed.netloc
            if domain not in url_tree:
                url_tree[domain] = {'children': {}, 'page': None}
            
            current = url_tree[domain]
            for part in path_parts:
                if part not in current['children']:
                    current['children'][part] = {'children': {}, 'page': None}
                current = current['children'][part]
            
            current['page'] = page
        
        # ツリーに追加
        def add_node(parent_id, name, node):
            page = node.get('page')
            
            if page:
                status_code = page.get('status_code', 200)
                depth = page.get('depth', 0)
                
                if status_code >= 400:
                    status = "❌"
                    tag = "error"
                elif status_code >= 300:
                    status = "⚠️"
                    tag = "warning"
                else:
                    status = "✅"
                    tag = "ok"
                
                item_id = self.tree.insert(
                    parent_id, "end",
                    text=f" {name}",
                    values=(status, depth),
                    tags=(tag,)
                )
                
                # ページデータを保存
                self._item_to_page = getattr(self, '_item_to_page', {})
                self._item_to_page[item_id] = page
            else:
                item_id = self.tree.insert(parent_id, "end", text=f" 📁 {name}")
            
            for child_name, child_node in node.get('children', {}).items():
                add_node(item_id, child_name, child_node)
        
        # ドメインごとにルートノード追加
        for domain, node in url_tree.items():
            domain_id = self.tree.insert("", "end", text=f" 🌐 {domain}")
            for child_name, child_node in node['children'].items():
                add_node(domain_id, child_name, child_node)
            
            # 展開
            self.tree.item(domain_id, open=True)
    
    def _on_tree_select(self, event):
        """ツリー選択時"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        page = getattr(self, '_item_to_page', {}).get(item_id)
        
        if page:
            self.selected_page = page
            self._show_page_preview(page)
    
    def _on_tree_double_click(self, event):
        """ツリーダブルクリック時"""
        if self.selected_page:
            self._open_in_browser()
    
    def _show_page_preview(self, page: Dict):
        """ページプレビューを表示"""
        # 詳細テキスト
        self.detail_text.delete("1.0", "end")
        
        info = f"""URL: {page.get('url', 'N/A')}
ステータス: {page.get('status_code', 'N/A')}
階層: {page.get('depth', 'N/A')}
タイトル: {page.get('title', 'N/A')}

--- 抽出テキスト (プレビュー) ---
{page.get('text_content', '')[:1000]}...
"""
        self.detail_text.insert("1.0", info)
        
        # サムネイル
        screenshot = page.get('screenshot_base64')
        if screenshot:
            try:
                img_data = base64.b64decode(screenshot)
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((500, 400))
                photo = ImageTk.PhotoImage(img)
                
                self.thumbnail_label.configure(image=photo, text="")
                self.thumbnail_label.image = photo
            except Exception as e:
                self.thumbnail_label.configure(text=f"画像読み込みエラー: {e}")
        else:
            self.thumbnail_label.configure(text="スクリーンショットなし")
    
    def _add_to_comparison(self):
        """比較に追加 - ページデータをコールバック経由で渡す"""
        if not self.selected_page:
            from tkinter import messagebox
            messagebox.showwarning("警告", "ページを選択してください")
            return
        
        page = self.selected_page
        
        # コールバックがあれば呼び出す
        if self.on_add_to_comparison:
            self.on_add_to_comparison(page)
            self.status_label.configure(text=f"✅ 比較に追加: {page.get('url', '')[:50]}...")
        else:
            from tkinter import messagebox
            messagebox.showinfo(
                "比較に追加", 
                f"ページを比較マトリクスに追加します\n\n"
                f"URL: {page.get('url', 'N/A')}\n"
                f"テキスト長: {len(page.get('text_content', ''))} 文字"
            )
    
    def _open_in_browser(self):
        """ブラウザで開く"""
        if self.selected_page:
            import webbrowser
            url = self.selected_page.get('url')
            if url:
                webbrowser.open(url)


class SitemapViewerFrame(ctk.CTkFrame):
    """サイトマップビューワー - 埋め込み用フレーム版"""
    
    def __init__(self, parent, api_client, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.api_client = api_client
        self.parent_app = parent.winfo_toplevel()  # UnifiedAppへの参照
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🗺️ サイトマップビューワー",
            font=("Meiryo", 16, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        ctk.CTkButton(
            header,
            text="↗️ 別ウィンドウで開く",
            command=self._open_window,
            fg_color="#616161"
        ).pack(side="right", padx=15)
        
        # 簡易表示エリア
        content = ctk.CTkFrame(self, fg_color="#2D2D2D")
        content.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            content,
            text="ダッシュボードでジョブを選択するか、\n「別ウィンドウで開く」をクリックしてください",
            font=("Meiryo", 12),
            text_color="gray"
        ).place(relx=0.5, rely=0.5, anchor="center")
    
    def _open_window(self):
        """別ウィンドウで開く"""
        # コールバック
        callback = None
        if hasattr(self.parent_app, 'add_web_page_to_comparison'):
            callback = self.parent_app.add_web_page_to_comparison
        
        # ローカルページデータ (スタンドアローンモード)
        local_pages = None
        if hasattr(self.parent_app, 'local_pages') and self.parent_app.local_pages:
            local_pages = self.parent_app.local_pages
        
        # 比較キューからも取得可能
        if not local_pages and hasattr(self.parent_app, 'comparison_queue') and self.parent_app.comparison_queue:
            local_pages = self.parent_app.comparison_queue
        
        window = SitemapViewerWindow(
            self.parent_app, 
            api_client=self.api_client,
            on_add_to_comparison=callback,
            local_pages=local_pages
        )
        window.focus()
