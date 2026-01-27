"""
OCR Pipeline Trace - OCR処理の各段階をトレースするユーティリティ

Phase 1.9.0: 観測性の追加
- raw_tokens: OCR出力
- normalized_tokens: 正規化後
- filtered_tokens: フィルタ通過
- dropped_tokens: 落とされたトークン（理由付き）
- clustered_paragraphs: クラスタリング結果
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json


@dataclass
class TokenTrace:
    """個別トークンのトレース情報"""
    text: str
    bbox: List[int]
    confidence: float = 0.0
    source_engine: str = "cloud_vision"
    drop_reason: Optional[str] = None  # None = 保持, "min_length", "noise", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_engine": self.source_engine,
            "drop_reason": self.drop_reason
        }


@dataclass
class PipelineTrace:
    """
    OCRパイプライン全体のトレース
    
    各段階でtokenを記録し、どこでテキストが消失したかを追跡可能にする
    """
    page_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_tokens: List[TokenTrace] = field(default_factory=list)
    normalized_tokens: List[TokenTrace] = field(default_factory=list)
    filtered_tokens: List[TokenTrace] = field(default_factory=list)
    dropped_tokens: List[TokenTrace] = field(default_factory=list)
    clustered_paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    
    # メタデータ
    image_size: Optional[List[int]] = None  # [width, height]
    total_raw_chars: int = 0
    total_filtered_chars: int = 0
    
    def add_raw_token(self, text: str, bbox: List[int], confidence: float = 0.0, source: str = "cloud_vision"):
        """生のOCRトークンを追加"""
        self.raw_tokens.append(TokenTrace(
            text=text,
            bbox=bbox,
            confidence=confidence,
            source_engine=source
        ))
        self.total_raw_chars += len(text)
    
    def add_filtered_token(self, text: str, bbox: List[int], confidence: float = 0.0):
        """フィルタを通過したトークンを追加"""
        self.filtered_tokens.append(TokenTrace(
            text=text,
            bbox=bbox,
            confidence=confidence
        ))
        self.total_filtered_chars += len(text)
    
    def add_dropped_token(self, text: str, bbox: List[int], reason: str, confidence: float = 0.0):
        """フィルタで落とされたトークンを記録"""
        self.dropped_tokens.append(TokenTrace(
            text=text,
            bbox=bbox,
            confidence=confidence,
            drop_reason=reason
        ))
    
    def add_paragraph(self, para_id: str, text: str, bbox: List[int], component_count: int = 0):
        """クラスタリング後のパラグラフを追加"""
        self.clustered_paragraphs.append({
            "id": para_id,
            "text": text,
            "text_len": len(text),
            "bbox": bbox,
            "component_count": component_count
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """トレースサマリーを取得"""
        return {
            "page_id": self.page_id,
            "timestamp": self.timestamp,
            "raw_tokens": len(self.raw_tokens),
            "filtered_tokens": len(self.filtered_tokens),
            "dropped_tokens": len(self.dropped_tokens),
            "paragraphs": len(self.clustered_paragraphs),
            "total_raw_chars": self.total_raw_chars,
            "total_filtered_chars": self.total_filtered_chars,
            "drop_rate": f"{(1 - self.total_filtered_chars / max(self.total_raw_chars, 1)) * 100:.1f}%"
        }
    
    def find_dropped_text(self, search_text: str) -> List[TokenTrace]:
        """指定テキストを含むdrop済みトークンを検索"""
        results = []
        for token in self.dropped_tokens:
            if search_text.lower() in token.text.lower():
                results.append(token)
        return results
    
    def save(self, base_dir: str = "./debug/ocr_traces") -> str:
        """トレースをJSONファイルに保存"""
        # タイムスタンプからディレクトリ名を生成
        dir_name = self.timestamp.replace(":", "-")[:19]
        dir_path = Path(base_dir) / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # ファイルパス
        file_path = dir_path / f"{self.page_id}.json"
        
        # データ変換
        data = {
            "page_id": self.page_id,
            "timestamp": self.timestamp,
            "image_size": self.image_size,
            "summary": self.get_summary(),
            "raw_tokens": [t.to_dict() for t in self.raw_tokens],
            "normalized_tokens": [t.to_dict() for t in self.normalized_tokens],
            "filtered_tokens": [t.to_dict() for t in self.filtered_tokens],
            "dropped_tokens": [t.to_dict() for t in self.dropped_tokens],
            "clustered_paragraphs": self.clustered_paragraphs
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[OCR Trace] Saved: {file_path}")
        return str(file_path)


class TraceManager:
    """
    複数ページのトレースを管理
    
    Usage:
        manager = TraceManager()
        trace = manager.create_trace("web_1")
        trace.add_raw_token(...)
        trace.add_filtered_token(...)
        manager.save_all()
    """
    
    def __init__(self, base_dir: str = "./debug/ocr_traces"):
        self.base_dir = base_dir
        self.traces: Dict[str, PipelineTrace] = {}
        self.enabled = True  # 開発者トグル
    
    def create_trace(self, page_id: str) -> PipelineTrace:
        """新しいトレースを作成"""
        trace = PipelineTrace(page_id=page_id)
        self.traces[page_id] = trace
        return trace
    
    def get_trace(self, page_id: str) -> Optional[PipelineTrace]:
        """既存のトレースを取得"""
        return self.traces.get(page_id)
    
    def save_all(self) -> List[str]:
        """全トレースを保存"""
        if not self.enabled:
            return []
        
        saved_paths = []
        for trace in self.traces.values():
            path = trace.save(self.base_dir)
            saved_paths.append(path)
        
        return saved_paths
    
    def print_summary(self):
        """全トレースのサマリーを出力"""
        print("\n" + "=" * 60)
        print("OCR Pipeline Trace Summary")
        print("=" * 60)
        
        for page_id, trace in self.traces.items():
            summary = trace.get_summary()
            print(f"\n📄 {page_id}:")
            print(f"   Raw: {summary['raw_tokens']} tokens ({summary['total_raw_chars']} chars)")
            print(f"   Filtered: {summary['filtered_tokens']} tokens ({summary['total_filtered_chars']} chars)")
            print(f"   Dropped: {summary['dropped_tokens']} tokens (drop rate: {summary['drop_rate']})")
            print(f"   Paragraphs: {summary['paragraphs']}")
            
            # ドロップされたトークンの理由を集計
            if trace.dropped_tokens:
                reasons = {}
                for t in trace.dropped_tokens:
                    reason = t.drop_reason or "unknown"
                    reasons[reason] = reasons.get(reason, 0) + 1
                print(f"   Drop reasons: {reasons}")
        
        print("=" * 60 + "\n")


# グローバルインスタンス（オプション）
_global_manager: Optional[TraceManager] = None

def get_trace_manager() -> TraceManager:
    """グローバルTraceManagerを取得（遅延初期化）"""
    global _global_manager
    if _global_manager is None:
        _global_manager = TraceManager()
    return _global_manager
