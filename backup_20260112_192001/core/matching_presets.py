"""
Per-Cluster Adaptive Matching Presets
クラスタ単位で最適なマッチング戦略を自動選択

Ultrathink: 最高の魔改造 :)
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MatchingPreset:
    """マッチング戦略プリセット"""
    name: str
    display_name: str
    text_weight: float      # テキスト類似度重み
    spatial_weight: float   # 空間位置重み
    image_weight: float     # 画像類似度重み
    syntax_weight: float    # 構文パターン重み
    similarity_threshold: float  # マッチ判定閾値
    description: str


# プリセット定義
PRESETS: Dict[str, MatchingPreset] = {
    "long_text": MatchingPreset(
        name="long_text",
        display_name="📄 長文モード",
        text_weight=0.60,
        spatial_weight=0.20,
        image_weight=0.10,
        syntax_weight=0.10,
        similarity_threshold=0.40,
        description="パンフレット、説明文向け。部分一致を重視"
    ),
    "short_text": MatchingPreset(
        name="short_text",
        display_name="🏷️ 短文モード",
        text_weight=0.80,
        spatial_weight=0.10,
        image_weight=0.05,
        syntax_weight=0.05,
        similarity_threshold=0.60,
        description="見出し、商品名向け。完全一致を重視"
    ),
    "table": MatchingPreset(
        name="table",
        display_name="📊 テーブルモード",
        text_weight=0.40,
        spatial_weight=0.50,
        image_weight=0.05,
        syntax_weight=0.05,
        similarity_threshold=0.50,
        description="表形式データ向け。位置関係を重視"
    ),
    "design": MatchingPreset(
        name="design",
        display_name="🎨 デザインモード",
        text_weight=0.20,
        spatial_weight=0.30,
        image_weight=0.40,
        syntax_weight=0.10,
        similarity_threshold=0.30,
        description="ロゴ、アイコン多め。画像類似度を重視"
    ),
}


class ClusterClassifier:
    """
    クラスタをコンテンツタイプに自動分類
    
    各クラスタの特徴を分析し、最適なプリセットを選択
    """
    
    # テーブル検出用の区切り文字
    TABLE_CHARS = r'[|｜┃│├┤┬┴┼─━]'
    
    # デザイン要素検出用パターン
    DESIGN_PATTERNS = [
        r'^\d+$',              # 数字のみ
        r'^[A-Z]{1,3}$',       # 短い大文字のみ
        r'^[★☆●○◆◇▲△▼▽]+$',  # 記号のみ
        r'^https?://',         # URL
    ]
    
    def classify(self, text: str) -> str:
        """
        テキストを分析してプリセット名を返す
        
        Args:
            text: クラスタのテキスト
            
        Returns:
            プリセット名 ("long_text", "short_text", "table", "design")
        """
        if not text:
            return "short_text"
        
        text = text.strip()
        length = len(text)
        
        # 特徴抽出
        features = self._extract_features(text)
        
        # 分類ロジック
        return self._classify_by_features(features, length)
    
    def _extract_features(self, text: str) -> Dict:
        """テキストから特徴を抽出"""
        length = len(text)
        
        # 文字種別の比率
        digit_count = sum(c.isdigit() for c in text)
        alpha_count = sum(c.isalpha() for c in text)
        space_count = sum(c.isspace() for c in text)
        
        # 改行数
        newline_count = text.count('\n')
        
        # テーブル文字の検出
        table_chars_found = len(re.findall(self.TABLE_CHARS, text))
        
        # デザインパターンの検出
        is_design_element = any(
            re.match(pattern, text.strip()) 
            for pattern in self.DESIGN_PATTERNS
        )
        
        # 日本語文の特徴（句点・読点）
        punctuation_count = text.count('。') + text.count('、') + text.count('！') + text.count('？')
        
        return {
            "length": length,
            "digit_ratio": digit_count / length if length else 0,
            "alpha_ratio": alpha_count / length if length else 0,
            "space_ratio": space_count / length if length else 0,
            "newline_count": newline_count,
            "table_chars": table_chars_found,
            "is_design": is_design_element,
            "punctuation_count": punctuation_count,
            "has_sentences": punctuation_count >= 1 and length > 20,
        }
    
    def _classify_by_features(self, features: Dict, length: int) -> str:
        """特徴に基づいて分類"""
        
        # 超短文（10文字未満）
        if length < 10:
            if features["is_design"] or features["digit_ratio"] > 0.5:
                return "design"
            return "short_text"
        
        # テーブル検出
        if features["table_chars"] >= 2:
            return "table"
        
        # 改行が多く、数字比率が高い → テーブル的
        if features["newline_count"] >= 3 and features["digit_ratio"] > 0.2:
            return "table"
        
        # デザイン要素
        if features["is_design"]:
            return "design"
        
        # 長文判定（文章らしさが高い）
        if length > 50 and features["has_sentences"]:
            return "long_text"
        
        # 中程度の長さ
        if length > 30:
            if features["punctuation_count"] >= 2:
                return "long_text"
            return "short_text"
        
        # デフォルト
        return "short_text"
    
    def get_preset(self, text: str) -> MatchingPreset:
        """テキストに最適なプリセットを取得"""
        preset_name = self.classify(text)
        return PRESETS[preset_name]
    
    def classify_with_reason(self, text: str) -> tuple:
        """分類結果と理由を返す（デバッグ用）"""
        preset_name = self.classify(text)
        features = self._extract_features(text)
        
        reason = f"len={len(text)}, "
        reason += f"digits={features['digit_ratio']:.0%}, "
        reason += f"newlines={features['newline_count']}, "
        reason += f"table_chars={features['table_chars']}, "
        reason += f"sentences={features['has_sentences']}"
        
        return preset_name, reason


def get_preset(name: str) -> Optional[MatchingPreset]:
    """プリセットを名前で取得"""
    return PRESETS.get(name)


def list_presets() -> list:
    """全プリセットのリストを取得"""
    return list(PRESETS.values())


# シングルトンインスタンス
classifier = ClusterClassifier()
