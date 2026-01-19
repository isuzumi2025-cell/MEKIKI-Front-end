"""
Error Dialog with Recovery Options

業務配布用エラーダイアログ:
- エラーコード表示
- 詳細情報の折りたたみ
- 復旧オプション（再試行、スキップ、レポート送信）
- 診断バンドル生成

Usage:
    from app.gui.dialogs.error_dialog import show_error_dialog
    from app.core.exceptions import OCRError, ErrorCode

    try:
        # ... some operation
    except OCRError as e:
        action = show_error_dialog(parent, e)
        if action == "retry":
            # retry logic
"""

import customtkinter as ctk
import tkinter as tk
from typing import Optional, Callable
from pathlib import Path
import traceback


class ErrorDialog(ctk.CTkToplevel):
    """
    エラーダイアログ

    エラーコード、メッセージ、復旧オプションを表示
    """

    def __init__(
        self,
        parent,
        exception: Exception,
        title: str = "エラーが発生しました",
        show_retry: bool = True,
        show_skip: bool = False,
        show_report: bool = True
    ):
        super().__init__(parent)

        self.exception = exception
        self.action = None  # "retry", "skip", "report", "close"

        # ウィンドウ設定
        self.title(title)
        self.geometry("600x500")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        # MekikiExceptionから情報抽出
        from app.core.exceptions import MekikiException
        if isinstance(exception, MekikiException):
            self.error_code = exception.error_code.value
            self.error_message = exception.message
            self.recovery_suggestion = exception.recovery_suggestion
            self.context = exception.context
            self.recoverable = exception.recoverable
        else:
            self.error_code = "E9999"
            self.error_message = str(exception)
            self.recovery_suggestion = "システム管理者にお問い合わせください。"
            self.context = {'exception_type': type(exception).__name__}
            self.recoverable = False

        self._build_ui(show_retry, show_skip, show_report)

        # 中央配置
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self, show_retry: bool, show_skip: bool, show_report: bool):
        # メインコンテナ
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. アイコンとタイトル
        header_frame = ctk.CTkFrame(main_frame, fg_color="#3D1B1B", corner_radius=10)
        header_frame.pack(fill="x", pady=(0, 15))

        icon_label = ctk.CTkLabel(
            header_frame,
            text="❌",
            font=("Arial", 40)
        )
        icon_label.pack(side="left", padx=20, pady=15)

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.pack(side="left", fill="x", expand=True, padx=(0, 20), pady=15)

        ctk.CTkLabel(
            title_frame,
            text="エラーが発生しました",
            font=("Meiryo", 18, "bold"),
            text_color="#F44336",
            anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text=f"エラーコード: {self.error_code}",
            font=("Arial", 12),
            text_color="#888888",
            anchor="w"
        ).pack(anchor="w", pady=(5, 0))

        # 2. エラーメッセージ
        message_frame = ctk.CTkFrame(main_frame, fg_color="#2B2B2B", corner_radius=8)
        message_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            message_frame,
            text="エラー内容:",
            font=("Meiryo", 11, "bold"),
            anchor="w"
        ).pack(anchor="w", padx=15, pady=(15, 5))

        message_text = ctk.CTkTextbox(
            message_frame,
            height=80,
            fg_color="#1E1E1E",
            wrap="word",
            font=("Meiryo", 11)
        )
        message_text.pack(fill="x", padx=15, pady=(0, 15))
        message_text.insert("1.0", self.error_message)
        message_text.configure(state="disabled")

        # 3. 復旧方法
        if self.recovery_suggestion:
            recovery_frame = ctk.CTkFrame(main_frame, fg_color="#1B3D1B", corner_radius=8)
            recovery_frame.pack(fill="x", pady=(0, 15))

            ctk.CTkLabel(
                recovery_frame,
                text="💡 対処方法:",
                font=("Meiryo", 11, "bold"),
                text_color="#4CAF50",
                anchor="w"
            ).pack(anchor="w", padx=15, pady=(15, 5))

            recovery_text = ctk.CTkTextbox(
                recovery_frame,
                height=60,
                fg_color="#0D2D0D",
                wrap="word",
                font=("Meiryo", 10)
            )
            recovery_text.pack(fill="x", padx=15, pady=(0, 15))
            recovery_text.insert("1.0", self.recovery_suggestion)
            recovery_text.configure(state="disabled")

        # 4. 詳細情報（折りたたみ可能）
        details_frame = ctk.CTkFrame(main_frame, fg_color="#2B2B2B", corner_radius=8)
        details_frame.pack(fill="both", expand=True, pady=(0, 15))

        self.details_visible = False
        self.details_button = ctk.CTkButton(
            details_frame,
            text="▶ 詳細を表示",
            command=self._toggle_details,
            fg_color="transparent",
            hover_color="#333333",
            anchor="w",
            width=150
        )
        self.details_button.pack(anchor="w", padx=15, pady=10)

        self.details_textbox = ctk.CTkTextbox(
            details_frame,
            fg_color="#1E1E1E",
            wrap="word",
            font=("Consolas", 9),
            height=0  # Initially hidden
        )
        # Don't pack yet - shown on toggle

        # 詳細情報の内容
        details_content = f"エラータイプ: {type(self.exception).__name__}\n"
        details_content += f"エラーコード: {self.error_code}\n\n"

        if self.context:
            details_content += "コンテキスト情報:\n"
            for key, value in self.context.items():
                details_content += f"  {key}: {value}\n"
            details_content += "\n"

        details_content += "スタックトレース:\n"
        details_content += traceback.format_exc()

        self.details_content = details_content

        # 5. アクションボタン
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x")

        # レポート送信ボタン（左側）
        if show_report:
            report_btn = ctk.CTkButton(
                button_frame,
                text="📤 レポート送信",
                command=self._on_report,
                width=130,
                fg_color="#FF9800",
                hover_color="#F57C00"
            )
            report_btn.pack(side="left", padx=(0, 5))

        # スペーサー
        ctk.CTkFrame(button_frame, fg_color="transparent").pack(side="left", fill="x", expand=True)

        # 右側のボタン群
        if show_skip and self.recoverable:
            skip_btn = ctk.CTkButton(
                button_frame,
                text="スキップ",
                command=self._on_skip,
                width=100,
                fg_color="#666666",
                hover_color="#555555"
            )
            skip_btn.pack(side="right", padx=(5, 0))

        if show_retry and self.recoverable:
            retry_btn = ctk.CTkButton(
                button_frame,
                text="🔄 再試行",
                command=self._on_retry,
                width=100,
                fg_color="#4CAF50",
                hover_color="#45A049"
            )
            retry_btn.pack(side="right", padx=(5, 0))

        close_btn = ctk.CTkButton(
            button_frame,
            text="閉じる",
            command=self._on_close,
            width=100
        )
        close_btn.pack(side="right", padx=(5, 0))

    def _toggle_details(self):
        """詳細情報の表示/非表示切り替え"""
        self.details_visible = not self.details_visible

        if self.details_visible:
            self.details_button.configure(text="▼ 詳細を非表示")
            self.details_textbox.configure(height=150)
            self.details_textbox.pack(fill="both", expand=True, padx=15, pady=(0, 15))
            self.details_textbox.delete("1.0", "end")
            self.details_textbox.insert("1.0", self.details_content)
            self.details_textbox.configure(state="disabled")
        else:
            self.details_button.configure(text="▶ 詳細を表示")
            self.details_textbox.pack_forget()
            self.details_textbox.configure(height=0)

    def _on_retry(self):
        """再試行ボタン"""
        self.action = "retry"
        self.destroy()

    def _on_skip(self):
        """スキップボタン"""
        self.action = "skip"
        self.destroy()

    def _on_report(self):
        """レポート送信ボタン"""
        self.action = "report"
        self._generate_report()

    def _on_close(self):
        """閉じるボタン"""
        self.action = "close"
        self.destroy()

    def _generate_report(self):
        """診断レポート生成"""
        try:
            from app.core.logger import get_logger

            logger = get_logger(__name__)
            bundle_path = logger.generate_diagnostic_bundle()

            # 成功通知
            tk.messagebox.showinfo(
                "レポート生成完了",
                f"診断レポートを生成しました:\n{bundle_path}\n\n"
                f"このファイルをサポートに送信してください。",
                parent=self
            )

            # レポート生成後も閉じない（ユーザーが他の操作を選べるように）

        except Exception as e:
            tk.messagebox.showerror(
                "レポート生成エラー",
                f"レポート生成に失敗しました:\n{e}",
                parent=self
            )


