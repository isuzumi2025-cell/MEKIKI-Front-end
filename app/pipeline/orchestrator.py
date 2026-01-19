"""
Proofing Pipeline Orchestrator
全パイプラインを統合して実行

Created: 2026-01-11
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Pipeline modules
from .ingest_web import WebIngestor, WebCaptureResult
from .ingest_pdf import PDFIngestor, PDFCaptureResult
from .normalize import TextNormalizer, normalize_text
from .match import ElementMatcher, MatchResult
from .diff import DiffClassifier, DiffResult, DiffType
from .spreadsheet_exporter import SpreadsheetExporter, export_issues

# Core modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.core.paragraphize import paragraphize
from app.core.fields_extract import extract_fields
from app.core.rules_engine import RulesEngine, evaluate_diff
from app.core.image_preprocessor import ImagePreprocessor


@dataclass
class ProofingResult:
    """検版結果"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    left_source: str = ""
    right_source: str = ""
    total_elements: int = 0
    matched_count: int = 0
    issue_count: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    export_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


class ProofingPipeline:
    """
    検版パイプライン
    Web/PDFの取り込み → 抽出 → マッチング → 差分検出 → エクスポート
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        rules_path: Optional[str] = None
    ):
        """
        初期化
        
        Args:
            storage_path: データ保存先
            rules_path: ルール設定ファイルパス
        """
        self.storage_path = Path(storage_path) if storage_path else Path("storage/runs")
        
        # コンポーネント初期化
        self.normalizer = TextNormalizer()
        self.matcher = ElementMatcher()
        self.diff_classifier = DiffClassifier()
        self.rules_engine = RulesEngine(rules_path)
        self.preprocessor = ImagePreprocessor()
        self.exporter = SpreadsheetExporter(storage_path)
    
    def run(
        self,
        left_source: str,
        right_source: str,
        left_type: str = "auto",  # web, pdf, auto
        right_type: str = "auto",
        export_xlsx: bool = True
    ) -> ProofingResult:
        """
        検版パイプラインを実行
        
        Args:
            left_source: 左側ソース (URL or PDF path)
            right_source: 右側ソース
            left_type: 左側ソースタイプ
            right_type: 右側ソースタイプ
            export_xlsx: Excel出力するか
            
        Returns:
            ProofingResult
        """
        result = ProofingResult(
            left_source=left_source,
            right_source=right_source
        )
        
        try:
            run_dir = self.storage_path / result.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. ソースタイプ判定
            left_type = self._detect_source_type(left_source) if left_type == "auto" else left_type
            right_type = self._detect_source_type(right_source) if right_type == "auto" else right_type
            
            # 2. 取り込み（同期版 - 簡易実装）
            left_elements = self._ingest_and_extract(left_source, left_type, result.run_id, "left")
            right_elements = self._ingest_and_extract(right_source, right_type, result.run_id, "right")
            
            result.total_elements = len(left_elements) + len(right_elements)
            
            # 3. マッチング
            matches = self.matcher.match_elements(left_elements, right_elements)
            result.matched_count = sum(1 for m in matches if m.status == "matched")
            
            # 4. 差分検出 + 重大度判定
            issues = []
            for match in matches:
                issue = self._analyze_match(match, left_elements, right_elements)
                if issue:
                    issues.append(issue)
                    
                    # カウント
                    severity = issue.get("severity", "INFO")
                    if severity == "CRITICAL":
                        result.critical_count += 1
                    elif severity == "MAJOR":
                        result.major_count += 1
                    elif severity == "MINOR":
                        result.minor_count += 1
            
            result.issues = issues
            result.issue_count = len(issues)
            
            # 5. エクスポート
            if export_xlsx and issues:
                export_result = self.exporter.export_xlsx(issues, result.run_id)
                result.export_path = export_result.file_path
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _detect_source_type(self, source: str) -> str:
        """ソースタイプを自動判定"""
        source_lower = source.lower()
        if source_lower.startswith("http://") or source_lower.startswith("https://"):
            return "web"
        elif source_lower.endswith(".pdf"):
            return "pdf"
        else:
            return "unknown"
    
    def _ingest_and_extract(
        self,
        source: str,
        source_type: str,
        run_id: str,
        side: str
    ) -> List[Dict[str, Any]]:
        """
        取り込み + テキスト抽出
        
        Returns:
            段落要素のリスト
        """
        elements = []
        
        if source_type == "pdf":
            ingestor = PDFIngestor(storage_path=str(self.storage_path))
            capture = ingestor.capture(source, run_id=run_id)
            
            for page in capture.pages:
                for block in page.text_blocks:
                    # 正規化
                    text_norm = self.normalizer.normalize(block.text)
                    
                    # フィールド抽出
                    fields = extract_fields(block.text)
                    
                    elements.append({
                        "id": f"{side}_p{page.page_num}_{len(elements)}",
                        "text": block.text,
                        "text_norm": text_norm,
                        "bbox": {
                            "x1": block.bbox[0],
                            "y1": block.bbox[1],
                            "x2": block.bbox[2],
                            "y2": block.bbox[3]
                        },
                        "page_num": page.page_num,
                        "kind": "paragraph",
                        "source_type": "pdf",
                        "fields": fields
                    })
        
        # Web (非同期は簡略化のため今回は省略)
        # 実際の実装ではasyncio.run()で呼び出す
        
        return elements
    
    def _analyze_match(
        self,
        match: MatchResult,
        left_elements: List[Dict[str, Any]],
        right_elements: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        マッチを分析してIssue辞書を生成
        """
        # 要素を取得
        left_elem = self._find_element(match.left_id, left_elements)
        right_elem = self._find_element(match.right_id, right_elements)
        
        # 差分分類
        if match.status == "unmatched_left":
            diff = self.diff_classifier.classify_missing(left_elem.get("text", "") if left_elem else "")
        elif match.status == "unmatched_right":
            diff = self.diff_classifier.classify_added(right_elem.get("text", "") if right_elem else "")
        else:
            left_text = left_elem.get("text_norm", "") if left_elem else ""
            right_text = right_elem.get("text_norm", "") if right_elem else ""
            diff = self.diff_classifier.classify_text_diff(left_text, right_text)
        
        # 完全一致はスキップ
        if diff.diff_type == DiffType.SAME:
            return None
        
        # 重大度判定
        severity_result = evaluate_diff(
            diff_type=diff.diff_type.value,
            left_value=left_elem.get("text") if left_elem else None,
            right_value=right_elem.get("text") if right_elem else None
        )
        
        # Issue辞書を構築
        return {
            "issue_id": str(uuid.uuid4()),
            "match_id": match.match_id,
            "left_id": match.left_id,
            "right_id": match.right_id,
            "page_left": left_elem.get("page_num") if left_elem else None,
            "page_right": right_elem.get("page_num") if right_elem else None,
            "element_kind": "paragraph",
            "left_text_norm": left_elem.get("text_norm", "") if left_elem else "",
            "right_text_norm": right_elem.get("text_norm", "") if right_elem else "",
            "field_types": [f["type"] for f in left_elem.get("fields", [])] if left_elem else [],
            "diff_type": diff.diff_type.value,
            "diff_html": diff.diff_html,
            "severity": severity_result["severity"],
            "risk_reason": severity_result["risk_reasons"],
            "score_total": match.score_total,
            "status": "OPEN"
        }
    
    def _find_element(self, elem_id: str, elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """IDで要素を検索"""
        if not elem_id:
            return None
        for elem in elements:
            if elem.get("id") == elem_id:
                return elem
        return None


# ========== Convenience Function ==========

def run_proofing(
    left_source: str,
    right_source: str,
    **kwargs
) -> ProofingResult:
    """
    検版実行（簡易インターフェース）
    """
    pipeline = ProofingPipeline()
    return pipeline.run(left_source, right_source, **kwargs)
