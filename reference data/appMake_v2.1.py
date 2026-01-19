import sys
import os
import platform
import subprocess
import shutil
import json
import logging
import tempfile
from pathlib import Path
from enum import Enum, auto
from typing import Optional, Tuple

try:
    import PyInstaller.__main__ as _pyinstaller_main  # バンドル用
except ImportError:
    _pyinstaller_main = None
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QRadioButton, QCheckBox, QMessageBox,
    QProgressBar, QButtonGroup, QScrollArea, QFrame, QAction, QMenuBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 定数の定義 ---
class MessageType(Enum):
    LOG = auto()
    INFO = auto()
    ERROR = auto()
    BUTTON_STATE = auto()
    PROGRESS_START = auto()
    PROGRESS_UPDATE = auto()
    PROGRESS_STOP = auto()

# UI定数
class UIConstants:
    """UI関連の定数をまとめたクラス"""
    # ウィンドウサイズ
    WINDOW_WIDTH = 700
    WINDOW_HEIGHT = 750

    # 余白とスペース
    MAIN_MARGIN = 30
    SECTION_SPACING = 20
    ELEMENT_SPACING = 8

    # 要素の高さ
    INPUT_HEIGHT = 44
    BUTTON_WIDTH = 80
    MAIN_BUTTON_HEIGHT = 60
    PROGRESS_BAR_HEIGHT = 4
    LOG_MIN_HEIGHT = 150

    # フォントサイズ
    FONT_TITLE = 20
    FONT_LABEL = 13
    FONT_BODY = 13
    FONT_BUTTON = 15
    FONT_LOG = 11

    # 角丸
    BORDER_RADIUS = 6
    BUTTON_RADIUS = 8

