"""
SelectionMixin - 範囲選択機能
SDK SelectionManager統合版

Features:
- 簡易選択 / フルスキャンモード切替
- 選択範囲のリアルタイムOCR
- ⭐ 即座にシート反映
- シンクロ率表示
"""

from typing import Optional, Tuple, List, Callable
import tkinter as tk

try:
    from app.sdk.selection import SelectionManager, SelectionMode, SelectionRegion, SyncResult
except ImportError:
    # フォールバック: SDKが利用できない場合
    SelectionManager = None
    SelectionMode = None


class SelectionMixin:
    """
    範囲選択Mixin
    
    AdvancedComparisonViewに組み込んで使用:
    - self.web_canvas, self.pdf_canvas を想定
    - self.web_image, self.pdf_image を想定
    - self.inline_spreadsheet を想定（シート反映用）
    """
    
    def _init_selection_manager(self):
        """SelectionManager初期化"""
        if SelectionManager is None:
            print("⚠️ SDK SelectionManager not available")
            self._selection_manager = None
            return
        
        self._selection_manager = SelectionManager(
            on_selection_complete=self._on_selection_complete,
            on_text_extracted=self._on_text_extracted,
            on_sync_complete=self._on_sync_complete,
            mode=SelectionMode.QUICK
        )
        
        # 選択矩形のCanvas ID
        self._selection_rect_id = None
        self._active_canvas = None
        
        print("✅ SelectionManager initialized (Quick mode)")
    
    def _set_selection_mode(self, mode: str):
        """
        選択モード設定
        
        Args:
            mode: "quick" or "full"
        """
        if self._selection_manager is None:
            return
        
        if mode == "quick":
            self._selection_manager.set_mode(SelectionMode.QUICK)
        else:
            self._selection_manager.set_mode(SelectionMode.FULL)
    
    def _bind_selection_events(self, canvas: tk.Canvas, source: str):
        """
        選択イベントをCanvasにバインド
        
        Args:
            canvas: tkinter Canvas
            source: "web" or "pdf"
        """
        canvas.bind("<ButtonPress-1>", lambda e: self._on_selection_start(e, canvas, source))
        canvas.bind("<B1-Motion>", lambda e: self._on_selection_drag(e, canvas))
        canvas.bind("<ButtonRelease-1>", lambda e: self._on_selection_end(e, canvas, source))
    
    def _on_selection_start(self, event, canvas: tk.Canvas, source: str):
        """選択開始"""
        if self._selection_manager is None:
            return
        
        # Canvas座標に変換
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        self._selection_manager.start_selection(int(cx), int(cy))
        self._active_canvas = canvas
        self._active_source = source
        
        # 既存の選択矩形を削除
        if self._selection_rect_id:
            canvas.delete(self._selection_rect_id)
            self._selection_rect_id = None
    
    def _on_selection_drag(self, event, canvas: tk.Canvas):
        """選択ドラッグ中"""
        if self._selection_manager is None:
            return
        
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        region = self._selection_manager.update_selection(int(cx), int(cy))
        
        if region:
            # 選択矩形を描画
            if self._selection_rect_id:
                canvas.delete(self._selection_rect_id)
            
            self._selection_rect_id = canvas.create_rectangle(
                region.x1, region.y1, region.x2, region.y2,
                outline="#00FF00", width=2, dash=(4, 2)
            )
    
    def _on_selection_end(self, event, canvas: tk.Canvas, source: str):
        """選択終了"""
        if self._selection_manager is None:
            return
        
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        # 画像ソースを取得
        image_source = None
        if source == "web" and hasattr(self, 'web_image') and self.web_image:
            image_source = self.web_image
        elif source == "pdf" and hasattr(self, 'pdf_image') and self.pdf_image:
            image_source = self.pdf_image
        
        # 選択完了 (バックグラウンドでOCR実行)
        region = self._selection_manager.complete_selection(int(cx), int(cy), image_source)
        
        if region:
            # 選択矩形を確定表示
            if self._selection_rect_id:
                canvas.itemconfig(self._selection_rect_id, outline="#FFFF00", dash=())
    
    def _on_selection_complete(self, region: SelectionRegion):
        """選択完了コールバック"""
        print(f"📐 Selection complete: {region.width}x{region.height}px")
    
    def _on_text_extracted(self, text: str, region: SelectionRegion):
        """
        テキスト抽出完了コールバック
        ⭐ 即座にシートに反映
        """
        print(f"📝 Text extracted: {len(text)} chars")
        
        # 即座にシートに反映
        self._update_sheet_with_selection(text, region)
    
    def _on_sync_complete(self, result: SyncResult):
        """
        シンクロ完了コールバック
        類似度とハイライト情報を表示
        """
        similarity_pct = result.similarity * 100
        print(f"🔄 Sync: {similarity_pct:.1f}%")
        
        # ステータス更新
        if hasattr(self, '_safe_status'):
            self._safe_status(f"Sync: {similarity_pct:.1f}%")
        
        # ハイライト表示（将来実装）
        # self._apply_diff_highlights(result.diff_highlights)
    
    def _update_sheet_with_selection(self, text: str, region: SelectionRegion):
        """
        選択領域のテキストをシートに即座反映
        ⭐ 最重要機能
        """
        if not hasattr(self, 'inline_spreadsheet') or self.inline_spreadsheet is None:
            print("⚠️ inline_spreadsheet not available")
            return
        
        try:
            # 新しい行を追加
            source = getattr(self, '_active_source', 'web')
            new_row = {
                'source': source.upper(),
                'area_code': f"SEL-{region.x1}-{region.y1}",
                'text': text[:100],  # 切り詰め
                'bbox': region.bbox,
                'sync': 0,
            }
            
            # シートに追加（メソッドが存在すれば）
            if hasattr(self.inline_spreadsheet, 'add_row'):
                self.inline_spreadsheet.add_row(new_row)
                print(f"✅ Added to sheet: {text[:30]}...")
            elif hasattr(self.inline_spreadsheet, 'refresh'):
                # リフレッシュのみ
                self.inline_spreadsheet.refresh()
            
        except Exception as e:
            print(f"❌ Sheet update error: {e}")
    
    def _cancel_selection(self):
        """選択キャンセル"""
        if self._selection_manager:
            self._selection_manager.cancel_selection()
        
        if self._selection_rect_id and self._active_canvas:
            self._active_canvas.delete(self._selection_rect_id)
            self._selection_rect_id = None


# Export
__all__ = ["SelectionMixin"]
