"""
Web/PDF比較校正テスト
パイプライン全体の動作確認

Usage: py -3 verify/test_proofing_pipeline.py
"""
import sys
import os
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

def test_proofing_pipeline():
    """比較校正パイプラインのテスト"""
    
    print("=" * 60)
    print("Web/PDF比較校正パイプライン テスト")
    print("=" * 60)
    
    # 1. テストデータ準備（左右）
    print("\n[1] テストデータ準備")
    print("-" * 40)
    
    left_elements = [
        {
            "id": "L1",
            "text": "商品名: プレミアムコーヒー豆 500g",
            "text_norm": "商品名: プレミアムコーヒー豆 500g",
            "bbox": {"x1": 50, "y1": 30, "x2": 400, "y2": 60},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [{"type": "product", "raw": "プレミアムコーヒー豆 500g", "value_norm": "プレミアムコーヒー豆 500g"}]
        },
        {
            "id": "L2",
            "text": "価格: ¥1,980（税込）",
            "text_norm": "価格: ¥1,980(税込)",
            "bbox": {"x1": 50, "y1": 80, "x2": 300, "y2": 110},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [{"type": "price", "raw": "¥1,980", "value_norm": "1980"}]
        },
        {
            "id": "L3",
            "text": "キャンペーン期間: 2024年1月15日〜2月28日",
            "text_norm": "キャンペーン期間: 2024-01-15~2024-02-28",
            "bbox": {"x1": 50, "y1": 130, "x2": 450, "y2": 160},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [
                {"type": "date", "raw": "2024年1月15日", "value_norm": "2024-01-15"},
                {"type": "date", "raw": "2月28日", "value_norm": "2024-02-28"}
            ]
        },
        {
            "id": "L4",
            "text": "※1 一部対象外商品あり",
            "text_norm": "※1 一部対象外商品あり",
            "bbox": {"x1": 50, "y1": 300, "x2": 250, "y2": 320},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [{"type": "legal_ref", "raw": "※1", "value_norm": "※1"}]
        }
    ]
    
    right_elements = [
        {
            "id": "R1",
            "text": "商品名: プレミアムコーヒー豆 500g",
            "text_norm": "商品名: プレミアムコーヒー豆 500g",
            "bbox": {"x1": 50, "y1": 30, "x2": 400, "y2": 60},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [{"type": "product", "raw": "プレミアムコーヒー豆 500g", "value_norm": "プレミアムコーヒー豆 500g"}]
        },
        {
            "id": "R2",
            "text": "価格: ¥1,880（税込）",  # ← 価格が違う！
            "text_norm": "価格: ¥1,880(税込)",
            "bbox": {"x1": 50, "y1": 80, "x2": 300, "y2": 110},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [{"type": "price", "raw": "¥1,880", "value_norm": "1880"}]
        },
        {
            "id": "R3",
            "text": "キャンペーン期間: 2024年1月15日〜3月31日",  # ← 日付が違う！
            "text_norm": "キャンペーン期間: 2024-01-15~2024-03-31",
            "bbox": {"x1": 50, "y1": 130, "x2": 450, "y2": 160},
            "page_num": 1,
            "kind": "paragraph",
            "fields": [
                {"type": "date", "raw": "2024年1月15日", "value_norm": "2024-01-15"},
                {"type": "date", "raw": "3月31日", "value_norm": "2024-03-31"}
            ]
        }
        # ← L4の注釈が右にはない！
    ]
    
    print(f"   左側要素数: {len(left_elements)}")
    print(f"   右側要素数: {len(right_elements)}")
    
    # 2. マッチング
    print("\n[2] マッチング")
    print("-" * 40)
    
    from app.pipeline.match import ElementMatcher
    matcher = ElementMatcher(threshold=0.3)
    matches = matcher.match_elements(left_elements, right_elements)
    
    for m in matches:
        status_icon = {"matched": "✓", "unmatched_left": "←", "unmatched_right": "→"}
        print(f"   {status_icon.get(m.status, '?')} {m.left_id or '(なし)':5} <-> {m.right_id or '(なし)':5} | {m.score_total:.0%} | {m.status}")
    
    # 3. 差分分類
    print("\n[3] 差分分類")
    print("-" * 40)
    
    from app.pipeline.diff import DiffClassifier, DiffType
    classifier = DiffClassifier()
    
    issues = []
    for m in matches:
        left_elem = next((e for e in left_elements if e["id"] == m.left_id), None)
        right_elem = next((e for e in right_elements if e["id"] == m.right_id), None)
        
        if m.status == "unmatched_left":
            diff = classifier.classify_missing(left_elem["text"] if left_elem else "")
        elif m.status == "unmatched_right":
            diff = classifier.classify_added(right_elem["text"] if right_elem else "")
        else:
            left_text = left_elem["text_norm"] if left_elem else ""
            right_text = right_elem["text_norm"] if right_elem else ""
            diff = classifier.classify_text_diff(left_text, right_text)
        
        if diff.diff_type != DiffType.SAME:
            issue = {
                "left_id": m.left_id,
                "right_id": m.right_id,
                "diff_type": diff.diff_type.value,
                "similarity": diff.similarity,
                "left_text": left_elem["text"] if left_elem else "",
                "right_text": right_elem["text"] if right_elem else "",
                "field_types": [f["type"] for f in (left_elem or {}).get("fields", [])]
            }
            issues.append(issue)
            
            print(f"   [{diff.diff_type.value:12}] {issue['left_text'][:30]}...")
    
    print(f"\n   → {len(issues)}件の差分検出")
    
    # 4. 重大度判定
    print("\n[4] 重大度判定")
    print("-" * 40)
    
    from app.core.rules_engine import evaluate_diff
    
    for issue in issues:
        field_type = issue["field_types"][0] if issue["field_types"] else None
        result = evaluate_diff(
            diff_type=issue["diff_type"],
            field_type=field_type,
            left_value=issue["left_text"],
            right_value=issue["right_text"]
        )
        issue["severity"] = result["severity"]
        issue["risk_reasons"] = result["risk_reasons"]
        
        severity_icon = {"CRITICAL": "🔴", "MAJOR": "🟠", "MINOR": "🟡", "INFO": "⚪"}
        print(f"   {severity_icon.get(result['severity'], '?')} {result['severity']:8} | {issue['left_text'][:35]}...")
        if result["risk_reasons"]:
            print(f"      理由: {', '.join(result['risk_reasons'])}")
    
    # 5. サマリー
    print("\n" + "=" * 60)
    print("検版結果サマリー")
    print("=" * 60)
    
    critical = sum(1 for i in issues if i.get("severity") == "CRITICAL")
    major = sum(1 for i in issues if i.get("severity") == "MAJOR")
    minor = sum(1 for i in issues if i.get("severity") == "MINOR")
    
    print(f"""
📊 要素数:
   左側: {len(left_elements)}
   右側: {len(right_elements)}
   マッチ: {sum(1 for m in matches if m.status == 'matched')}

⚠️ 検出Issue: {len(issues)}件
   🔴 CRITICAL: {critical}
   🟠 MAJOR:    {major}
   🟡 MINOR:    {minor}
""")
    
    if critical > 0:
        print("❌ CRITICAL Issue があります！確認が必要です。")
    elif len(issues) == 0:
        print("✅ 差分なし！完全一致です。")
    else:
        print("⚠️ 軽微な差分があります。")
    
    print("\n" + "=" * 60)
    print("✅ パイプラインテスト完了")
    print("=" * 60)
    
    return issues


if __name__ == "__main__":
    test_proofing_pipeline()
