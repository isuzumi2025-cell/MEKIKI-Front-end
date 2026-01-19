"""
Table Extraction Module
PDFとWebから表構造を抽出しGrid化

Created: 2026-01-11
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import uuid
import re


@dataclass
class TableCell:
    """テーブルセル"""
    cell_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    row: int = 0
    col: int = 0
    text: str = ""
    text_norm: str = ""
    bbox: Optional[Dict[str, float]] = None
    colspan: int = 1
    rowspan: int = 1
    is_header: bool = False
    fields: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExtractedTable:
    """抽出されたテーブル"""
    table_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    page_num: int = 0
    bbox: Optional[Dict[str, float]] = None
    caption: Optional[str] = None
    surrounding_heading: Optional[str] = None
    header_rows: int = 1
    header_cols: int = 0
    grid: List[List[TableCell]] = field(default_factory=list)
    row_count: int = 0
    col_count: int = 0


class TableExtractor:
    """
    テーブル抽出器
    テキストブロックから表構造を検出しグリッド化
    """
    
    def __init__(
        self,
        min_rows: int = 2,
        min_cols: int = 2,
        header_detection: bool = True
    ):
        """
        初期化
        
        Args:
            min_rows: 最小行数
            min_cols: 最小列数
            header_detection: ヘッダ自動検出
        """
        self.min_rows = min_rows
        self.min_cols = min_cols
        self.header_detection = header_detection
    
    def extract_from_blocks(
        self,
        text_blocks: List[Dict[str, Any]],
        page_num: int = 0
    ) -> List[ExtractedTable]:
        """
        テキストブロックから表を抽出
        
        Args:
            text_blocks: テキストブロックのリスト [{text, bbox}, ...]
            page_num: ページ番号
            
        Returns:
            ExtractedTableのリスト
        """
        if not text_blocks:
            return []
        
        tables = []
        
        # 1. 表候補領域を検出（水平整列したブロック群）
        table_regions = self._detect_table_regions(text_blocks)
        
        for region in table_regions:
            # 2. グリッド化
            table = self._regionalize_to_grid(region, page_num)
            
            if table and table.row_count >= self.min_rows and table.col_count >= self.min_cols:
                # 3. ヘッダ検出
                if self.header_detection:
                    self._detect_headers(table)
                
                tables.append(table)
        
        return tables
    
    def _detect_table_regions(
        self,
        blocks: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        表の候補領域を検出
        
        水平方向に複数ブロックが整列している領域を検出
        """
        if not blocks:
            return []
        
        # Y座標でソート
        sorted_blocks = sorted(blocks, key=lambda b: b.get("bbox", {}).get("y1", 0))
        
        # 行をグループ化（Y座標が近いものをまとめる）
        rows = []
        current_row = []
        current_y = None
        y_tolerance = 15  # ピクセル
        
        for block in sorted_blocks:
            bbox = block.get("bbox", {})
            y = bbox.get("y1", 0)
            
            if current_y is None or abs(y - current_y) <= y_tolerance:
                current_row.append(block)
                if current_y is None:
                    current_y = y
            else:
                if current_row:
                    rows.append(sorted(current_row, key=lambda b: b.get("bbox", {}).get("x1", 0)))
                current_row = [block]
                current_y = y
        
        if current_row:
            rows.append(sorted(current_row, key=lambda b: b.get("bbox", {}).get("x1", 0)))
        
        # 表候補: 連続して2列以上あるセクション
        table_regions = []
        current_region = []
        
        for row in rows:
            if len(row) >= 2:  # 2列以上
                current_region.append(row)
            else:
                if len(current_region) >= self.min_rows:
                    table_regions.append(current_region)
                current_region = []
        
        if len(current_region) >= self.min_rows:
            table_regions.append(current_region)
        
        return table_regions
    
    def _regionalize_to_grid(
        self,
        region: List[List[Dict[str, Any]]],
        page_num: int
    ) -> Optional[ExtractedTable]:
        """
        領域をグリッド構造に変換
        """
        if not region:
            return None
        
        # 列境界を推定
        all_x_positions = []
        for row in region:
            for block in row:
                bbox = block.get("bbox", {})
                all_x_positions.append(bbox.get("x1", 0))
                all_x_positions.append(bbox.get("x2", 0))
        
        if not all_x_positions:
            return None
        
        # 列境界をクラスタリング
        col_boundaries = self._cluster_positions(sorted(set(all_x_positions)))
        
        table = ExtractedTable(page_num=page_num)
        
        # グリッド構築
        for row_idx, row_blocks in enumerate(region):
            grid_row = []
            
            for col_idx, boundary in enumerate(col_boundaries[:-1]):
                next_boundary = col_boundaries[col_idx + 1]
                
                # この列に属するブロックを探す
                cell_text = ""
                cell_bbox = None
                
                for block in row_blocks:
                    bbox = block.get("bbox", {})
                    block_center_x = (bbox.get("x1", 0) + bbox.get("x2", 0)) / 2
                    
                    if boundary <= block_center_x < next_boundary:
                        cell_text = block.get("text", "")
                        cell_bbox = bbox
                        break
                
                cell = TableCell(
                    row=row_idx,
                    col=col_idx,
                    text=cell_text,
                    text_norm=self._normalize_cell_text(cell_text),
                    bbox=cell_bbox
                )
                grid_row.append(cell)
            
            table.grid.append(grid_row)
        
        table.row_count = len(table.grid)
        table.col_count = len(col_boundaries) - 1 if col_boundaries else 0
        
        # 外接矩形
        if region:
            all_blocks = [b for row in region for b in row]
            table.bbox = self._calculate_union_bbox(all_blocks)
        
        return table
    
    def _cluster_positions(
        self,
        positions: List[float],
        tolerance: float = 20
    ) -> List[float]:
        """
        位置をクラスタリングして境界を決定
        """
        if not positions:
            return []
        
        clusters = []
        current_cluster = [positions[0]]
        
        for pos in positions[1:]:
            if abs(pos - current_cluster[-1]) <= tolerance:
                current_cluster.append(pos)
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [pos]
        
        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))
        
        return clusters
    
    def _detect_headers(self, table: ExtractedTable):
        """
        ヘッダ行/列を検出
        """
        if not table.grid:
            return
        
        # 最初の行をヘッダ候補としてチェック
        first_row = table.grid[0]
        
        # ヘッダ判定条件:
        # - 数字が少ない
        # - 短いテキスト
        # - 特定のキーワード
        header_keywords = ["名前", "項目", "商品", "価格", "数量", "合計", 
                          "日付", "期間", "サイズ", "カラー", "型番"]
        
        is_header_row = True
        for cell in first_row:
            text = cell.text_norm
            
            # 数字が多い場合はデータ行
            digit_ratio = sum(1 for c in text if c.isdigit()) / max(len(text), 1)
            if digit_ratio > 0.5:
                is_header_row = False
                break
            
            # 価格っぽい場合はデータ行
            if re.search(r'[¥￥]\s*[\d,]+|[\d,]+円', text):
                is_header_row = False
                break
        
        if is_header_row:
            table.header_rows = 1
            for cell in first_row:
                cell.is_header = True
    
    def _normalize_cell_text(self, text: str) -> str:
        """セルテキストを正規化"""
        # 空白・改行を統一
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _calculate_union_bbox(self, blocks: List[Dict[str, Any]]) -> Dict[str, float]:
        """ブロック群の外接矩形"""
        if not blocks:
            return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
        
        x1s, y1s, x2s, y2s = [], [], [], []
        for block in blocks:
            bbox = block.get("bbox", {})
            x1s.append(bbox.get("x1", 0))
            y1s.append(bbox.get("y1", 0))
            x2s.append(bbox.get("x2", 0))
            y2s.append(bbox.get("y2", 0))
        
        return {
            "x1": min(x1s),
            "y1": min(y1s),
            "x2": max(x2s),
            "y2": max(y2s)
        }


