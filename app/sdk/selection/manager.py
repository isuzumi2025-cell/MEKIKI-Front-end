"""
SDK Selection Module
範囲選択機能 - 簡易選択/フルスキャンモード

⭐ 最重要: 選択範囲内の画像・文字情報が即座にシート反映される

Usage:
    from app.sdk.selection import SelectionManager, SelectionMode
    
    manager = SelectionManager(on_selection_complete=callback)
    manager.set_mode(SelectionMode.QUICK)  # 簡易選択
    manager.set_mode(SelectionMode.FULL)   # フルスキャン
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Optional, Callable, Any
from datetime import datetime
import threading


class SelectionMode(Enum):
    """選択モード"""
    QUICK = "quick"   # 簡易選択（少ない範囲の確認）
    FULL = "full"     # フルスキャン（全領域スキャン）


@dataclass
class SelectionRegion:
    """選択領域"""
    x1: int
    y1: int
    x2: int
    y2: int
    text: str = ""
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def width(self) -> int:
        return abs(self.x2 - self.x1)
    
    @property
    def height(self) -> int:
        return abs(self.y2 - self.y1)
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        return (min(self.x1, self.x2), min(self.y1, self.y2),
                max(self.x1, self.x2), max(self.y1, self.y2))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "text": self.text,
            "confidence": self.confidence,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class SyncResult:
    """シンクロ結果"""
    similarity: float  # 0.0 - 1.0
    matched_text: str
    target_text: str
    diff_highlights: List[Tuple[int, int, str]]  # (start, end, type: "add"|"del"|"match")


class SelectionManager:
    """
    選択マネージャー
    
    ⭐ 最重要機能:
    - 選択範囲内の画像・文字情報が即座にシート反映
    - 簡易選択/フルスキャンモード切替
    - 比較ターゲットとのシンクロ率表示
    """
    
    def __init__(
        self,
        on_selection_complete: Optional[Callable[[SelectionRegion], None]] = None,
        on_text_extracted: Optional[Callable[[str, SelectionRegion], None]] = None,
        on_sync_complete: Optional[Callable[[SyncResult], None]] = None,
        mode: SelectionMode = SelectionMode.QUICK
    ):
        """
        初期化
        
        Args:
            on_selection_complete: 選択完了時コールバック
            on_text_extracted: テキスト抽出完了時コールバック (即座にシート反映用)
            on_sync_complete: シンクロ完了時コールバック
            mode: 選択モード
        """
        self.mode = mode
        self.on_selection_complete = on_selection_complete
        self.on_text_extracted = on_text_extracted
        self.on_sync_complete = on_sync_complete
        
        self._current_selection: Optional[SelectionRegion] = None
        self._target_text: str = ""
        self._is_selecting: bool = False
        self._start_pos: Optional[Tuple[int, int]] = None
    
    def set_mode(self, mode: SelectionMode):
        """モード設定"""
        self.mode = mode
        print(f"📐 Selection Mode: {mode.value}")
    
    def set_target_text(self, text: str):
        """比較ターゲットテキスト設定"""
        self._target_text = text
    
    def start_selection(self, x: int, y: int):
        """選択開始"""
        self._is_selecting = True
        self._start_pos = (x, y)
    
    def update_selection(self, x: int, y: int) -> Optional[SelectionRegion]:
        """選択更新（ドラッグ中）"""
        if not self._is_selecting or not self._start_pos:
            return None
        
        self._current_selection = SelectionRegion(
            x1=self._start_pos[0],
            y1=self._start_pos[1],
            x2=x,
            y2=y
        )
        return self._current_selection
    
    def complete_selection(self, x: int, y: int, image_source: Any = None) -> Optional[SelectionRegion]:
        """
        選択完了
        
        ⭐ 即座にテキスト抽出してコールバックを発火
        """
        if not self._is_selecting or not self._start_pos:
            return None
        
        self._is_selecting = False
        
        region = SelectionRegion(
            x1=self._start_pos[0],
            y1=self._start_pos[1],
            x2=x,
            y2=y
        )
        
        # 選択完了コールバック
        if self.on_selection_complete:
            self.on_selection_complete(region)
        
        # テキスト抽出（バックグラウンド）
        if image_source is not None:
            self._extract_text_async(region, image_source)
        
        self._current_selection = region
        return region
    
    def _extract_text_async(self, region: SelectionRegion, image_source: Any):
        """
        バックグラウンドでテキスト抽出
        ⭐ 完了後即座にコールバック発火
        """
        def extract():
            try:
                text = self._extract_text_from_region(region, image_source)
                region.text = text
                
                # ⭐ 即座にシート反映用コールバック発火
                if self.on_text_extracted:
                    self.on_text_extracted(text, region)
                
                # シンクロ計算
                if self._target_text:
                    sync_result = self._calculate_sync(text, self._target_text)
                    if self.on_sync_complete:
                        self.on_sync_complete(sync_result)
                        
            except Exception as e:
                print(f"❌ Text extraction error: {e}")
        
        thread = threading.Thread(target=extract, daemon=True)
        thread.start()
    
    def _extract_text_from_region(self, region: SelectionRegion, image_source: Any) -> str:
        """
        領域からテキスト抽出
        
        モードに応じて処理を変える:
        - QUICK: 小さな領域は軽量処理
        - FULL: 高精度OCR
        """
        try:
            from PIL import Image
            
            # 画像を領域でクロップ
            if isinstance(image_source, str):
                img = Image.open(image_source)
            elif isinstance(image_source, Image.Image):
                img = image_source
            else:
                return ""
            
            bbox = region.bbox
            cropped = img.crop(bbox)
            
            # モード別処理
            if self.mode == SelectionMode.QUICK and region.area < 50000:
                # 簡易モード: 小さい領域は軽量モデル
                return self._quick_ocr(cropped)
            else:
                # フルスキャン: 高精度
                return self._full_ocr(cropped)
                
        except Exception as e:
            print(f"❌ Extract error: {e}")
            return ""
    
    def _quick_ocr(self, image) -> str:
        """簡易OCR (高速)"""
        try:
            from app.sdk.ocr import GeminiOCREngine
            engine = GeminiOCREngine(model="gemini-2.0-flash-lite")
            result = engine.detect_document_text(image)
            return result.get("full_text", "") if result else ""
        except:
            return ""
    
    def _full_ocr(self, image) -> str:
        """フルOCR (高精度)"""
        try:
            from app.sdk.ocr import GeminiOCREngine
            engine = GeminiOCREngine(model="gemini-2.0-flash")
            result = engine.detect_document_text(image)
            return result.get("full_text", "") if result else ""
        except:
            return ""
    
    def _calculate_sync(self, text1: str, text2: str) -> SyncResult:
        """
        シンクロ率計算
        一致部分の色分け情報も生成
        """
        from difflib import SequenceMatcher
        
        # 正規化
        t1 = text1.strip().replace("\n", " ")
        t2 = text2.strip().replace("\n", " ")
        
        matcher = SequenceMatcher(None, t1, t2)
        similarity = matcher.ratio()
        
        # 差分ハイライト
        highlights = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                highlights.append((i1, i2, "match"))
            elif tag == "delete":
                highlights.append((i1, i2, "del"))
            elif tag == "insert":
                highlights.append((j1, j2, "add"))
            elif tag == "replace":
                highlights.append((i1, i2, "del"))
                highlights.append((j1, j2, "add"))
        
        return SyncResult(
            similarity=similarity,
            matched_text=t1,
            target_text=t2,
            diff_highlights=highlights
        )
    
    def cancel_selection(self):
        """選択キャンセル"""
        self._is_selecting = False
        self._start_pos = None
        self._current_selection = None


# ========== Convenience exports ==========
__all__ = ["SelectionManager", "SelectionMode", "SelectionRegion", "SyncResult"]