class WorkerThread(QThread):
    """
    バックグラウンドでPyInstallerと後処理を実行するためのQThreadサブクラス

    Attributes:
        result_signal: UIに結果を通知するシグナル
        script_path: ビルド対象のPythonスクリプトのパス
        output_dir: 出力先ディレクトリ
        icon_path: アイコンファイルのパス（オプション）
        target_arch: ターゲットアーキテクチャ (auto/arm64/x86_64)
        codesign_enabled: ad-hoc署名を実行するか
        create_zip_enabled: 配布用ZIPを作成するか
        is_running: スレッドが実行中かのフラグ
    """
    result_signal = pyqtSignal(tuple)

    def __init__(
        self,
        script_path: str,
        output_dir: str,
        icon_path: Optional[str],
        target_arch: str,
        codesign_enabled: bool,
        create_zip_enabled: bool
    ):
        super().__init__()
        self.script_path = Path(script_path)
        self.output_dir = Path(output_dir)
        self.icon_path = Path(icon_path) if icon_path else None
        self.target_arch = target_arch
        self.codesign_enabled = codesign_enabled
        self.create_zip_enabled = create_zip_enabled
        self.is_running = True

    def stop(self) -> None:
        """スレッドの停止を要求"""
        self.is_running = False
        self.result_signal.emit((MessageType.LOG, "🛑 処理の中断を要求しました..."))

    def _get_writable_work_dir(self, preferred: Path) -> Path:
        """
        作業ディレクトリとして書き込み可能なパスを返す。
        指定パスに書き込めない場合は一時ディレクトリへ退避。
        """
        try:
            preferred.mkdir(parents=True, exist_ok=True)
            probe = preferred / ".appmake_write_test"
            probe.touch()
            probe.unlink()
            return preferred
        except Exception as e:
            logger.warning(f"作業ディレクトリに書き込めません: {preferred} - {e}")
            self.result_signal.emit((MessageType.LOG, f"⚠️ 作業ディレクトリが書き込み不可のため一時ディレクトリを使用します"))
            temp_dir = Path(tempfile.mkdtemp(prefix="appmake_build_"))
            self.result_signal.emit((MessageType.LOG, f"📂 一時ディレクトリ: {temp_dir}"))
            return temp_dir

    def _script_uses_tkinter(self) -> bool:
        """
        ターゲットスクリプトがtkinter/tkinterdnd2を使っていそうか簡易判定
        """
        try:
            text = self.script_path.read_text(encoding="utf-8", errors="ignore")
            import re
            return bool(re.search(r"\b(tkinter|tkinterdnd2)\b", text))
        except Exception:
            return False

    def _python_supports_tk(self, python_exe: str) -> bool:
        """
        指定Pythonでtkinterがimportできるか判定
        """
        try:
            proc = subprocess.run(
                [python_exe, "-c", "import tkinter"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            return proc.returncode == 0
        except Exception as e:
            logger.warning(f"tkinterチェック失敗: {e}")
            return False

    def _select_tk_capable_pyinstaller(self) -> Optional[str]:
        """
        tkinterを必要とする場合に、tkinterを持つPythonで動くpyinstaller CLIを選ぶ
        """
        for cli_path in self._find_host_pyinstaller():
            try:
                first_line = Path(cli_path).read_text().splitlines()[0]
                python_candidate = first_line[2:].strip().split()[0] if first_line.startswith("#!") else None
            except Exception:
                python_candidate = None
            if python_candidate and self._python_supports_tk(python_candidate):
                return cli_path
        return None

    def _find_host_pyinstaller(self) -> list:
        """
        ホスト環境のpyinstaller CLIを探す。

        Bundled環境ではPATHが細いことがあるため、/usr/local/bin や /opt/homebrew/bin も見る。
        """
        candidates = []
        path_list = os.environ.get("PATH", "").split(os.pathsep)
        # よくあるインストール先を追加
        for extra in ["/usr/local/bin", "/opt/homebrew/bin", "/usr/bin"]:
            if extra not in path_list:
                path_list.append(extra)
        for p in path_list:
            cand = Path(p) / "pyinstaller"
            if cand.exists() and os.access(str(cand), os.X_OK):
                candidates.append(str(cand))
        # パスの順序どおりに返す
        return candidates

    def _build_pyinstaller_args(self, work_dir: Path = None, include_pyinstaller: bool = True) -> list:
        """
        PyInstallerの引数リストを構築

        Args:
            work_dir: 作業ディレクトリ（specファイルとbuildディレクトリの配置場所）
            include_pyinstaller: PyInstaller自身をバンドルするか（バンドル版実行時はFalse）

        Returns:
            PyInstallerに渡す引数のリスト
        """
        # work_dirが指定されていない場合はスクリプトの親ディレクトリを使用
        if work_dir is None:
            work_dir = self.script_path.parent

        args = [
            "--noconfirm", "--onedir", "--windowed",
            f"--distpath={self.output_dir}",
            f"--workpath={work_dir / 'build'}",
            f"--specpath={work_dir}",
        ]

        # バンドル版から実行する場合はPyInstallerの再収集を避ける
        if include_pyinstaller:
            args.extend([
                "--hidden-import=PyInstaller.__main__",
                "--collect-submodules=PyInstaller",
            ])

        if self.icon_path:
            args.append(f"--icon={self.icon_path}")

        if platform.system() == "Darwin" and self.target_arch and self.target_arch != "auto":
            args.append(f"--target-architecture={self.target_arch}")
            self.result_signal.emit((MessageType.LOG, f"🎯 ターゲットアーキテクチャ: {self.target_arch}"))

        args.append(str(self.script_path))
        return args

    def run(self) -> None:
        """
        バックグラウンドでPyInstallerビルドと後処理を実行

        ビルドの流れ:
        1. PyInstallerで実行ファイルを生成
        2. (macOSのみ) ad-hoc署名を実行
        3. (macOSのみ) 配布用ZIPを作成
        4. 中間ファイルをクリーンアップ
        """
        self.result_signal.emit((MessageType.BUTTON_STATE, False))
        self.result_signal.emit((MessageType.PROGRESS_START, "PyInstallerを準備中..."))
        success = False
        try:
            if not self.is_running:
                return

            build_platform = platform.system()

            self.result_signal.emit((MessageType.LOG, "🚀 PyInstallerによるアプリビルドを開始..."))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.result_signal.emit((MessageType.LOG, f"📁 出力ディレクトリ: {self.output_dir}"))

            app_basename = self.script_path.stem
            work_dir = self._get_writable_work_dir(self.script_path.parent)
            self.result_signal.emit((MessageType.LOG, f"📂 使用作業ディレクトリ: {work_dir}"))

            # バンドル版PyInstallerが利用可能かチェック
            pyinstaller_main = _pyinstaller_main
            if pyinstaller_main is None:
                try:
                    import PyInstaller.__main__ as pyinstaller_main
                except ImportError:
                    pyinstaller_main = None

            uses_tk = self._script_uses_tkinter()
            tk_cli = self._select_tk_capable_pyinstaller() if uses_tk else None

            # バンドル版を使う場合はPyInstallerの再収集を避ける
            is_bundled = (pyinstaller_main is not None)

            # PyInstallerの引数を構築
            pyinstaller_args = self._build_pyinstaller_args(work_dir, include_pyinstaller=not is_bundled)

            # tkinterを使うスクリプトの場合は、PyInstaller実行Pythonがtkを持っているか事前チェック
            if uses_tk:
                if tk_cli:
                    self.result_signal.emit((MessageType.LOG, f"🎯 tkinter対応のPyInstallerを使用: {tk_cli}"))
                else:
                    msg = (
                        "このスクリプトはtkinterを使用していますが、現在のPyInstaller実行環境のPythonにtkinterが入っていません。\n"
                        "Python.org版など、tkinter付きPythonにPyInstallerをインストールし、PATHを切り替えてから再実行してください。"
                    )
                    self.result_signal.emit((MessageType.ERROR, msg))
                    return

            self.result_signal.emit((MessageType.LOG, f"💻 実行コマンド: pyinstaller {' '.join(pyinstaller_args)}"))
            self.result_signal.emit((MessageType.PROGRESS_UPDATE, "PyInstallerを実行中... (数分かかる場合があります)"))
            spec_file = work_dir / f"{app_basename}.spec"
            build_dir = work_dir / "build"

            if spec_file.exists():
                try:
                    spec_file.unlink()
                except OSError as e:
                    logger.warning(f"specファイルの削除に失敗: {e}")

            if build_dir.is_dir():
                try:
                    shutil.rmtree(build_dir)
                except OSError as e:
                    logger.warning(f"buildディレクトリの削除に失敗: {e}")

            old_cwd = Path.cwd()

            # 作業ディレクトリが書き込み可能か確認
            try:
                # バンドル版の場合はCLIプロセスとしてPyInstallerを実行（サブプロセスの問題を回避）
                if is_bundled:
                    self.result_signal.emit((MessageType.LOG, "📦 バンドル版から実行中 - PyInstallerをCLIモードで起動します"))
                    self.result_signal.emit((MessageType.LOG, f"📂 作業ディレクトリ: {work_dir}"))

                    # 作業ディレクトリに移動
                    try:
                        os.chdir(work_dir)
                        self.result_signal.emit((MessageType.LOG, f"✅ 作業ディレクトリへ移動: {os.getcwd()}"))
                    except (OSError, PermissionError) as e:
                        logger.error(f"作業ディレクトリへの移動失敗: {e}")
                        self.result_signal.emit((MessageType.LOG, f"⚠️ 作業ディレクトリへアクセス失敗: {work_dir}"))
                        # 書き込み可能な場所に移動
                        import tempfile
                        temp_work = Path(tempfile.gettempdir()) / "pyinstaller_work"
                        temp_work.mkdir(exist_ok=True)
                        os.chdir(temp_work)
                        self.result_signal.emit((MessageType.LOG, f"✅ 一時ディレクトリを使用: {temp_work}"))
                        # 引数を一時ディレクトリ用に再構築
                        pyinstaller_args = self._build_pyinstaller_args(temp_work, include_pyinstaller=False)

                    # ホスト環境のpyinstallerがある場合はそれを優先して使う（Pillowなど外部依存が必要なケース用）
                    host_cli_list = self._find_host_pyinstaller()
                    cli_path = tk_cli or (host_cli_list[0] if host_cli_list else None)
                    if cli_path:
                        self.result_signal.emit((MessageType.LOG, f"📦 バンドル版ですがホストのPyInstallerを使用します: {cli_path}"))
                        self.result_signal.emit((MessageType.LOG, f"💻 実行コマンド: {cli_path} {' '.join(pyinstaller_args)}"))
                        try:
                            proc = subprocess.Popen(
                                [cli_path, *pyinstaller_args],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                bufsize=1,
                                encoding='utf-8',
                                cwd=os.getcwd(),
                            )

                            for line in iter(proc.stdout.readline, ''):
                                if not self.is_running:
                                    proc.terminate()
                                    break
                                self.result_signal.emit((MessageType.LOG, f"   {line.strip()}"))
                            for line in iter(proc.stderr.readline, ''):
                                if not self.is_running:
                                    break
                                self.result_signal.emit((MessageType.LOG, f"   ⚠️ {line.strip()}"))

                            if not self.is_running:
                                return
                            return_code = proc.wait()
                        except Exception as e:
                            logger.error(f"ホストPyInstallerの実行エラー: {e}")
                            self.result_signal.emit((MessageType.LOG, f"❌ 実行エラー詳細: {e}"))
                            return_code = 1
                    else:
                        self.result_signal.emit((MessageType.LOG, "⚠️ ホストPyInstallerが見つからないため、バンドル版で続行します"))
                        # バンドル版の場合、ブートストラップスクリプトで sys.frozen を隠してPyInstallerを実行
                        # これによりPyInstallerが自分がバンドル環境で動いていることを検出しなくなる

                        import tempfile
                        bootstrap_script = None
                        try:
                            # ブートストラップスクリプトを作成
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                                bootstrap_script = Path(f.name)
                                # sys.frozen と sys._MEIPASS を隠してPyInstallerを実行
                                f.write("""
import sys
import os

# バンドル環境の痕跡を隠す
_hidden_attrs = {}
if hasattr(sys, '_MEIPASS'):
    _hidden_attrs['_MEIPASS'] = sys._MEIPASS
    delattr(sys, '_MEIPASS')
if hasattr(sys, 'frozen'):
    _hidden_attrs['frozen'] = sys.frozen
    delattr(sys, 'frozen')

# PyInstallerをインポートして実行
try:
    import PyInstaller.__main__
    args = sys.argv[1:]
    PyInstaller.__main__.run(args)
except SystemExit as e:
    sys.exit(e.code if isinstance(e.code, int) else 0)
finally:
    # 念のため復元（到達しない可能性が高いが）
        for attr, value in _hidden_attrs.items():
            setattr(sys, attr, value)
""")

                            self.result_signal.emit((MessageType.LOG, f"🔧 ブートストラップスクリプト作成: {bootstrap_script}"))

                            # sys.executableを使ってブートストラップを実行
                            # 環境変数からもバンドル関連の情報を削除
                            env = os.environ.copy()
                            env.pop('_MEIPASS2', None)

                            command = [sys.executable, str(bootstrap_script), *pyinstaller_args]
                            self.result_signal.emit((MessageType.LOG, f"💻 実行コマンド: <bundled-python> <bootstrap> {' '.join(pyinstaller_args)}"))

                            proc = subprocess.Popen(
                                command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                bufsize=1,
                                encoding='utf-8',
                                cwd=os.getcwd(),
                                env=env
                            )

                            for line in iter(proc.stdout.readline, ''):
                                if not self.is_running:
                                    proc.terminate()
                                    break
                                self.result_signal.emit((MessageType.LOG, f"   {line.strip()}"))
                            for line in iter(proc.stderr.readline, ''):
                                if not self.is_running:
                                    break
                                self.result_signal.emit((MessageType.LOG, f"   ⚠️ {line.strip()}"))

                            if not self.is_running:
                                return
                            return_code = proc.wait()
                        except Exception as e:
                            logger.error(f"バンドル版PyInstaller実行エラー: {e}")
                            self.result_signal.emit((MessageType.LOG, f"❌ 実行エラー詳細: {e}"))
                            import traceback
                            tb = traceback.format_exc()
                            for line in tb.splitlines():
                                self.result_signal.emit((MessageType.LOG, f"   {line}"))
                            return_code = 1
                        finally:
                            # ブートストラップスクリプトを削除
                            if bootstrap_script and bootstrap_script.exists():
                                try:
                                    bootstrap_script.unlink()
                                    self.result_signal.emit((MessageType.LOG, "🗑️ ブートストラップスクリプト削除完了"))
                                except OSError as e:
                                    logger.warning(f"ブートストラップスクリプトの削除に失敗: {e}")

                elif pyinstaller_main is not None:
                    # 非バンドル版で、PyInstallerが直接importできる場合
                    self.result_signal.emit((MessageType.LOG, "📦 インポート済みPyInstallerを使用してビルドします"))
                    self.result_signal.emit((MessageType.LOG, f"📂 作業ディレクトリ: {work_dir}"))

                    # 標準出力/エラー出力をキャプチャするために、subprocessで実行
                    try:
                        original_dir = os.getcwd()
                        os.chdir(work_dir)
                        self.result_signal.emit((MessageType.LOG, f"✅ 作業ディレクトリへ移動成功: {os.getcwd()}"))

                        # 標準出力/エラーをキャプチャ
                        import io
                        from contextlib import redirect_stdout, redirect_stderr

                        stdout_capture = io.StringIO()
                        stderr_capture = io.StringIO()

                        old_argv = sys.argv
                        sys.argv = ['pyinstaller'] + pyinstaller_args

                        try:
                            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                                try:
                                    pyinstaller_main.run(pyinstaller_args)
                                    return_code = 0
                                except SystemExit as e:
                                    return_code = e.code if isinstance(e.code, int) else 0
                        finally:
                            sys.argv = old_argv

                            # キャプチャした出力を表示
                            stdout_text = stdout_capture.getvalue()
                            stderr_text = stderr_capture.getvalue()

                            if stdout_text:
                                for line in stdout_text.splitlines():
                                    if line.strip():
                                        self.result_signal.emit((MessageType.LOG, f"   {line}"))

                            if stderr_text:
                                for line in stderr_text.splitlines():
                                    if line.strip():
                                        self.result_signal.emit((MessageType.LOG, f"   ⚠️ {line}"))

                            os.chdir(original_dir)
                    except Exception as e:
                        logger.error(f"PyInstallerの実行エラー: {e}")
                        self.result_signal.emit((MessageType.LOG, f"❌ 実行エラー詳細: {e}"))
                        import traceback
                        tb = traceback.format_exc()
                        for line in tb.splitlines():
                            self.result_signal.emit((MessageType.LOG, f"   {line}"))
                        return_code = 1
                else:
                    # 外部プロセスとしてPyInstallerを実行
                    os.chdir(work_dir)
                    command = [sys.executable, "-m", "PyInstaller", *pyinstaller_args]
                    self.result_signal.emit((MessageType.LOG, f"💻 実行コマンド: {' '.join(command)}"))
                    try:
                        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8', cwd=work_dir)
                    except FileNotFoundError:
                        cli_path = shutil.which("pyinstaller")
                        if not cli_path:
                            self.result_signal.emit((MessageType.ERROR, "PyInstallerが見つかりません。`python -m pip install pyinstaller` を実行するか、PATHにpyinstallerを追加してください。"))
                            return
                        command = [cli_path, *pyinstaller_args]
                        self.result_signal.emit((MessageType.LOG, f"💻 実行コマンド: {' '.join(command)}"))
                        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8', cwd=work_dir)

                    module_missing = False
                    for line in iter(proc.stdout.readline, ''):
                        if not self.is_running:
                            proc.terminate()
                            break
                        self.result_signal.emit((MessageType.LOG, f"   {line.strip()}"))
                    for line in iter(proc.stderr.readline, ''):
                        if not self.is_running: break
                        if "No module named PyInstaller" in line:
                            module_missing = True
                        self.result_signal.emit((MessageType.LOG, f"   ⚠️ {line.strip()}"))

                    if not self.is_running: return
                    return_code = proc.wait()

                    # モジュールが見つからない場合は、pyinstaller CLI を再探索して再実行
                    if module_missing and return_code != 0:
                        cli_path = shutil.which("pyinstaller")
                        if cli_path:
                            self.result_signal.emit((MessageType.LOG, f"🔄 モジュール未検出のためCLI版で再試行: {cli_path}"))
                            command = [cli_path, *pyinstaller_args]
                            try:
                                proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8', cwd=work_dir)
                                for line in iter(proc.stdout.readline, ''):
                                    if not self.is_running:
                                        proc.terminate()
                                        break
                                    self.result_signal.emit((MessageType.LOG, f"   {line.strip()}"))
                                for line in iter(proc.stderr.readline, ''):
                                    if not self.is_running: break
                                    self.result_signal.emit((MessageType.LOG, f"   ⚠️ {line.strip()}"))
                                if not self.is_running: return
                                return_code = proc.wait()
                            except FileNotFoundError:
                                pass
                    os.chdir(old_cwd)
            except Exception as e:
                logger.error(f"PyInstaller実行中のエラー: {e}")
                self.result_signal.emit((MessageType.ERROR, f"実行エラー: {e}"))
                return
            finally:
                # 元のディレクトリに戻る
                try:
                    os.chdir(old_cwd)
                except Exception:
                    pass

            if return_code != 0:
                self.result_signal.emit((MessageType.LOG, f"❌ エラー終了コード: {return_code}"))
                self.result_signal.emit((MessageType.ERROR, "アプリビルド中にエラーが発生しました。"))
                return

            self.result_signal.emit((MessageType.LOG, "✅ PyInstallerビルド完了"))

            app_name = self.script_path.stem
            if build_platform == "Darwin":
                final_app_path = self.output_dir / f"{app_name}.app"
            elif build_platform == "Windows":
                final_app_path = self.output_dir / f"{app_name}.exe"
            else:
                final_app_path = self.output_dir / app_name

            if not final_app_path.exists():
                self.result_signal.emit((MessageType.ERROR, "生成されたアプリファイルが見つかりません。"))
                return

            if final_app_path.is_dir():
                app_size_mb = sum(f.stat().st_size for f in final_app_path.glob('**/*') if f.is_file()) / (1024 * 1024)
            else:
                app_size_mb = final_app_path.stat().st_size / (1024 * 1024)
            self.result_signal.emit((MessageType.LOG, f"📱 アプリ生成完了: {final_app_path} ({app_size_mb:.1f}MB)"))

            if build_platform == "Darwin":
                if self.codesign_enabled:
                    self.result_signal.emit((MessageType.PROGRESS_UPDATE, "ad-hoc署名を実行中..."))
                    self._run_codesign(final_app_path)
                if not self.is_running: return

                if self.create_zip_enabled:
                    self.result_signal.emit((MessageType.PROGRESS_UPDATE, "ZIP作成中..."))
                    self._create_distribution_zip(final_app_path)
                if not self.is_running: return

            self._cleanup_intermediate_files(spec_file, build_dir)

            success = True

        except Exception as e:
            if self.is_running:
                self.result_signal.emit((MessageType.LOG, f"❌ 予期せぬエラー: {e}"))
                self.result_signal.emit((MessageType.ERROR, f"予期せぬエラーが発生しました: {e}"))
        finally:
            if self.is_running:
                if success:
                    self.result_signal.emit((MessageType.LOG, "🎉 すべて完了しました！"))
                    self.result_signal.emit((MessageType.INFO, "処理が完了しました！"))
                else:
                    self.result_signal.emit((MessageType.LOG, "❌ 処理未完了"))

            self.result_signal.emit((MessageType.PROGRESS_STOP, ""))
            self.result_signal.emit((MessageType.BUTTON_STATE, True))

    def _run_codesign(self, app_path: Path) -> None:
        """
        macOSアプリにad-hoc署名を実行

        Args:
            app_path: 署名対象の.appバンドルのパス
        """
        self.result_signal.emit((MessageType.LOG, "🔐 ad-hoc署名中..."))
        command = ["codesign", "--force", "--deep", "--sign", "-", str(app_path)]
        try:
            subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
            self.result_signal.emit((MessageType.LOG, "✅ 署名完了"))
        except Exception as e:
            logger.error(f"署名エラー: {e}")
            self.result_signal.emit((MessageType.LOG, f"❌ 署名エラー: {e}"))

    def _create_distribution_zip(self, app_path: Path) -> None:
        """
        配布用ZIPファイルを作成

        Args:
            app_path: ZIP化する.appバンドルのパス
        """
        self.result_signal.emit((MessageType.LOG, "📦 ZIP作成中..."))
        zip_path = app_path.with_suffix('.zip')
        try:
            subprocess.run(
                ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app_path.name, zip_path.name],
                capture_output=True, text=True, check=False, timeout=180, cwd=app_path.parent
            )
            self.result_signal.emit((MessageType.LOG, f"✅ ZIP作成完了: {zip_path.name}"))
        except Exception as e:
            logger.error(f"ZIPエラー: {e}")
            self.result_signal.emit((MessageType.LOG, f"❌ ZIPエラー: {e}"))

    def _cleanup_intermediate_files(self, spec_file: Path, build_dir: Path) -> None:
        """
        ビルド後の中間ファイルをクリーンアップ

        Args:
            spec_file: PyInstallerのspecファイルパス
            build_dir: ビルドディレクトリのパス
        """
        for path in [spec_file, build_dir]:
            try:
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            except OSError as e:
                logger.warning(f"一時ファイル削除に失敗: {path} - {e}")
                self.result_signal.emit((MessageType.LOG, f"⚠️ 一時ファイル削除に失敗: {path}"))


class AppConverterApp(QWidget):
    """
    PyInstallerを使ったアプリ化GUIツールのメインウィンドウ

    Attributes:
        conversion_thread: バックグラウンドビルドスレッド
        settings_file: ユーザー設定ファイルのパス
    """
    def __init__(self):
        super().__init__()
        self.conversion_thread: Optional[WorkerThread] = None
        self.settings_file = Path.home() / ".appMake_settings.json"
        self._setup_styles_and_methods()
        self._setup_ui_layout()
        self._load_settings()
        QApplication.instance().aboutToQuit.connect(self._on_closing)
        self.setAcceptDrops(True)

    def _setup_styles_and_methods(self):
        # よりシンプルでモダンな配色
        self.COLORS = {
            'bg': '#1e1e1e',           # メイン背景
            'input_bg': '#2d2d2d',     # 入力フィールド背景
            'input_border': '#3d3d3d', # 入力フィールド枠線
            'text': '#ffffff',         # テキスト
            'text_dim': '#a0a0a0',     # 薄いテキスト
            'primary': '#528dfc',      # メインボタン (#528dfcに変更)
            'primary_hover': '#4a7fe3', # ホバー色
            'secondary': '#383838',    # サブボタン (グレー系)
            'secondary_hover': '#4a4a4a',
            'scroll_handle': '#505050',
            'divider': '#333333'
        }

        is_mac = platform.system() == "Darwin"
        base_font = 'SF Pro Text' if is_mac else 'Segoe UI'

        self.FONTS = {
            'h1': (base_font, 20, QFont.Bold),
            'label': (base_font, 13, QFont.Bold),
            'body': (base_font, 13),
            'button': (base_font, 13, QFont.Bold),
            'log': ('Menlo' if is_mac else 'Consolas', 11)
        }

    def _setup_ui_layout(self) -> None:
        """UIレイアウトを構築"""
        self.setWindowTitle("Python App Converter")
        self.resize(UIConstants.WINDOW_WIDTH, UIConstants.WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color: {self.COLORS['bg']}; color: {self.COLORS['text']};")

        # トップレベルレイアウト
        top_layout = QVBoxLayout(self)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # メニューバー
        self._create_menu_bar()
        top_layout.addWidget(self.menu_bar)

        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{ border: none; background-color: {self.COLORS['bg']}; }}
            QScrollBar:vertical {{
                background-color: {self.COLORS['bg']}; width: 12px; margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.COLORS['scroll_handle']}; border-radius: 6px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

        # スクロールエリアの中身
        content_widget = QWidget()
        self.main_layout = QVBoxLayout(content_widget)
        self.main_layout.setContentsMargins(
            UIConstants.MAIN_MARGIN, UIConstants.MAIN_MARGIN,
            UIConstants.MAIN_MARGIN, UIConstants.MAIN_MARGIN
        )
        self.main_layout.setSpacing(UIConstants.ELEMENT_SPACING)

        # タイトル削除
        # self._create_header()

        # 各セクション
        self._create_section_label("Pythonスクリプト")
        self.script_path_entry = self._create_input_row("ファイルまたはフォルダをドラッグ＆ドロップ...", self._browse_script_path)
        self.script_path_entry.textChanged.connect(self._update_output_path_suggestion)
        self.main_layout.addSpacing(UIConstants.SECTION_SPACING)

        self._create_section_label("アイコン (オプション)")
        self.icon_path_entry = self._create_input_row("アイコン画像 (.ico, .png, .jpg...)", self._browse_icon_path)
        self.main_layout.addSpacing(UIConstants.SECTION_SPACING)

        self._create_section_label("出力ディレクトリ")
        default_path = str(Path.home() / "Desktop" / "AppOutput")
        self.output_path_entry = self._create_input_row("", self._browse_output_path)
        self.output_path_entry.setText(default_path)
        self.main_layout.addSpacing(UIConstants.SECTION_SPACING)

        self._create_options_section()

        self._create_action_section()

        self.main_layout.addSpacing(10)
        self._create_log_section()

        # レイアウトの組み立て
        self.main_layout.addStretch()
        scroll_area.setWidget(content_widget)
        top_layout.addWidget(scroll_area)

    def _create_menu_bar(self):
        self.menu_bar = QMenuBar(self)
        self.menu_bar.setStyleSheet(f"""
            QMenuBar {{ background-color: {self.COLORS['bg']}; color: {self.COLORS['text']}; padding: 4px; border-bottom: 1px solid {self.COLORS['divider']}; }}
            QMenuBar::item:selected {{ background-color: {self.COLORS['secondary']}; border-radius: 4px; }}
            QMenu {{ background-color: {self.COLORS['bg']}; border: 1px solid {self.COLORS['divider']}; }}
            QMenu::item:selected {{ background-color: {self.COLORS['primary']}; }}
        """)
        help_menu = self.menu_bar.addMenu("ヘルプ")

        usage_action = QAction("使い方", self)
        usage_action.triggered.connect(self._show_usage)
        help_menu.addAction(usage_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_header(self):
        # タイトル削除
        pass

    def _create_section_label(self, text):
        label = QLabel(text)
        label.setFont(QFont(*self.FONTS['label']))
        label.setStyleSheet(f"color: {self.COLORS['text']}; margin-top: 0px;") # マージン調整
        self.main_layout.addWidget(label)

    def _create_input_row(self, placeholder: str, browse_func) -> QLineEdit:
        """
        入力フィールドと参照ボタンの行を作成

        Args:
            placeholder: プレースホルダーテキスト
            browse_func: 参照ボタンのクリックハンドラ

        Returns:
            作成されたQLineEdit
        """
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        entry = QLineEdit()
        entry.setFont(QFont(*self.FONTS['body']))
        entry.setFixedHeight(UIConstants.INPUT_HEIGHT)
        entry.setPlaceholderText(placeholder)
        entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.COLORS['input_bg']};
                border: 1px solid {self.COLORS['input_border']};
                border-radius: {UIConstants.BORDER_RADIUS}px;
                padding: 0 12px;
                color: {self.COLORS['text']};
                selection-background-color: {self.COLORS['primary']};
            }}
            QLineEdit:focus {{
                border: 1px solid {self.COLORS['primary']};
                background-color: {self.COLORS['input_bg']};
            }}
        """)

        # 参照ボタン
        btn = QPushButton("参照")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(QFont(*self.FONTS['button']))
        btn.setFixedSize(UIConstants.BUTTON_WIDTH, UIConstants.INPUT_HEIGHT)
        btn.clicked.connect(browse_func)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['secondary']};
                color: {self.COLORS['text']};
                border: none;
                border-radius: {UIConstants.BORDER_RADIUS}px;
            }}
            QPushButton:hover {{ background-color: {self.COLORS['secondary_hover']}; }}
            QPushButton:pressed {{ background-color: #2a2a2a; }}
        """)

        layout.addWidget(entry)
        layout.addWidget(btn)
        self.main_layout.addWidget(container)
        return entry

    def _create_options_section(self):
        if platform.system() == "Darwin":
            self._create_section_label("ビルド設定")

            # アーキテクチャ設定
            arch_frame = QFrame()
            arch_layout = QHBoxLayout(arch_frame)
            arch_layout.setContentsMargins(0, 5, 0, 5)
            arch_layout.setSpacing(20)

            self.architecture_group = QButtonGroup(self)
            self.radios = {
                "auto": QRadioButton("自動 (推奨)"),
                "arm64": QRadioButton("Apple Silicon"),
                "x86_64": QRadioButton("Intel")
            }

            for arch_id, radio in self.radios.items():
                radio.setFont(QFont(*self.FONTS['body']))
                radio.setStyleSheet(f"""
                    QRadioButton {{ color: {self.COLORS['text']}; spacing: 8px; }}
                    QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 2px solid {self.COLORS['text_dim']}; }}
                    QRadioButton::indicator:checked {{ background-color: {self.COLORS['primary']}; border-color: {self.COLORS['primary']}; }}
                """)
                self.architecture_group.addButton(radio)
                arch_layout.addWidget(radio)

            self.radios["auto"].setChecked(True)
            arch_layout.addStretch()
            self.main_layout.addWidget(arch_frame)

            # チェックボックス
            check_layout = QHBoxLayout()
            check_layout.setSpacing(20)

            self.codesign_checkbox = QCheckBox("ad-hoc署名")
            self.create_zip_checkbox = QCheckBox("配布用ZIP作成")

            for cb in [self.codesign_checkbox, self.create_zip_checkbox]:
                cb.setChecked(True)
                cb.setFont(QFont(*self.FONTS['body']))
                cb.setStyleSheet(f"""
                    QCheckBox {{ color: {self.COLORS['text']}; spacing: 8px; }}
                    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 2px solid {self.COLORS['text_dim']}; }}
                    QCheckBox::indicator:checked {{ background-color: {self.COLORS['primary']}; border-color: {self.COLORS['primary']}; }}
                """)
                check_layout.addWidget(cb)

            check_layout.addStretch()
            self.main_layout.addLayout(check_layout)
            self.main_layout.addSpacing(20)

    def _create_action_section(self) -> None:
        """メインアクションボタンとプログレスバーを作成"""
        # メインアクションボタン
        self.convert_button = QPushButton("アプリ化を開始")
        self.convert_button.setCursor(Qt.PointingHandCursor)
        self.convert_button.setFont(QFont(self.FONTS['button'][0], UIConstants.FONT_BUTTON, QFont.Bold))
        self.convert_button.setFixedHeight(UIConstants.MAIN_BUTTON_HEIGHT)
        self.convert_button.clicked.connect(self._start_conversion)
        self.convert_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLORS['primary']};
                color: white;
                border: none;
                border-radius: {UIConstants.BUTTON_RADIUS}px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: {self.COLORS['primary_hover']};
                margin-top: -1px;
            }}
            QPushButton:pressed {{
                background-color: {self.COLORS['primary']};
                margin-top: 1px;
            }}
            QPushButton:disabled {{
                background-color: {self.COLORS['secondary']};
                color: {self.COLORS['text_dim']};
            }}
        """)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(UIConstants.PROGRESS_BAR_HEIGHT)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: {self.COLORS['input_bg']}; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {self.COLORS['primary']}; border-radius: 2px; }}
        """)

        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont(*self.FONTS['body']))
        self.progress_label.setStyleSheet(f"color: {self.COLORS['text_dim']};")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setVisible(False)

        self.main_layout.addWidget(self.convert_button)
        self.main_layout.addWidget(self.progress_bar)
        self.main_layout.addWidget(self.progress_label)

    def _create_log_section(self) -> None:
        """ログ表示エリアを作成"""
        self._create_section_label("処理ログ")
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont(*self.FONTS['log']))
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(UIConstants.LOG_MIN_HEIGHT)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #121212;
                color: #d0d0d0;
                border: 1px solid {self.COLORS['divider']};
                border-radius: {UIConstants.BORDER_RADIUS}px;
                padding: 12px;
            }}
        """)
        self.main_layout.addWidget(self.log_text)

    # --- イベントハンドラ ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        script_file, icon_file = None, None
        for path in paths:
            if path.suffix == '.py' and not script_file: script_file = path
            elif path.is_dir() and not script_file: script_file = path
            elif path.suffix.lower() in ['.ico', '.icns', '.png', '.jpg', '.jpeg'] and not icon_file: icon_file = path

        if script_file: self.script_path_entry.setText(str(script_file))
        if icon_file: self.icon_path_entry.setText(str(icon_file))

    def _browse_path(self, file_mode=True):
        if file_mode: path, _ = QFileDialog.getOpenFileName(self, "選択", "", "Python (*.py);;All (*)")
        else: path = QFileDialog.getExistingDirectory(self, "選択")
        return Path(path) if path else None

    def _browse_script_path(self):
        p = self._browse_path(True)
        if p: self.script_path_entry.setText(str(p))

    def _browse_icon_path(self):
        p, _ = QFileDialog.getOpenFileName(self, "アイコン選択", "", "Images (*.ico *.icns *.png *.jpg *.jpeg)")
        if p: self.icon_path_entry.setText(str(p))

    def _browse_output_path(self):
        p = self._browse_path(False)
        if p: self.output_path_entry.setText(str(p))

    def _update_output_path_suggestion(self, path_str):
        if not path_str: return
        p = Path(path_str)
        if p.exists(): self.output_path_entry.setText(str(p.parent / f"{p.stem}_app"))

    def _start_conversion(self):
        script_path = Path(self.script_path_entry.text()).expanduser()
        output_dir = self.output_path_entry.text()

        if not script_path.exists() or not script_path.is_file() or script_path.suffix.lower() != ".py":
            QMessageBox.critical(self, "エラー", "Pythonの .py ファイルを指定してください。")
            return
        if not output_dir:
            QMessageBox.critical(self, "エラー", "出力ディレクトリを指定してください。")
            return

        target_arch, codesign, create_zip = "auto", False, False
        if platform.system() == "Darwin":
            codesign = self.codesign_checkbox.isChecked()
            create_zip = self.create_zip_checkbox.isChecked()
            btn = self.architecture_group.checkedButton()
            for k, v in self.radios.items():
                if v == btn: target_arch = k

        self.log_text.clear()
        self.log_text.append("--- 処理開始 ---")

        self.conversion_thread = WorkerThread(
            str(script_path), output_dir, self.icon_path_entry.text(), target_arch, codesign, create_zip
        )
        self.conversion_thread.result_signal.connect(self._handle_thread_result)
        self.conversion_thread.finished.connect(lambda: self.convert_button.setText("アプリ化を開始"))
        self.conversion_thread.start()
        self.convert_button.setText("処理中...")
        self.convert_button.setEnabled(False)

    def _handle_thread_result(self, result):
        msg_type, data = result
        if msg_type == MessageType.LOG: self.log_text.append(data)
        elif msg_type == MessageType.INFO: QMessageBox.information(self, "完了", data)
        elif msg_type == MessageType.ERROR: QMessageBox.critical(self, "エラー", data)
        elif msg_type == MessageType.BUTTON_STATE: self.convert_button.setEnabled(data)
        elif msg_type == MessageType.PROGRESS_START:
            self.progress_label.setText(data)
            self.progress_label.setVisible(True)
            self.progress_bar.setVisible(True)
        elif msg_type == MessageType.PROGRESS_UPDATE: self.progress_label.setText(data)
        elif msg_type == MessageType.PROGRESS_STOP:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

    def _on_closing(self):
        self._save_settings()
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.conversion_thread.wait(3000)

    def _save_settings(self) -> None:
        """
        ユーザー設定をJSONファイルに保存
        """
        try:
            settings = {
                "output_dir": self.output_path_entry.text(),
            }
            if platform.system() == "Darwin" and hasattr(self, 'radios'):
                btn = self.architecture_group.checkedButton()
                for k, v in self.radios.items():
                    if v == btn: settings["architecture"] = k
                settings["codesign"] = self.codesign_checkbox.isChecked()
                settings["create_zip"] = self.create_zip_checkbox.isChecked()

            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            logger.info(f"設定を保存しました: {self.settings_file}")
        except (IOError, OSError) as e:
            logger.warning(f"設定ファイルの保存に失敗: {e}")

    def _load_settings(self) -> None:
        """
        保存されたユーザー設定をロード
        """
        try:
            if not self.settings_file.exists():
                logger.info("設定ファイルが存在しないため、デフォルト設定を使用します")
                return

            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            if "output_dir" in settings:
                self.output_path_entry.setText(settings["output_dir"])

            if platform.system() == "Darwin" and hasattr(self, 'radios'):
                if "architecture" in settings:
                    self.radios.get(settings["architecture"], self.radios["auto"]).setChecked(True)
                if "codesign" in settings:
                    self.codesign_checkbox.setChecked(settings["codesign"])
                if "create_zip" in settings:
                    self.create_zip_checkbox.setChecked(settings["create_zip"])

            logger.info(f"設定を読み込みました: {self.settings_file}")
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"設定ファイルの読み込みに失敗: {e}")

    def _show_usage(self):
        QMessageBox.information(self, "使い方", "1. Pythonファイルを選択\n2. 出力先を指定\n3. 「アプリ化を開始」をクリック")

    def _show_about(self):
        QMessageBox.information(self, "About", "Python App Converter v1.0")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppConverterApp()
    window.show()
    sys.exit(app.exec_())
