# Excelレポート出力機能 - 実装ドキュメント

## 概要
プロジェクトの比較結果を詳細なExcelレポートとして出力する業務レベルの機能を実装しました。

## 実装完了機能

### ✅ 1. ライブラリ
- **`openpyxl>=3.1.0`** を使用
- `requirements.txt`に追加済み

### ✅ 2. レイアウト

#### シート1: 比較結果（メインシート）

```
┌────┬─────────┬─────────┬──────────┬─────────┬──────────┬────────┐
│No. │シンクロ率│ Web画像 │Webテキスト│ PDF画像 │PDFテキスト│  備考  │
├────┼─────────┼─────────┼──────────┼─────────┼──────────┼────────┤
│ 1  │  85%   │[サムネイル]│ 折り返し │[サムネイル]│ 折り返し │URL/File│
│    │  緑背景  │  250px  │ 表示    │  250px  │ 表示    │ページ  │
├────┼─────────┼─────────┼──────────┼─────────┼──────────┼────────┤
│ 2  │  45%   │[サムネイル]│ 折り返し │[サムネイル]│ 折り返し │URL/File│
│    │  黄背景  │  250px  │ 表示    │  250px  │ 表示    │ページ  │
└────┴─────────┴─────────┴──────────┴─────────┴──────────┴────────┘
```

**特徴**:
- 1行1ペア（Webページ vs PDFページ）
- 行の高さ: 200ピクセル（画像表示用）
- テキストは折り返し表示（`wrap_text=True`）
- セルの背景色でスコアを視覚化

#### シート2: 詳細差分（差分分析）

```
┌────┬─────────┬────────┬───────────────────┬────────┐
│No. │Web/PDF  │行番号   │ テキスト          │ 状態   │
├────┼─────────┼────────┼───────────────────┼────────┤
│ 1  │ 共通    │   1    │ 見出しテキスト     │ 一致   │
│    │         │        │                   │ 緑背景  │
├────┼─────────┼────────┼───────────────────┼────────┤
│ 1  │ Web     │   2    │ Web固有のテキスト  │ 削除   │
│    │         │        │ (赤文字)          │ 赤背景  │
├────┼─────────┼────────┼───────────────────┼────────┤
│ 1  │ PDF     │   3    │ PDF固有のテキスト  │ 追加   │
│    │         │        │ (青文字)          │ 青背景  │
└────┴─────────┴────────┴───────────────────┴────────┘
```

**特徴**:
- 行単位でテキスト差分を分析
- `difflib.ndiff()`を使用した正確な差分検出
- 色分けで状態を視覚化:
  - 緑: 一致
  - 赤: 削除（Webのみ）
  - 青: 追加（PDFのみ）

### ✅ 3. 画像貼り付け

**実装内容**:
```python
def _add_image_to_cell(self, pil_image, row, col, max_width=250, max_height=180):
    # 画像をリサイズ（アスペクト比を保持）
    img_copy = pil_image.copy()
    img_copy.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    
    # PIL ImageをバイトストリームでExcel画像に変換
    img_buffer = io.BytesIO()
    img_copy.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Excel画像オブジェクトを作成
    xl_image = XLImage(img_buffer)
    xl_image.anchor = f"{col_letter}{row}"
    self.worksheet.add_image(xl_image)
```

**特徴**:
- PIL Imageから直接Excelに貼り付け
- サムネイル化（250x180px以内）
- アスペクト比を保持
- メモリ効率的な処理

### ✅ 4. 差分強調

**スコアによる色分け**:
```python
if score >= 0.7:
    # 高スコア: 緑背景
    cell.fill = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
    cell.font = Font(bold=True, color="2E7D32")
elif score >= 0.4:
    # 中スコア: 黄背景
    cell.fill = PatternFill(start_color="FFF9C4", end_color="FFF9C4", fill_type="solid")
    cell.font = Font(bold=True, color="F57F17")
else:
    # 低スコア: 赤背景
    cell.fill = PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")
    cell.font = Font(bold=True, color="C62828")
```

**テキスト差分の強調**:
```python
# 差分がある場合、PDFテキストセルの背景を薄いピンクに
if web_page.text != pdf_page.text:
    pdf_text_cell.fill = PatternFill(start_color="FFE0E0", end_color="FFE0E0", fill_type="solid")
```

**詳細差分の強調**:
- 一致: 緑背景 (`C8E6C9`)
- 削除: 赤背景 + 赤文字 (`FFCDD2`, `C62828`)
- 追加: 青背景 + 青文字 (`BBDEFB`, `1976D2`)

### ✅ 5. UI統合

**ボタンの追加**:
```python
ctk.CTkButton(
    process_frame, 
    text="📤 Excelレポート出力", 
    command=self.export_excel_report,
    width=180,
    fg_color="#FF6F00",  # オレンジ色
    hover_color="#E65100",
    font=("Meiryo", 11)
)
```

**配置場所**:
- プロジェクト管理画面のツールバー
- 「処理」セクション内
- 「プロジェクト読込」ボタンの右側

## 使用方法

### 基本的な流れ

1. **Webクロール実行**
   - 「Web一括クロール」ボタンをクリック
   - WebページとスクリーンショットをURL取得

