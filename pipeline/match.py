"""
Element Matching Module
Paragraph/Table/Cell の対応付け

Created: 2026-01-11
"""
import difflib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import uuid


@dataclass
class MatchCandidate:
    """マッチング候補"""
    right_id: str
    score_total: float
    score_text: float = 0.0
    score_layout: float = 0.0
    score_embed: float = 0.0
    score_visual: float = 0.0


@dataclass
class MatchResult:
    """マッチング結果"""
    match_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    left_id: str = ""
    right_id: Optional[str] = None
    kind: str = "paragraph"  # paragraph, table, cell
    score_total: float = 0.0
    score_text: float = 0.0
    score_layout: float = 0.0
    score_embed: float = 0.0
    score_visual: float = 0.0
    candidates: List[MatchCandidate] = field(default_factory=list)
    status: str = "matched"  # matched, unmatched_left, unmatched_right


class ElementMatcher:
    """
    要素マッチングエンジン
    左右の要素を対応付け
    """
    
    def __init__(
        self,
        alpha_text: float = 0.4,
        beta_embed: float = 0.2,
        gamma_layout: float = 0.2,
        delta_visual: float = 0.2,
        threshold: float = 0.3,
        top_k: int = 3
    ):
        """
        初期化
        
        Args:
            alpha_text: テキスト類似度の重み
            beta_embed: 埋め込み類似度の重み
            gamma_layout: レイアウト類似度の重み
            delta_visual: 視覚整合性の重み
            threshold: マッチング閾値
            top_k: 候補数
        """
        self.alpha = alpha_text
        self.beta = beta_embed
        self.gamma = gamma_layout
        self.delta = delta_visual
        self.threshold = threshold
        self.top_k = top_k
    
    def match_elements(
        self,
        left_elements: List[Dict[str, Any]],
        right_elements: List[Dict[str, Any]],
        use_layout: bool = True
    ) -> List[MatchResult]:
        """
        左右の要素リストをマッチング
        
        Args:
            left_elements: 左側要素リスト [{id, text, bbox, ...}, ...]
            right_elements: 右側要素リスト
            use_layout: レイアウト情報を使用するか
            
        Returns:
            MatchResultのリスト
        """
        results = []
        used_right_ids = set()
        
        # 全ペアのスコアを計算
        score_matrix = []
        for left in left_elements:
            row = []
            for right in right_elements:
                score = self._calculate_score(left, right, use_layout)
                row.append((right["id"], score))
            score_matrix.append(row)
        
        # Greedy マッチング（将来はHungarianに置換可能）
        for i, left in enumerate(left_elements):
            candidates = sorted(score_matrix[i], key=lambda x: -x[1]["total"])[:self.top_k]
            
            best_match = None
            for right_id, scores in candidates:
                if right_id not in used_right_ids and scores["total"] >= self.threshold:
                    best_match = (right_id, scores)
                    break
            
            if best_match:
                right_id, scores = best_match
                used_right_ids.add(right_id)
                
                results.append(MatchResult(
                    left_id=left["id"],
                    right_id=right_id,
                    kind=left.get("kind", "paragraph"),
                    score_total=scores["total"],
                    score_text=scores["text"],
                    score_layout=scores["layout"],
                    score_embed=scores.get("embed", 0.0),
                    score_visual=scores.get("visual", 0.0),
                    candidates=[
                        MatchCandidate(
                            right_id=rid,
                            score_total=sc["total"],
                            score_text=sc["text"],
                            score_layout=sc["layout"]
                        )
                        for rid, sc in candidates
                    ],
                    status="matched"
                ))
            else:
                # 左側のみ（右に対応なし）
                results.append(MatchResult(
                    left_id=left["id"],
                    right_id=None,
                    kind=left.get("kind", "paragraph"),
                    score_total=0.0,
                    candidates=[
                        MatchCandidate(
                            right_id=rid,
                            score_total=sc["total"],
                            score_text=sc["text"],
                            score_layout=sc["layout"]
                        )
                        for rid, sc in candidates
                    ],
                    status="unmatched_left"
                ))
        
        # 右側のみの要素（左に対応なし）
        for right in right_elements:
            if right["id"] not in used_right_ids:
                results.append(MatchResult(
                    left_id="",
                    right_id=right["id"],
                    kind=right.get("kind", "paragraph"),
                    score_total=0.0,
                    status="unmatched_right"
                ))
        
        return results
    
    def _calculate_score(
        self,
        left: Dict[str, Any],
        right: Dict[str, Any],
        use_layout: bool = True
    ) -> Dict[str, float]:
        """
        ペアのスコアを計算
        
        Returns:
            {"total", "text", "layout", "embed", "visual"}
        """
        # テキスト類似度
        text_sim = self._text_similarity(
            left.get("text", ""),
            right.get("text", "")
        )
        
        # レイアウト類似度
        layout_sim = 0.0
        if use_layout:
            layout_sim = self._layout_similarity(
                left.get("bbox"),
                right.get("bbox")
            )
        
        # 埋め込み・視覚は将来実装（現在は0）
        embed_sim = 0.0
        visual_sim = 0.0
        
        # 総合スコア
        total = (
            self.alpha * text_sim +
            self.beta * embed_sim +
            self.gamma * layout_sim +
            self.delta * visual_sim
        )
        
        return {
            "total": total,
            "text": text_sim,
            "layout": layout_sim,
            "embed": embed_sim,
            "visual": visual_sim
        }
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        テキスト類似度を計算（ハイブリッド）
        difflib + Jaccard
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # difflib (sequence matching)
        seq_ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # Jaccard (word-based)
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1 & words2
        union = words1 | words2
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # ハイブリッド (60% difflib + 40% Jaccard)
        return 0.6 * seq_ratio + 0.4 * jaccard
    
    def _layout_similarity(
        self,
        bbox1: Optional[Dict[str, float]],
        bbox2: Optional[Dict[str, float]]
    ) -> float:
        """
        レイアウト類似度を計算（位置の近さ）
        """
        if not bbox1 or not bbox2:
            return 0.0
        
        # 中心座標
        cx1 = (bbox1.get("x1", 0) + bbox1.get("x2", 0)) / 2
        cy1 = (bbox1.get("y1", 0) + bbox1.get("y2", 0)) / 2
        cx2 = (bbox2.get("x1", 0) + bbox2.get("x2", 0)) / 2
        cy2 = (bbox2.get("y1", 0) + bbox2.get("y2", 0)) / 2
        
        # 正規化距離（画面幅を基準）
        # 仮定: 画面幅1920
        norm_width = 1920
        norm_height = 1080
        
        dx = abs(cx1 - cx2) / norm_width
        dy = abs(cy1 - cy2) / norm_height
        
        distance = (dx ** 2 + dy ** 2) ** 0.5
        
        # 距離を類似度に変換（0.5以上離れていたら0）
        similarity = max(0, 1 - distance * 2)
        
        return similarity


