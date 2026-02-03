"""
Antigravity Web Search Cache
AntigravityのWeb検索結果をキャッシュし、Orchestra等から利用可能にする

使い方:
    # Antigravity側でWeb検索してキャッシュ設定
    from app.sdk.web_cache import set_search_result, get_search_result
    
    set_search_result("OCR optimization", "検索結果...")
    result = get_search_result("OCR optimization")
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

# キャッシュファイルパス
CACHE_PATH = Path("c:/Users/raiko/OneDrive/Desktop/26/OCR/data/web_cache.json")


def _load_cache() -> Dict:
    """キャッシュを読み込み"""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding='utf-8'))
        except:
            pass
    return {}


def _save_cache(cache: Dict):
    """キャッシュを保存"""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


def set_search_result(query: str, result: str):
    """
    Web検索結果をキャッシュに保存
    
    Args:
        query: 検索クエリ
        result: 検索結果
    """
    cache = _load_cache()
    cache[query.lower()] = {
        'result': result,
        'timestamp': datetime.now().isoformat()
    }
    _save_cache(cache)
    print(f"📦 Web検索結果キャッシュ: {query[:30]}...")


def get_search_result(query: str) -> Optional[str]:
    """
    キャッシュからWeb検索結果を取得
    
    Args:
        query: 検索クエリ
    
    Returns:
        検索結果またはNone
    """
    cache = _load_cache()
    
    # 完全一致
    if query.lower() in cache:
        return cache[query.lower()]['result']
    
    # 部分一致
    for key, value in cache.items():
        if query.lower() in key or key in query.lower():
            return value['result']
    
    return None


def get_latest_result() -> Optional[Dict]:
    """最新のキャッシュを取得"""
    cache = _load_cache()
    if not cache:
        return None
    
    # 最新のものを返す
    latest = max(cache.items(), key=lambda x: x[1].get('timestamp', ''))
    return {
        'query': latest[0],
        'result': latest[1]['result'],
        'timestamp': latest[1]['timestamp']
    }


def list_cached_queries() -> list:
    """キャッシュされているクエリ一覧"""
    return list(_load_cache().keys())


# 現在のセッション用メモリキャッシュ
_session_cache: Dict[str, str] = {}

def set_session_result(query: str, result: str):
    """セッション内キャッシュに保存（永続化しない）"""
    _session_cache[query.lower()] = result

def get_session_result(query: str) -> Optional[str]:
    """セッション内キャッシュから取得"""
    return _session_cache.get(query.lower())
