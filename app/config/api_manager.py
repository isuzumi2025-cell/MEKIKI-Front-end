"""
Secure API Key Manager
業務配布用のセキュアなAPIキー管理システム

Features:
- 暗号化保存（base64 + XOR簡易暗号化）
- アプリケーション相対パス
- 複数プロバイダー対応
- GUI設定画面連携

Security Note:
本実装は簡易暗号化です。より高度なセキュリティが必要な場合は
cryptography ライブラリの Fernet を使用してください。
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass, asdict


@dataclass
class APIKeys:
    """API Keys Container"""
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    grok_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_cloud_credentials: Optional[str] = None  # Path to credentials.json

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Optional[str]]) -> 'APIKeys':
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class APIKeyManager:
    """
    セキュアなAPIキー管理

    保存場所:
    - 開発時: プロジェクトルート/config/api_keys.json
    - 配布時: 実行ファイルディレクトリ/config/api_keys.json

    暗号化:
    - 簡易XOR暗号化（base64エンコード）
    - マシン固有の鍵生成
    """

    # 暗号化キー（マシン固有の値で生成）
    _ENCRYPTION_SEED = "MEKIKI_OCR_2026"

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Args:
            config_dir: 設定ディレクトリ（Noneの場合は自動検出）
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # アプリケーションディレクトリを自動検出
            self.config_dir = self._get_config_dir()

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "api_keys.json"

        # キャッシュ
        self._keys: Optional[APIKeys] = None

    def _get_config_dir(self) -> Path:
        """
        設定ディレクトリを取得

        優先順位:
        1. 実行ファイルと同じディレクトリ/config
        2. プロジェクトルート/app/config
        """
        # 実行ファイルのディレクトリ
        if getattr(sys, 'frozen', False):
            # PyInstaller でパッケージ化されている場合
            app_dir = Path(sys.executable).parent
        else:
            # 開発環境
            app_dir = Path(__file__).resolve().parent.parent.parent

        return app_dir / "config"

    def _get_encryption_key(self) -> bytes:
        """
        マシン固有の暗号化キーを生成

        Note: 本番環境ではより強固なキー生成を推奨
        """
        # マシン名 + ユーザー名 + シード で簡易キー生成
        import platform
        machine_id = f"{platform.node()}{os.getlogin()}{self._ENCRYPTION_SEED}"
        return machine_id.encode('utf-8')

    def _encrypt(self, text: str) -> str:
        """
        簡易XOR暗号化 + base64エンコード

        Args:
            text: 平文

        Returns:
            暗号化文字列
        """
        if not text:
            return ""

        key = self._get_encryption_key()
        encrypted_bytes = bytearray()

        for i, char in enumerate(text.encode('utf-8')):
            encrypted_bytes.append(char ^ key[i % len(key)])

        return base64.b64encode(encrypted_bytes).decode('utf-8')

    def _decrypt(self, encrypted_text: str) -> str:
        """
        XOR復号化 + base64デコード

        Args:
            encrypted_text: 暗号化文字列

        Returns:
            平文
        """
        if not encrypted_text:
            return ""

        try:
            key = self._get_encryption_key()
            encrypted_bytes = base64.b64decode(encrypted_text.encode('utf-8'))

            decrypted_bytes = bytearray()
            for i, byte in enumerate(encrypted_bytes):
                decrypted_bytes.append(byte ^ key[i % len(key)])

            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            print(f"[WARN] Decryption error: {e}")
            return ""

    def load(self) -> APIKeys:
        """
        APIキーをロード

        優先順位:
        1. 環境変数
        2. 設定ファイル（暗号化）
        3. デフォルト（None）

        Returns:
            APIKeys instance
        """
        # キャッシュ確認
        if self._keys is not None:
            return self._keys

        # 環境変数から取得
        keys = APIKeys(
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            grok_api_key=os.getenv("GROK_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            google_cloud_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        )

        # 設定ファイルから補完
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    encrypted_data = json.load(f)

                # 復号化
                for key_name, encrypted_value in encrypted_data.items():
                    if encrypted_value and not getattr(keys, key_name, None):
                        decrypted = self._decrypt(encrypted_value)
                        setattr(keys, key_name, decrypted)

                print(f"[OK] API keys loaded from {self.config_file}")

            except Exception as e:
                print(f"[WARN] Failed to load API keys: {e}")

        # 環境変数に設定（他のモジュールが参照できるように）
        self._set_environment_variables(keys)

        self._keys = keys
        return keys

    def save(self, keys: APIKeys) -> bool:
        """
        APIキーを保存（暗号化）

        Args:
            keys: APIKeys instance

        Returns:
            成功した場合True
        """
        try:
            # 暗号化
            encrypted_data = {}
            for key_name, value in keys.to_dict().items():
                if value:
                    encrypted_data[key_name] = self._encrypt(value)
                else:
                    encrypted_data[key_name] = None

            # 保存
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(encrypted_data, f, indent=2)

            print(f"[OK] API keys saved to {self.config_file}")

            # 環境変数を更新
            self._set_environment_variables(keys)

            # キャッシュ更新
            self._keys = keys

            return True

        except Exception as e:
            print(f"[ERR] Failed to save API keys: {e}")
            return False

    def _set_environment_variables(self, keys: APIKeys):
        """
        APIキーを環境変数に設定

        Args:
            keys: APIKeys instance
        """
        if keys.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = keys.gemini_api_key
            os.environ["GOOGLE_API_KEY"] = keys.gemini_api_key  # Alias

        if keys.openai_api_key:
            os.environ["OPENAI_API_KEY"] = keys.openai_api_key

        if keys.grok_api_key:
            os.environ["GROK_API_KEY"] = keys.grok_api_key

        if keys.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = keys.anthropic_api_key

        if keys.google_cloud_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = keys.google_cloud_credentials

    def get_key(self, provider: str) -> Optional[str]:
        """
        特定プロバイダーのAPIキーを取得

        Args:
            provider: "gemini", "openai", "grok", "anthropic"

        Returns:
            API Key or None
        """
        keys = self.load()

        provider_map = {
            "gemini": keys.gemini_api_key,
            "openai": keys.openai_api_key,
            "grok": keys.grok_api_key,
            "anthropic": keys.anthropic_api_key,
        }

        return provider_map.get(provider.lower())

    def validate(self) -> Dict[str, bool]:
        """
        各APIキーの設定状況を検証

        Returns:
            {"gemini": True, "openai": False, ...}
        """
        keys = self.load()

        return {
            "gemini": bool(keys.gemini_api_key),
            "openai": bool(keys.openai_api_key),
            "grok": bool(keys.grok_api_key),
            "anthropic": bool(keys.anthropic_api_key),
            "google_cloud": bool(keys.google_cloud_credentials),
        }


# グローバルインスタンス
import sys
_manager: Optional[APIKeyManager] = None


def get_api_manager() -> APIKeyManager:
    """
    APIKeyManager のシングルトン取得

    Returns:
        APIKeyManager instance
    """
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager


# 互換性のための関数
def get_api_key(provider: str) -> Optional[str]:
    """
    APIキーを取得（簡易インターフェース）

    Args:
        provider: "gemini", "openai", "grok", "anthropic"

    Returns:
        API Key or None
    """
    return get_api_manager().get_key(provider)


if __name__ == "__main__":
    # テスト
    print("=" * 60)
    print("🔐 API Key Manager Test")
    print("=" * 60)

    manager = APIKeyManager()

    # 検証
    status = manager.validate()
    print("\n📊 API Keys Status:")
    for provider, is_set in status.items():
        status_icon = "✅" if is_set else "❌"
        print(f"  {status_icon} {provider.upper()}")

    # 設定ファイルパス
    print(f"\n📁 Config file: {manager.config_file}")
    print(f"   Exists: {manager.config_file.exists()}")

    print("\n" + "=" * 60)
