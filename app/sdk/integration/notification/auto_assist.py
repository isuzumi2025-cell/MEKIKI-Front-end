"""
Clawdbot 自律アシスタント
作業開始前に自動でコンテキストを収集してSlack/Antigravityに告知

機能:
- Vault/KI検索
- Grokリアルタイム検索（X/Web）
- Slack通知

使用方法:
    python -m app.sdk.notification.auto_assist "問題の説明"
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from .context_search import find_related_context, extract_keywords
from .clawdbot_client import notify_slack, get_clawdbot_client

# Grokクライアント（遅延インポート）
def get_grok_search():
    """Grok検索関数を取得（利用可能な場合）"""
    try:
        from app.sdk.llm.grok_client import search_realtime, is_grok_available
        if is_grok_available():
            return search_realtime
    except ImportError:
        pass
    return None

# Web検索結果を格納（Antigravity経由）
_web_search_results: Optional[str] = None

def set_web_search_results(results: str):
    """Antigravityからの検索結果を設定"""
    global _web_search_results
    _web_search_results = results

def get_web_search_results() -> Optional[str]:
    """Web検索結果を取得"""
    return _web_search_results


def prepare_work_briefing(problem_description: str) -> dict:
    """
    作業開始前のブリーフィング資料を準備
    
    Args:
        problem_description: 問題の説明
    
    Returns:
        ブリーフィング情報の辞書
    """
    keywords = extract_keywords(problem_description)
    context = find_related_context(' '.join(keywords))
    
    # Grokリアルタイム検索（利用可能な場合）
    grok_result = None
    grok_search = get_grok_search()
    if grok_search:
        try:
            grok_result = grok_search(problem_description)
            print("🔍 Grokリアルタイム検索完了")
        except Exception as e:
            print(f"⚠️ Grok検索エラー: {e}")
    
    briefing = {
        'timestamp': datetime.now().isoformat(),
        'problem': problem_description,
        'keywords': keywords,
        'vault_matches': context['vault'],
        'ki_matches': context['knowledge_items'],
        'grok_result': grok_result,
        'recommended_reading': [],
        'warnings': []
    }
    
    # 推奨読了ファイルを抽出
    for v in context['vault'][:3]:
        briefing['recommended_reading'].append(v['full_path'])
    
    # 慎重操作ファイルの警告
    cautious_files = [
        'unified_app.py', 
        'advanced_comparison_view.py',
        'ocr_engine.py'
    ]
    for kw in keywords:
        for cf in cautious_files:
            if cf.lower() in kw.lower():
                briefing['warnings'].append(f"⚠️ 慎重操作ファイル検出: {cf}")
    
    return briefing


def notify_slack_briefing(briefing: dict) -> bool:
    """
    Slackにブリーフィングを送信
    """
    lines = [
        f"🤖 [Clawdbot Auto-Assist] {datetime.now().strftime('%H:%M')}",
        f"📋 Problem: {briefing['problem'][:100]}...",
        f"🔑 Keywords: {', '.join(briefing['keywords'][:5])}",
        ""
    ]
    
    if briefing['vault_matches']:
        lines.append("📁 Related Vault Files:")
        for v in briefing['vault_matches'][:3]:
            lines.append(f"  - {v['path']}")
    
    if briefing['ki_matches']:
        lines.append("🧠 Related KI:")
        for k in briefing['ki_matches'][:2]:
            lines.append(f"  - {k['name']}")
    
    if briefing['warnings']:
        lines.append("")
        lines.extend(briefing['warnings'])
    
    message = '\n'.join(lines)
    return notify_slack(message)


def generate_antigravity_context(briefing: dict) -> str:
    """
    Antigravity (Claude) に渡すコンテキストを生成
    """
    lines = [
        "=" * 60,
        "🤖 CLAWDBOT AUTO-ASSIST BRIEFING",
        "=" * 60,
        f"Time: {briefing['timestamp']}",
        f"Problem: {briefing['problem']}",
        "",
        "📚 RECOMMENDED READING (before making changes):",
    ]
    
    for path in briefing['recommended_reading']:
        lines.append(f"  - {path}")
    
    if briefing['vault_matches']:
        lines.append("")
        lines.append("📁 VAULT CONTEXT:")
        for v in briefing['vault_matches'][:3]:
            lines.append(f"  [{v['path']}]")
            if v.get('preview'):
                for pl in v['preview'].split('\n')[:2]:
                    lines.append(f"    > {pl}")
    
    if briefing['ki_matches']:
        lines.append("")
        lines.append("🧠 KNOWLEDGE ITEMS:")
        for k in briefing['ki_matches'][:2]:
            lines.append(f"  [{k['name']}]")
            lines.append(f"    {k['summary'][:150]}...")
    
    # Grok検索結果
    if briefing.get('grok_result'):
        lines.append("")
        lines.append("🌐 GROK REALTIME SEARCH:")
        grok = briefing['grok_result']
        if isinstance(grok, dict) and grok.get('summary'):
            lines.append(f"  {grok['summary'][:300]}...")
        elif isinstance(grok, str):
            lines.append(f"  {grok[:300]}...")
    
    if briefing['warnings']:
        lines.append("")
        lines.append("⚠️ WARNINGS:")
        lines.extend(f"  {w}" for w in briefing['warnings'])
    
    lines.append("")
    lines.append("=" * 60)
    
    return '\n'.join(lines)


def auto_assist(problem_description: str, notify_to_slack: bool = True) -> str:
    """
    メイン関数: 自律的にコンテキスト収集して告知
    
    Args:
        problem_description: 問題の説明
        notify_to_slack: Slackに通知するか
    
    Returns:
        Antigravity用のコンテキスト文字列
    """
    # ブリーフィング準備
    briefing = prepare_work_briefing(problem_description)
    
    # Slack通知（オプション）
    if notify_to_slack:
        try:
            notify_slack_briefing(briefing)
        except Exception as e:
            print(f"Slack notification failed: {e}")
    
    # Antigravity用コンテキスト生成
    context = generate_antigravity_context(briefing)
    
    return context


# CLI実行
if __name__ == "__main__":
    if len(sys.argv) > 1:
        problem = ' '.join(sys.argv[1:])
        result = auto_assist(problem)
        print(result)
    else:
        print("Usage: python -m app.sdk.notification.auto_assist 'problem description'")
