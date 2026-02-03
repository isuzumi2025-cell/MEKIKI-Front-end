"""
Clawdbot Context Search Module
開発時に関連コンテキストを自動検索してアシスト

機能:
- Obsidian Vault検索
- Knowledge Items (KI)検索
- 過去の会話ログ検索
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import json

# パス設定
VAULT_PATH = Path("c:/Users/raiko/OneDrive/Desktop/26/OCR/Vault")
KI_PATH = Path("C:/Users/raiko/.gemini/antigravity/knowledge")
CONVERSATIONS_PATH = Path("C:/Users/raiko/.gemini/antigravity/conversations")


def search_vault(query: str, max_results: int = 5) -> List[Dict]:
    """
    Obsidian Vaultを検索
    
    Args:
        query: 検索クエリ（キーワード）
        max_results: 最大結果数
    
    Returns:
        マッチしたファイル情報のリスト
    """
    results = []
    query_lower = query.lower()
    keywords = query_lower.split()
    
    if not VAULT_PATH.exists():
        return results
    
    for md_file in VAULT_PATH.rglob("*.md"):
        try:
            content = md_file.read_text(encoding='utf-8', errors='ignore')
            content_lower = content.lower()
            
            # キーワードマッチング
            match_count = sum(1 for kw in keywords if kw in content_lower)
            if match_count > 0:
                # 関連行を抽出
                relevant_lines = []
                for line in content.split('\n'):
                    if any(kw in line.lower() for kw in keywords):
                        relevant_lines.append(line.strip()[:100])
                        if len(relevant_lines) >= 3:
                            break
                
                results.append({
                    'path': str(md_file.relative_to(VAULT_PATH)),
                    'full_path': str(md_file),
                    'match_score': match_count,
                    'preview': '\n'.join(relevant_lines[:3])
                })
        except Exception:
            continue
    
    # スコア順でソート
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:max_results]


def search_knowledge_items(query: str, max_results: int = 3) -> List[Dict]:
    """
    Knowledge Itemsを検索
    
    Args:
        query: 検索クエリ
        max_results: 最大結果数
    
    Returns:
        マッチしたKI情報のリスト
    """
    results = []
    query_lower = query.lower()
    keywords = query_lower.split()
    
    if not KI_PATH.exists():
        return results
    
    for ki_dir in KI_PATH.iterdir():
        if not ki_dir.is_dir():
            continue
        
        metadata_file = ki_dir / "metadata.json"
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
                summary = metadata.get('summary', '').lower()
                
                match_count = sum(1 for kw in keywords if kw in summary)
                if match_count > 0:
                    results.append({
                        'name': ki_dir.name,
                        'summary': metadata.get('summary', '')[:200],
                        'match_score': match_count,
                        'artifacts': list((ki_dir / 'artifacts').rglob('*.md'))[:5] if (ki_dir / 'artifacts').exists() else []
                    })
            except Exception:
                continue
    
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:max_results]


def find_related_context(topic: str) -> Dict:
    """
    トピックに関連するコンテキストを総合検索
    
    Args:
        topic: 検索トピック（例: "canvas error", "thumbnail link"）
    
    Returns:
        {
            'vault': [...],
            'knowledge_items': [...],
            'summary': str
        }
    """
    vault_results = search_vault(topic)
    ki_results = search_knowledge_items(topic)
    
    summary_parts = []
    
    if vault_results:
        summary_parts.append(f"📁 Vault: {len(vault_results)} files found")
        for r in vault_results[:3]:
            summary_parts.append(f"  - {r['path']}")
    
    if ki_results:
        summary_parts.append(f"🧠 KI: {len(ki_results)} items found")
        for r in ki_results[:2]:
            summary_parts.append(f"  - {r['name']}")
    
    return {
        'vault': vault_results,
        'knowledge_items': ki_results,
        'summary': '\n'.join(summary_parts) if summary_parts else 'No related context found'
    }


def assist_with_context(problem_description: str) -> str:
    """
    問題に対して関連コンテキストを検索してアシスト
    
    Args:
        problem_description: 問題の説明
    
    Returns:
        アシストメッセージ
    """
    # キーワード抽出
    keywords = extract_keywords(problem_description)
    
    # 関連コンテキスト検索
    context = find_related_context(' '.join(keywords))
    
    # レポート生成
    report = [
        "🤖 [Clawdbot Context Search]",
        f"Keywords: {', '.join(keywords)}",
        "",
        context['summary']
    ]
    
    # 最も関連性の高いファイルの内容を追加
    if context['vault']:
        top_match = context['vault'][0]
        report.append(f"\n📄 Top Match: {top_match['path']}")
        if top_match.get('preview'):
            report.append(f"Preview:\n{top_match['preview']}")
    
    return '\n'.join(report)


def extract_keywords(text: str) -> List[str]:
    """テキストからキーワードを抽出"""
    # 日本語と英語のキーワードを抽出
    # 一般的なストップワードを除外
    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                 'が', 'の', 'に', 'を', 'は', 'で', 'と', 'も', 'や'}
    
    # 単語分割（簡易版）
    words = re.findall(r'[a-zA-Z]{3,}|[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]{2,}', text)
    
    # ストップワード除去
    keywords = [w.lower() for w in words if w.lower() not in stopwords]
    
    # 重複除去して返す
    return list(dict.fromkeys(keywords))[:10]


# クイックアクセス関数
def quick_search(query: str) -> None:
    """クイック検索（コンソール出力）"""
    result = assist_with_context(query)
    print(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
        quick_search(query)
    else:
        print("Usage: python context_search.py <query>")
        print("Example: python context_search.py canvas thumbnail error")
