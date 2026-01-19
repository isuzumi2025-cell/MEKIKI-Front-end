# 次回作業開始ガイド (NEXT_SESSION_GUIDE)

## 🕒 保存と終了の手順

現在、検証作業 (`verify/run_verify_all.ps1`) の途中です。安全に終了するために以下の手順を実行してください。

### 1. サーバープロセスの停止
もし `uvicorn` や `python` のサーバープロセスが裏で動いている場合は停止します。
PowerShell で以下を実行してください（エラーが出ても問題ありません）:
```powershell
Get-Process python* | Stop-Process -Force
```

### 2. バックアップの作成 (推奨)
作業状態を保存するために、現在の `OCR` フォルダのバックアップを作成することをお勧めします。
PowerShell で以下を実行してください:
```powershell
$date = Get-Date -Format "yyyyMMdd_HHmmss"
$source = "c:\Users\raiko\OneDrive\Desktop\26\OCR"
$dest = "c:\Users\raiko\OneDrive\Desktop\26\OCR_backup_$date"
Copy-Item -Path $source -Destination $dest -Recurse
Write-Host "Backup created at $dest"
```

### 3. エディタの終了
VS Code を閉じてください。ファイルは自動保存されているか、閉じる際に保存を聞かれます。

---

## 🚀 次回作業の開始手順

### 1. 復帰
次回はこのフォルダ (`c:\Users\raiko\OneDrive\Desktop\26\OCR`) を VS Code で開いてください。

### 2. 検証の再開
現在開いている `verify/run_verify_all.ps1` を実行して、環境が正常か確認できます。
```powershell
cd c:\Users\raiko\OneDrive\Desktop\26\OCR
.\verify\run_verify_all.ps1
```

### 3. アプリケーションの起動
メインアプリを起動する場合:
```powershell
py -3 run_unified.py
```

### 4. コンテキストの復元
前回の作業内容は `RUNBOOK.md` の "🚀 NEXT" セクションを確認してください。
- 現在のフェーズ: テキスト抽出パイプライン再設計 / AI分析モード検証
