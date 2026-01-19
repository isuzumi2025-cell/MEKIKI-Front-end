"""
SDK-04: テレメトリ薄ラッパ
PIIレスのイベントトラッキング
"""
import time
from typing import Dict, Any, Optional
from datetime import datetime


# PIIガード: 送信禁止キーワード
_PII_KEYWORDS = {'url', 'text', 'content', 'email', 'name', 'address', 'phone'}


def _sanitize_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """PIIを含む可能性のあるキーを除去"""
    safe_props = {}
    for key, value in props.items():
        key_lower = key.lower()
        # PIIキーワードを含むキーはスキップ
        if any(kw in key_lower for kw in _PII_KEYWORDS):
            continue
        # 文字列が長すぎる場合はトランケート
        if isinstance(value, str) and len(value) > 100:
            safe_props[key] = f"{value[:50]}...(truncated)"
        else:
            safe_props[key] = value
    return safe_props


def track(event_name: str, props: Optional[Dict[str, Any]] = None) -> None:
    """
    イベントをトラッキング
    
    Args:
        event_name: イベント名
        props: プロパティ（PIIレスにサニタイズされる）
    
    Note:
        現在はローカルログのみ。将来的に外部送信を追加可能。
    """
    safe_props = _sanitize_props(props or {})
    timestamp = datetime.now().isoformat()
    
    # ローカルログ出力
    print(f"[Telemetry] {timestamp} | {event_name} | {safe_props}")


def track_timing(event_name: str, duration_ms: float, extra: Optional[Dict[str, Any]] = None) -> None:
    """
    タイミングイベントをトラッキング
    
    Args:
        event_name: イベント名
        duration_ms: 処理時間（ミリ秒）
        extra: 追加プロパティ
    """
    props = {'duration_ms': round(duration_ms, 2)}
    if extra:
        props.update(_sanitize_props(extra))
    track(event_name, props)


class Timer:
    """処理時間計測ヘルパー"""
    
    def __init__(self, event_name: str, extra: Optional[Dict[str, Any]] = None):
        self.event_name = event_name
        self.extra = extra
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        track_timing(self.event_name, duration_ms, self.extra)