class TableComparator:
    """
    テーブル比較器
    2つの表を比較し差分を検出
    """
    
    def compare_tables(
        self,
        left_table: ExtractedTable,
        right_table: ExtractedTable
    ) -> Dict[str, Any]:
        """
        2つのテーブルを比較
        
        Returns:
            {
                "match_score": float,
                "row_diff": {"added": [...], "removed": [...], "modified": [...]},
                "col_diff": {"added": [...], "removed": [...]},
                "cell_diffs": [{"row", "col", "left", "right"}, ...]
            }
        """
        result = {
            "match_score": 0.0,
            "row_diff": {"added": [], "removed": [], "modified": []},
            "col_diff": {"added": [], "removed": []},
            "cell_diffs": []
        }
        
        # 行数・列数の差分
        if left_table.row_count != right_table.row_count:
            if left_table.row_count > right_table.row_count:
                result["row_diff"]["removed"] = list(range(right_table.row_count, left_table.row_count))
            else:
                result["row_diff"]["added"] = list(range(left_table.row_count, right_table.row_count))
        
        if left_table.col_count != right_table.col_count:
            if left_table.col_count > right_table.col_count:
                result["col_diff"]["removed"] = list(range(right_table.col_count, left_table.col_count))
            else:
                result["col_diff"]["added"] = list(range(left_table.col_count, right_table.col_count))
        
        # セル単位比較
        min_rows = min(left_table.row_count, right_table.row_count)
        min_cols = min(left_table.col_count, right_table.col_count)
        
        match_count = 0
        total_cells = 0
        
        for r in range(min_rows):
            for c in range(min_cols):
                left_cell = left_table.grid[r][c] if r < len(left_table.grid) and c < len(left_table.grid[r]) else None
                right_cell = right_table.grid[r][c] if r < len(right_table.grid) and c < len(right_table.grid[r]) else None
                
                left_text = left_cell.text_norm if left_cell else ""
                right_text = right_cell.text_norm if right_cell else ""
                
                total_cells += 1
                
                if left_text == right_text:
                    match_count += 1
                else:
                    result["cell_diffs"].append({
                        "row": r,
                        "col": c,
                        "left": left_text,
                        "right": right_text
                    })
        
        result["match_score"] = match_count / total_cells if total_cells > 0 else 1.0
        
        return result


