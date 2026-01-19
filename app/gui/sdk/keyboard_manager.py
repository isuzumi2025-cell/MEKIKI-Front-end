"""
Keyboard Shortcut Manager
業務アプリ向けの統合キーボードショートカット管理

Features:
- 統一されたショートカット定義
- カスタマイズ可能
- 衝突検出
- プラットフォーム対応（Windows/Mac）
- ヘルプ画面自動生成

Usage:
    from app.gui.sdk.keyboard_manager import KeyboardManager

    manager = KeyboardManager(window)

    # コールバック登録
    manager.bind("save", callback=save_function)
    manager.bind("export", callback=export_function)

    # カスタムショートカット
    manager.register_custom("my_action", "Ctrl+Shift+M", my_callback)
"""

import sys
import tkinter as tk
from typing import Dict, Callable, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class ShortcutCategory(Enum):
    """ショートカットカテゴリ"""
    FILE = "ファイル操作"
    EDIT = "編集"
    VIEW = "表示"
    TOOLS = "ツール"
    HELP = "ヘルプ"


@dataclass
class Shortcut:
    """ショートカット定義"""
    id: str
    name: str
    key: str  # "Ctrl+S", "Command+S" など
    description: str
    category: ShortcutCategory
    callback: Optional[Callable] = None
    enabled: bool = True

    def get_display_key(self) -> str:
        """表示用のキー文字列を取得"""
        if sys.platform == "darwin":
            # Mac: Ctrl → ⌘, Alt → ⌥
            return self.key.replace("Ctrl", "⌘").replace("Alt", "⌥").replace("Shift", "⇧")
        return self.key