def show_error_dialog(
    parent,
    exception: Exception,
    title: str = "エラーが発生しました",
    show_retry: bool = True,
    show_skip: bool = False,
    show_report: bool = True
) -> str:
    """
    エラーダイアログを表示

    Args:
        parent: 親ウィンドウ
        exception: 例外オブジェクト
        title: ダイアログタイトル
        show_retry: 再試行ボタンを表示
        show_skip: スキップボタンを表示
        show_report: レポート送信ボタンを表示

    Returns:
        ユーザーの選択（"retry", "skip", "report", "close"）
    """
    dialog = ErrorDialog(parent, exception, title, show_retry, show_skip, show_report)
    dialog.wait_window()
    return dialog.action or "close"


if __name__ == "__main__":
    # テスト
    from app.core.exceptions import OCRError, ErrorCode, APIError

    root = ctk.CTk()
    root.title("Error Dialog Test")
    root.geometry("400x300")

    def test_ocr_error():
        try:
            raise OCRError(
                "Gemini APIがタイムアウトしました。ネットワーク接続が不安定か、APIサーバーが応答していない可能性があります。",
                ErrorCode.OCR_TIMEOUT,
                context={'model': 'gemini-2.0-flash', 'timeout_sec': 30, 'retry_count': 3}
            )
        except Exception as e:
            action = show_error_dialog(root, e, show_retry=True, show_skip=True)
            print(f"User action: {action}")

    def test_api_error():
        try:
            raise APIError(
                "APIキーが無効です",
                ErrorCode.API_INVALID_KEY,
                context={'api_name': 'Gemini'}
            )
        except Exception as e:
            action = show_error_dialog(root, e, show_retry=False)
            print(f"User action: {action}")

    def test_generic_error():
        try:
            raise ValueError("予期しないエラーが発生しました")
        except Exception as e:
            action = show_error_dialog(root, e)
            print(f"User action: {action}")

    # テストボタン
    ctk.CTkButton(root, text="Test OCR Error", command=test_ocr_error).pack(pady=10)
    ctk.CTkButton(root, text="Test API Error", command=test_api_error).pack(pady=10)
    ctk.CTkButton(root, text="Test Generic Error", command=test_generic_error).pack(pady=10)

    root.mainloop()
