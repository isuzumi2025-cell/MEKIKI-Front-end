"""
MEKIKI Configuration Classes

ハードコード値を設定クラスに集約し、調整を容易にする
"""
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class MatchConfig:
    """マッチング処理の設定"""
    
    # スコア重み係数
    alpha_text: float = 0.4       # テキスト類似度の重み
    beta_embed: float = 0.2       # 埋め込み類似度の重み
    gamma_layout: float = 0.2     # レイアウト類似度の重み
    delta_visual: float = 0.2     # 視覚類似度の重み
    
    # 閾値
    threshold: float = 0.3        # マッチング閾値
    min_match_length: int = 8     # 共通文字最小長
    
    # 数量制限
    max_paragraphs: int = 30      # 最大パラグラフ数
    max_segments: int = 50        # 最大セグメント数
    
    # レイアウト正規化
    norm_width: int = 1920
    norm_height: int = 1080


@dataclass
class CrawlConfig:
    """クローリング処理の設定"""
    
    # 遅延設定
    request_delay: float = 0.5    # リクエスト間遅延（秒）
    scroll_delay: float = 0.5     # スクロール遅延（秒）
    preroll_delay: float = 0.8    # プレロール遅延（秒）
    
    # タイムアウト
    page_timeout: int = 60000     # ページタイムアウト（ms）
    network_idle_timeout: int = 3000  # networkidle待機（ms）
    
    # 数量制限
    max_pages: int = 50           # 最大ページ数
    max_depth: int = 5            # 最大深さ
    max_scrolls: int = 10         # 最大スクロール回数
    
    # ビューポート
    viewport_width: int = 1920
    viewport_height: int = 1080


@dataclass
class OCRConfig:
    """OCR処理の設定"""
    
    # 画像設定
    max_image_dim: int = 1024     # LLM送信時の最大サイズ
    pdf_dpi: int = 300            # PDFレンダリングDPI
    
    # 数量制限
    max_pages_per_scan: int = 10  # AI分析の最大ページ数
    min_paragraph_length: int = 10  # 最小パラグラフ長
    
    # 品質設定
    jpeg_quality: int = 85


# シングルトンインスタンス（グローバル設定）
_match_config: Optional[MatchConfig] = None
_crawl_config: Optional[CrawlConfig] = None
_ocr_config: Optional[OCRConfig] = None


def get_match_config() -> MatchConfig:
    """MatchConfig のシングルトン取得"""
    global _match_config
    if _match_config is None:
        _match_config = MatchConfig()
    return _match_config


def get_crawl_config() -> CrawlConfig:
    """CrawlConfig のシングルトン取得"""
    global _crawl_config
    if _crawl_config is None:
        _crawl_config = CrawlConfig()
    return _crawl_config


def get_ocr_config() -> OCRConfig:
    """OCRConfig のシングルトン取得"""
    global _ocr_config
    if _ocr_config is None:
        _ocr_config = OCRConfig()
    return _ocr_config
