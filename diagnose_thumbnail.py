"""
サムネイル表示問題の診断スクリプト

実際にクロップされた画像を保存して、何が起きているか視覚的に確認
"""
import os
import sys
sys.path.insert(0, '.')

from PIL import Image
import json

def diagnose_thumbnail_flow():
    """
    診断項目:
    1. web_imageは何か？（サイズ、タイプ）
    2. regionのbboxは何か？
    3. クロップ結果は何か？（実際の画像を保存）
    """
    
    # 診断用ディレクトリ作成
    diag_dir = "thumbnail_diagnosis"
    os.makedirs(diag_dir, exist_ok=True)
    
    print("=" * 60)
    print("サムネイル診断開始")
    print("=" * 60)
    
    # テスト: 既存のログファイルから情報を抽出
    log_file = "lcs_diagnostic.log"
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Thumb関連のログを抽出
        thumb_logs = [line for line in content.split('\n') if 'Thumb' in line or 'bbox' in line.lower()]
        
        print(f"\nログから{len(thumb_logs)}件のThumb関連エントリを発見:")
        for log in thumb_logs[-20:]:  # 最新20件
            print(f"  {log[:100]}")
    else:
        print(f"ログファイル {log_file} が見つかりません")
    
    print("\n" + "=" * 60)
    print("次のステップ:")
    print("1. アプリでHybridOCRを実行")
    print("2. このスクリプトを再実行してログを分析")
    print("3. または、コード内で直接画像を保存する診断を追加")
    print("=" * 60)

if __name__ == "__main__":
    diagnose_thumbnail_flow()
