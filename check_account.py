import json
import os
import gspread

def check_identity():
    file_name = "service_account.json"
    
    # 1. ファイルが存在するか確認
    if not os.path.exists(file_name):
        print(f"❌ エラー: {file_name} が見つかりません！")
        print("新しい鍵ファイルを、この 'check_account.py' と同じ場所に置いてください。")
        return

    # 2. JSONの中身を直接読んで、メールアドレスを表示
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            data = json.load(f)
            email_in_file = data.get("client_email", "不明")
            print(f"📂 ファイル内のメールアドレス: {email_in_file}")
    except Exception as e:
        print(f"❌ ファイル読み込みエラー: {e}")
        return

    # 3. 実際にGoogleに接続して、ログイン中のIDを確認
    print("\nGoogleに問い合わせ中...")
    try:
        gc = gspread.service_account(filename=file_name)
        # テスト用の通信
        print("✅ 認証成功！")
        print("--------------------------------------------------")
        print(f"現在、アプリはこのロボットとして動作しています:\n{email_in_file}")
        print("--------------------------------------------------")
        
        # もしこれが「古いアカウント」なら、上書きが失敗しています。
        # もしこれが「新しいアカウント」なのにエラーが出るなら、Google側の反映待ちです。
        
    except Exception as e:
        print(f"❌ 認証エラー: {e}")

if __name__ == "__main__":
    check_identity()