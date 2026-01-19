"""
認証プロファイル管理
Basic認証設定をJSONファイルで永続化
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class AuthProfile:
    """認証プロファイル"""
    name: str
    url: str
    username: str
    password: str
    auth_type: str = "basic"  # basic, form, none
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class AuthProfileManager:
    """認証プロファイル管理クラス"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: プロファイル保存先のJSONファイルパス
        """
        if config_path is None:
            # デフォルト: OCRフォルダ直下のauth_profiles.json
            self.config_path = Path(__file__).parent.parent.parent / "auth_profiles.json"
        else:
            self.config_path = Path(config_path)
        
        self._profiles: Dict[str, AuthProfile] = {}
        self._load()
    
    def _load(self):
        """ファイルからプロファイルを読み込み"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, profile_data in data.get('profiles', {}).items():
                        self._profiles[name] = AuthProfile(**profile_data)
            except Exception as e:
                print(f"⚠️ プロファイル読み込みエラー: {e}")
    
    def _save(self):
        """プロファイルをファイルに保存"""
        try:
            data = {
                'profiles': {
                    name: asdict(profile) 
                    for name, profile in self._profiles.items()
                }
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ プロファイル保存エラー: {e}")
    
    def list_profiles(self) -> List[AuthProfile]:
        """全プロファイルを取得"""
        return list(self._profiles.values())
    
    def get_profile(self, name: str) -> Optional[AuthProfile]:
        """指定名のプロファイルを取得"""
        return self._profiles.get(name)
    
    def get_profile_names(self) -> List[str]:
        """プロファイル名一覧を取得"""
        return list(self._profiles.keys())
    
    def add_profile(self, profile: AuthProfile) -> bool:
        """プロファイルを追加"""
        if profile.name in self._profiles:
            return False  # 既に存在
        self._profiles[profile.name] = profile
        self._save()
        return True
    
    def update_profile(self, name: str, profile: AuthProfile) -> bool:
        """プロファイルを更新"""
        if name not in self._profiles:
            return False
        # 名前変更の場合
        if name != profile.name:
            del self._profiles[name]
        self._profiles[profile.name] = profile
        self._save()
        return True
    
    def delete_profile(self, name: str) -> bool:
        """プロファイルを削除"""
        if name not in self._profiles:
            return False
        del self._profiles[name]
        self._save()
        return True
    
    def get_credentials_for_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        URLに対応する認証情報を取得
        完全一致または部分一致で検索
        """
        from urllib.parse import urlparse
        target_domain = urlparse(url).netloc
        
        # 完全一致を優先
        for profile in self._profiles.values():
            if profile.url == url:
                return {
                    'username': profile.username,
                    'password': profile.password,
                    'auth_type': profile.auth_type
                }
        
        # ドメイン一致
        for profile in self._profiles.values():
            profile_domain = urlparse(profile.url).netloc
            if profile_domain == target_domain:
                return {
                    'username': profile.username,
                    'password': profile.password,
                    'auth_type': profile.auth_type
                }
        
        return None


# シングルトンインスタンス
_manager_instance: Optional[AuthProfileManager] = None

def get_auth_manager() -> AuthProfileManager:
    """シングルトンマネージャーを取得"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AuthProfileManager()
    return _manager_instance
