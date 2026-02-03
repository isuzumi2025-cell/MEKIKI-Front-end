"""
Slack Bidirectional Integration - MEKIKI Remote Control

双方向Slack連携:
1. 遠隔表示: Antigravityの現在状態をSlackにリアルタイム配信
2. コマンド入力: Slackからのコマンドを受信して実行
3. Web調査結果: Grok/Web検索結果をフォーマットして投稿

使用方法:
    from app.sdk.notification.slack_bidirectional import SlackBidirectional
    
    # 初期化
    slack = SlackBidirectional()
    
    # ステータス配信
    slack.broadcast_status("🤖 HybridOCR実行中: 3/10ページ完了")
    
    # コマンド受信開始
    slack.start_command_listener()
    
    # Web調査結果配信
    slack.broadcast_research("検索クエリ", research_results)
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from queue import Queue
import logging

from .clawdbot_client import SlackNotificationClient, notify_slack

logger = logging.getLogger(__name__)


@dataclass
class SlackCommand:
    """Slackから受信したコマンド"""
    command: str
    args: List[str] = field(default_factory=list)
    user: str = ""
    channel: str = ""
    timestamp: str = ""
    raw_text: str = ""


class CommandRegistry:
    """コマンドハンドラーレジストリ"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._register_default_commands()
    
    def _register_default_commands(self):
        """デフォルトコマンドを登録"""
        self.register("status", self._cmd_status, "現在のタスク状態を表示")
        self.register("help", self._cmd_help, "利用可能なコマンド一覧")
        self.register("tasks", self._cmd_tasks, "タスクリストを表示")
        self.register("go", self._cmd_go, "次のタスクを開始")
        self.register("stop", self._cmd_stop, "現在のタスクを停止")
        self.register("research", self._cmd_research, "Web検索を実行")
    
    def register(self, name: str, handler: Callable, description: str = ""):
        """コマンドを登録"""
        self._handlers[name] = {
            'handler': handler,
            'description': description
        }
    
    def execute(self, cmd: SlackCommand) -> str:
        """コマンドを実行"""
        if cmd.command not in self._handlers:
            return f"❌ 不明なコマンド: `{cmd.command}`\n`/mekiki help` でコマンド一覧を確認"
        
        try:
            handler = self._handlers[cmd.command]['handler']
            return handler(cmd)
        except Exception as e:
            return f"❌ コマンドエラー: {e}"
    
    # デフォルトコマンド実装
    def _cmd_status(self, cmd: SlackCommand) -> str:
        """現在のステータスを返す"""
        try:
            # task.mdから現在の状態を読み取る
            task_paths = list(Path.home().glob(".gemini/antigravity/brain/*/task.md"))
            if task_paths:
                latest = max(task_paths, key=lambda p: p.stat().st_mtime)
                content = latest.read_text(encoding='utf-8')
                # 最初の進捗セクションを抽出
                lines = content.split('\n')[:20]
                return "📋 **現在のタスク状態**\n```\n" + '\n'.join(lines) + "\n```"
        except Exception as e:
            logger.error(f"Status read error: {e}")
        return "📋 タスク情報を取得できませんでした"
    
    def _cmd_help(self, cmd: SlackCommand) -> str:
        """ヘルプを表示"""
        lines = ["🤖 **MEKIKI Remote Commands**", ""]
        for name, info in self._handlers.items():
            lines.append(f"• `/mekiki {name}` - {info['description']}")
        return '\n'.join(lines)
    
    def _cmd_tasks(self, cmd: SlackCommand) -> str:
        """タスクリストを表示"""
        try:
            task_paths = list(Path.home().glob(".gemini/antigravity/brain/*/task.md"))
            if task_paths:
                latest = max(task_paths, key=lambda p: p.stat().st_mtime)
                content = latest.read_text(encoding='utf-8')
                return f"📝 **タスクリスト**\n```\n{content}\n```"
        except Exception as e:
            logger.error(f"Tasks read error: {e}")
        return "📝 タスク情報を取得できませんでした"
    
    def _cmd_go(self, cmd: SlackCommand) -> str:
        """次のタスクを開始（シグナルファイル作成）"""
        signal_file = Path.home() / ".gemini" / "antigravity" / "signals" / "go.signal"
        signal_file.parent.mkdir(parents=True, exist_ok=True)
        signal_file.write_text(json.dumps({
            'command': 'go',
            'args': cmd.args,
            'timestamp': datetime.now().isoformat(),
            'user': cmd.user
        }))
        return "✅ **GO** シグナル送信完了。Antigravityが次のタスクを開始します。"
    
    def _cmd_stop(self, cmd: SlackCommand) -> str:
        """タスクを停止（シグナルファイル作成）"""
        signal_file = Path.home() / ".gemini" / "antigravity" / "signals" / "stop.signal"
        signal_file.parent.mkdir(parents=True, exist_ok=True)
        signal_file.write_text(json.dumps({
            'command': 'stop',
            'timestamp': datetime.now().isoformat(),
            'user': cmd.user
        }))
        return "🛑 **STOP** シグナル送信完了。"
    
    def _cmd_research(self, cmd: SlackCommand) -> str:
        """Web検索を実行"""
        if not cmd.args:
            return "⚠️ 検索クエリを指定してください: `/mekiki research <query>`"
        
        query = ' '.join(cmd.args)
        # 検索リクエストをキューに追加
        signal_file = Path.home() / ".gemini" / "antigravity" / "signals" / "research.signal"
        signal_file.parent.mkdir(parents=True, exist_ok=True)
        signal_file.write_text(json.dumps({
            'command': 'research',
            'query': query,
            'timestamp': datetime.now().isoformat(),
            'user': cmd.user
        }))
        return f"🔍 検索リクエスト送信: `{query}`\n結果は完了後に投稿されます。"


