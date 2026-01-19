"""
Page Matcher - ページ単位の類似度マッチング
1ページが複数ページにマッチする可能性を考慮

Format: Web1 → PDF4 76% | PDF3 12% | PDF6 8%
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from PIL import Image
import re


@dataclass
class PageMatch:
    """ページマッチング結果"""
    target_page: int
    similarity: float  # 0-100%
    text_preview: str = ""
    
    def format(self) -> str:
        """PDF4 76% 形式"""
        return f"P{self.target_page} {self.similarity:.0f}%"


@dataclass
class PageEntry:
    """ページエントリ（Overview Map用）"""
    source_type: str  # "web" or "pdf"
    page_number: int
    image: Optional[Image.Image] = None
    text: str = ""
    matches: List[PageMatch] = field(default_factory=list)
    
    @property
    def best_match(self) -> Optional[PageMatch]:
        """最良マッチ"""
        return max(self.matches, key=lambda m: m.similarity) if self.matches else None
    
    @property
    def match_display(self) -> str:
        """Web1→PDF4 76% | PDF3 12% 形式"""
        if not self.matches:
            return "未マッチ"
        
        prefix = f"{'Web' if self.source_type == 'web' else 'PDF'}{self.page_number}"
        target_prefix = "PDF" if self.source_type == "web" else "Web"
        
        # 上位3件まで表示
        sorted_matches = sorted(self.matches, key=lambda m: m.similarity, reverse=True)[:3]
        match_strs = [f"{target_prefix}{m.target_page} {m.similarity:.0f}%" for m in sorted_matches]
        
        return f"{prefix} → " + " | ".join(match_strs)
    
    @property
    def overall_sync(self) -> float:
        """総合Sync率（最良マッチの値）"""
        return self.best_match.similarity if self.best_match else 0.0


class PageMatcher:
    """
    ページ単位の類似度マッチング
    1ページが複数ページにマッチする可能性を考慮
    """
    
    def __init__(self, min_similarity: float = 5.0):
        """
        Args:
            min_similarity: 表示する最小類似度 (%)
        """
        self.min_similarity = min_similarity
    
    def _normalize_text(self, text: str) -> str:
        """テキスト正規化"""
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        # 全角→半角
        text = text.translate(str.maketrans(
            'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
            'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
            '０１２３４５６７８９',
            'abcdefghijklmnopqrstuvwxyz'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            '0123456789'
        ))
        return text
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """類似度計算 (0-100%)"""
        if not text1 or not text2:
            return 0.0
        
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio() * 100
    
    def match_pages(
        self,
        source_pages: List[PageEntry],
        target_pages: List[PageEntry]
    ) -> List[PageEntry]:
        """
        ソースページをターゲットページとマッチング
        
        Args:
            source_pages: 主体ページ (WebまたはPDF)
            target_pages: ターゲットページ (PDFまたはWeb)
        
        Returns:
            マッチング結果が埋め込まれたソースページのリスト
        """
        for source in source_pages:
            source.matches = []
            
            for target in target_pages:
                similarity = self.calculate_similarity(source.text, target.text)
                
                if similarity >= self.min_similarity:
                    source.matches.append(PageMatch(
                        target_page=target.page_number,
                        similarity=similarity,
                        text_preview=target.text[:50] if target.text else ""
                    ))
            
            # 類似度でソート
            source.matches.sort(key=lambda m: m.similarity, reverse=True)
        
        return source_pages
    
    def get_overview_data(
        self,
        source_pages: List[PageEntry]
    ) -> List[Dict]:
        """
        Overview Map用のデータを生成
        
        Returns:
            [
                {
                    "source_page": 1,
                    "source_type": "web",
                    "display": "Web1 → PDF4 76% | PDF3 12%",
                    "best_match": 4,
                    "best_similarity": 76.0,
                    "matches": [...]
                },
                ...
            ]
        """
        result = []
        
        for page in source_pages:
            result.append({
                "source_page": page.page_number,
                "source_type": page.source_type,
                "display": page.match_display,
                "best_match": page.best_match.target_page if page.best_match else None,
                "best_similarity": page.overall_sync,
                "matches": [
                    {
                        "target_page": m.target_page,
                        "similarity": m.similarity
                    }
                    for m in page.matches
                ]
            })
        
        return result
    
    def get_overall_sync_rate(self, source_pages: List[PageEntry]) -> float:
        """全体のSync率を計算"""
        if not source_pages:
            return 0.0
        
        total = sum(p.overall_sync for p in source_pages)
        return total / len(source_pages)


# テスト
if __name__ == "__main__":
    matcher = PageMatcher()
    
    web_pages = [
        PageEntry(source_type="web", page_number=1, text="おトクなきっぷで九州の寺社めぐり"),
        PageEntry(source_type="web", page_number=2, text="JR九州の鉄道とバスで巡る旅"),
    ]
    
    pdf_pages = [
        PageEntry(source_type="pdf", page_number=1, text="北海道の観光情報"),
        PageEntry(source_type="pdf", page_number=2, text="JR九州の鉄道とバスで九州周遊"),
        PageEntry(source_type="pdf", page_number=3, text="沖縄の寺社めぐり"),
        PageEntry(source_type="pdf", page_number=4, text="おトクなきっぷで九州の寺社めぐりをしよう"),
    ]
    
    result = matcher.match_pages(web_pages, pdf_pages)
    
    for page in result:
        print(page.match_display)