# ========== Convenience Function ==========

def extract_tables(
    text_blocks: List[Dict[str, Any]],
    page_num: int = 0
) -> List[ExtractedTable]:
    """
    テーブル抽出（簡易インターフェース）
    """
    extractor = TableExtractor()
    return extractor.extract_from_blocks(text_blocks, page_num)


if __name__ == "__main__":
    # テスト
    test_blocks = [
        {"text": "商品名", "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 120}},
        {"text": "価格", "bbox": {"x1": 220, "y1": 100, "x2": 300, "y2": 120}},
        {"text": "数量", "bbox": {"x1": 320, "y1": 100, "x2": 400, "y2": 120}},
        {"text": "商品A", "bbox": {"x1": 100, "y1": 130, "x2": 200, "y2": 150}},
        {"text": "¥1,980", "bbox": {"x1": 220, "y1": 130, "x2": 300, "y2": 150}},
        {"text": "2", "bbox": {"x1": 320, "y1": 130, "x2": 400, "y2": 150}},
        {"text": "商品B", "bbox": {"x1": 100, "y1": 160, "x2": 200, "y2": 180}},
        {"text": "¥2,500", "bbox": {"x1": 220, "y1": 160, "x2": 300, "y2": 180}},
        {"text": "1", "bbox": {"x1": 320, "y1": 160, "x2": 400, "y2": 180}},
    ]
    
    tables = extract_tables(test_blocks)
    
    for table in tables:
        print(f"Table: {table.row_count} rows x {table.col_count} cols")
        print(f"Header rows: {table.header_rows}")
        for row in table.grid:
            print([cell.text for cell in row])
