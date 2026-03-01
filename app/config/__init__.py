"""
MEKIKI Configuration Module
"""
from app.config.settings import (
    MatchConfig,
    CrawlConfig,
    OCRConfig,
    get_match_config,
    get_crawl_config,
    get_ocr_config
)

# ============================================================
# カード検出設定
# ============================================================
# False: 既存動作を完全維持（Match:70 に影響なし）
# True : カード型レイアウト境界検出を有効にする
ENABLE_CARD_DETECTION = False

# SSIM 繰り返しパターン検出（重い、2-5秒追加）
ENABLE_CARD_SSIM = False

__all__ = [
    'MatchConfig',
    'CrawlConfig',
    'OCRConfig',
    'get_match_config',
    'get_crawl_config',
    'get_ocr_config',
    'ENABLE_CARD_DETECTION',
    'ENABLE_CARD_SSIM',
]
