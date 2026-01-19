import os
import requests
import google.auth.transport.requests
from google.oauth2 import service_account

def force_empty_trash():
    """
    サービスアカウントのGoogleドライブの「ゴミ箱」を裏口(API)から強制的に空にするツール
    """
    cred_path = "service_account.json"
    
    print("--- ゴミ箱 強制クリーナー ---")
    if not os.path.exists(cred_path):
        print(f"❌ エラー: {cred_path} が見つかりません。")
        return

    # 1. 認証 (Driveへのフルアクセス権限)
    print("🔑 認証情報を読み込んでいます...")
    scopes = ['https://www.googleapis.com/auth/drive']
    
    try:
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
        # 有効なトークンを取得
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        token = creds.token
    except Exception as e:
        print(f"❌ 認証エラー: {e}")
        print("service_account.json が正しいか確認してください。")
        return

    # 2. APIを叩いてゴミ箱を空にする (DELETEリクエスト)
    print("🗑️ ゴミ箱を空にする命令を送信中...")
    
    url = "https://www.googleapis.com/drive/v3/files/trash"
    headers = {"Authorization": f"Bearer {token}"}
    
    # API実行
    response = requests.delete(url, headers=headers)

    # 3. 結果確認
    if response.status_code == 204:
        print("\n✅ 【成功】ゴミ箱を完全に空にしました！")
        print("   容量が確保されました。")
        print("   これでOCRアプリの「Google Sheets出力」が動くはずです。")
    else:
        print(f"\n⚠️ エラーが発生しました (Code: {response.status_code})")
        print("詳細:", response.text)

if __name__ == "__main__":
    force_empty_trash()