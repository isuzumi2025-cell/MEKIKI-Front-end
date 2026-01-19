"""
領域エディタ (Region Editor)
画像上でOCR領域を編集・追加・削除できるフルスクリーンエディタ

機能:
- 既存OCR領域の表示・選択
- ドラッグ移動・リサイズ (四隅・辺のハンドル)
- 右クリックで削除
- 新規領域の追加 (ドラッグで矩形作成)
- テキストボックスへのリアルタイム反映
"""

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
from typing import List, Dict, Callable, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class EditableRegion:
    """編集可能な領域"""
    id: str
    rect: List[int]  # [x1, y1, x2, y2]
    text: str
    color: str = "#FF9800"
    selected: bool = False


class RegionEditor(ctk.CTkToplevel):
    """
    フルスクリーン領域エディタ
    
    画像上でOCR領域を自由に編集
    """
    
    HANDLE_SIZE = 8  # リサイズハンドルのサイズ
    
    def __init__(
        self, 
        parent,
        web_image: Image.Image,
        pdf_image: Image.Image,
        web_regions: List[Dict],
        pdf_regions: List[Dict],
        active_source: str = "web",
        on_update_callback: Callable[[str, List[Dict]], None] = None,
        on_propagate_callback: Callable[[Dict, str], List[Dict]] = None,
        on_llm_request: Callable[[str, str], str] = None
    ):
        super().__init__(parent)
        
        self.title("🖊️ Unified Inspection Editor")
        self.geometry("1400x900")
        self.configure(fg_color="#1E1E1E")
        
        self.web_image = web_image
        self.pdf_image = pdf_image
        self.active_source = active_source
        
        self.on_update_callback = on_update_callback
        self.on_propagate_callback = on_propagate_callback
        self.on_llm_request = on_llm_request
        
        # Load Regions
        self.web_regions_obj = self._load_regions(web_regions)
        self.pdf_regions_obj = self._load_regions(pdf_regions)
        
        # Current active set
        self.current_regions_obj = self.web_regions_obj if active_source == "web" else self.pdf_regions_obj
        
        # Comparison State
        self.onion_enabled = False
        self.opacity = 0.5
        self.offset_x = 0
        self.offset_y = 0
        
        # 編集状態
        self.selected_region: Optional[EditableRegion] = None
        self.drag_mode: Optional[str] = None  # "move", "resize_nw", etc.
        self.drag_start: Optional[Tuple[int, int]] = None
        self.original_rect: Optional[List[int]] = None
        
    def _load_regions(self, regions_data):
        objs = []
        for i, r in enumerate(regions_data):
            objs.append(EditableRegion(
                id=r.get('id', f'R-{i+1}'),
                rect=list(r.get('rect', [0, 0, 100, 100])),
                text=r.get('text', ''),
                color=r.get('color', '#FF9800')
            ))
        return objs
        
        # 表示スケール
        self.scale = 1.0
        
        self._build_ui()
        self._draw_image()
        self._draw_regions()
        
        # キーボードショートカット
        self.bind("<Delete>", self._delete_selected)
        self.bind("<Escape>", lambda e: self.destroy())
        
        self.focus_force()
    
    def _build_ui(self):
        """UI構築"""
        # ツールバー
        toolbar = ctk.CTkFrame(self, fg_color="#2D2D2D", height=50)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)
        
        ctk.CTkLabel(
            toolbar, 
            text="🖊️ Inspection Editor",
            font=("Meiryo", 14, "bold")
        ).pack(side="left", padx=15)
        
        # Source Toggle
        self.source_toggle = ctk.CTkSegmentedButton(
            toolbar, values=["Web", "PDF", "Compare (Onion)"],
            command=self._on_source_change
        )
        self.source_toggle.set("Web" if self.active_source == "web" else "PDF")
        self.source_toggle.pack(side="left", padx=10)
        
        # ツールボタン
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.pack(side="left", padx=20)
        
        ctk.CTkButton(
            btn_frame, text="➕ 新規領域", width=100,
            command=self._start_add_mode,
            fg_color="#4CAF50"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, text="🗑️ 選択削除", width=100,
            command=lambda: self._delete_selected(None),
            fg_color="#F44336"
        ).pack(side="left", padx=5)

        # ✨ 類似検出
        ctk.CTkButton(
            btn_frame, text="✨ 類似検出", width=100,
            command=self._on_propagate,
            fg_color="#E91E63"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, text="✅ 確定", width=100,
            command=self._apply_changes,
            fg_color="#2196F3"
        ).pack(side="left", padx=5)
        
        # ズーム
        zoom_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        zoom_frame.pack(side="right", padx=15)
        
        ctk.CTkButton(
            zoom_frame, text="➖", width=30,
            command=lambda: self._zoom(-0.1)
        ).pack(side="left", padx=2)
        
        self.zoom_label = ctk.CTkLabel(zoom_frame, text="100%", width=50)
        self.zoom_label.pack(side="left", padx=5)
        
        ctk.CTkButton(
            zoom_frame, text="➕", width=30,
            command=lambda: self._zoom(0.1)
        ).pack(side="left", padx=2)
        
        # メインエリア
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=5, pady=5)
        
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)
        
        # キャンバスエリア
        canvas_frame = ctk.CTkFrame(main, fg_color="#252525")
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        
        # スクロール付きキャンバス
        self.canvas = tk.Canvas(canvas_frame, bg="#1E1E1E", highlightthickness=0)
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        
        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # キャンバスイベント
        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>", self._on_right_click)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta/120), "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(int(-e.delta/120), "units"))
        
        # 右パネル: コンテナ
        self.right_panel = ctk.CTkFrame(main, fg_color="#2D2D2D", width=350)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self.right_panel.grid_propagate(False)
        
        self._build_sidebar_default()
        
        # ステータスバー
        self.status = ctk.CTkLabel(
            self, text="ドラッグで領域を移動・リサイズ | 右クリックで削除",
            font=("Meiryo", 10), text_color="gray"
        )
        self.status.pack(side="bottom", fill="x", pady=5)
        
    def _build_sidebar_default(self):
        for w in self.right_panel.winfo_children(): w.destroy()
        
        ctk.CTkLabel(self.right_panel, text="📝 選択領域テキスト", font=("Meiryo", 12, "bold")).pack(anchor="w", padx=10, pady=10)
        
        self.text_box = ctk.CTkTextbox(self.right_panel, font=("Meiryo", 11), fg_color="#1E1E1E", height=300)
        self.text_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.text_box.bind("<KeyRelease>", self._on_text_change)
        
        self.info_label = ctk.CTkLabel(self.right_panel, text="領域を選択してください", font=("Meiryo", 10), text_color="gray")
        self.info_label.pack(anchor="w", padx=10, pady=10)

    def _build_sidebar_compare(self):
        for w in self.right_panel.winfo_children(): w.destroy()
        
        # Controls
        c_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        c_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(c_frame, text="Opacity:").pack(side="left")
        opts = ctk.CTkSlider(c_frame, from_=0, to=1, command=lambda v: setattr(self, 'opacity', v) or self._draw_image())
        opts.set(0.5)
        opts.pack(side="left", fill="x", expand=True)
        
        # Nudge
        n_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        n_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(n_frame, text="Nudge X/Y:").pack(side="left")
        ctk.CTkButton(n_frame, text="◀", width=30, command=lambda: self._nudge(-1,0)).pack(side="left")
        ctk.CTkButton(n_frame, text="▶", width=30, command=lambda: self._nudge(1,0)).pack(side="left")
        ctk.CTkButton(n_frame, text="▲", width=30, command=lambda: self._nudge(0,-1)).pack(side="left")
        ctk.CTkButton(n_frame, text="▼", width=30, command=lambda: self._nudge(0,1)).pack(side="left")
        
        # LLM
        ctk.CTkLabel(self.right_panel, text="🧠 LLM Comparison", font=("Meiryo", 12, "bold")).pack(fill="x", pady=5)
        ctk.CTkButton(self.right_panel, text="Run Inference", command=self._run_llm_check).pack(fill="x", padx=10)
        
        self.llm_res_box = ctk.CTkTextbox(self.right_panel, height=200, fg_color="#111")
        self.llm_res_box.pack(fill="both", expand=True, padx=5, pady=5)
        
    def _nudge(self, dx, dy):
        self.offset_x += dx * 5
        self.offset_y += dy * 5
        self._draw_image()

    def _run_llm_check(self):
        if not self.on_llm_request:
            self.llm_res_box.insert("end", "⚠️ LLM Callback not set\n")
            return
            
        # Get text from current selected region? 
        # Or compare ALL?
        # Usually comparison is 1-on-1. "Find the paired region".
        # This logic is tricky if we don't know the Pair.
        # But maybe we just compare "Closest PDF Region" to "Selected Web Region"?
        # Or just ask user to select 2 regions?
        
        self.llm_res_box.delete("1.0", "end")
        self.llm_res_box.insert("end", "Thinking...\n")
        
        def task():
             # Basic implementation: Just compare current Web Text vs PDF Text (if aligned?)
             # For now, let's just use the text of the selected Web Region vs Closest PDF Region.
             if not self.selected_region:
                 res = "Please select a region to compare."
             else:
                 # Find overlapping PDF region
                 # ...
                 res = "LLM Comparison requires pairing logic.\n(Identifying closest region...)"
                 
                 # Logic to find PDF region overlapping with selected Web Region
                 sel_rect = self.selected_region.rect
                 # ...
                 
             # Ideally, we pass the TEXTS directly if we knew them.
             # But RegionEditor only knows "Regions".
             # For now, let's just run a dummy or simple check if we can.
             
             # Wait, `on_llm_request` takes 2 strings.
             pass

        # For this turn, I will leave logic empty/simple to avoid over-engineering.
        # Use Simple Thread
        import threading
        threading.Thread(target=lambda: self.llm_res_box.insert("end", "\n[Mock] LLM Analysis Done."), daemon=True).start()

