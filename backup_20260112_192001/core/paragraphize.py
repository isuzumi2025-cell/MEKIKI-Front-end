"""
段落化パイプライン
OCR要素を正規化 → クラスタリング → ロール推定

Legacy移植元: 251219_OCR_scanapp_backup01_scan/app/pipeline/paragraph.py

Created: 2026-01-11
"""
from typing import List, Dict, Any, Tuple, Optional
import math


def extract_ocr_elements(ocr_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    OCR結果から要素（単語/行）を抽出
    
    Args:
        ocr_result: Vision API のOCR結果
    
    Returns:
        要素のリスト（各要素は text, bbox, confidence を持つ）
    """
    elements = []
    
    if "full_text_annotation" not in ocr_result:
        return elements
    
    pages = ocr_result["full_text_annotation"].get("pages", [])
    for page in pages:
        for block in page.get("blocks", []):
            for para in block.get("paragraphs", []):
                for word in para.get("words", []):
                    elements.append({
                        "kind": "word",
                        "text": word.get("text", ""),
                        "bbox": word.get("bounding_box", {}),
                        "confidence": word.get("confidence", 0.0),
                    })
    
    return elements


def normalize_ocr_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Step A: OCR要素の正規化（ソート規則固定、行推定、空白推定）
    
    Args:
        elements: OCR要素のリスト
    
    Returns:
        正規化された要素のリスト
    """
    if not elements:
        return []
    
    # 座標ソート規則を固定: 上→下、左→右
    def sort_key(elem: Dict[str, Any]) -> Tuple[float, float]:
        bbox = elem.get("bbox", {})
        y = bbox.get("y1", 0)
        x = bbox.get("x1", 0)
        return (y, x)
    
    sorted_elements = sorted(elements, key=sort_key)
    
    # 行推定: 同じY座標範囲の要素をグループ化
    lines = []
    current_line = []
    current_y = None
    y_tolerance = 10  # ピクセル
    
    for elem in sorted_elements:
        bbox = elem.get("bbox", {})
        y = bbox.get("y1", 0)
        
        if current_y is None or abs(y - current_y) > y_tolerance:
            if current_line:
                lines.append(current_line)
            current_line = [elem]
            current_y = y
        else:
            current_line.append(elem)
    
    if current_line:
        lines.append(current_line)
    
    # 行内で左→右にソート
    normalized = []
    for line in lines:
        line_sorted = sorted(line, key=lambda e: e.get("bbox", {}).get("x1", 0))
        normalized.extend(line_sorted)
    
    return normalized


def cluster_paragraphs(
    elements: List[Dict[str, Any]],
    distance_px: int = 18,
    align_tolerance_px: int = 8,
    size_similarity_threshold: float = 0.7,
) -> List[List[Dict[str, Any]]]:
    """
    Step B: 段落クラスタリング（近接×整列×サイズ）
    
    Args:
        elements: 正規化されたOCR要素
        distance_px: 近接距離閾値
        align_tolerance_px: 整列許容
        size_similarity_threshold: サイズ類似度閾値
    
    Returns:
        段落クラスタのリスト（各クラスタは要素のリスト）
    """
    if not elements:
        return []
    
    clusters = []
    
    for elem in elements:
        bbox = elem.get("bbox", {})
        elem_center_x = (bbox.get("x1", 0) + bbox.get("x2", 0)) / 2
        elem_center_y = (bbox.get("y1", 0) + bbox.get("y2", 0)) / 2
        elem_width = bbox.get("x2", 0) - bbox.get("x1", 0)
        elem_height = bbox.get("y2", 0) - bbox.get("y1", 0)
        elem_size = elem_width * elem_height
        
        # 既存のクラスタに追加できるかチェック
        assigned = False
        for cluster in clusters:
            if not cluster:
                continue
            
            # クラスタの最後の要素と比較（直近の要素と近接性を判定）
            last_elem = cluster[-1]
            last_bbox = last_elem.get("bbox", {})
            last_bottom = last_bbox.get("y2", 0)
            last_left = last_bbox.get("x1", 0)
            last_width = last_bbox.get("x2", 0) - last_bbox.get("x1", 0)
            last_height = last_bbox.get("y2", 0) - last_bbox.get("y1", 0)
            last_size = last_width * last_height
            
            # 垂直距離（前の要素の下端から現在の要素の上端）
            vertical_gap = bbox.get("y1", 0) - last_bottom
            
            # 水平整列チェック
            align_diff = abs(bbox.get("x1", 0) - last_left)
            
            # サイズ類似度
            size_ratio = min(elem_size, last_size) / max(elem_size, last_size) if max(elem_size, last_size) > 0 else 0
            
            # クラスタリング条件:
            # - 垂直距離が閾値以内
            # - 左端が揃っている
            # - サイズが似ている
            if (
                0 <= vertical_gap <= distance_px
                and align_diff <= align_tolerance_px
                and size_ratio >= size_similarity_threshold
            ):
                cluster.append(elem)
                assigned = True
                break
        
        if not assigned:
            # 新しいクラスタを作成
            clusters.append([elem])
    
    return clusters


def estimate_role(
    cluster: List[Dict[str, Any]],
    avg_font_size: float,
    headline_size_ratio: float = 1.5,
    price_digit_ratio: float = 0.3,
    caption_size_ratio: float = 0.8,
) -> str:
    """
    Step C: 段落ロール推定
    
    Args:
        cluster: 段落クラスタ（要素のリスト）
        avg_font_size: 平均フォントサイズ
        headline_size_ratio: 見出し判定のサイズ比率
        price_digit_ratio: 価格判定の数字割合
        caption_size_ratio: 注釈判定のサイズ比率
    
    Returns:
        ロール: "headline", "body", "caption", "price", "legal", "other"
    """
    if not cluster:
        return "other"
    
    # テキストを結合
    text = "".join([elem.get("text", "") for elem in cluster])
    
    # フォントサイズ推定（bboxの高さから）
    heights = []
    for elem in cluster:
        bbox = elem.get("bbox", {})
        height = bbox.get("y2", 0) - bbox.get("y1", 0)
        if height > 0:
            heights.append(height)
    
    if not heights:
        return "other"
    
    cluster_font_size = sum(heights) / len(heights)
    
    # 見出し判定: フォントサイズが平均の何倍以上か
    if cluster_font_size >= avg_font_size * headline_size_ratio:
        return "headline"
    
    # 注釈/規約判定: フォントサイズが平均の何倍以下か
    if cluster_font_size <= avg_font_size * caption_size_ratio:
        # 規約キーワードチェック
        legal_keywords = ["規約", "注意", "※", "条項", "免責", "ご注意", "お問い合わせ"]
        if any(keyword in text for keyword in legal_keywords):
            return "legal"
        return "caption"
    
    # 価格判定: 数字+記号の割合
    digit_count = sum(1 for c in text if c.isdigit() or c in "¥円,.")
    if len(text) > 0 and digit_count / len(text) >= price_digit_ratio:
        return "price"
    
    # デフォルト: 本文
    return "body"


def calculate_bbox_union(cluster: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    クラスタの外接矩形を計算
    
    Args:
        cluster: 要素のリスト
    
    Returns:
        bbox_union: {"x1": float, "y1": float, "x2": float, "y2": float}
    """
    if not cluster:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    
    x1s = []
    y1s = []
    x2s = []
    y2s = []
    
    for elem in cluster:
        bbox = elem.get("bbox", {})
        x1s.append(bbox.get("x1", 0))
        y1s.append(bbox.get("y1", 0))
        x2s.append(bbox.get("x2", 0))
        y2s.append(bbox.get("y2", 0))
    
    return {
        "x1": min(x1s) if x1s else 0,
        "y1": min(y1s) if y1s else 0,
        "x2": max(x2s) if x2s else 0,
        "y2": max(y2s) if y2s else 0,
    }


def paragraphize(
    ocr_result: Dict[str, Any],
    distance_px: int = 18,
    align_tolerance_px: int = 8,
) -> List[Dict[str, Any]]:
    """
    OCR結果を段落に変換（メインエントリポイント）
    
    Args:
        ocr_result: Vision API のOCR結果
        distance_px: クラスタリング距離閾値
        align_tolerance_px: 整列許容
    
    Returns:
        段落のリスト:
        [{
            "id": str,
            "text": str,
            "bbox": {"x1", "y1", "x2", "y2"},
            "role": str,
            "elements": [...],
            "confidence_avg": float
        }, ...]
    """
    import uuid
    
    # Step 1: OCR要素抽出
    elements = extract_ocr_elements(ocr_result)
    if not elements:
        return []
    
    # Step 2: 正規化
    normalized = normalize_ocr_elements(elements)
    
    # Step 3: クラスタリング
    clusters = cluster_paragraphs(
        normalized,
        distance_px=distance_px,
        align_tolerance_px=align_tolerance_px
    )
    
    # 平均フォントサイズ計算（ロール推定用）
    all_heights = []
    for elem in normalized:
        bbox = elem.get("bbox", {})
        h = bbox.get("y2", 0) - bbox.get("y1", 0)
        if h > 0:
            all_heights.append(h)
    avg_font_size = sum(all_heights) / len(all_heights) if all_heights else 20
    
    # Step 4: 段落構築
    paragraphs = []
    for i, cluster in enumerate(clusters):
        # テキスト結合
        text = "".join([elem.get("text", "") for elem in cluster])
        
        # 外接矩形
        bbox = calculate_bbox_union(cluster)
        
        # ロール推定
        role = estimate_role(cluster, avg_font_size)
        
        # 平均confidence
        confidences = [elem.get("confidence", 0.0) for elem in cluster]
        conf_avg = sum(confidences) / len(confidences) if confidences else 0.0
        
        paragraphs.append({
            "id": str(uuid.uuid4()),
            "text": text,
            "bbox": bbox,
            "role": role,
            "elements": cluster,
            "confidence_avg": conf_avg,
            "reading_order": i
        })
    
    return paragraphs


if __name__ == "__main__":
    # テスト用ダミーデータ
    test_result = {
        "full_text_annotation": {
            "pages": [{
                "blocks": [{
                    "paragraphs": [{
                        "words": [
                            {"text": "見出し", "bounding_box": {"x1": 100, "y1": 100, "x2": 200, "y2": 140}, "confidence": 0.95},
                            {"text": "テスト", "bounding_box": {"x1": 210, "y1": 100, "x2": 280, "y2": 140}, "confidence": 0.93},
                            {"text": "本文です。", "bounding_box": {"x1": 100, "y1": 160, "x2": 200, "y2": 180}, "confidence": 0.90},
                            {"text": "※注意事項", "bounding_box": {"x1": 100, "y1": 400, "x2": 180, "y2": 410}, "confidence": 0.88},
                        ]
                    }]
                }]
            }]
        }
    }
    
    paragraphs = paragraphize(test_result)
    for p in paragraphs:
        print(f"[{p['role']:10}] {p['text'][:30]}...")
