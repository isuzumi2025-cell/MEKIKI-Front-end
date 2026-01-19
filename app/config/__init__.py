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

__all__ = [
    'MatchConfig',
    'CrawlConfig', 
    'OCRConfig',
    'get_match_config',
    'get_crawl_config',
    'get_ocr_config'
]
