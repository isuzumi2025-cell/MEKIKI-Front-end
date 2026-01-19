"""
テキストマッチングエンジン
Jaccard係数とdifflibの組み合わせによるハイブリッド類似度計算

Source: OCRappBackupFile/251220_NewOCR_B4Claude/app/core/matcher.py
Ported: 2026-01-11
"""
from typing import List, Dict, Optional
import difflib
from collections import defaultdict


class TextMatcher:
    """テキストマッチャークラス"""
    
    def __init__(self, similarity_threshold: float = 0.1):
        """
        Args:
            similarity_threshold: 類似度の閾値（これ以上でマッチングとみなす）
                                 デフォルト0.1に緩和（10%以上の一致で候補として表示）
        """
        self.similarity_threshold = similarity_threshold
    
    def match_all(
        self,
        web_pages: List[Dict],
        pdf_pages: List[Dict],
        force_matching: bool = True
    ) -> List[Dict]:
        """
        全Webページと全PDFページをマッチング
        
        Args:
            web_pages: [{"page_id": int, "text": str, ...}, ...]
            pdf_pages: [{"page_id": int, "text": str, ...}, ...]
            force_matching: Trueの場合、類似度が低くても各Webページごとに最良のPDFページ（トップ1）を必ず返す
        
        Returns:
            [{"web_id": int, "pdf_id": int, "score": float, "similarity_score": float}, ...]
        """
        pairs = []
        
        for web_page in web_pages:
            web_id = web_page.get("page_id")
            web_text = web_page.get("text", "")
            
            if not web_text:
                continue
            
            best_match = None
            best_score = 0.0
            
            # 全てのPDFページと比較して最高スコアを探す
            for pdf_page in pdf_pages:
                pdf_id = pdf_page.get("page_id")
                pdf_text = pdf_page.get("text", "")
                
                # PDFテキストが空でも比較は行う（スコアは0になる）
                # 類似度を計算
                score = self._calculate_similarity(web_text, pdf_text)
                
                # 強制マッチングモード: 閾値チェックなし、常に最高スコアを記録
                if force_matching:
                    if score > best_score:
                        best_score = score
                        best_match = {
                            "web_id": web_id,
                            "pdf_id": pdf_id,
                            "score": score,
                            "similarity_score": score
                        }
                else:
                    # 従来モード: 閾値チェックあり
                    if score > best_score and score >= self.similarity_threshold:
                        best_score = score
                        best_match = {
                            "web_id": web_id,
                            "pdf_id": pdf_id,
                            "score": score,
                            "similarity_score": score
                        }
            
            # 強制マッチングモード: PDFページが1つでも存在すれば必ず結果を返す
            if force_matching and pdf_pages:
                if best_match is None:
                    # テキストが全て空の場合でも、最初のPDFページをマッチさせる
                    best_match = {
                        "web_id": web_id,
                        "pdf_id": pdf_pages[0].get("page_id"),
                        "score": 0.0,
                        "similarity_score": 0.0
                    }
                pairs.append(best_match)
            elif best_match:
                pairs.append(best_match)
        
        # 重複を除去（1つのPDFページに複数のWebページがマッチする場合、最高スコアのみ）
        pairs = self._deduplicate_pairs(pairs)
        
        return pairs
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの類似度を計算（0.0-1.0）
        Jaccard係数とdifflibの組み合わせ
        """
        if not text1 or not text2:
            return 0.0
        
        # テキストを正規化（空白を統一）
        text1_normalized = " ".join(text1.split())
        text2_normalized = " ".join(text2.split())
        
        if not text1_normalized or not text2_normalized:
            return 0.0
        
        # Jaccard係数（単語レベル）
        words1 = set(text1_normalized.split())
        words2 = set(text2_normalized.split())
        
        if not words1 or not words2:
            jaccard = 0.0
        else:
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            jaccard = intersection / union if union > 0 else 0.0
        
        # difflib（文字列レベル）
        sequence_ratio = difflib.SequenceMatcher(
            None, text1_normalized, text2_normalized
        ).ratio()
        
        # 平均を取る（重み付け: Jaccard 40%, difflib 60%）
        similarity = (jaccard * 0.4 + sequence_ratio * 0.6)
        
        return similarity
    
    def _deduplicate_pairs(self, pairs: List[Dict]) -> List[Dict]:
        """
        重複を除去（1つのPDFページに複数のWebページがマッチする場合、最高スコアのみ）
        """
        # PDF IDごとに最高スコアのペアを保持
        pdf_best = defaultdict(lambda: {"score": 0.0, "pair": None})
        
        for pair in pairs:
            pdf_id = pair["pdf_id"]
            score = pair["score"]
            
            if score > pdf_best[pdf_id]["score"]:
                pdf_best[pdf_id] = {"score": score, "pair": pair}
        
        # 結果をリストに変換
        result = [pdf_best[pdf_id]["pair"] for pdf_id in pdf_best if pdf_best[pdf_id]["pair"]]
        
        return result
    
    def match_single(
        self,
        web_text: str,
        pdf_pages: List[Dict]
    ) -> Optional[Dict]:
        """
        単一のWebページテキストとPDFページリストをマッチング
        
        Returns:
            {"pdf_id": int, "score": float} または None
        """
        if not web_text:
            return None
        
        best_match = None
        best_score = 0.0
        
        for pdf_page in pdf_pages:
            pdf_id = pdf_page.get("page_id")
            pdf_text = pdf_page.get("text", "")
            
            if not pdf_text:
                continue
            
            score = self._calculate_similarity(web_text, pdf_text)
            
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_match = {
                    "pdf_id": pdf_id,
                    "score": score
                }
        
        return best_match
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        公開インターフェース: 2つのテキストの類似度を計算
        
        Args:
            text1: 比較対象テキスト1
            text2: 比較対象テキスト2
        
        Returns:
            類似度 (0.0-1.0)
        """
        return self._calculate_similarity(text1, text2)
