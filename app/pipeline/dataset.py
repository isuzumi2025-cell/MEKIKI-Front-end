"""
Human-in-the-loop Dataset Module
教師データ蓄積・管理

Created: 2026-01-11
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import uuid


@dataclass
class MatchingSample:
    """マッチング教師データ"""
    sample_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    left_text: str = ""
    right_text: str = ""
    left_bbox: Optional[Dict[str, float]] = None
    right_bbox: Optional[Dict[str, float]] = None
    is_match: bool = True  # 正解ペアかどうか
    user_confirmed: bool = False
    confidence_before: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class OCRCorrection:
    """OCR補正データ"""
    correction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_crop_path: str = ""
    ocr_text: str = ""  # OCRが出力したテキスト
    corrected_text: str = ""  # ユーザーが補正したテキスト
    error_type: str = ""  # misread, missing, extra, etc.
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FieldExtraction:
    """フィールド抽出教師データ"""
    extraction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    raw_text: str = ""
    extracted_fields: List[Dict[str, Any]] = field(default_factory=list)
    corrected_fields: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TableAlignment:
    """テーブル対応付け教師データ"""
    alignment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    left_table_id: str = ""
    right_table_id: str = ""
    row_mapping: Dict[int, int] = field(default_factory=dict)  # left_row -> right_row
    col_mapping: Dict[int, int] = field(default_factory=dict)
    header_correction: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class DatasetManager:
    """
    教師データ管理クラス
    Human-in-the-loopで収集したデータをJSONL形式で保存
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        初期化
        
        Args:
            storage_path: 保存先ディレクトリ
        """
        self.storage_path = Path(storage_path) if storage_path else Path("storage/datasets")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # ファイルパス
        self.matching_file = self.storage_path / "matching_samples.jsonl"
        self.ocr_file = self.storage_path / "ocr_corrections.jsonl"
        self.fields_file = self.storage_path / "field_extractions.jsonl"
        self.tables_file = self.storage_path / "table_alignments.jsonl"
    
    # ========== Matching Samples ==========
    
    def add_matching_sample(
        self,
        left_text: str,
        right_text: str,
        is_match: bool,
        left_bbox: Optional[Dict] = None,
        right_bbox: Optional[Dict] = None,
        confidence_before: float = 0.0
    ) -> MatchingSample:
        """マッチングサンプルを追加"""
        sample = MatchingSample(
            left_text=left_text,
            right_text=right_text,
            is_match=is_match,
            left_bbox=left_bbox,
            right_bbox=right_bbox,
            user_confirmed=True,
            confidence_before=confidence_before
        )
        
        self._append_jsonl(self.matching_file, asdict(sample))
        return sample
    
    def get_matching_samples(self, limit: int = 1000) -> List[MatchingSample]:
        """マッチングサンプルを取得"""
        data = self._read_jsonl(self.matching_file, limit)
        return [MatchingSample(**d) for d in data]
    
    # ========== OCR Corrections ==========
    
    def add_ocr_correction(
        self,
        image_crop_path: str,
        ocr_text: str,
        corrected_text: str,
        error_type: str = ""
    ) -> OCRCorrection:
        """OCR補正を追加"""
        correction = OCRCorrection(
            image_crop_path=image_crop_path,
            ocr_text=ocr_text,
            corrected_text=corrected_text,
            error_type=error_type
        )
        
        self._append_jsonl(self.ocr_file, asdict(correction))
        return correction
    
    def get_ocr_corrections(self, limit: int = 1000) -> List[OCRCorrection]:
        """OCR補正を取得"""
        data = self._read_jsonl(self.ocr_file, limit)
        return [OCRCorrection(**d) for d in data]
    
    # ========== Field Extractions ==========
    
    def add_field_extraction(
        self,
        raw_text: str,
        extracted_fields: List[Dict],
        corrected_fields: List[Dict]
    ) -> FieldExtraction:
        """フィールド抽出教師データを追加"""
        extraction = FieldExtraction(
            raw_text=raw_text,
            extracted_fields=extracted_fields,
            corrected_fields=corrected_fields
        )
        
        self._append_jsonl(self.fields_file, asdict(extraction))
        return extraction
    
    def get_field_extractions(self, limit: int = 1000) -> List[FieldExtraction]:
        """フィールド抽出教師データを取得"""
        data = self._read_jsonl(self.fields_file, limit)
        return [FieldExtraction(**d) for d in data]
    
    # ========== Table Alignments ==========
    
    def add_table_alignment(
        self,
        left_table_id: str,
        right_table_id: str,
        row_mapping: Dict[int, int],
        col_mapping: Dict[int, int] = None,
        header_correction: Dict = None
    ) -> TableAlignment:
        """テーブル対応付け教師データを追加"""
        alignment = TableAlignment(
            left_table_id=left_table_id,
            right_table_id=right_table_id,
            row_mapping=row_mapping,
            col_mapping=col_mapping or {},
            header_correction=header_correction
        )
        
        self._append_jsonl(self.tables_file, asdict(alignment))
        return alignment
    
    def get_table_alignments(self, limit: int = 1000) -> List[TableAlignment]:
        """テーブル対応付け教師データを取得"""
        data = self._read_jsonl(self.tables_file, limit)
        return [TableAlignment(**d) for d in data]
    
    # ========== Statistics ==========
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            "matching_samples": self._count_lines(self.matching_file),
            "ocr_corrections": self._count_lines(self.ocr_file),
            "field_extractions": self._count_lines(self.fields_file),
            "table_alignments": self._count_lines(self.tables_file),
            "storage_path": str(self.storage_path)
        }
    
    # ========== Internal Methods ==========
    
    def _append_jsonl(self, file_path: Path, data: Dict):
        """JSONL形式で追記"""
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def _read_jsonl(self, file_path: Path, limit: int) -> List[Dict]:
        """JSONL形式で読み込み"""
        if not file_path.exists():
            return []
        
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                try:
                    data.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return data
    
    def _count_lines(self, file_path: Path) -> int:
        """行数をカウント"""
        if not file_path.exists():
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)


# ========== Convenience Functions ==========

def save_matching_feedback(
    left_text: str,
    right_text: str,
    is_match: bool,
    **kwargs
) -> MatchingSample:
    """マッチングフィードバック保存"""
    manager = DatasetManager()
    return manager.add_matching_sample(left_text, right_text, is_match, **kwargs)


def save_ocr_feedback(
    image_path: str,
    ocr_text: str,
    corrected_text: str,
    error_type: str = ""
) -> OCRCorrection:
    """OCRフィードバック保存"""
    manager = DatasetManager()
    return manager.add_ocr_correction(image_path, ocr_text, corrected_text, error_type)


def get_dataset_stats() -> Dict[str, Any]:
    """データセット統計取得"""
    manager = DatasetManager()
    return manager.get_statistics()


if __name__ == "__main__":
    # テスト
    manager = DatasetManager()
    
    # マッチングサンプル追加
    manager.add_matching_sample(
        left_text="商品価格: ¥1,980",
        right_text="商品価格: ¥1,880",
        is_match=True,
        confidence_before=0.85
    )
    
    # OCR補正追加
    manager.add_ocr_correction(
        image_crop_path="/path/to/crop.png",
        ocr_text="¥l,980",  # 1が小文字Lに誤認識
        corrected_text="¥1,980",
        error_type="misread"
    )
    
    # 統計表示
    stats = manager.get_statistics()
    print(f"Statistics: {stats}")