2. **PDF読込実行**
   - 「PDF一括読込」ボタンをクリック
   - PDFページと画像を読み込み

3. **マッチング実行**
   - 「一括マッチング」ボタンをクリック
   - WebとPDFの類似度を自動計算

4. **Excelレポート出力** ✨
   - 「📤 Excelレポート出力」ボタンをクリック
   - 保存先を選択
   - 自動的に2シートのExcelファイルが生成される

### エラーハンドリング

**マッチング結果がない場合**:
```
⚠️ 警告
マッチング結果がありません。
先に「一括マッチング」を実行してください。
```

**出力成功時**:
```
✅ 完了
Excelレポートを出力しました。

C:\Users\...\比較レポート.xlsx

📊 2つのシートが含まれています:
• 比較結果: 画像とテキストの一覧
• 詳細差分: 行単位の差分分析
```

## API詳細

### ReportGenerator クラス

```python
from app.core.report_generator import ReportGenerator

generator = ReportGenerator()
```

#### メソッド

##### `generate_excel_report()`
基本的なExcelレポートを生成

```python
success = generator.generate_excel_report(
    output_path="report.xlsx",
    web_pages=[...],  # WebPageオブジェクトのリスト
    pdf_pages=[...],  # PDFPageオブジェクトのリスト
    pairs=[...],      # MatchPairオブジェクトのリスト
    project_name="比較プロジェクト"
)
```

**戻り値**: `bool` - 成功時True

##### `generate_detailed_diff_report()`
詳細な差分レポートを生成（推奨）

```python
success = generator.generate_detailed_diff_report(
    output_path="detailed_report.xlsx",
    web_pages=[...],
    pdf_pages=[...],
    pairs=[...],
    project_name="比較プロジェクト"
)
```

**戻り値**: `bool` - 成功時True

**機能**:
- 基本レポート（シート1）
- 詳細差分分析（シート2）

### 内部メソッド

| メソッド | 説明 |
|---------|------|
| `_setup_header()` | ヘッダー行を設定 |
| `_add_comparison_row()` | 比較データ行を追加 |
| `_add_image_to_cell()` | 画像をセルに貼り付け |
| `_adjust_column_widths()` | 列幅を調整 |
| `_get_border()` | セルの枠線を取得 |
| `_add_diff_analysis()` | 差分分析シートを追加 |

## レポートの詳細

### カラム構成

| カラム | 幅 | 内容 |
|--------|---|------|
| A (No.) | 8 | 連番 |
| B (シンクロ率) | 12 | スコア（色分け）|
| C (Web画像) | 35 | サムネイル画像 |
| D (Webテキスト) | 50 | 抽出テキスト（折り返し）|
| E (PDF画像) | 35 | サムネイル画像 |
| F (PDFテキスト) | 50 | 抽出テキスト（折り返し）|
| G (備考) | 30 | URL/ファイル名/ページ番号 |

### スタイル設定

**タイトル行**:
- フォント: 16pt, 太字, 白文字
- 背景: 青 (`2196F3`)
- 高さ: 30px
- 中央揃え

**ヘッダー行**:
- フォント: 太字, 白文字
- 背景: 緑 (`4CAF50`)
- 高さ: 25px
- 中央揃え

**データ行**:
- 高さ: 200px（画像表示用）
- 折り返し: テキストセルは自動折り返し
- 枠線: 全セルに薄灰色の枠線

## パフォーマンス

### メモリ効率

- 画像はサムネイル化（250x180px以内）
- BytesIOを使用した効率的な画像処理
- 不要なオブジェクトは自動解放

### 処理時間

| ペア数 | 推定時間 |
|-------|---------|
| 10件 | 5-10秒 |
| 50件 | 20-40秒 |
| 100件 | 40-80秒 |

※画像のサイズとテキスト量により変動

### バックグラウンド処理

```python
# UIフリーズを防ぐため、別スレッドで実行
threading.Thread(target=self._run_export_excel, args=(output_path,), daemon=True).start()
```

## トラブルシューティング

### 画像が表示されない

**原因**: PIL Imageが存在しない
**解決策**: `screenshot_image`と`page_image`が正しく設定されているか確認

### ファイルが保存できない

**原因**: ファイルが開かれている
**解決策**: Excelファイルを閉じてから再実行

### メモリエラー

**原因**: 大量のペアまたは大きな画像
**解決策**: 
- ペア数を減らす
- 画像のサムネイルサイズを小さくする

## まとめ

✅ **実装完了機能**:
1. `openpyxl`を使用したExcel生成
2. 1行1ペアのレイアウト
3. 画像のサムネイル化と貼り付け
4. テキストの折り返し表示
5. 差分の色分け強調
6. 詳細差分分析シート
7. UI統合（ボタン追加）

🎯 **ビジネスメリット**:
- 比較結果を業務レベルのレポートとして出力
- 視覚的に分かりやすい（画像+色分け）
- 詳細な差分分析が可能
- Excelなので加工・共有が容易

🚀 **今後の拡張可能性**:
- グラフ・チャートの追加
- サマリーシートの作成
- フィルター機能の追加
- カスタムテンプレート対応

