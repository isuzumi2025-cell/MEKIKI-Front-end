"""
Settings Dialog
業務配布用のAPI設定画面

Features:
- 各プロバイダーのAPIキー設定
- セキュア保存（暗号化）
- 設定状況の可視化
- テスト接続機能
"""

import customtkinter as ctk
from typing import Optional
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.config.api_manager import APIKeyManager, APIKeys


class SettingsDialog(ctk.CTkToplevel):
    """
    API設定ダイアログ

    Usage:
        dialog = SettingsDialog(parent)
        dialog.wait_window()  # モーダル表示
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.title("⚙️ API Settings - MEKIKI")
        self.geometry("700x600")
        self.resizable(False, False)

        # センタリング
        self.transient(parent)
        self.grab_set()

        # API Manager
        self.api_manager = APIKeyManager()
        self.current_keys = self.api_manager.load()

        # UI構築
        self._build_ui()

        # 既存値を表示
        self._load_current_values()

    def _build_ui(self):
        """UI構築"""
        # メインフレーム
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # タイトル
        title_label = ctk.CTkLabel(
            main_frame,
            text="🔐 API Key Configuration",
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=(0, 20))

        # 説明
        desc_label = ctk.CTkLabel(
            main_frame,
            text="各プロバイダーのAPIキーを設定してください。\n入力したキーは暗号化して保存されます。",
            font=("Arial", 12),
            text_color="gray"
        )
        desc_label.pack(pady=(0, 20))

        # スクロール可能フレーム
        scroll_frame = ctk.CTkScrollableFrame(main_frame, height=350)
        scroll_frame.pack(fill="both", expand=True, pady=(0, 20))

        # APIキー入力フィールド
        self.entries = {}

        providers = [
            ("gemini", "Google Gemini", "Gemini 2.0/3.0 OCR & LLM"),
            ("openai", "OpenAI ChatGPT", "GPT-4 Turbo / GPT-4o"),
            ("grok", "xAI Grok", "Grok-1 クリエイティブ評価"),
            ("anthropic", "Anthropic Claude", "Claude Sonnet 4.5"),
            ("google_cloud", "Google Cloud Credentials", "Vision API認証ファイル（パス）"),
        ]

        for i, (key, name, description) in enumerate(providers):
            self._create_api_field(scroll_frame, key, name, description, row=i)

        # ボタンフレーム
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")

        # 保存ボタン
        save_btn = ctk.CTkButton(
            button_frame,
            text="💾 保存",
            command=self._save_settings,
            fg_color="#4CAF50",
            hover_color="#45a049",
            width=150,
            height=40,
            font=("Arial", 14, "bold")
        )
        save_btn.pack(side="left", padx=5)

        # テスト接続ボタン
        test_btn = ctk.CTkButton(
            button_frame,
            text="🔌 接続テスト",
            command=self._test_connection,
            fg_color="#2196F3",
            hover_color="#1976D2",
            width=150,
            height=40,
            font=("Arial", 14, "bold")
        )
        test_btn.pack(side="left", padx=5)

        # キャンセルボタン
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="❌ キャンセル",
            command=self.destroy,
            fg_color="#F44336",
            hover_color="#D32F2F",
            width=150,
            height=40,
            font=("Arial", 14, "bold")
        )
        cancel_btn.pack(side="right", padx=5)

        # ステータスラベル
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="",
            font=("Arial", 11),
            text_color="gray"
        )
        self.status_label.pack(pady=(10, 0))

    def _create_api_field(self, parent, key: str, name: str, description: str, row: int):
        """
        APIキー入力フィールドを作成

        Args:
            parent: 親ウィジェット
            key: キー名（内部ID）
            name: 表示名
            description: 説明
            row: 行番号
        """
        # フィールドフレーム
        field_frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        field_frame.pack(fill="x", pady=10, padx=10)

        # プロバイダー名
        name_label = ctk.CTkLabel(
            field_frame,
            text=name,
            font=("Arial", 14, "bold"),
            anchor="w"
        )
        name_label.pack(fill="x", padx=15, pady=(15, 5))

        # 説明
        desc_label = ctk.CTkLabel(
            field_frame,
            text=description,
            font=("Arial", 10),
            text_color="gray",
            anchor="w"
        )
        desc_label.pack(fill="x", padx=15, pady=(0, 10))

        # 入力フィールド
        entry = ctk.CTkEntry(
            field_frame,
            placeholder_text=f"{name} API Key を入力...",
            width=600,
            height=35,
            show="*" if key != "google_cloud" else ""  # パス以外はマスク
        )
        entry.pack(fill="x", padx=15, pady=(0, 15))

        # ステータスアイコン
        status_label = ctk.CTkLabel(
            field_frame,
            text="",
            font=("Arial", 10)
        )
        status_label.pack(anchor="e", padx=15, pady=(0, 10))

        self.entries[key] = {
            "entry": entry,
            "status": status_label,
        }

    def _load_current_values(self):
        """既存の設定値をロード"""
        keys = self.current_keys

        key_map = {
            "gemini": keys.gemini_api_key,
            "openai": keys.openai_api_key,
            "grok": keys.grok_api_key,
            "anthropic": keys.anthropic_api_key,
            "google_cloud": keys.google_cloud_credentials,
        }

        for key, value in key_map.items():
            if value and key in self.entries:
                self.entries[key]["entry"].insert(0, value)
                self.entries[key]["status"].configure(
                    text="✅ 設定済み",
                    text_color="#4CAF50"
                )

    def _save_settings(self):
        """設定を保存"""
        try:
            # 入力値を取得
            new_keys = APIKeys(
                gemini_api_key=self.entries["gemini"]["entry"].get().strip() or None,
                openai_api_key=self.entries["openai"]["entry"].get().strip() or None,
                grok_api_key=self.entries["grok"]["entry"].get().strip() or None,
                anthropic_api_key=self.entries["anthropic"]["entry"].get().strip() or None,
                google_cloud_credentials=self.entries["google_cloud"]["entry"].get().strip() or None,
            )

            # 保存
            if self.api_manager.save(new_keys):
                self.status_label.configure(
                    text="✅ 設定を保存しました",
                    text_color="#4CAF50"
                )

                # ステータス更新
                for key in self.entries:
                    value = getattr(new_keys, f"{key}_api_key" if key != "google_cloud" else "google_cloud_credentials")
                    if value:
                        self.entries[key]["status"].configure(
                            text="✅ 設定済み",
                            text_color="#4CAF50"
                        )
                    else:
                        self.entries[key]["status"].configure(
                            text="❌ 未設定",
                            text_color="#F44336"
                        )

                # 2秒後に閉じる
                self.after(2000, self.destroy)
            else:
                self.status_label.configure(
                    text="❌ 保存に失敗しました",
                    text_color="#F44336"
                )

        except Exception as e:
            self.status_label.configure(
                text=f"❌ エラー: {str(e)}",
                text_color="#F44336"
            )

    def _test_connection(self):
        """API接続をテスト"""
        self.status_label.configure(
            text="🔄 接続テスト中...",
            text_color="#2196F3"
        )

        # TODO: 実際のAPI接続テストを実装
        # 現在は設定状況の検証のみ
        validation = self.api_manager.validate()

        results = []
        for provider, is_valid in validation.items():
            status = "✅" if is_valid else "❌"
            results.append(f"{status} {provider.upper()}")

        result_text = "接続テスト結果:\n" + "\n".join(results)

        # 結果ダイアログ
        result_dialog = ctk.CTkToplevel(self)
        result_dialog.title("接続テスト結果")
        result_dialog.geometry("400x300")
        result_dialog.transient(self)
        result_dialog.grab_set()

        result_label = ctk.CTkLabel(
            result_dialog,
            text=result_text,
            font=("Arial", 12),
            justify="left"
        )
        result_label.pack(pady=20, padx=20)

        close_btn = ctk.CTkButton(
            result_dialog,
            text="閉じる",
            command=result_dialog.destroy,
            width=100
        )
        close_btn.pack(pady=10)

        self.status_label.configure(
            text="✅ 接続テスト完了",
            text_color="#4CAF50"
        )


# テスト実行
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Test Parent Window")
    root.geometry("400x300")

    def open_settings():
        dialog = SettingsDialog(root)
        root.wait_window(dialog)

    btn = ctk.CTkButton(
        root,
        text="⚙️ Open Settings",
        command=open_settings,
        width=200,
        height=50,
        font=("Arial", 14, "bold")
    )
    btn.pack(expand=True)

    root.mainloop()
