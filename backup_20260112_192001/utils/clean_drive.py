import gspread
import os

def clean_service_account_drive():
    """
    サービスアカウントのドライブ内にある全スプレッドシートを削除して容量を空けるツール
    """
    cred_path = "service_account.json"
    if not os.path.exists(cred_path):
        print(f"エラー: {cred_path} が見つかりません。")
        return

    # ドライブ操作権限を含めて認証
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    print("認証中...")
    gc = gspread.service_account(filename=cred_path, scopes=scopes)
    
    print("ファイル一覧を取得中...")
    # サービスアカウントが閲覧可能な全スプレッドシートを取得
    files = gc.list_spreadsheet_files()
    
    if not files:
        print("削除できるファイルはありませんでした。ドライブは空です。")
        return

    print(f"\n{len(files)} 個のファイルが見つかりました。")
    print("これらを全て削除しますか？ (Y/N)")
    choice = input(">> ").upper()

    if choice != 'Y':
        print("中止しました。")
        return

    print("\n削除を開始します...")
    deleted_count = 0
    
    for f in files:
        file_id = f['id']
        file_name = f['name']
        try:
            print(f"削除中: {file_name} ({file_id}) ... ", end="")
            gc.del_spreadsheet(file_id)
            print("OK")
            deleted_count += 1
        except Exception as e:
            print(f"失敗: {e}")

    print(f"\n完了: {deleted_count} 個のファイルを削除しました。")
    print("これで容量が空きました。アプリを再実行してみてください。")

if __name__ == "__main__":
    clean_service_account_drive()