# ========== Convenience Function ==========

def match_paragraphs(
    left_paragraphs: List[Dict[str, Any]],
    right_paragraphs: List[Dict[str, Any]],
    threshold: float = 0.3
) -> List[MatchResult]:
    """
    段落マッチング（簡易インターフェース）
    """
    matcher = ElementMatcher(threshold=threshold)
    return matcher.match_elements(left_paragraphs, right_paragraphs)


if __name__ == "__main__":
    # テスト
    left = [
        {"id": "L1", "text": "商品の価格は1,980円です", "bbox": {"x1": 100, "y1": 100, "x2": 300, "y2": 130}},
        {"id": "L2", "text": "送料無料キャンペーン", "bbox": {"x1": 100, "y1": 150, "x2": 250, "y2": 180}},
    ]
    
    right = [
        {"id": "R1", "text": "商品の価格は1,880円です", "bbox": {"x1": 100, "y1": 100, "x2": 300, "y2": 130}},
        {"id": "R2", "text": "送料無料キャンペーン実施中", "bbox": {"x1": 100, "y1": 150, "x2": 280, "y2": 180}},
    ]
    
    results = match_paragraphs(left, right)
    for r in results:
        print(f"{r.left_id} <-> {r.right_id}: {r.score_total:.2f} ({r.status})")
