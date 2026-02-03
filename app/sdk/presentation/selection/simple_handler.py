"""
SimpleSelectionHandler - Ultra Professional Selection Manager

Phase 1.6: シンプルで確実な範囲選択マネージャー

Features:
- ドラッグ選択 → Gemini Vision OCR → シート反映
- 右クリック削除
- 類似検索 (Similar Search)
- マッチ検索 (Match Search)

Design Principles:
- シンプル: 1クラスで完結、Mixin不使用
- 確実: 直接Gemini API呼び出し
- 透明: 全ステップでログ出力
"""

import tkinter as tk
from typing import Optional, Callable, List, Tuple, Any
from PIL import Image
from dataclasses import dataclass


@dataclass
class SelectionResult:
    """選択結果"""
    rect: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    text: str
    source: str  # "web" or "pdf"
    area_code: str


class SimpleSelectionHandler:
    """
    Ultra Professional - シンプル範囲選択ハンドラ
    
    Usage:
        handler = SimpleSelectionHandler(
            canvas=pdf_canvas,
            image=pdf_image,
            source="pdf",
            on_selection_complete=self._on_new_selection,
            on_selection_deleted=self._on_selection_removed
        )
    """
    
    def __init__(
        self,
        canvas: tk.Canvas,
        image: Optional[Image.Image],  # None allowed for deferred init
        source: str,
        on_selection_complete: Callable[[SelectionResult], None],
        on_selection_deleted: Optional[Callable[[str], None]] = None,
        image_getter: Optional[Callable[[], Optional[Image.Image]]] = None,  # ★ Dynamic image getter
    ):
        self.canvas = canvas
        self.image = image
        self.source = source
        self.on_selection_complete = on_selection_complete
        self.on_selection_deleted = on_selection_deleted
        self.image_getter = image_getter  # ★ For getting current image dynamically
        
        # 選択状態
        self._start_x: Optional[int] = None
        self._start_y: Optional[int] = None
        self._rect_id: Optional[int] = None
        
        # 既存選択領域
        self._regions: List[SelectionResult] = []
        self._region_counter = 0
        
        # イベントバインド
        self._bind_events()
        print(f"✅ SimpleSelectionHandler initialized for {source}")
    
    def set_image(self, image: Image.Image):
        """画像を設定（遅延初期化用）"""
        self.image = image
        print(f"[SimpleSelection] Image set: {image.size if image else 'None'}")
    
    def _bind_events(self):
        """イベントをバインド"""
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_click)
        print(f"  → Events bound: Press, Drag, Release, RightClick")
    
    def _on_press(self, event):
        """マウス押下 - 選択開始"""
        self._start_x = self.canvas.canvasx(event.x)
        self._start_y = self.canvas.canvasy(event.y)
        
        # 既存の選択矩形を削除
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        
        print(f"[Selection] Press at ({self._start_x:.0f}, {self._start_y:.0f})")
    
    def _on_drag(self, event):
        """ドラッグ中 - 選択矩形を描画"""
        if self._start_x is None:
            return
        
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # 既存の矩形を更新
        if self._rect_id:
            self.canvas.delete(self._rect_id)
        
        self._rect_id = self.canvas.create_rectangle(
            self._start_x, self._start_y, x, y,
            outline="#00FF00", width=2, dash=(4, 2),
            tags="simple_selection"
        )
    
    def _on_release(self, event):
        """マウスリリース - 選択完了 → Gemini OCR"""
        import sys
        print(f"\n{'='*60}")
        print(f"[SimpleSelection] ★ RELEASE - Selection Complete!")
        print(f"{'='*60}")
        sys.stdout.flush()
        
        if self._start_x is None:
            print("[SimpleSelection] No start point, skipping")
            return
        
        x2 = self.canvas.canvasx(event.x)
        y2 = self.canvas.canvasy(event.y)
        
        # 正規化 (左上→右下) - キャンバス座標
        canvas_x1 = min(self._start_x, x2)
        canvas_y1 = min(self._start_y, y2)
        canvas_x2 = max(self._start_x, x2)
        canvas_y2 = max(self._start_y, y2)
        
        # 小さすぎる選択はスキップ
        if abs(canvas_x2 - canvas_x1) < 10 or abs(canvas_y2 - canvas_y1) < 10:
            print("[SimpleSelection] Selection too small, skipping")
            self._start_x = None
            return
        
        # ★ キャンバス座標 → 元画像座標への変換
        # CanvasTransform オブジェクトから取得（正しい方法）
        tf = getattr(self.canvas, '_coord_tf', None)
        if tf:
            scale_x = tf.scale_x
            scale_y = tf.scale_y
            offset_x = tf.offset_x
            offset_y = tf.offset_y
        else:
            # フォールバック: 直接属性
            scale_x = getattr(self.canvas, 'scale_x', 1.0)
            scale_y = getattr(self.canvas, 'scale_y', 1.0)
            offset_x = getattr(self.canvas, 'offset_x', 0)
            offset_y = getattr(self.canvas, 'offset_y', 0)
        
        print(f"[SimpleSelection] Canvas coords: ({canvas_x1:.0f}, {canvas_y1:.0f}) -> ({canvas_x2:.0f}, {canvas_y2:.0f})")
        
        # ★ キャンバス座標 → 元画像座標への変換
        # シンプル化: scale のみ使用 (offset は表示オフセットでありクリック座標には不要)
        # canvasx/canvasy はスクロール位置を含むため、スケールのみで逆変換可能
        if tf:
            scale = tf.scale_x  # scale_x == scale_y (等倍スケール)
            print(f"[SimpleSelection] Transform: scale={scale:.4f}, offset=({tf.offset_x}, {tf.offset_y}) [offset ignored]")
        else:
            scale = scale_x
            print(f"[SimpleSelection] Transform: scale={scale:.4f} (fallback)")
        
        # シンプルなスケール変換のみ
        img_x1 = int(canvas_x1 / scale) if scale > 0 else int(canvas_x1)
        img_y1 = int(canvas_y1 / scale) if scale > 0 else int(canvas_y1)
        img_x2 = int(canvas_x2 / scale) if scale > 0 else int(canvas_x2)
        img_y2 = int(canvas_y2 / scale) if scale > 0 else int(canvas_y2)
        
        rect = (img_x1, img_y1, img_x2, img_y2)
        print(f"[SimpleSelection] Image coords: {rect}")
        
        # 選択矩形を確定表示
        if self._rect_id:
            self.canvas.itemconfig(self._rect_id, outline="#FFFF00", dash=())
        
        # ★ Gemini Vision OCR
        print("[SimpleSelection] 🚀 Starting Gemini Vision OCR...")
        text = self._extract_text_with_gemini(rect)
        
        if text:
            print(f"[SimpleSelection] ✅ Extracted {len(text)} chars")
        else:
            print("[SimpleSelection] ⚠️ No text extracted")
            text = "[テキスト抽出失敗 - 手動入力可]"
        
        # 結果を作成
        self._region_counter += 1
        area_code = f"SEL_{self._region_counter:03d}"
        
        result = SelectionResult(
            rect=rect,
            text=text,
            source=self.source,
            area_code=area_code
        )
        
        self._regions.append(result)
        
        # コールバック
        if self.on_selection_complete:
            self.on_selection_complete(result)
        
        # リセット
        self._start_x = None
        print(f"[SimpleSelection] ✅ Complete: {area_code}")
    
    def _extract_text_with_gemini(self, rect: Tuple[int, int, int, int]) -> str:
        """OCR でテキスト抽出 (CloudOCREngine primary, Gemini fallback)"""
        try:
            # ★ 動的に画像取得（ページ変更に対応）
            current_image = self.image
            if self.image_getter:
                fetched = self.image_getter()
                if fetched:
                    current_image = fetched
            
            if not current_image:
                print("[OCR] ❌ No image available")
                return ""
            
            x1, y1, x2, y2 = rect
            
            # 画像クロップ
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(current_image.width, x2)
            y2 = min(current_image.height, y2)
            
            if x2 <= x1 or y2 <= y1:
                print("[OCR] Invalid crop region")
                return ""
            
            print(f"[OCR] Cropping: ({x1}, {y1}) -> ({x2}, {y2})")
            cropped = current_image.crop((x1, y1, x2, y2))
            print(f"[OCR] Cropped size: {cropped.size}")
            
            # ★ Method 1: CloudOCREngine (Google Cloud Vision API) - 実績のある方法
            try:
                from app.core.engine_cloud import CloudOCREngine
                
                print("[OCR] 🔄 Trying CloudOCREngine (Google Cloud Vision)...")
                engine = CloudOCREngine()
                clusters, raw_words = engine.extract_text(cropped)
                
                if clusters:
                    # クラスタからテキストを結合
                    texts = [c.get('text', '') for c in clusters]
                    combined_text = '\n'.join(texts).strip()
                    
                    if combined_text:
                        print(f"[OCR] ✅ CloudOCREngine SUCCESS! {len(combined_text)} chars")
                        if len(combined_text) > 80:
                            print(f"[OCR] Preview: {combined_text[:80]}...")
                        return combined_text
                
                print("[OCR] CloudOCREngine returned no text, trying Gemini...")
                
            except Exception as cloud_err:
                print(f"[OCR] CloudOCREngine failed: {cloud_err}, trying Gemini...")
            
            # ★ Method 2: Gemini Vision (フォールバック)
            try:
                from app.sdk.llm import GeminiClient
                
                client = GeminiClient(model="gemini-2.0-flash")
                
                if not client.model:
                    print("[OCR] ⚠️ Gemini client init failed - check GEMINI_API_KEY")
                    return ""
                
                prompt = """この画像に含まれるテキストを正確に抽出してください。

ルール:
1. 画像内のテキストをそのまま抽出（翻訳・解釈しない）
2. 日本語・英語混在可
3. 説明文は不要、テキストのみ出力

出力:"""
                
                print("[OCR] 🔄 Calling Gemini Vision API...")
                result = client.generate(prompt, images=[cropped])
                
                if result:
                    clean_text = result.strip()
                    print(f"[OCR] ✅ Gemini SUCCESS! {len(clean_text)} chars")
                    return clean_text
                
            except Exception as gemini_err:
                print(f"[OCR] Gemini also failed: {gemini_err}")
            
            print("[OCR] All OCR methods failed")
            return ""
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[OCR] ❌ Error: {e}")
            return ""
    
    def _on_right_click(self, event):
        """右クリック - 選択範囲を削除"""
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        print(f"[Selection] Right-click at ({x:.0f}, {y:.0f})")
        
        # クリック位置の範囲を検索
        for region in self._regions:
            x1, y1, x2, y2 = region.rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                print(f"[Selection] Deleting: {region.area_code}")
                self._regions.remove(region)
                
                # キャンバスから選択矩形を削除
                self.canvas.delete("simple_selection")
                
                # コールバック
                if self.on_selection_deleted:
                    self.on_selection_deleted(region.area_code)
                
                return
        
        print("[Selection] No region found at click position")
    
    def get_regions(self) -> List[SelectionResult]:
        """全選択領域を返す"""
        return self._regions.copy()
    
    def clear_all(self):
        """全選択をクリア"""
        self._regions.clear()
        self.canvas.delete("simple_selection")
        print("[Selection] All selections cleared")


# ========== Export ==========
__all__ = ["SimpleSelectionHandler", "SelectionResult"]
