"""
Phase 1: ペアリング管理クラス
WebページとPDFページのマッピングを管理
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import difflib
import json


@dataclass
class PagePair:
    """ページペア情報"""
    pair_id: int
    web_id: int
    pdf_id: int
    web_url: str
    pdf_filename: str
    pdf_page_num: int
    similarity_score: float
    is_manual: bool  # 手動ペアリングか自動か
    notes: str = ""


class PairingManager:
    """WebとPDFのペアリングを管理"""
    
    def __init__(self):
        """初期化"""
        self.pairs: List[PagePair] = []
        self.next_pair_id: int = 1
    
    def add_pair(
        self,
        web_id: int,
        pdf_id: int,
        web_url: str,
        pdf_filename: str,
        pdf_page_num: int,
        similarity_score: float = 0.0,
        is_manual: bool = True,
        notes: str = ""
    ) -> int:
        """
        ペアを追加
        
        Args:
            web_id: WebページID
            pdf_id: PDFページID
            web_url: WebページURL
            pdf_filename: PDFファイル名
            pdf_page_num: PDFページ番号
            similarity_score: 類似度スコア
            is_manual: 手動ペアリングか
            notes: メモ
        
        Returns:
            pair_id: 追加されたペアのID
        """
        pair = PagePair(
            pair_id=self.next_pair_id,
            web_id=web_id,
            pdf_id=pdf_id,
            web_url=web_url,
            pdf_filename=pdf_filename,
            pdf_page_num=pdf_page_num,
            similarity_score=similarity_score,
            is_manual=is_manual,
            notes=notes
        )
        
        self.pairs.append(pair)
        self.next_pair_id += 1
        
        return pair.pair_id
    
    def remove_pair(self, pair_id: int) -> bool:
        """
        ペアを削除
        
        Args:
            pair_id: 削除するペアのID
        
        Returns:
            成功した場合True
        """
        for i, pair in enumerate(self.pairs):
            if pair.pair_id == pair_id:
                self.pairs.pop(i)
                return True
        return False
    
    def get_pair(self, pair_id: int) -> Optional[PagePair]:
        """
        ペアを取得
        
        Args:
            pair_id: ペアID
        
        Returns:
            PagePairオブジェクト、見つからない場合None
        """
        for pair in self.pairs:
            if pair.pair_id == pair_id:
                return pair
        return None
    
    def get_all_pairs(self) -> List[PagePair]:
        """全ペアを取得"""
        return self.pairs.copy()
    
    def get_pair_by_web_id(self, web_id: int) -> Optional[PagePair]:
        """WebページIDからペアを検索"""
        for pair in self.pairs:
            if pair.web_id == web_id:
                return pair
        return None
    
    def get_pair_by_pdf_id(self, pdf_id: int) -> Optional[PagePair]:
        """PDFページIDからペアを検索"""
        for pair in self.pairs:
            if pair.pdf_id == pdf_id:
                return pair
        return None
    
    def auto_match(
        self,
        web_pages: List[Dict],
        pdf_pages: List[Dict],
        threshold: float = 0.3
    ) -> List[PagePair]:
        """
        自動マッチング
        
        Args:
            web_pages: [{"id": int, "url": str, "text": str}, ...]
            pdf_pages: [{"id": int, "filename": str, "page_num": int, "text": str}, ...]
            threshold: 類似度の閾値
        
        Returns:
            マッチしたペアのリスト
        """
        print(f"🔍 自動マッチング開始: Web {len(web_pages)}件 × PDF {len(pdf_pages)}件")
        
        matched_pairs = []
        used_pdf_ids = set()
        
        for web_page in web_pages:
            web_id = web_page["id"]
            web_url = web_page["url"]
            web_text = web_page.get("text", "")
            
            if not web_text:
                continue
            
            best_match = None
            best_score = 0.0
            
            for pdf_page in pdf_pages:
                pdf_id = pdf_page["id"]
                
                # 既にマッチ済みのPDFはスキップ
                if pdf_id in used_pdf_ids:
                    continue
                
                pdf_filename = pdf_page["filename"]
                pdf_page_num = pdf_page["page_num"]
                pdf_text = pdf_page.get("text", "")
                
                if not pdf_text:
                    continue
                
                # 類似度計算
                score = self._calculate_similarity(web_text, pdf_text)
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = {
                        "web_id": web_id,
                        "pdf_id": pdf_id,
                        "web_url": web_url,
                        "pdf_filename": pdf_filename,
                        "pdf_page_num": pdf_page_num,
                        "score": score
                    }
            
            # ベストマッチがあればペアを追加
            if best_match:
                pair_id = self.add_pair(
                    web_id=best_match["web_id"],
                    pdf_id=best_match["pdf_id"],
                    web_url=best_match["web_url"],
                    pdf_filename=best_match["pdf_filename"],
                    pdf_page_num=best_match["pdf_page_num"],
                    similarity_score=best_match["score"],
                    is_manual=False,
                    notes="自動マッチング"
                )
                
                matched_pairs.append(self.get_pair(pair_id))
                used_pdf_ids.add(best_match["pdf_id"])
        
        print(f"✅ 自動マッチング完了: {len(matched_pairs)}ペア")
        return matched_pairs
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        テキストの類似度を計算
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            類似度 (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        # 正規化
        text1_normalized = " ".join(text1.split())
        text2_normalized = " ".join(text2.split())
        
        if not text1_normalized or not text2_normalized:
            return 0.0
        
        # Jaccard係数
        words1 = set(text1_normalized.split())
        words2 = set(text2_normalized.split())
        
        if not words1 or not words2:
            jaccard = 0.0
        else:
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            jaccard = intersection / union if union > 0 else 0.0
        
        # difflib
        sequence_ratio = difflib.SequenceMatcher(
            None, text1_normalized, text2_normalized
        ).ratio()
        
        # 加重平均
        similarity = (jaccard * 0.4 + sequence_ratio * 0.6)
        
        return similarity
    
    def save_to_file(self, filepath: str):
        """ペアリング情報をファイルに保存"""
        data = {
            "pairs": [
                {
                    "pair_id": p.pair_id,
                    "web_id": p.web_id,
                    "pdf_id": p.pdf_id,
                    "web_url": p.web_url,
                    "pdf_filename": p.pdf_filename,
                    "pdf_page_num": p.pdf_page_num,
                    "similarity_score": p.similarity_score,
                    "is_manual": p.is_manual,
                    "notes": p.notes
                }
                for p in self.pairs
            ],
            "next_pair_id": self.next_pair_id
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, filepath: str):
        """ファイルからペアリング情報を読み込み"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.pairs = [
            PagePair(**pair_data)
            for pair_data in data["pairs"]
        ]
        self.next_pair_id = data["next_pair_id"]

