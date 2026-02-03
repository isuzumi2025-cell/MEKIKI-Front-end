"""
MEKIKI SDK v2.0.0 - 4層アーキテクチャ
クリエイティブ評価ツール用SDK

Architecture:
├── sdk.core          - 基盤処理 (segment, canvas, ocr)
├── sdk.integration   - 外部連携 (llm, notification, scraping)
├── sdk.presentation  - 出力・表示 (export, storyboard, selection)
└── sdk.orchestration - AI調整 (orchestra, matching, similarity)

Migration from v1.x:
- sdk.ocr -> sdk.core.ocr
- sdk.canvas -> sdk.core.canvas
- sdk.llm -> sdk.integration.llm
- sdk.notification -> sdk.integration.notification
- sdk.scraping -> sdk.integration.scraping
- sdk.export -> sdk.presentation.export
- sdk.storyboard -> sdk.presentation.storyboard
- sdk.selection -> sdk.presentation.selection
- sdk.orchestra -> sdk.orchestration.orchestra
- sdk.matching -> sdk.orchestration.matching
- sdk.similarity -> sdk.orchestration.similarity
"""

__version__ = "2.0.0"

# ==========================================
# 完全互換性レイヤー - 旧importパスをサポート
# from app.sdk.ocr import X -> 新パスにリダイレクト
# ==========================================

import sys
from types import ModuleType

def _create_alias(old_path: str, new_module):
    """旧パスを新モジュールにリダイレクト"""
    if new_module is not None:
        sys.modules[old_path] = new_module

# Core層
try:
    from .core import canvas as _canvas
    from .core import ocr as _ocr
    from .core import segment as _segment
    _create_alias('app.sdk.canvas', _canvas)
    _create_alias('app.sdk.ocr', _ocr)
    _create_alias('app.sdk.segment', _segment)
    # 直接エクスポート用
    canvas = _canvas
    ocr = _ocr
    segment = _segment
except ImportError:
    pass

# Integration層
try:
    from .integration import llm as _llm
    from .integration import notification as _notification
    from .integration import scraping as _scraping
    _create_alias('app.sdk.llm', _llm)
    _create_alias('app.sdk.notification', _notification)
    _create_alias('app.sdk.scraping', _scraping)
    llm = _llm
    notification = _notification
    scraping = _scraping
except ImportError:
    pass

# Presentation層
try:
    from .presentation import export as _export
    from .presentation import storyboard as _storyboard
    from .presentation import selection as _selection
    _create_alias('app.sdk.export', _export)
    _create_alias('app.sdk.storyboard', _storyboard)
    _create_alias('app.sdk.selection', _selection)
    export = _export
    storyboard = _storyboard
    selection = _selection
except ImportError:
    pass

# Orchestration層
try:
    from .orchestration import orchestra as _orchestra
    from .orchestration import matching as _matching
    from .orchestration import similarity as _similarity
    _create_alias('app.sdk.orchestra', _orchestra)
    _create_alias('app.sdk.matching', _matching)
    _create_alias('app.sdk.similarity', _similarity)
    orchestra = _orchestra
    matching = _matching
    similarity = _similarity
except ImportError:
    pass

