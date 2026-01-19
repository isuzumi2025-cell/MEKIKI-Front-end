"""
main_window.py の動作確認スクリプト
NavigationPanel統合、新規プロジェクト機能のテスト
"""
import sys
import io
from pathlib import Path

# Windows UTF-8対応
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_main_window():
    """MainWindowのテスト"""
    print("=" * 60)
    print("🧪 MainWindow 統合テスト")
    print("=" * 60)
    
    from app.gui.main_window import MainWindow
    
    print("\n✅ アプリ起動完了")
    print("\n📝 テスト手順:")
    print("  1. ウェルカム画面が表示されます")
    print("  2. 左のナビゲーションから「➕ 新規プロジェクト」をクリック")
    print("  3. ダイアログで設定を入力")
    print("  4. 「🚀 分析開始」をクリック")
    print("  5. 処理が完了したら全体マップが表示されます")
    print("\n" + "=" * 60)
    
    # GUIを起動
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    print("\n🚀 MainWindow 統合テスト開始\n")
    
    try:
        test_main_window()
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

