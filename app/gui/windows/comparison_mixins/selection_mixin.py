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
    
    def _canvas_to_image_coords(self, rect, source: str) -> list:
        """
        キャンバス座標を元画像座標に逆変換
        
        Args:
            rect: (x1, y1, x2, y2) キャンバス座標
            source: "web" or "pdf"
        
        Returns:
            [x1, y1, x2, y2] 元画像座標
        """
        canvas = self.web_canvas if source == "web" else self.pdf_canvas
        
        if not canvas:
            return [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]
        
        scale_x = getattr(canvas, 'scale_x', 1.0)
        scale_y = getattr(canvas, 'scale_y', 1.0)
        
        # 逆変換: キャンバス座標 / スケール = 元画像座標
        if scale_x > 0 and scale_y > 0:
            return [
                int(rect[0] / scale_x),
                int(rect[1] / scale_y),
                int(rect[2] / scale_x),
                int(rect[3] / scale_y)
            ]
        
        return [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]
    
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
        """選択終了 - ★ Phase 1.6: Gemini Vision OCR 統合"""
        import sys
        print(f"\n{'★'*30}")
        print(f"[SelectionMixin] _on_selection_end CALLED!")
        print(f"[SelectionMixin] source: {source}")
        print(f"{'★'*30}")
        sys.stdout.flush()
        
        # 選択開始点を取得 (AdvancedComparisonView から)
        if not hasattr(self, '_selection_start') or self._selection_start is None:
            print("[SelectionMixin] ❌ No _selection_start, returning")
            return
        
        x1, y1 = self._selection_start
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        # 正規化 (左上→右下)
        rect = (min(x1, cx), min(y1, cy), max(x1, cx), max(y1, cy))
        
        # 選択範囲が小さすぎる場合はスキップ
        if abs(cx - x1) < 10 or abs(cy - y1) < 10:
            print("[SelectionMixin] Selection too small, skipping")
            self._selection_start = None
            return
        
        print(f"[SelectionMixin] Selection rect: {rect}")
        
        # 画像ソースを取得
        image_source = None
        if source == "web" and hasattr(self, 'web_image') and self.web_image:
            image_source = self.web_image
        elif source == "pdf" and hasattr(self, 'pdf_image') and self.pdf_image:
            image_source = self.pdf_image
        
        if not image_source:
            print("[SelectionMixin] ❌ No image source available")
            self._selection_start = None
            return
        
        # ★★★ Phase 1.6: Gemini Vision OCR で直接テキスト抽出 ★★★
        print("[SelectionMixin] 🚀 Starting Gemini Vision OCR...")
        extracted_text = self._extract_text_with_gemini(rect, image_source)
        
        if extracted_text:
            print(f"[SelectionMixin] ✅ Extracted {len(extracted_text)} chars")
        else:
            print("[SelectionMixin] ⚠️ No text extracted")
            extracted_text = "[テキスト抽出失敗 - 手動入力可]"
        
        # ★ シート反映用のデータ作成
        self._add_selection_to_sheet(source, rect, extracted_text)
        
        # 選択矩形を確定表示
        if hasattr(self, '_selection_rect_id') and self._selection_rect_id:
            canvas.itemconfig(self._selection_rect_id, outline="#FFFF00", dash=())
        
        # リセット
        self._selection_start = None
    
    def _extract_text_with_gemini(self, rect, image) -> str:
        """Gemini Vision OCR でテキスト抽出"""
        try:
            # 選択範囲をクロップ
            sx1, sy1, sx2, sy2 = [int(max(0, v)) for v in rect]
            sx2 = min(sx2, image.width)
            sy2 = min(sy2, image.height)
            
            if sx2 <= sx1 or sy2 <= sy1:
                return ""
            
            print(f"[GeminiOCR] Cropping: ({sx1}, {sy1}) -> ({sx2}, {sy2})")
            cropped = image.crop((sx1, sy1, sx2, sy2))
            print(f"[GeminiOCR] Cropped size: {cropped.size}")
            
            # Gemini Client
            from app.sdk.llm import GeminiClient
            client = GeminiClient(model="gemini-2.0-flash")
            
            if not client.model:
                print("[GeminiOCR] ⚠️ Gemini client init failed")
                return ""
            
            # OCR プロンプト
            prompt = """この画像に含まれるテキストを正確に抽出してください。
ルール:
1. 画像内のテキストをそのまま抽出
2. 日本語・英語混在可
3. 説明文は不要、テキストのみ出力
出力:"""
            
            print("[GeminiOCR] Calling Gemini Vision API...")
            result = client.generate(prompt, images=[cropped])
            
            if result:
                clean_text = result.strip()
                print(f"[GeminiOCR] ✅ SUCCESS! {len(clean_text)} chars")
                print(f"[GeminiOCR] Preview: {clean_text[:80]}...")
                return clean_text
            
            return ""
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[GeminiOCR] ❌ Error: {e}")
            return ""
    
    def _add_selection_to_sheet(self, source: str, rect, text: str):
        """選択をシートに追加"""
        try:
            # EditableRegion を作成
            from dataclasses import dataclass
            
            region_id = len(getattr(self, 'web_regions', [])) + len(getattr(self, 'pdf_regions', [])) + 1
            area_code = f"SEL_{region_id:03d}"
            
            # regions リストに追加
            if hasattr(self, 'web_regions') and hasattr(self, 'pdf_regions'):
                from app.gui.windows.advanced_comparison_view import EditableRegion
                
                new_region = EditableRegion(
                    id=region_id,
                    # ★ 修正: キャンバス座標を元画像座標に逆変換
                    rect=self._canvas_to_image_coords(rect, source),
                    text=text,
                    area_code=area_code,
                    sync_number=None,
                    similarity=0.0,
                    source=source
                )
                
                if source == "web":
                    self.web_regions.append(new_region)
                else:
                    self.pdf_regions.append(new_region)
                
                print(f"[Sheet] ✅ Added region: {area_code}")
            
            # SyncPair 作成
            if hasattr(self, 'sync_pairs'):
                from app.core.paragraph_matcher import SyncPair
                
                rect_list = [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]
                
                if source == "web":
                    new_pair = SyncPair(
                        web_id=area_code, pdf_id="",
                        similarity=0.0, color="#FF9800",
                        web_bbox=rect_list, pdf_bbox=None,
                        web_text=text, pdf_text=""
                    )
                else:
                    new_pair = SyncPair(
                        web_id="", pdf_id=area_code,
                        similarity=0.0, color="#FF9800",
                        web_bbox=None, pdf_bbox=rect_list,
                        web_text="", pdf_text=text
                    )
                
                self.sync_pairs.append(new_pair)
                print(f"[Sheet] ✅ SyncPair added: {area_code}")
            
            # シート更新
            if hasattr(self, '_refresh_inline_spreadsheet'):
                self._refresh_inline_spreadsheet()
                print("[Sheet] ✅ Spreadsheet refreshed")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Sheet] ❌ Error: {e}")
    
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
