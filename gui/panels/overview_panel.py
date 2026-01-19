import customtkinter as ctk
from PIL import Image, ImageTk
from typing import List, Tuple, Optional, Callable

class OverviewPanel(ctk.CTkFrame):
    """
    ページサムネイル・オーバービューパネル
    - マルチページドキュメントのナビゲーション
    - 長尺画像のページ分割表示
    """
    def __init__(self, parent, on_select: Callable[[int, Optional[Tuple[int, int]]], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.on_select = on_select
        
        # Data
        self.pages = []  # List of images or data objects
        self.page_regions = [] # List of (y1, y2)
        self.current_idx = 0
        
        self._build_ui()
        
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=30, fg_color="#333333")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="📑 Pages", font=("Meiryo", 12, "bold")).pack(padx=10)
        
        # Scrollable Area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="#222222")
        self.scroll_frame.pack(fill="both", expand=True)
        
    def set_pages(self, pages: List[dict]):
        """複数のWebページ(URL単位など)を設定"""
        self.pages = pages
        self.page_regions = [] # Reset regions
        self._refresh_thumbnails(mode="pages")
        
    def set_regions(self, source_image: Image.Image, regions: List[Tuple[int, int]]):
        """単一画像内の領域(分割ページ)を設定"""
        self.pages = [source_image] # Keep source
        self.page_regions = regions
        self._refresh_thumbnails(mode="regions")
        
    def _refresh_thumbnails(self, mode="pages"):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        if mode == "pages":
            for i, page in enumerate(self.pages):
                self._create_thumbnail_btn(i, page.get('image'), f"Page {i+1}")
        
        elif mode == "regions":
            source_img = self.pages[0]
            for i, (y1, y2) in enumerate(self.page_regions):
                # Crop logic
                if source_img:
                    crop = source_img.crop((0, y1, source_img.width, y2))
                    self._create_thumbnail_btn(i, crop, f"Region {i+1}", region_idx=i)

    def _create_thumbnail_btn(self, idx, image, label_text, region_idx=None):
        # Thumbnail generation logic
        if not image: return
        
        # Resize for thumb
        aspect = image.height / image.width
        w = 80
        h = int(w * aspect)
        thumb = ctk.CTkImage(image, size=(w, h))
        
        frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        frame.pack(pady=5)
        
        btn = ctk.CTkButton(
            frame,
            image=thumb,
            text=label_text,
            compound="top",
            width=w+10,
            fg_color="#444444" if idx == self.current_idx else "#333333",
            command=lambda: self._on_click(idx, region_idx)
        )
        btn.pack()
        
    def _on_click(self, idx, region_idx):
        self.current_idx = idx
        # Redraw highlights
        # Invoke callback
        region = self.page_regions[region_idx] if region_idx is not None and self.page_regions else None
        self.on_select(idx, region)
