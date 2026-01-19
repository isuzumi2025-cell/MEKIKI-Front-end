import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# セキュアなAPIキー管理システムをインポート
try:
    from app.config.api_manager import get_api_manager, APIKeyManager
    _USE_NEW_API_MANAGER = True
except ImportError:
    _USE_NEW_API_MANAGER = False
    print("⚠️ New API Manager not available, using legacy config")


class Config:
    """
    Application Configuration

    業務配布対応版:
    - セキュアなAPIキー管理（暗号化保存）
    - アプリケーション相対パス
    - 複数プロバイダー対応
    """

    # Base paths
    BASE_DIR = Path(__file__).resolve().parent

    # API Keys（後方互換性のため保持）
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    @classmethod
    def load_keys(cls):
        """
        APIキーをロード

        新システム使用時:
        - app.config.api_manager.APIKeyManager を使用
        - 暗号化保存、複数プロバイダー対応

        レガシーモード:
        - 環境変数のみ
        """
        if _USE_NEW_API_MANAGER:
            # 新しいAPIキー管理システムを使用
            try:
                manager = get_api_manager()
                keys = manager.load()

                # Config クラスに設定（後方互換性）
                cls.GEMINI_API_KEY = keys.gemini_api_key or cls.GEMINI_API_KEY
                cls.OPENAI_API_KEY = keys.openai_api_key or cls.OPENAI_API_KEY
                cls.GROK_API_KEY = keys.grok_api_key or cls.GROK_API_KEY
                cls.ANTHROPIC_API_KEY = keys.anthropic_api_key or cls.ANTHROPIC_API_KEY

                # 環境変数に設定（既に manager._set_environment_variables で設定済み）
                print("✅ API keys loaded via secure manager")

            except Exception as e:
                print(f"⚠️ Failed to load API keys via manager: {e}")
                print("   Falling back to environment variables")
        else:
            # レガシーモード: 環境変数のみ
            print("ℹ️ Using legacy API key loading (environment variables only)")

    @classmethod
    def get_api_key(cls, provider: str) -> str:
        """
        APIキーを取得（便利メソッド）

        Args:
            provider: "gemini", "openai", "grok", "anthropic"

        Returns:
            API Key or None
        """
        provider_map = {
            "gemini": cls.GEMINI_API_KEY,
            "openai": cls.OPENAI_API_KEY,
            "grok": cls.GROK_API_KEY,
            "anthropic": cls.ANTHROPIC_API_KEY,
        }
        return provider_map.get(provider.lower())


# Initialize keys on import
Config.load_keys()
