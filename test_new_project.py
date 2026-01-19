"""
新規プロジェクト機能のテストスクリプト
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


def test_project_dialog():
    """プロジェクトダイアログのテスト"""
    print("=" * 60)
    print("🧪 プロジェクトダイアログのテスト")
    print("=" * 60)
    
    from app.gui.main_window_v2 import MainWindow
    
    # GUIを起動
    app = MainWindow()
    
    print("✅ アプリ起動完了")
    print("   左のナビゲーションから「➕ 新規プロジェクト」をクリックしてください")
    
    app.mainloop()


if __name__ == "__main__":
    print("\n🚀 新規プロジェクト機能テスト\n")
    
    try:
        test_project_dialog()
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