class SlackBidirectional:
    """Slack双方向連携クラス"""
    
    def __init__(self, channel: str = "context"):
        self.client = SlackNotificationClient(channel=channel)
        self.channel = channel
        self.command_registry = CommandRegistry()
        self._command_queue: Queue = Queue()
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_ts: Optional[str] = None
    
    # === 1. 遠隔表示 (Status Broadcasting) ===
    
    def broadcast_status(self, status: str, emoji: str = "🤖") -> bool:
        """
        現在のステータスをSlackに配信
        
        Args:
            status: ステータスメッセージ
            emoji: プレフィックス絵文字
        """
        message = f"{emoji} **[Antigravity Status]** {datetime.now().strftime('%H:%M:%S')}\n{status}"
        return self.client.send_message(text=message)
    
    def broadcast_progress(self, task: str, current: int, total: int) -> bool:
        """
        進捗をSlackに配信
        
        Args:
            task: タスク名
            current: 現在の進捗
            total: 合計
        """
        percent = (current / total * 100) if total > 0 else 0
        bar_filled = int(percent / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        
        message = f"📊 **{task}**\n`{bar}` {current}/{total} ({percent:.1f}%)"
        return self.client.send_message(text=message)
    
    def broadcast_context(self, context: Dict[str, Any]) -> bool:
        """
        現在のコンテキストをSlackに配信
        
        Args:
            context: コンテキスト情報（task, files, status等）
        """
        lines = [
            f"🧠 **[Antigravity Context]** {datetime.now().strftime('%H:%M:%S')}",
            f"📋 Task: {context.get('task', 'N/A')}",
            f"📁 Files: {', '.join(context.get('files', [])[:3])}",
            f"⚡ Status: {context.get('status', 'N/A')}"
        ]
        return self.client.send_message(text='\n'.join(lines))
    
    # === 2. コマンド入力 (Command Input) ===
    
    def parse_command(self, text: str) -> Optional[SlackCommand]:
        """
        Slackメッセージからコマンドをパース
        
        Args:
            text: Slackメッセージテキスト
            
        Returns:
            SlackCommandまたはNone
        """
        text = text.strip()
        
        # /mekiki <command> <args...> 形式
        if text.startswith("/mekiki"):
            parts = text.split()
            if len(parts) >= 2:
                return SlackCommand(
                    command=parts[1],
                    args=parts[2:] if len(parts) > 2 else [],
                    raw_text=text
                )
        
        # @mekiki <command> 形式も対応
        if "@mekiki" in text.lower():
            parts = text.lower().split("@mekiki")
            if len(parts) > 1:
                cmd_parts = parts[1].strip().split()
                if cmd_parts:
                    return SlackCommand(
                        command=cmd_parts[0],
                        args=cmd_parts[1:] if len(cmd_parts) > 1 else [],
                        raw_text=text
                    )
        
        return None
    
    def handle_command(self, cmd: SlackCommand) -> str:
        """
        コマンドを処理して結果を返す
        
        Args:
            cmd: SlackCommand
            
        Returns:
            レスポンスメッセージ
        """
        return self.command_registry.execute(cmd)
    
    def register_command(self, name: str, handler: Callable, description: str = ""):
        """
        カスタムコマンドを登録
        
        Args:
            name: コマンド名
            handler: ハンドラー関数
            description: 説明
        """
        self.command_registry.register(name, handler, description)
    
    # === 3. Web調査結果 (Research Broadcasting) ===
    
    def broadcast_research(self, query: str, results: Dict[str, Any]) -> bool:
        """
        Web検索結果をSlackに配信
        
        Args:
            query: 検索クエリ
            results: 検索結果
        """
        lines = [
            f"🌐 **[Web Research Results]**",
            f"🔍 Query: `{query}`",
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # Grok結果
        if results.get('grok'):
            lines.append("**🤖 Grok Analysis:**")
            grok_text = results['grok'][:500]
            lines.append(f"```\n{grok_text}\n```")
        
        # Web検索結果
        if results.get('web'):
            lines.append("**🌍 Web Sources:**")
            for i, source in enumerate(results['web'][:5], 1):
                title = source.get('title', 'N/A')[:50]
                url = source.get('url', '')
                lines.append(f"{i}. [{title}]({url})")
        
        # サマリー
        if results.get('summary'):
            lines.append("")
            lines.append("**📝 Summary:**")
            lines.append(results['summary'][:500])
        
        return self.client.send_message(text='\n'.join(lines))
    
    def broadcast_obsidian_context(self, matches: List[Dict]) -> bool:
        """
        Obsidian検索結果をSlackに配信
        
        Args:
            matches: Obsidianマッチ結果
        """
        if not matches:
            return self.client.send_message(text="📚 関連するObsidianドキュメントは見つかりませんでした")
        
        lines = [
            "📚 **[Obsidian Context]**",
            ""
        ]
        
        for match in matches[:5]:
            path = match.get('path', 'unknown')
            preview = match.get('preview', '')[:100]
            lines.append(f"• **{path}**")
            if preview:
                lines.append(f"  > {preview}...")
        
        return self.client.send_message(text='\n'.join(lines))
    
    # === ユーティリティ ===
    
    def check_signals(self) -> Optional[Dict]:
        """
        シグナルファイルをチェック
        
        Returns:
            シグナルデータまたはNone
        """
        signal_dir = Path.home() / ".gemini" / "antigravity" / "signals"
        if not signal_dir.exists():
            return None
        
        for signal_file in signal_dir.glob("*.signal"):
            try:
                data = json.loads(signal_file.read_text())
                signal_file.unlink()  # 読み取り後に削除
                return data
            except Exception as e:
                logger.error(f"Signal read error: {e}")
        
        return None


# シングルトンインスタンス
_bidirectional: Optional[SlackBidirectional] = None


def get_slack_bidirectional() -> SlackBidirectional:
    """SlackBidirectionalシングルトンを取得"""
    global _bidirectional
    if _bidirectional is None:
        _bidirectional = SlackBidirectional()
    return _bidirectional


# 便利関数
def broadcast_status(status: str) -> bool:
    """ステータスをSlackに配信"""
    return get_slack_bidirectional().broadcast_status(status)


def broadcast_progress(task: str, current: int, total: int) -> bool:
    """進捗をSlackに配信"""
    return get_slack_bidirectional().broadcast_progress(task, current, total)


def broadcast_research(query: str, results: Dict) -> bool:
    """検索結果をSlackに配信"""
    return get_slack_bidirectional().broadcast_research(query, results)


# CLI実行
if __name__ == "__main__":
    import sys
    
    slack = SlackBidirectional()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            slack.broadcast_status("CLI Test: Bidirectional Slack Integration Active")
        elif cmd == "test":
            # テストコマンド
            test_cmd = SlackCommand(command="help")
            result = slack.handle_command(test_cmd)
            print(result)
            slack.broadcast_status(f"Test Result:\n{result}")
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Usage: python -m app.sdk.notification.slack_bidirectional [status|test]")
