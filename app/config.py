"""
MEKIKI Application Configuration

グローバル設定フラグ
"""

# ============================================================
# Gemini API 設定
# ============================================================

# Gemini API 完全無効化フラグ
# True: 全てのGemini API呼び出しをスキップし、フォールバック処理を使用
# False: 通常通りGemini APIを使用
DISABLE_GEMINI_API = True

# Hybrid OCR (Cloud Vision + Gemini補正) 無効化
# True: Cloud Visionのみ使用
USE_HYBRID_OCR = False

# デバッグトレース無効化
DEBUG_TRACE_ENABLED = False


# ============================================================
# パフォーマンス設定
# ============================================================

# OCR最小文字数フィルタ
MIN_PARAGRAPH_LENGTH = 5

# Gemini API タイムアウト (秒)
GEMINI_TIMEOUT = 30


# ============================================================
# ログ設定
# ============================================================

# 詳細ログ出力
VERBOSE_LOGGING = False
