import os
import requests
import google.auth.transport.requests
from google.oauth2 import service_account

def nuke_all_files():
    print("--- ☢️ Google Drive 完全初期化ツール ☢️ ---")
    cred_path = "service_account.json"
    
    # 1. 認証
    if not os.path.exists(cred_path):
        print(f"❌ エラー: {cred_path} がありません")
        return

    scopes = ['https://www.googleapis.com/auth/drive']
    try:
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        token = creds.token
    except Exception as e:
        print(f"❌ 認証エラー: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. 現在の容量使用量を確認
    print("\n📊 容量チェック中...")
    about_url = "https://www.googleapis.com/drive/v3/about?fields=storageQuota"
    res_about = requests.get(about_url, headers=headers)
    if res_about.status_code == 200:
        quota = res_about.json().get('storageQuota', {})
        usage = int(quota.get('usage', 0))
        limit = int(quota.get('limit', 1))
        print(f"   使用量: {usage / 1024 / 1024:.2f} MB")
        print(f"   上限　: {limit / 1024 / 1024:.2f} MB")
    else:
        print("   容量情報の取得に失敗")

    # 3. 全ファイルリスト取得 (ゴミ箱以外)
    print("\n🔍 全ファイルを捜索中...")
    # qパラメータで「ゴミ箱に入っていない」かつ「フォルダではない」ファイルを探す
    list_url = "https://www.googleapis.com/drive/v3/files?q=trashed=false&fields=files(id,name,mimeType,size)"
    res_list = requests.get(list_url, headers=headers)
    
    files = res_list.json().get('files', [])
    
    if not files:
        print("✅ ファイルは見つかりませんでした（容量消費の原因はゴミ箱の反映待ちか、不明なデータです）")
        return

    print(f"⚠️ {len(files)} 個のファイルが見つかりました！これらが容量を圧迫しています。")
    for f in files[:5]: # 最初の5個だけ表示
        print(f"   - {f.get('name')} ({f.get('mimeType')})")
    if len(files) > 5: print("   ...他")

    # 4. 削除確認
    choice = input("\n🧨 これらを全て削除しますか？ (y/n): ")
    if choice.lower() != 'y':
        print("中止しました")
        return

    # 5. 削除実行
    print("\n🚀 削除開始...")
    count = 0
    for f in files:
        file_id = f['id']
        # deleteメソッドで完全に消す（ゴミ箱を経由しない）
        del_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        requests.delete(del_url, headers=headers)
        count += 1
        print(f"   削除完了: {f.get('name')}")

    print(f"\n✨ {count} 個のファイルを抹消しました。")
    print("これで容量が空くはずです。アプリを再実行してください。")

if __name__ == "__main__":
    nuke_all_files()