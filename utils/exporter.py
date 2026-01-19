import csv
import gspread
import os
from datetime import datetime

class DataExporter:
    """
    抽出データを外部ファイル(CSV, Google Sheets)に出力するクラス
    """
    
    @staticmethod
    def export_to_csv(filepath, clusters):
        """CSV形式で保存"""
        header = ["Area ID", "Text", "Note", "Status"]
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for i, c in enumerate(clusters):
                row = [f"Area {i+1}", c["text"], "", ""]
                writer.writerow(row)

    @staticmethod
    def export_to_gsheet(sheet_input, clusters, user_email=None, folder_url=None, cred_path="service_account.json"):
        """
        sheet_input: 
          - https://... から始まる場合 → その既存シートを開いて上書き
          - それ以外の場合 → 新規作成（容量0だと失敗する）
        """
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"認証ファイル({cred_path})が見つかりません")

        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            gc = gspread.service_account(filename=cred_path, scopes=scopes)
            
            # ★【変更点】入力がURLなら、既存シートを開くモードにする
            if sheet_input.startswith("https://"):
                try:
                    sh = gc.open_by_url(sheet_input)
                except gspread.SpreadsheetNotFound:
                    raise Exception("指定されたURLのスプレッドシートが見つかりません。共有設定を確認してください。")
            else:
                # 従来通り：新規作成モード（今のロボットでは失敗する可能性大）
                folder_id = None
                if folder_url:
                    if "folders/" in folder_url:
                        folder_id = folder_url.split("folders/")[-1].split("?")[0]
                    else:
                        folder_id = folder_url

                if folder_id:
                    sh = gc.create(sheet_input, folder_id=folder_id)
                else:
                    sh = gc.create(sheet_input)
                
                # 新規作成した場合は共有設定が必要
                if user_email:
                    sh.share(user_email, perm_type='user', role='writer')
            
            # --- データの書き込み（共通処理） ---
            worksheet = sh.get_worksheet(0)
            worksheet.clear() 
            
            header = ["Area ID", "Extracted Text", "Human Verify", "Correction", "Timestamp"]
            rows = [header]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for i, c in enumerate(clusters):
                rows.append([f"Area {i+1}", c["text"], "", "", now])
                
            worksheet.update(rows)
            return sh.url

        except Exception as e:
            raise e
    
    @staticmethod
    def export_comparison_to_gsheet(
        sheet_input, 
        comparison_results, 
        user_email=None, 
        folder_url=None, 
        cred_path="service_account.json"
    ):
        """
        比較結果をGoogle Sheetsに出力する
        
        Args:
            sheet_input: スプレッドシートURLまたは名前
            comparison_results: ComparisonResultオブジェクトのリスト
            user_email: 共有するGmailアドレス（オプション）
            folder_url: 保存先フォルダURL（オプション）
            cred_path: 認証ファイルのパス
        
        Returns:
            スプレッドシートのURL
        """
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"認証ファイル({cred_path})が見つかりません")
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            gc = gspread.service_account(filename=cred_path, scopes=scopes)
            
            # 既存シートを開くか新規作成
            if sheet_input.startswith("https://"):
                try:
                    sh = gc.open_by_url(sheet_input)
                except gspread.SpreadsheetNotFound:
                    raise Exception("指定されたURLのスプレッドシートが見つかりません。共有設定を確認してください。")
            else:
                folder_id = None
                if folder_url:
                    if "folders/" in folder_url:
                        folder_id = folder_url.split("folders/")[-1].split("?")[0]
                    else:
                        folder_id = folder_url
                
                if folder_id:
                    sh = gc.create(sheet_input, folder_id=folder_id)
                else:
                    sh = gc.create(sheet_input)
                
                if user_email:
                    sh.share(user_email, perm_type='user', role='writer')
            
            # 比較結果専用のワークシートを作成または取得
            try:
                worksheet = sh.worksheet("比較結果")
            except gspread.WorksheetNotFound:
                worksheet = sh.add_worksheet(title="比較結果", rows=1000, cols=6)
            
            worksheet.clear()
            
            # ヘッダー行
            header = [
                "Area ID",
                "Source A Text",
                "Source B Text",
                "Sync Rate (%)",
                "Status",
                "Diff Details"
            ]
            rows = [header]
            
            # データ行
            for result in comparison_results:
                sync_rate_str = f"{result.sync_rate:.1f}%" if result.sync_rate > 0 else "-"
                rows.append([
                    f"Area {result.area_id}",
                    result.source_a_text,
                    result.source_b_text,
                    sync_rate_str,
                    result.status,
                    result.diff_details
                ])
            
            # 書き込み
            worksheet.update(rows)
            
            # 書式設定（オプション）: ヘッダー行を太字にする
            try:
                worksheet.format('A1:F1', {'textFormat': {'bold': True}})
            except:
                pass  # 書式設定が失敗しても続行
            
            return sh.url
            
        except Exception as e:
            raise e