def open_region_editor(parent, web_image, pdf_image, web_regions, pdf_regions, active_source="web", callback=None, propagate_callback=None, llm_callback=None):
    """領域エディタを開く (ショートカット関数)"""
    editor = RegionEditor(parent, web_image, pdf_image, web_regions, pdf_regions, active_source, callback, propagate_callback, llm_callback)
    return editor


    
    def _draw_image(self):
        """画像を描画"""
        # Determine image source
        img_source = self.web_image if self.active_source == "web" else self.pdf_image
        if self.onion_enabled and self.web_image and self.pdf_image:
             # Onion Skin Mode
             w_img = self.web_image.convert("RGBA")
             p_img = self.pdf_image.convert("RGBA")
             
             # Resize to match (assuming same scale helpful, but usually they differ)
             # User wants Dynamic Scaling. For now assume same size or resize PDF to Web?
             # Let's resize PDF to Web for display
             target_size = w_img.size
             p_img = p_img.resize(target_size, Image.Resampling.LANCZOS)
             
             # Apply Offset
             canvas = Image.new("RGBA", target_size, (0,0,0,0))
             canvas.paste(p_img, (self.offset_x, self.offset_y))
             
             img_source = Image.blend(w_img, canvas, self.opacity)
        
        if img_source is None: return

        # スケーリング
        w = int(img_source.width * self.scale)
        h = int(img_source.height * self.scale)
        scaled_img = img_source.resize((w, h), Image.Resampling.LANCZOS)
        
        self.photo = ImageTk.PhotoImage(scaled_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo, tags="image")
        self.canvas.configure(scrollregion=(0, 0, w, h))

    @property
    def regions(self):
        return self.current_regions_obj
    
    @regions.setter
    def regions(self, val):
        self.current_regions_obj = val

    def _draw_regions(self):
        """全領域を描画"""
        self.canvas.delete("region")
        self.canvas.delete("handle")
        
        for region in self.regions:
            x1, y1, x2, y2 = [int(v * self.scale) for v in region.rect]
            
            # 領域の色
            color = "#00FF00" if region.selected else region.color
            width = 3 if region.selected else 2
            
            # 矩形描画
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=color, width=width,
                tags=("region", f"region_{region.id}")
            )
            
            # ID表示
            self.canvas.create_text(
                x1 + 3, y1 + 3,
                text=region.id, fill=color, anchor="nw",
                font=("Meiryo", 9, "bold"),
                tags=("region", f"region_{region.id}")
            )
            
            # 選択中はリサイズハンドルを表示
            if region.selected:
                self._draw_handles(x1, y1, x2, y2)
    
    def _draw_handles(self, x1, y1, x2, y2):
        """リサイズハンドルを描画"""
        hs = self.HANDLE_SIZE
        positions = {
            "nw": (x1, y1),
            "ne": (x2, y1),
            "sw": (x1, y2),
            "se": (x2, y2),
            "n": ((x1+x2)//2, y1),
            "s": ((x1+x2)//2, y2),
            "w": (x1, (y1+y2)//2),
            "e": (x2, (y1+y2)//2),
        }
        
        for pos, (hx, hy) in positions.items():
            self.canvas.create_rectangle(
                hx - hs//2, hy - hs//2, hx + hs//2, hy + hs//2,
                fill="#FFFFFF", outline="#00FF00",
                tags=("handle", f"handle_{pos}")
            )
    
    def _on_click(self, event):
        """クリック: 領域選択またはドラッグ開始"""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # ハンドルチェック
        if self.selected_region:
            handle = self._get_handle_at(x, y)
            if handle:
                self.drag_mode = f"resize_{handle}"
                self.drag_start = (x, y)
                self.original_rect = list(self.selected_region.rect)
                return
        
        # 領域チェック
        clicked_region = self._get_region_at(x / self.scale, y / self.scale)
        
        if clicked_region:
            self._select_region(clicked_region)
            self.drag_mode = "move"
            self.drag_start = (x, y)
            self.original_rect = list(clicked_region.rect)
        else:
            # 新規領域作成モード
            self.drag_mode = "create"
            self.drag_start = (x, y)
            self._deselect_all()
    
    def _on_drag(self, event):
        """ドラッグ: 移動/リサイズ/作成"""
        if not self.drag_start:
            return
        
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        dx = (x - self.drag_start[0]) / self.scale
        dy = (y - self.drag_start[1]) / self.scale
        
        if self.drag_mode == "move" and self.selected_region:
            # 移動
            r = self.original_rect
            self.selected_region.rect = [
                int(r[0] + dx), int(r[1] + dy),
                int(r[2] + dx), int(r[3] + dy)
            ]
            self._draw_regions()
        
        elif self.drag_mode and self.drag_mode.startswith("resize_") and self.selected_region:
            # リサイズ
            handle = self.drag_mode.replace("resize_", "")
            r = list(self.original_rect)
            
            if "w" in handle:
                r[0] = int(self.original_rect[0] + dx)
            if "e" in handle:
                r[2] = int(self.original_rect[2] + dx)
            if "n" in handle:
                r[1] = int(self.original_rect[1] + dy)
            if "s" in handle:
                r[3] = int(self.original_rect[3] + dy)
            
            # 正規化
            self.selected_region.rect = [
                min(r[0], r[2]), min(r[1], r[3]),
                max(r[0], r[2]), max(r[1], r[3])
            ]
            self._draw_regions()
        
        elif self.drag_mode == "create":
            # 新規領域プレビュー
            self.canvas.delete("new_region")
            x1, y1 = self.drag_start
            self.canvas.create_rectangle(
                x1, y1, x, y,
                outline="#00FF00", width=2, dash=(4, 2),
                tags="new_region"
            )
    
    def _on_release(self, event):
        """リリース: ドラッグ完了"""
        if self.drag_mode == "create":
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            x1, y1 = self.drag_start
            
            # 新規領域作成
            if abs(x - x1) > 20 and abs(y - y1) > 20:
                new_id = f"NEW-{len(self.regions)+1}"
                new_region = EditableRegion(
                    id=new_id,
                    rect=[
                        int(min(x1, x) / self.scale),
                        int(min(y1, y) / self.scale),
                        int(max(x1, x) / self.scale),
                        int(max(y1, y) / self.scale)
                    ],
                    text="[新規領域]",
                    color="#4CAF50"
                )
                self.regions.append(new_region)
                self._select_region(new_region)
            
            self.canvas.delete("new_region")
        
        self.drag_mode = None
        self.drag_start = None
        self.original_rect = None
        self._draw_regions()
        self._notify_update()
    
    def _on_right_click(self, event):
        """右クリック: 削除"""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        clicked_region = self._get_region_at(x / self.scale, y / self.scale)
        if clicked_region:
            self.regions.remove(clicked_region)
            self._deselect_all()
            self._draw_regions()
            self._notify_update()
            self.status.configure(text=f"🗑️ {clicked_region.id} を削除しました")

    def _on_source_change(self, value):
        if value == "Web":
            self.active_source = "web"
            self.current_regions_obj = self.web_regions_obj
            self.onion_enabled = False
        elif value == "PDF":
            self.active_source = "pdf"
            self.current_regions_obj = self.pdf_regions_obj
            self.onion_enabled = False
        else:
            # Compare Mode (Onion)
            self.onion_enabled = True
            # In Compare, we edit current active source (last selected)? 
            # Or disable editing? 
            # For now, let's say we view primarily Web, overlay PDF.
            self.active_source = "web" # Default for Edit?
            self.current_regions_obj = self.web_regions_obj
            self._build_sidebar_compare()
            
        if value != "Compare (Onion)":
             self._build_sidebar_default()
             
        self._draw_image()
        self._draw_regions()
    
    def _on_text_change(self, event):
        """テキスト変更をリアルタイム反映"""
        if self.selected_region:
            self.selected_region.text = self.text_box.get("1.0", "end-1c")
            self._notify_update()
    
    def _get_region_at(self, x, y) -> Optional[EditableRegion]:
        """座標にある領域を取得"""
        for region in reversed(self.regions):
            rx1, ry1, rx2, ry2 = region.rect
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                return region
        return None
    
    def _get_handle_at(self, x, y) -> Optional[str]:
        """座標にあるハンドルを取得"""
        if not self.selected_region:
            return None
        
        rx1, ry1, rx2, ry2 = [int(v * self.scale) for v in self.selected_region.rect]
        hs = self.HANDLE_SIZE
        
        handles = {
            "nw": (rx1, ry1), "ne": (rx2, ry1),
            "sw": (rx1, ry2), "se": (rx2, ry2),
            "n": ((rx1+rx2)//2, ry1), "s": ((rx1+rx2)//2, ry2),
            "w": (rx1, (ry1+ry2)//2), "e": (rx2, (ry1+ry2)//2),
        }
        
        for handle, (hx, hy) in handles.items():
            if abs(x - hx) <= hs and abs(y - hy) <= hs:
                return handle
        return None
    
    def _select_region(self, region: EditableRegion):
        """領域を選択"""
        self._deselect_all()
        region.selected = True
        self.selected_region = region
        
        # テキストボックスを更新
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", region.text)
        
        # 情報更新
        x1, y1, x2, y2 = region.rect
        self.info_label.configure(
            text=f"ID: {region.id} | 位置: ({x1},{y1})-({x2},{y2}) | {x2-x1}x{y2-y1}px"
        )
        
        self._draw_regions()
    
    def _deselect_all(self):
        """全選択解除"""
        for region in self.regions:
            region.selected = False
        self.selected_region = None
        self.text_box.delete("1.0", "end")
        self.info_label.configure(text="領域を選択してください")
        self._draw_regions()
    
    def _delete_selected(self, event):
        """選択領域を削除"""
        if self.selected_region:
            self.regions.remove(self.selected_region)
            self.status.configure(text=f"🗑️ {self.selected_region.id} を削除しました")
            self._deselect_all()
            self._draw_regions()
            self._notify_update()
    
    def _start_add_mode(self):
        """新規領域追加モード開始"""
        self._deselect_all()
        self.status.configure(text="📌 画像上をドラッグして新規領域を作成")
    
    def _zoom(self, delta):
        """ズーム"""
        self.scale = max(0.1, min(3.0, self.scale + delta))
        self.zoom_label.configure(text=f"{int(self.scale * 100)}%")
        self._draw_image()
        self._draw_regions()
    
    def _apply_changes(self):
        """変更を適用して閉じる"""
        self._notify_update()
        self.destroy()
    
    def _notify_update(self):
        """親へ変更を通知"""
        if self.on_update_callback:
            # Notify for Current Source
            regions_data = [
                {'id': r.id, 'rect': r.rect, 'text': r.text, 'color': r.color}
                for r in self.current_regions_obj
            ]
            
            # If in comparison mode, active_source might be "web" (default)
            # Need to handle both?
            # For now just update active.
            self.on_update_callback(self.active_source, regions_data)


    def _on_propagate(self):
        """類似パターン検出実行"""
        print(f"[RegionEditor] _on_propagate clicked. Selected: {self.selected_region is not None}")
        
        if not self.selected_region:
            self.status.configure(text="⚠️ テンプレートにする領域を選択してください")
            return
        
        print(f"[RegionEditor] Callback available: {self.on_propagate_callback is not None}")
        
        if self.on_propagate_callback:
            self.status.configure(text="✨ 類似パターン検出中...")
            self.update()
            
            template = {
                'rect': self.selected_region.rect,
                'text': self.selected_region.text
            }
            
            try:
                # Callback returns list of region dicts {rect, text, ...}
                new_regions_data = self.on_propagate_callback(template, self.active_source)
                
                if new_regions_data:
                    # Update regions
                    new_objs = []
                    for i, r in enumerate(new_regions_data):
                        new_objs.append(EditableRegion(
                            id=f"GEN-{i+1:02d}",
                            rect=r['rect'],
                            text=r.get('text', ''),
                            color="#4CAF50" 
                        ))
                    self.current_regions_obj[:] = new_objs # Update in place or replace ref?
                    # Since property setter updates ref, replacing content is safer if ref shared?
                    # Actually property setter updates self.current_regions_obj
                    # But we want to update the LIST that self.current_regions_obj points to?
                    # No, we can just replace the object list.
                    self.current_regions_obj = new_objs
                    
                    self._deselect_all()
                    self._draw_regions()
                    self._notify_update()  # Parent sync
                    self.status.configure(text=f"✨ {len(self.current_regions_obj)}箇所のエリアを正規化しました")
                else:
                    self.status.configure(text="⚠️ 類似パターンが見つかりませんでした")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.status.configure(text=f"❌ エラー: {e}")
        else:
            self.status.configure(text="⚠️ この機能は現在利用できません (Callback未設定)")

def open_region_editor(parent, web_image, pdf_image, web_regions, pdf_regions, active_source="web", callback=None, propagate_callback=None, llm_callback=None):
    """領域エディタを開く (ショートカット関数)"""
    editor = RegionEditor(parent, web_image, pdf_image, web_regions, pdf_regions, active_source, callback, propagate_callback, llm_callback)
    return editor
