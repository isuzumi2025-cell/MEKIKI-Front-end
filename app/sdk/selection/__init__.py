"""
SDK Selection Module
範囲選択機能 - 簡易選択/フルスキャンモード
⭐ 選択範囲内の画像・文字情報が即座にシート反映
"""

from .manager import SelectionManager, SelectionMode, SelectionRegion, SyncResult

__all__ = ["SelectionManager", "SelectionMode", "SelectionRegion", "SyncResult"]
