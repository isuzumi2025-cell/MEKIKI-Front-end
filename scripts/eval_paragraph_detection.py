"""
段落検出評価スクリプト

Paragraph Boundary F1, Over-split率, Over-merge率を計測
"""
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParagraphSpan:
    """段落の範囲を示す"""
    start_line: int
    end_line: int
    text: str = ""
    paragraph_id: str = ""


@dataclass
class EvaluationResult:
    """評価結果"""
    precision: float
    recall: float
    f1: float
    over_split_rate: float
    over_merge_rate: float
    total_gold: int
    total_pred: int
    matched: int


def extract_boundaries(paragraphs: List[ParagraphSpan]) -> List[int]:
    """段落リストから境界位置（行番号）を抽出"""
    boundaries = set()
    for p in paragraphs:
        boundaries.add(p.start_line)
        boundaries.add(p.end_line + 1)  # 終端の次
    return sorted(boundaries)


def calculate_boundary_f1(
    gold_paragraphs: List[ParagraphSpan],
    pred_paragraphs: List[ParagraphSpan],
    tolerance: int = 0
) -> EvaluationResult:
    """
    段落境界のF1スコアを計算
    
    Args:
        gold_paragraphs: 正解段落リスト
        pred_paragraphs: 予測段落リスト
        tolerance: 境界位置の許容誤差（行数）
    
    Returns:
        EvaluationResult: 評価結果
    """
    gold_boundaries = extract_boundaries(gold_paragraphs)
    pred_boundaries = extract_boundaries(pred_paragraphs)
    
    # マッチング
    matched = 0
    used_pred = set()
    
    for g in gold_boundaries:
        for i, p in enumerate(pred_boundaries):
            if i not in used_pred and abs(g - p) <= tolerance:
                matched += 1
                used_pred.add(i)
                break
    
    precision = matched / len(pred_boundaries) if pred_boundaries else 0.0
    recall = matched / len(gold_boundaries) if gold_boundaries else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Over-split: 予測が正解より多い
    over_split_rate = max(0, len(pred_paragraphs) - len(gold_paragraphs)) / len(gold_paragraphs) if gold_paragraphs else 0.0
    
    # Over-merge: 予測が正解より少ない
    over_merge_rate = max(0, len(gold_paragraphs) - len(pred_paragraphs)) / len(gold_paragraphs) if gold_paragraphs else 0.0
    
    return EvaluationResult(
        precision=precision,
        recall=recall,
        f1=f1,
        over_split_rate=over_split_rate,
        over_merge_rate=over_merge_rate,
        total_gold=len(gold_paragraphs),
        total_pred=len(pred_paragraphs),
        matched=matched
    )


def load_gold_annotations(json_path: Path) -> List[ParagraphSpan]:
    """正解アノテーションをJSONから読み込み"""
    if not json_path.exists():
        return []
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    paragraphs = []
    for item in data.get('paragraphs', []):
        paragraphs.append(ParagraphSpan(
            start_line=item.get('start_line', 0),
            end_line=item.get('end_line', 0),
            text=item.get('text', ''),
            paragraph_id=item.get('id', '')
        ))
    
    return paragraphs


def evaluate_document(
    gold_path: Path,
    pred_paragraphs: List[ParagraphSpan]
) -> Optional[EvaluationResult]:
    """1ドキュメントの評価"""
    gold_paragraphs = load_gold_annotations(gold_path)
    if not gold_paragraphs:
        print(f"⚠️ No gold annotations found: {gold_path}")
        return None
    
    result = calculate_boundary_f1(gold_paragraphs, pred_paragraphs)
    return result


def run_evaluation_suite(eval_dir: Path) -> Dict[str, EvaluationResult]:
    """
    評価セット全体を実行
    
    eval_dir構造:
    - eval_dir/
      - sample_001/
        - gold.json
        - input.pdf/.html/.png
      - sample_002/
        - ...
    """
    results = {}
    
    for sample_dir in eval_dir.iterdir():
        if not sample_dir.is_dir():
            continue
        
        gold_path = sample_dir / 'gold.json'
        if not gold_path.exists():
            print(f"⏭️ Skipping {sample_dir.name}: no gold.json")
            continue
        
        # TODO: 実際の段落検出を実行
        # pred_paragraphs = detect_paragraphs(sample_dir)
        pred_paragraphs = []  # プレースホルダー
        
        result = evaluate_document(gold_path, pred_paragraphs)
        if result:
            results[sample_dir.name] = result
    
    return results


def print_summary(results: Dict[str, EvaluationResult]):
    """結果サマリーを表示"""
    if not results:
        print("No results to summarize")
        return
    
    print("\n" + "=" * 60)
    print("📊 Paragraph Detection Evaluation Summary")
    print("=" * 60)
    
    total_f1 = 0.0
    total_over_split = 0.0
    total_over_merge = 0.0
    
    for name, r in results.items():
        print(f"\n📄 {name}")
        print(f"   F1: {r.f1:.3f} (P={r.precision:.3f}, R={r.recall:.3f})")
        print(f"   Over-split: {r.over_split_rate:.1%}, Over-merge: {r.over_merge_rate:.1%}")
        print(f"   Gold: {r.total_gold} paragraphs, Pred: {r.total_pred} paragraphs")
        
        total_f1 += r.f1
        total_over_split += r.over_split_rate
        total_over_merge += r.over_merge_rate
    
    n = len(results)
    print("\n" + "-" * 60)
    print(f"📈 Average F1: {total_f1/n:.3f}")
    print(f"📈 Average Over-split: {total_over_split/n:.1%}")
    print(f"📈 Average Over-merge: {total_over_merge/n:.1%}")
    print("=" * 60)


# サンプル正解データテンプレート
GOLD_TEMPLATE = {
    "document_id": "sample_001",
    "source_type": "pdf",  # pdf | web | ocr
    "paragraphs": [
        {
            "id": "P1",
            "start_line": 1,
            "end_line": 5,
            "text": "段落1のテキスト...",
            "bbox": [0, 0, 100, 50]
        },
        {
            "id": "P2", 
            "start_line": 6,
            "end_line": 10,
            "text": "段落2のテキスト...",
            "bbox": [0, 50, 100, 100]
        }
    ]
}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        eval_dir = Path(sys.argv[1])
    else:
        eval_dir = Path("Vault/40_Evals")
    
    print(f"🔍 Evaluating: {eval_dir}")
    results = run_evaluation_suite(eval_dir)
    print_summary(results)