class KeyboardManager:
    """
    キーボードショートカットマネージャー

    統一されたショートカット管理、カスタマイズ、ヘルプ生成
    """

    # デフォルトショートカット定義
    DEFAULT_SHORTCUTS = [
        # ファイル操作
        Shortcut("save", "保存", "Ctrl+S", "現在の作業を保存", ShortcutCategory.FILE),
        Shortcut("open", "開く", "Ctrl+O", "ファイルを開く", ShortcutCategory.FILE),
        Shortcut("export_excel", "Excel出力", "Ctrl+E", "結果をExcelにエクスポート", ShortcutCategory.FILE),
        Shortcut("settings", "設定", "Ctrl+Comma", "アプリケーション設定を開く", ShortcutCategory.FILE),
        Shortcut("quit", "終了", "Ctrl+Q", "アプリケーションを終了", ShortcutCategory.FILE),

        # 編集
        Shortcut("undo", "元に戻す", "Ctrl+Z", "最後の操作を元に戻す", ShortcutCategory.EDIT),
        Shortcut("redo", "やり直し", "Ctrl+Y", "元に戻した操作をやり直す", ShortcutCategory.EDIT),
        Shortcut("find", "検索", "Ctrl+F", "テキストを検索", ShortcutCategory.EDIT),
        Shortcut("copy", "コピー", "Ctrl+C", "選択項目をコピー", ShortcutCategory.EDIT),
        Shortcut("paste", "貼り付け", "Ctrl+V", "クリップボードから貼り付け", ShortcutCategory.EDIT),

        # 表示
        Shortcut("zoom_in", "拡大", "Ctrl+Plus", "表示を拡大", ShortcutCategory.VIEW),
        Shortcut("zoom_out", "縮小", "Ctrl+Minus", "表示を縮小", ShortcutCategory.VIEW),
        Shortcut("zoom_reset", "リセット", "Ctrl+0", "表示を100%に戻す", ShortcutCategory.VIEW),
        Shortcut("toggle_fullscreen", "フルスクリーン", "F11", "フルスクリーン切り替え", ShortcutCategory.VIEW),
        Shortcut("refresh", "再読み込み", "F5", "表示を再読み込み", ShortcutCategory.VIEW),

        # ツール
        Shortcut("run_ocr", "OCR実行", "Ctrl+R", "OCRを実行", ShortcutCategory.TOOLS),
        Shortcut("match_all", "自動マッチング", "Ctrl+M", "自動マッチングを実行", ShortcutCategory.TOOLS),
        Shortcut("toggle_sync_scroll", "スクロール同期", "Ctrl+L", "スクロール同期のON/OFF", ShortcutCategory.TOOLS),

        # ヘルプ
        Shortcut("help", "ヘルプ", "F1", "ヘルプを表示", ShortcutCategory.HELP),
        Shortcut("shortcuts", "ショートカット一覧", "Ctrl+Slash", "ショートカット一覧を表示", ShortcutCategory.HELP),
    ]

    def __init__(self, root_window: tk.Tk):
        """
        初期化

        Args:
            root_window: ルートウィンドウ
        """
        self.root = root_window
        self.shortcuts: Dict[str, Shortcut] = {}
        self.key_bindings: Dict[str, str] = {}  # key -> shortcut_id

        # プラットフォーム検出
        self.is_mac = sys.platform == "darwin"
        self.modifier_key = "Command" if self.is_mac else "Control"

        # デフォルトショートカットをロード
        self._load_defaults()

        # カスタム設定をロード（存在する場合）
        self._load_custom_config()

        print(f"✅ KeyboardManager initialized ({len(self.shortcuts)} shortcuts)")

    def _load_defaults(self):
        """デフォルトショートカットをロード"""
        for shortcut in self.DEFAULT_SHORTCUTS:
            # Mac用にキー変換
            if self.is_mac:
                shortcut.key = shortcut.key.replace("Ctrl", "Command")

            self.shortcuts[shortcut.id] = shortcut

    def _load_custom_config(self):
        """カスタム設定をロード"""
        config_file = Path("config/keyboard_shortcuts.json")

        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    custom = json.load(f)

                for shortcut_id, key in custom.items():
                    if shortcut_id in self.shortcuts:
                        self.shortcuts[shortcut_id].key = key
                        print(f"  Custom shortcut: {shortcut_id} -> {key}")

            except Exception as e:
                print(f"⚠️ Failed to load custom shortcuts: {e}")

    def save_custom_config(self):
        """カスタム設定を保存"""
        config_file = Path("config/keyboard_shortcuts.json")
        config_file.parent.mkdir(parents=True, exist_ok=True)

        custom = {
            shortcut_id: shortcut.key
            for shortcut_id, shortcut in self.shortcuts.items()
        }

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(custom, f, indent=2, ensure_ascii=False)

            print(f"✅ Custom shortcuts saved to {config_file}")
            return True

        except Exception as e:
            print(f"❌ Failed to save custom shortcuts: {e}")
            return False

    def bind(self, shortcut_id: str, callback: Callable):
        """
        ショートカットにコールバックを登録

        Args:
            shortcut_id: ショートカットID
            callback: 実行する関数

        Returns:
            成功した場合True
        """
        if shortcut_id not in self.shortcuts:
            print(f"⚠️ Unknown shortcut ID: {shortcut_id}")
            return False

        shortcut = self.shortcuts[shortcut_id]
        shortcut.callback = callback

        # Tkinterイベントバインド
        tk_key = self._convert_to_tk_format(shortcut.key)
        self.root.bind(tk_key, lambda event: self._handle_shortcut(shortcut_id))

        self.key_bindings[tk_key] = shortcut_id

        print(f"  Bound: {shortcut_id} ({shortcut.key}) -> {callback.__name__}")
        return True

    def unbind(self, shortcut_id: str):
        """
        ショートカットのバインドを解除

        Args:
            shortcut_id: ショートカットID
        """
        if shortcut_id not in self.shortcuts:
            return

        shortcut = self.shortcuts[shortcut_id]
        tk_key = self._convert_to_tk_format(shortcut.key)

        self.root.unbind(tk_key)
        if tk_key in self.key_bindings:
            del self.key_bindings[tk_key]

        shortcut.callback = None

    def _convert_to_tk_format(self, key: str) -> str:
        """
        キー文字列をTkinter形式に変換

        Args:
            key: "Ctrl+S", "Command+Shift+O" など

        Returns:
            "<Control-s>", "<Command-Shift-o>" など
        """
        # 修飾キーの変換
        key = key.replace("Ctrl", "Control")
        key = key.replace("Cmd", "Command")
        key = key.replace("Alt", "Alt")
        key = key.replace("Shift", "Shift")

        # 特殊キーの変換
        key = key.replace("Plus", "plus")
        key = key.replace("Minus", "minus")
        key = key.replace("Comma", "comma")
        key = key.replace("Slash", "slash")

        # 大文字を小文字に
        parts = key.split("+")
        if len(parts) > 1:
            parts[-1] = parts[-1].lower()

        return f"<{'-'.join(parts)}>"

    def _handle_shortcut(self, shortcut_id: str):
        """
        ショートカット実行

        Args:
            shortcut_id: ショートカットID
        """
        if shortcut_id not in self.shortcuts:
            return

        shortcut = self.shortcuts[shortcut_id]

        if not shortcut.enabled:
            print(f"⚠️ Shortcut disabled: {shortcut_id}")
            return

        if shortcut.callback is None:
            print(f"⚠️ No callback for shortcut: {shortcut_id}")
            return

        try:
            print(f"⚡ Executing shortcut: {shortcut_id} ({shortcut.name})")
            shortcut.callback()

        except Exception as e:
            print(f"❌ Shortcut execution error ({shortcut_id}): {e}")

    def register_custom(
        self,
        shortcut_id: str,
        key: str,
        callback: Callable,
        name: str = "",
        description: str = "",
        category: ShortcutCategory = ShortcutCategory.TOOLS
    ):
        """
        カスタムショートカットを登録

        Args:
            shortcut_id: ショートカットID
            key: キー（"Ctrl+Shift+M"など）
            callback: コールバック関数
            name: 表示名
            description: 説明
            category: カテゴリ
        """
        shortcut = Shortcut(
            id=shortcut_id,
            name=name or shortcut_id,
            key=key,
            description=description,
            category=category,
            callback=callback
        )

        self.shortcuts[shortcut_id] = shortcut
        self.bind(shortcut_id, callback)

        print(f"✅ Custom shortcut registered: {shortcut_id} ({key})")

    def get_shortcuts_by_category(self) -> Dict[ShortcutCategory, List[Shortcut]]:
        """カテゴリ別にショートカットを取得"""
        result = {}

        for shortcut in self.shortcuts.values():
            if shortcut.category not in result:
                result[shortcut.category] = []
            result[shortcut.category].append(shortcut)

        return result

    def show_help_dialog(self):
        """ショートカット一覧ダイアログを表示"""
        import customtkinter as ctk

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("⌨️ キーボードショートカット")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()

        # タイトル
        title_label = ctk.CTkLabel(
            dialog,
            text="⌨️ キーボードショートカット一覧",
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=20)

        # スクロール可能フレーム
        scroll_frame = ctk.CTkScrollableFrame(dialog, height=450)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # カテゴリ別に表示
        shortcuts_by_category = self.get_shortcuts_by_category()

        for category, shortcuts in shortcuts_by_category.items():
            # カテゴリヘッダー
            category_label = ctk.CTkLabel(
                scroll_frame,
                text=category.value,
                font=("Arial", 14, "bold"),
                anchor="w"
            )
            category_label.pack(fill="x", pady=(15, 5), padx=10)

            # ショートカット一覧
            for shortcut in shortcuts:
                shortcut_frame = ctk.CTkFrame(scroll_frame, fg_color="#2b2b2b")
                shortcut_frame.pack(fill="x", pady=2, padx=10)

                # 名前
                name_label = ctk.CTkLabel(
                    shortcut_frame,
                    text=shortcut.name,
                    font=("Arial", 12),
                    anchor="w"
                )
                name_label.pack(side="left", padx=15, pady=8)

                # キー
                key_label = ctk.CTkLabel(
                    shortcut_frame,
                    text=shortcut.get_display_key(),
                    font=("Arial", 12, "bold"),
                    text_color="#4CAF50"
                )
                key_label.pack(side="right", padx=15, pady=8)

        # 閉じるボタン
        close_btn = ctk.CTkButton(
            dialog,
            text="閉じる",
            command=dialog.destroy,
            width=100
        )
        close_btn.pack(pady=10)

    def detect_conflicts(self) -> List[Tuple[str, str, str]]:
        """
        ショートカットの衝突を検出

        Returns:
            [(key, shortcut_id1, shortcut_id2), ...] のリスト
        """
        key_map = {}
        conflicts = []

        for shortcut_id, shortcut in self.shortcuts.items():
            key = shortcut.key

            if key in key_map:
                conflicts.append((key, key_map[key], shortcut_id))
            else:
                key_map[key] = shortcut_id

        return conflicts


