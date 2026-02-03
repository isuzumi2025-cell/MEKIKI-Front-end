"""
デバッグモード設定
環境変数 MEKIKI_DEBUG=1 で有効化
"""
import os

def is_debug():
    """デバッグモードかどうか"""
    return os.environ.get("MEKIKI_DEBUG") == "1"

def skip_gemini_correction():
    """Gemini補正をスキップするか"""
    return os.environ.get("MEKIKI_SKIP_GEMINI_CORRECTION") == "1"

def use_fixture():
    """Fixtureデータを使用するか"""
    return os.environ.get("MEKIKI_USE_FIXTURE") == "1"

def skip_crawl():
    """クロールをスキップするか"""
    return os.environ.get("MEKIKI_SKIP_CRAWL") == "1"

# デバッグ設定（コードから直接変更可能）
class DebugConfig:
    # True にすると重い処理をスキップ
    SKIP_GEMINI_CORRECTION = False
    SKIP_CRAWL = False
    USE_FIXTURE = False
    
    # ログ詳細度
    VERBOSE_OCR = False
    VERBOSE_MATCHING = False
    
    @classmethod
    def from_env(cls):
        """環境変数から設定を読み込み"""
        cls.SKIP_GEMINI_CORRECTION = skip_gemini_correction()
        cls.USE_FIXTURE = use_fixture()
        cls.SKIP_CRAWL = skip_crawl()
        return cls

# 起動時に環境変数から読み込み
DebugConfig.from_env()
