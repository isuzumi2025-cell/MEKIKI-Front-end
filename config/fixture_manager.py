"""
Fixtureマネージャー
OCR/クロール結果をキャッシュして再利用
"""
import os
import pickle
from pathlib import Path
from typing import Any, Callable, Optional

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

def ensure_fixture_dir():
    """Fixtureディレクトリを作成"""
    FIXTURE_DIR.mkdir(exist_ok=True)

def get_fixture_path(name: str) -> Path:
    """Fixture ファイルパスを取得"""
    ensure_fixture_dir()
    return FIXTURE_DIR / f"{name}.pkl"

def save_fixture(name: str, data: Any) -> Path:
    """データをFixtureとして保存"""
    path = get_fixture_path(name)
    with open(path, 'wb') as f:
        pickle.dump(data, f)
    print(f"💾 Saved fixture: {path}")
    return path

def load_fixture(name: str) -> Optional[Any]:
    """Fixtureを読み込み"""
    path = get_fixture_path(name)
    if path.exists():
        with open(path, 'rb') as f:
            data = pickle.load(f)
        print(f"📦 Loaded fixture: {path}")
        return data
    return None

def get_or_create_fixture(name: str, creator_fn: Callable[[], Any]) -> Any:
    """
    Fixtureがあれば読み込み、なければ作成
    
    使用例:
        web_data = get_or_create_fixture(
            "jrkyushu_web",
            lambda: run_web_crawl()
        )
    """
    data = load_fixture(name)
    if data is not None:
        return data
    
    print(f"🔧 Creating fixture: {name}...")
    data = creator_fn()
    save_fixture(name, data)
    return data

def list_fixtures() -> list:
    """利用可能なFixture一覧"""
    ensure_fixture_dir()
    return [f.stem for f in FIXTURE_DIR.glob("*.pkl")]

def clear_fixtures():
    """すべてのFixtureを削除"""
    ensure_fixture_dir()
    for f in FIXTURE_DIR.glob("*.pkl"):
        f.unlink()
    print("🗑️ All fixtures cleared")
