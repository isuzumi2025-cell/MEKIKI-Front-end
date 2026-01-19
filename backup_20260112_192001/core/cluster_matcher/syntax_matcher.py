"""
SyntaxPatternMatcher - 構文パターンマッチャー

機能:
- テキスト構造の認識 (コピー、名前、住所、価格等)
- 日本語特有パターン (〒、TEL、神社、駅等)
- パターンテンプレートの学習・保存
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum, auto


class SyntaxType(Enum):
    """構文タイプ定義"""
    UNKNOWN = auto()
    COPY = auto()           # キャッチコピー
    GIMMICK = auto()        # ギミック接続詞 (〜！、〜？など)
    DESCRIPTION = auto()    # 説明文
    NAME = auto()           # 人名・団体名
    PRODUCT = auto()        # 商品名
    POSTAL_CODE = auto()    # 郵便番号
    ADDRESS = auto()        # 住所
    PHONE = auto()          # 電話番号
    PROPER_NOUN = auto()    # 固有名詞
    PRICE = auto()          # 価格
    DECORATIVE = auto()     # 飾り文字・装飾テキスト


@dataclass
class SyntaxSignature:
    """構文シグネチャ"""
    detected_types: Set[SyntaxType]
    pattern_scores: Dict[SyntaxType, float]
    dominant_type: SyntaxType
    confidence: float
    
    def similarity(self, other: 'SyntaxSignature') -> float:
        """他のシグネチャとの類似度を計算"""
        if not self.detected_types and not other.detected_types:
            return 0.0
        
        intersection = self.detected_types & other.detected_types
        union = self.detected_types | other.detected_types
        
        if not union:
            return 0.0
        
        # Jaccard係数ベースの類似度
        jaccard = len(intersection) / len(union)
        
        # 支配的タイプが同じならボーナス
        if self.dominant_type == other.dominant_type and self.dominant_type != SyntaxType.UNKNOWN:
            jaccard = min(1.0, jaccard * 1.3)
        
        return jaccard


class SyntaxPatternMatcher:
    """
    構文パターンマッチャー
    
    日本語テキストの構造パターンを認識し、類似構文を持つ領域をグルーピング
    """
    
    # 承認済みパターン定義
    PATTERNS = {
        SyntaxType.POSTAL_CODE: [
            r'〒?\d{3}[-−]\d{4}',
            r'〒\d{7}',
        ],
        SyntaxType.ADDRESS: [
            r'[都道府県市区町村].{3,30}[番地号]',
            r'[都道府県].{2,}[市区町村].+',
            r'\d+[-−]\d+[-−]\d+',
        ],
        SyntaxType.PHONE: [
            r'(TEL|電話|☎|📞)[:：]?\s*[\d\-()（）]+',
            r'0\d{1,4}[-−(]?\d{1,4}[-−)]?\d{2,4}',
            r'\d{2,4}[-−]\d{2,4}[-−]\d{2,4}',
        ],
        SyntaxType.PRICE: [
            r'[¥￥][\d,]+',
            r'[\d,]+円',
            r'税込[\d,]+',
            r'[\d,]+税抜',
        ],
        SyntaxType.PROPER_NOUN: [
            r'.*神社.*',
            r'.*寺院.*',
            r'.*温泉.*',
            r'.*駅.*',
            r'.*公園.*',
            r'.*山.*',
            r'.*川.*',
        ],
        SyntaxType.NAME: [
            r'駅長\s*.+',
            r'.+長\s*[:：]?\s*.+',
            r'.+氏',
            r'.+さん',
            r'.+様',
        ],
        SyntaxType.PRODUCT: [
            r'.+セット',
            r'.+プラン',
            r'.+コース',
            r'.+パック',
            r'おすすめ.+',
        ],
        SyntaxType.COPY: [
            r'^.{3,20}[！!]$',
            r'^[「『].+[」』]$',
            r'^.{5,30}$',  # 短い独立テキスト
        ],
        SyntaxType.GIMMICK: [
            r'.*[！!]{2,}',
            r'.*[？?]{2,}',
            r'★+.*',
            r'●+.*',
            r'▶.*',
            r'◆.*',
        ],
        SyntaxType.DESCRIPTION: [
            r'.{30,}',  # 30文字以上の説明文
            r'.+[。、].+[。、].+',  # 複数の句点を含む
        ],
        SyntaxType.DECORATIVE: [
            r'^[☆★◆◇●○▶▷►◀◁◄]+$',
            r'^[─━═╌╍]+$',
            r'^[♪♫♬♩]+.*',
            r'^\s*[・]+\s*$',
        ],
    }
    
    def __init__(self):
        # 正規表現をコンパイル
        self.compiled_patterns: Dict[SyntaxType, List[re.Pattern]] = {}
        for syntax_type, patterns in self.PATTERNS.items():
            self.compiled_patterns[syntax_type] = [
                re.compile(p, re.UNICODE) for p in patterns
            ]
    
    def extract_syntax_signature(self, text: str) -> SyntaxSignature:
        """
        テキストの構文シグネチャを抽出
        
        Args:
            text: 分析対象テキスト
        
        Returns:
            SyntaxSignature: 検出されたパターン情報
        """
        if not text or not text.strip():
            return SyntaxSignature(
                detected_types=set(),
                pattern_scores={},
                dominant_type=SyntaxType.UNKNOWN,
                confidence=0.0
            )
        
        text = text.strip()
        detected_types: Set[SyntaxType] = set()
        pattern_scores: Dict[SyntaxType, float] = {}
        
        for syntax_type, patterns in self.compiled_patterns.items():
            match_count = 0
            for pattern in patterns:
                if pattern.search(text):
                    match_count += 1
            
            if match_count > 0:
                detected_types.add(syntax_type)
                # マッチしたパターン数に基づくスコア
                pattern_scores[syntax_type] = min(1.0, match_count * 0.5)
        
        # 支配的タイプを決定
        if pattern_scores:
            dominant_type = max(pattern_scores.keys(), key=lambda k: pattern_scores[k])
            confidence = pattern_scores[dominant_type]
        else:
            dominant_type = SyntaxType.UNKNOWN
            confidence = 0.0
        
        return SyntaxSignature(
            detected_types=detected_types,
            pattern_scores=pattern_scores,
            dominant_type=dominant_type,
            confidence=confidence
        )
    
    def calculate_syntax_similarity(
        self, 
        text1: str, 
        text2: str
    ) -> float:
        """
        2つのテキスト間の構文類似度を計算
        
        Returns:
            0.0-1.0 の類似度スコア
        """
        sig1 = self.extract_syntax_signature(text1)
        sig2 = self.extract_syntax_signature(text2)
        
        return sig1.similarity(sig2)
    
    def find_similar_syntax_clusters(
        self,
        web_regions: List,
        pdf_regions: List,
        threshold: float = 0.5
    ) -> List[Tuple[any, any, float, SyntaxType]]:
        """
        構文が類似するクラスターペアを発見
        
        Args:
            web_regions: Web領域リスト
            pdf_regions: PDF領域リスト
            threshold: 類似度閾値
        
        Returns:
            (web_region, pdf_region, similarity, dominant_type) のリスト
        """
        matches = []
        
        # 各領域の構文シグネチャを事前計算
        web_signatures = []
        for r in web_regions:
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            web_signatures.append(self.extract_syntax_signature(text))
        
        pdf_signatures = []
        for r in pdf_regions:
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            pdf_signatures.append(self.extract_syntax_signature(text))
        
        # マッチング
        for i, (wr, ws) in enumerate(zip(web_regions, web_signatures)):
            for j, (pr, ps) in enumerate(zip(pdf_regions, pdf_signatures)):
                sim = ws.similarity(ps)
                
                if sim >= threshold:
                    # 支配的タイプを決定
                    if ws.dominant_type == ps.dominant_type:
                        dtype = ws.dominant_type
                    elif ws.confidence > ps.confidence:
                        dtype = ws.dominant_type
                    else:
                        dtype = ps.dominant_type
                    
                    matches.append((wr, pr, sim, dtype))
        
        print(f"[SyntaxMatcher] 構文類似ペア {len(matches)}件を発見")
        return matches
    
    def group_by_syntax_type(
        self, 
        regions: List
    ) -> Dict[SyntaxType, List]:
        """
        構文タイプごとに領域をグルーピング
        
        Args:
            regions: 領域リスト
        
        Returns:
            {SyntaxType: [領域リスト]} の辞書
        """
        groups: Dict[SyntaxType, List] = {}
        
        for r in regions:
            text = r.text if hasattr(r, 'text') else r.get('text', '')
            sig = self.extract_syntax_signature(text)
            
            if sig.dominant_type not in groups:
                groups[sig.dominant_type] = []
            groups[sig.dominant_type].append(r)
        
        for stype, regs in groups.items():
            print(f"[SyntaxMatcher] {stype.name}: {len(regs)}件")
        
        return groups
