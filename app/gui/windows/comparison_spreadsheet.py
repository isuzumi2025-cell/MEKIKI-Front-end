"""
比較スプレッドシートウィンドウ (画面2) - 2列構成版
Web/PDF横並び、シンクロ箇所は同列に配置
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Optional, Callable, Tuple
from PIL import Image, ImageTk
from dataclasses import dataclass
import io
from app.gui.managers.thumbnail_manager import ThumbnailManager


@dataclass  
class ComparisonRow:
    """比較行データ（2列構成）"""
    row_no: int
    # Web側
    web_id: str = ""
    web_text: str = ""
    web_rect: List[int] = None
    # PDF側
    pdf_id: str = ""
    pdf_text: str = ""
    pdf_rect: List[int] = None
    # マッチ情報
    similarity: float = 0.0
    sync_area: str = ""  # "P1-3 ↔ PDF-5"
    
    @property
    def status_icon(self) -> str:
        if self.similarity >= 0.5:
            return "🟢"
        elif self.similarity >= 0.3:
            return "🟡"
        elif self.sync_area:
            return "🔴"
        else:
            return "⚪"
    
    @property
    def web_preview(self) -> str:
        text = self.web_text.replace('\n', ' ')[:60]
        return text + "..." if len(self.web_text) > 60 else text
    
    @property
    def pdf_preview(self) -> str:
        text = self.pdf_text.replace('\n', ' ')[:60]
        return text + "..." if len(self.pdf_text) > 60 else text


class ComparisonSpreadsheetWindow(ctk.CTkToplevel):
    """
    2列構成の比較スプレッドシート
    ┌────────────────────────┬────────────────────────┬──────┐
    │  Web (No/画像/テキスト) │ PDF (No/画像/テキスト)  │Sync  │
    └────────────────────────┴────────────────────────┴──────┘
    """
    
    def __init__(self, parent, on_row_select: Callable = None, **kwargs):
        super().__init__(parent)
        
        self.title("📊 Web/PDF 比較校正シート (2列構成)")
        self.geometry("1400x750")
        self.configure(fg_color="#1A1A1A")
        
        self.on_row_select = on_row_select
        self.rows: List[ComparisonRow] = []
        self.web_image: Optional[Image.Image] = None
        self.pdf_image: Optional[Image.Image] = None
        self.thumbnails: Dict[int, Tuple[ImageTk.PhotoImage, ImageTk.PhotoImage]] = {}
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#2D2D2D", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="📊 Web/PDF 比較校正シート",
            font=("Meiryo", 14, "bold")
        ).pack(side="left", padx=15, pady=10)
        
        self.count_label = ctk.CTkLabel(
            header, text="0件", font=("Meiryo", 11), text_color="gray"
        )
        self.count_label.pack(side="left", padx=10)
        
        # ツールバー
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=10)
        
        ctk.CTkButton(
            toolbar, text="📥 Excel出力", width=100, fg_color="#4CAF50",
            command=self._export_excel
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="🔄 更新", width=80, fg_color="#2196F3",
            command=self._refresh
        ).pack(side="left", padx=5)
        
        # カラムヘッダー (2列構成)
        col_header = ctk.CTkFrame(self, fg_color="#383838", height=40)
        col_header.pack(fill="x", padx=5, pady=2)
        col_header.pack_propagate(False)
        
        # Web列ヘッダー
        web_header = ctk.CTkFrame(col_header, fg_color="#2E7D32", width=600)
        web_header.pack(side="left", fill="y", padx=1)
        web_header.pack_propagate(False)
        ctk.CTkLabel(web_header, text="🌐 Web側", font=("Meiryo", 12, "bold")).pack(pady=8)
        
        # PDF列ヘッダー
        pdf_header = ctk.CTkFrame(col_header, fg_color="#1565C0", width=600)
        pdf_header.pack(side="left", fill="y", padx=1)
        pdf_header.pack_propagate(False)
        ctk.CTkLabel(pdf_header, text="📄 PDF側", font=("Meiryo", 12, "bold")).pack(pady=8)
        
        # Sync列ヘッダー
        sync_header = ctk.CTkFrame(col_header, fg_color="#FF6F00", width=180)
        sync_header.pack(side="left", fill="y", padx=1)
        sync_header.pack_propagate(False)
        ctk.CTkLabel(sync_header, text="🔗 Sync", font=("Meiryo", 12, "bold")).pack(pady=8)
        
        # サブヘッダー
        sub_header = ctk.CTkFrame(self, fg_color="#2D2D2D", height=25)
        sub_header.pack(fill="x", padx=5)
        sub_header.pack_propagate(False)
        
        # Web側サブヘッダー
        for text, w in [("No", 50), ("画像", 100), ("テキスト", 430)]:
            ctk.CTkLabel(sub_header, text=text, width=w, font=("Meiryo", 9)).pack(side="left", padx=1)
        
        # スペーサー
        ctk.CTkLabel(sub_header, text="|", width=10, text_color="gray").pack(side="left")
        
        # PDF側サブヘッダー
        for text, w in [("No", 50), ("画像", 100), ("テキスト", 430)]:
            ctk.CTkLabel(sub_header, text=text, width=w, font=("Meiryo", 9)).pack(side="left", padx=1)
        
        # スペーサー
        ctk.CTkLabel(sub_header, text="|", width=10, text_color="gray").pack(side="left")
        
        # Sync側サブヘッダー
        for text, w in [("率", 50), ("エリア", 120)]:
            ctk.CTkLabel(sub_header, text=text, width=w, font=("Meiryo", 9)).pack(side="left", padx=1)
        
        # メインフレーム
        main_frame = ctk.CTkFrame(self, fg_color="#1E1E1E")
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(main_frame, bg="#1E1E1E", highlightthickness=0)
        scrollbar_y = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color="#1E1E1E")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar_y.set)
        
        scrollbar_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def load_data(self, web_regions: List, pdf_regions: List, 
                  web_image: Image.Image = None, pdf_image: Image.Image = None,
                  sync_pairs: List = None):
        """データをロード（2列構成用）"""
        self.web_image = web_image
        self.pdf_image = pdf_image
        self.rows = []
        
        web_map = {r.area_code: r for r in web_regions}
        pdf_map = {r.area_code: r for r in pdf_regions}
        
        used_web = set()
        used_pdf = set()
        row_no = 1
        
        # 1. マッチペアを行に（横並び） - Sync率降順ソート
        if sync_pairs:
            # Sort by similarity DESC
            sync_pairs.sort(key=lambda x: x.similarity, reverse=True)
            
            for sp in sync_pairs:
                if sp.similarity < 0.1: continue # Filter noise? No, show all matched.
                
                web_r = web_map.get(sp.web_id)
                pdf_r = pdf_map.get(sp.pdf_id)
                
                row = ComparisonRow(
                    row_no=row_no,
                    web_id=sp.web_id,
                    web_text=web_r.text if web_r else "",
                    web_rect=list(web_r.rect) if web_r else None,
                    pdf_id=sp.pdf_id,
                    pdf_text=pdf_r.text if pdf_r else "",
                    pdf_rect=list(pdf_r.rect) if pdf_r else None,
                    similarity=sp.similarity,
                    sync_area=f"{sp.web_id} ↔ {sp.pdf_id}"
                )
                self.rows.append(row)
                used_web.add(sp.web_id)
                used_pdf.add(sp.pdf_id)
                row_no += 1
        
        # 2. マッチしなかったWeb (PDF側空欄)
        for r in web_regions:
            if r.area_code not in used_web:
                row = ComparisonRow(
                    row_no=row_no,
                    web_id=r.area_code,
                    web_text=r.text,
                    web_rect=list(r.rect),
                    similarity=0.0
                )
                self.rows.append(row)
                row_no += 1
        
        # 3. マッチしなかったPDF (Web側空欄)
        for r in pdf_regions:
            if r.area_code not in used_pdf:
                row = ComparisonRow(
                    row_no=row_no,
                    pdf_id=r.area_code,
                    pdf_text=r.text,
                    pdf_rect=list(r.rect),
                    similarity=0.0
                )
                self.rows.append(row)
                row_no += 1
        
        self._generate_thumbnails()
        self._refresh_rows()
    
    def _generate_thumbnails(self):
        """サムネイル生成 (ThumbnailManager利用)"""
        self.thumbnails = {}
        
        for row in self.rows:
            web_thumb = None
            pdf_thumb = None
            
            if self.web_image and row.web_rect:
                web_thumb = ThumbnailManager.create_thumbnail(self.web_image, row.web_rect)
            
            if self.pdf_image and row.pdf_rect:
                pdf_thumb = ThumbnailManager.create_thumbnail(self.pdf_image, row.pdf_rect)
            
            self.thumbnails[row.row_no] = (web_thumb, pdf_thumb)
    
    def _refresh_rows(self):
        """行を再描画"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        for i, row in enumerate(self.rows):
            self._create_row(row, i)
        
        self.count_label.configure(text=f"{len(self.rows)}件")
    
    def _create_row(self, row: ComparisonRow, index: int):
        """1行作成（2列構成）"""
        bg = "#2B2B2B" if index % 2 == 0 else "#333333"
        row_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=bg, height=60)
        row_frame.pack(fill="x", pady=1)
        row_frame.pack_propagate(False)
        
        row_frame.bind("<Button-1>", lambda e, r=row: self._on_row_click(r))
        row_frame.bind("<Double-1>", lambda e, r=row: self._on_row_double_click(r))
        
        # === Web列 ===
        # No
        ctk.CTkLabel(row_frame, text=row.web_id or "-", width=50, font=("Meiryo", 9), text_color="#4CAF50").pack(side="left", padx=1)
        
        # 画像
        web_thumb, pdf_thumb = self.thumbnails.get(row.row_no, (None, None))
        web_img_frame = ctk.CTkFrame(row_frame, fg_color="#1E1E1E", width=100, height=55)
        web_img_frame.pack(side="left", padx=1)
        web_img_frame.pack_propagate(False)
        if web_thumb:
            lbl = tk.Label(web_img_frame, image=web_thumb, bg="#1E1E1E")
            lbl.image = web_thumb
            lbl.pack(expand=True)
        
        # テキスト (Web)
        web_txt_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=430)
        web_txt_frame.pack(side="left", padx=1, fill="y")
        web_txt_frame.pack_propagate(False)
        web_text_widget = tk.Text(web_txt_frame, bg=bg, fg="#E0E0E0", relief="flat", font=("Meiryo", 9), wrap="char")
        web_text_widget.pack(fill="both", expand=True)
        
        # 区切り
        ctk.CTkLabel(row_frame, text="│", width=10, text_color="#555").pack(side="left")
        
        # === PDF列 ===
        # No
        ctk.CTkLabel(row_frame, text=row.pdf_id or "-", width=50, font=("Meiryo", 9), text_color="#2196F3").pack(side="left", padx=1)
        
        # 画像
        pdf_img_frame = ctk.CTkFrame(row_frame, fg_color="#1E1E1E", width=100, height=55)
        pdf_img_frame.pack(side="left", padx=1)
        pdf_img_frame.pack_propagate(False)
        if pdf_thumb:
            lbl = tk.Label(pdf_img_frame, image=pdf_thumb, bg="#1E1E1E")
            lbl.image = pdf_thumb
            lbl.pack(expand=True)
        
        # テキスト (PDF)
        pdf_txt_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=430)
        pdf_txt_frame.pack(side="left", padx=1, fill="y")
        pdf_txt_frame.pack_propagate(False)
        pdf_text_widget = tk.Text(pdf_txt_frame, bg=bg, fg="#E0E0E0", relief="flat", font=("Meiryo", 9), wrap="char")
        pdf_text_widget.pack(fill="both", expand=True)
        
        # 区切り
        ctk.CTkLabel(row_frame, text="│", width=10, text_color="#555").pack(side="left")

        # Diff Apply
        self._apply_diff_highlight(web_text_widget, pdf_text_widget, row.web_text, row.pdf_text)
    
    def _apply_diff_highlight(self, w_widget, p_widget, t1, t2):
        import difflib
        seq = difflib.SequenceMatcher(None, t1, t2)
        
        # Tags: Common=Charcoal(#888888), Diff=Red(#FF5252)/Blue(#448AFF)
        w_widget.tag_config("common", foreground="#888888")
        w_widget.tag_config("diff", foreground="#FF5252", background="#330000") # slightly dark bg for contrast
        p_widget.tag_config("common", foreground="#888888")
        p_widget.tag_config("diff", foreground="#448AFF", background="#000033")
        
        for tag, i1, i2, j1, j2 in seq.get_opcodes():
            if tag == 'equal':
                w_widget.insert("end", t1[i1:i2], "common")
                p_widget.insert("end", t2[j1:j2], "common")
            elif tag == 'replace':
                w_widget.insert("end", t1[i1:i2], "diff")
                p_widget.insert("end", t2[j1:j2], "diff")
            elif tag == 'delete':
                w_widget.insert("end", t1[i1:i2], "diff")
            elif tag == 'insert':
                p_widget.insert("end", t2[j1:j2], "diff")
                
        w_widget.configure(state="disabled")
        p_widget.configure(state="disabled")
        
        # === Sync列 ===
        sim_color = "#4CAF50" if row.similarity >= 0.5 else "#FF9800" if row.similarity >= 0.3 else "#888"
        ctk.CTkLabel(row_frame, text=f"{row.status_icon} {row.similarity*100:.0f}%", width=50, font=("Meiryo", 9, "bold"), text_color=sim_color).pack(side="left", padx=1)
        ctk.CTkLabel(row_frame, text=row.sync_area, width=120, font=("Meiryo", 8), text_color="gray").pack(side="left", padx=1)
    
    def _on_row_click(self, row):
        if self.on_row_select:
            self.on_row_select(row, "click")
    
    def _on_row_double_click(self, row):
        if self.on_row_select:
            self.on_row_select(row, "double_click")
    
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _refresh(self):
        self._generate_thumbnails()
        self._refresh_rows()
    
    def _export_excel(self):
        """Excel出力（2列構成）"""
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill
            from pathlib import Path
            from datetime import datetime
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "比較シート"
            
            # ヘッダー
            headers = ["No", "Web ID", "Webテキスト", "PDF ID", "PDFテキスト", "Sync率", "Syncエリア"]
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=h)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="4CAF50", fill_type="solid")
            
            # データ
            for i, row in enumerate(self.rows, 2):
                ws.cell(row=i, column=1, value=row.row_no)
                ws.cell(row=i, column=2, value=row.web_id)
                ws.cell(row=i, column=3, value=row.web_text[:200])
                ws.cell(row=i, column=4, value=row.pdf_id)
                ws.cell(row=i, column=5, value=row.pdf_text[:200])
                ws.cell(row=i, column=6, value=f"{row.similarity*100:.0f}%")
                ws.cell(row=i, column=7, value=row.sync_area)
            
            # 列幅調整
            ws.column_dimensions['C'].width = 50
            ws.column_dimensions['E'].width = 50
            
            # 保存
            Path("./exports").mkdir(exist_ok=True)
            filename = f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            output_path = f"./exports/{filename}"
            wb.save(output_path)
            
            print(f"✅ Excel出力完了: {output_path}")
            import os
            os.startfile(output_path)
            
        except Exception as e:
            print(f"Excel出力エラー: {e}")
            import traceback
            traceback.print_exc()