# グローバルインスタンス（オプション）
_global_manager: Optional[KeyboardManager] = None


def get_keyboard_manager(root_window: tk.Tk = None) -> KeyboardManager:
    """
    グローバルKeyboardManagerを取得

    Args:
        root_window: ルートウィンドウ（初回のみ必要）

    Returns:
        KeyboardManager instance
    """
    global _global_manager

    if _global_manager is None:
        if root_window is None:
            raise ValueError("root_window is required for first initialization")
        _global_manager = KeyboardManager(root_window)

    return _global_manager


if __name__ == "__main__":
    # テスト
    print("=" * 60)
    print("⌨️ Keyboard Manager Test")
    print("=" * 60)

    root = tk.Tk()
    manager = KeyboardManager(root)

    # テストコールバック
    def test_save():
        print("💾 Save executed!")

    def test_export():
        print("📤 Export executed!")

    # バインド
    manager.bind("save", test_save)
    manager.bind("export", test_export)

    # 衝突チェック
    conflicts = manager.detect_conflicts()
    if conflicts:
        print("\n⚠️ Conflicts detected:")
        for key, id1, id2 in conflicts:
            print(f"  {key}: {id1} vs {id2}")
    else:
        print("\n✅ No conflicts")

    print("\n" + "=" * 60)
    print(f"Total shortcuts: {len(manager.shortcuts)}")
    print("=" * 60)
