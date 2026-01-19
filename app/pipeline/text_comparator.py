"""
Phase 3/4: テキスト全文比較と完全一致検索

CSVから抽出したWeb/PDFテキストを比較し、
8文字以上の共通部分を持つパラグラフペアを特定する
"""

import csv
from difflib import SequenceMatcher
from pathlib import Path

def find_common_substrings(text1, text2, min_length=8):
    """8文字以上の共通部分文字列を検索"""
    if not text1 or not text2:
        return []
    
    # 正規化（改行を空白に置換）
    t1 = text1.replace('\n', ' ').strip()
    t2 = text2.replace('\n', ' ').strip()
    
    shorter = t1 if len(t1) <= len(t2) else t2
    longer = t2 if len(t1) <= len(t2) else t1
    
    if len(shorter) < min_length:
        return []
    
    # 最長共通部分文字列を探索
    for length in range(min(80, len(shorter)), min_length - 1, -1):
        for i in range(len(shorter) - length + 1):
            substring = shorter[i:i+length]
            if len(substring.strip()) >= min_length and substring in longer:
                return [substring]
    
    return []


def run_text_comparison():
    # 最新のCSVファイルを探す
    exports_dir = Path('./exports')
    csv_files = sorted(exports_dir.glob('metadata_*.csv'), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not csv_files:
        print("ERROR: No metadata CSV found in exports/")
        return
    
    csv_path = csv_files[0]
    print(f"Reading: {csv_path}")
    print("=" * 80)
    
    # CSVファイル読み込み
    web_texts = []
    pdf_texts = []
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Source'] == 'web':
                web_texts.append({'id': row['ID'], 'text': row['Text']})
            else:
                pdf_texts.append({'id': row['ID'], 'text': row['Text']})
    
    print(f"Web paragraphs: {len(web_texts)}")
    print(f"PDF paragraphs: {len(pdf_texts)}")
    print("=" * 80)
    
    # マッチング実行
    match_results = []
    
    for w in web_texts:
        for p in pdf_texts:
            common = find_common_substrings(w['text'], p['text'])
            if common:
                match_results.append({
                    'web_id': w['id'],
                    'pdf_id': p['id'],
                    'common': common[0],
                    'common_len': len(common[0]),
                    'web_text': w['text'][:100],
                    'pdf_text': p['text'][:100]
                })
    
    # 結果をソート（共通部分が長い順）
    match_results.sort(key=lambda x: x['common_len'], reverse=True)
    
    # 重複を除去（同じWeb IDは最も長いマッチのみ）
    seen_web = set()
    unique_results = []
    for m in match_results:
        if m['web_id'] not in seen_web:
            unique_results.append(m)
            seen_web.add(m['web_id'])
    
    print(f"\nTotal matching pairs (raw): {len(match_results)}")
    print(f"Unique Web matches: {len(unique_results)}")
    print("\n" + "=" * 80)
    print("TOP 30 MATCHES (by common substring length)")
    print("=" * 80)
    
    for i, m in enumerate(unique_results[:30]):
        print(f"\n[{i+1}] {m['web_id']} <=> {m['pdf_id']} ({m['common_len']} chars)")
        print(f"  Common substring: [{m['common'][:70]}...]")
        print(f"  Web: {m['web_text'][:80]}...")
        print(f"  PDF: {m['pdf_text'][:80]}...")
    
    # 結果をCSVに出力
    output_path = exports_dir / f"comparison_results.csv"
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['#', 'Web_ID', 'PDF_ID', 'Common_Length', 'Common_Substring', 'Web_Text', 'PDF_Text'])
        for i, m in enumerate(unique_results):
            writer.writerow([
                i + 1,
                m['web_id'],
                m['pdf_id'],
                m['common_len'],
                m['common'][:200],
                m['web_text'][:300],
                m['pdf_text'][:300]
            ])
    
    print(f"\n\nResults saved to: {output_path}")
    print(f"Total unique paragraph matches: {len(unique_results)}")
    
    # Phase 4: 比較結果Excelを出力 (RUNBOOKフォーマット)
    try:
        from app.pipeline.metadata_exporter import export_comparison_results
        excel_path = export_comparison_results(unique_results, str(exports_dir))
        if excel_path:
            print(f"Comparison Excel: {excel_path}")
    except Exception as e:
        print(f"Excel export skipped: {e}")
    
    return unique_results


if __name__ == '__main__':
    run_text_comparison()
