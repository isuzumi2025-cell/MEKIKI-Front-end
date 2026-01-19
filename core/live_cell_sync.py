"""
即時セル反映機能
エリア選択時にスプレッドシートセルを即座に更新

Source: Phase D 新規実装
Created: 2026-01-11
"""
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import difflib


@dataclass
class CellData:
    """セルデータ"""
    unique_id: str = ""
    source: str = ""  # "web" or "pdf"
    text: str = ""
    rect: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    sync_rate: float = 0.0
    matched_id: Optional[str] = None


class LiveCellSync:
    """
    即時セル反映クラス
    キャンバス上のエリア選択をスプレッドシートに即座に反映
    """
    
    def __init__(self, on_cell_update: Callable = None):
        """
        Args:
            on_cell_update: セル更新時のコールバック
                           callback(cell_data: CellData, row_index: int)
        """
        self.on_cell_update = on_cell_update
        self.web_cells: Dict[str, CellData] = {}  # {unique_id: CellData}
        self.pdf_cells: Dict[str, CellData] = {}
        self.matches: List[Dict] = []  # [{"web_id": str, "pdf_id": str, "score": float}]
        self._next_web_id = 1
        self._next_pdf_id = 1
        self._current_page = 1
    
    def set_page(self, page_num: int):
        """現在のページ番号を設定"""
        self._current_page = page_num
    
    def generate_web_id(self) -> str:
        """WebエリアのユニークIDを生成"""
        uid = f"WEB-{self._next_web_id:03d}"
        self._next_web_id += 1
        return uid
    
    def generate_pdf_id(self) -> str:
        """PDFエリアのユニークIDを生成"""
        uid = f"PDF-P{self._current_page}-{self._next_pdf_id:03d}"
        self._next_pdf_id += 1
        return uid
    
    def add_web_cell(self, text: str, rect: List[int]) -> CellData:
        """Webエリアを追加"""
        uid = self.generate_web_id()
        cell = CellData(
            unique_id=uid,
            source="web",
            text=text,
            rect=rect.copy() if rect else [0, 0, 0, 0]
        )
        self.web_cells[uid] = cell
        return cell
    
    def add_pdf_cell(self, text: str, rect: List[int]) -> CellData:
        """PDFエリアを追加"""
        uid = self.generate_pdf_id()
        cell = CellData(
            unique_id=uid,
            source="pdf",
            text=text,
            rect=rect.copy() if rect else [0, 0, 0, 0]
        )
        self.pdf_cells[uid] = cell
        return cell
    
    def update_cell_text(self, unique_id: str, text: str):
        """セルのテキストを更新"""
        if unique_id in self.web_cells:
            self.web_cells[unique_id].text = text
            self._recalculate_sync_rate(unique_id)
        elif unique_id in self.pdf_cells:
            self.pdf_cells[unique_id].text = text
            self._recalculate_sync_rate(unique_id)
    
    def on_area_selected(self, area_id: int, source: str, text: str):
        """
        InteractiveCanvasからのコールバック
        エリア選択時に呼び出される
        
        Args:
            area_id: エリアID
            source: "web" or "pdf"
            text: エリアのテキスト
        """
        # 既存のセルを検索または新規作成
        if source == "web":
            uid = f"WEB-{area_id:03d}"
            if uid not in self.web_cells:
                cell = CellData(
                    unique_id=uid,
                    source="web",
                    text=text,
                    rect=[0, 0, 0, 0]
                )
                self.web_cells[uid] = cell
            else:
                self.web_cells[uid].text = text
            
            cell = self.web_cells[uid]
        else:
            uid = f"PDF-P{self._current_page}-{area_id:03d}"
            if uid not in self.pdf_cells:
                cell = CellData(
                    unique_id=uid,
                    source="pdf",
                    text=text,
                    rect=[0, 0, 0, 0]
                )
                self.pdf_cells[uid] = cell
            else:
                self.pdf_cells[uid].text = text
            
            cell = self.pdf_cells[uid]
        
        # シンクロ率を再計算
        self._recalculate_sync_rate(uid)
        
        # コールバック発火
        if self.on_cell_update:
            row_index = self._find_row_index(uid)
            self.on_cell_update(cell, row_index)
        
        print(f"📝 Cell updated: {uid} -> {text[:50]}..." if len(text) > 50 else f"📝 Cell updated: {uid} -> {text}")
    
    def _recalculate_sync_rate(self, unique_id: str):
        """シンクロ率を再計算"""
        cell = None
        matched_cell = None
        
        if unique_id in self.web_cells:
            cell = self.web_cells[unique_id]
            # マッチングを探す
            for match in self.matches:
                if match.get("web_id") == unique_id:
                    pdf_id = match.get("pdf_id")
                    matched_cell = self.pdf_cells.get(pdf_id)
                    break
        elif unique_id in self.pdf_cells:
            cell = self.pdf_cells[unique_id]
            for match in self.matches:
                if match.get("pdf_id") == unique_id:
                    web_id = match.get("web_id")
                    matched_cell = self.web_cells.get(web_id)
                    break
        
        if cell and matched_cell:
            # 類似度計算
            sync_rate = self._calculate_similarity(cell.text, matched_cell.text)
            cell.sync_rate = sync_rate
            cell.matched_id = matched_cell.unique_id
            matched_cell.sync_rate = sync_rate
            matched_cell.matched_id = cell.unique_id
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似度を計算"""
        if not text1 or not text2:
            return 0.0
        
        t1 = " ".join(text1.split())
        t2 = " ".join(text2.split())
        
        return difflib.SequenceMatcher(None, t1, t2).ratio()
    
    def _find_row_index(self, unique_id: str) -> int:
        """セルに対応する行インデックスを特定"""
        # Web/PDFのソート順に基づいて行番号を返す
        all_ids = list(self.web_cells.keys()) + list(self.pdf_cells.keys())
        all_ids.sort()
        
        try:
            return all_ids.index(unique_id)
        except ValueError:
            return -1
    
    def add_match(self, web_id: str, pdf_id: str, score: float = 0.0):
        """マッチングを追加"""
        self.matches.append({
            "web_id": web_id,
            "pdf_id": pdf_id,
            "score": score
        })
        
        # シンクロ率を更新
        if web_id in self.web_cells:
            self._recalculate_sync_rate(web_id)
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        web_count = len(self.web_cells)
        pdf_count = len(self.pdf_cells)
        match_count = len(self.matches)
        
        # 平均シンクロ率
        all_rates = [c.sync_rate for c in self.web_cells.values() if c.sync_rate > 0]
        all_rates.extend([c.sync_rate for c in self.pdf_cells.values() if c.sync_rate > 0])
        
        avg_sync = sum(all_rates) / len(all_rates) if all_rates else 0.0
        
        return {
            "web_count": web_count,
            "pdf_count": pdf_count,
            "match_count": match_count,
            "avg_sync_rate": avg_sync
        }
    
    def get_summary_text(self) -> str:
        """サマリーテキストを生成"""
        stats = self.get_statistics()
        return (
            f"Web: {stats['web_count']} | PDF: {stats['pdf_count']} | "
            f"Match: {stats['match_count']} | Avg Sync: {stats['avg_sync_rate']*100:.1f}%"
        )
    
    def clear(self):
        """全データをクリア"""
        self.web_cells.clear()
        self.pdf_cells.clear()
        self.matches.clear()
        self._next_web_id = 1
        self._next_pdf_id = 1
