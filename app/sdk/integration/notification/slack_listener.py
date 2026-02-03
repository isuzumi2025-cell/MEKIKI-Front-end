"""
Slack Message Listener - Poll for new messages and commands

Usage:
    python -m app.sdk.notification.slack_listener
    
Features:
- Poll #context for new messages
- Detect commands starting with @mekiki or /mekiki
- Execute commands and respond
"""
import subprocess
import json
import urllib.request
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

# Config
POLL_INTERVAL = 5  # seconds
CHANNEL_NAME = "context"


def load_token() -> Optional[str]:
    """Load Slack bot token from config"""
    try:
        result = subprocess.run(
            ['wsl', 'cat', '/home/raiko/.clawdbot/clawdbot.json'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            config = json.loads(result.stdout)
            return config.get('channels', {}).get('slack', {}).get('botToken')
    except Exception as e:
        print(f"Token load error: {e}")
    return None


def get_bot_user_id(token: str) -> Optional[str]:
    """Get the bot's user ID"""
    try:
        req = urllib.request.Request(
            'https://slack.com/api/auth.test',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get('ok'):
                return data.get('user_id')
    except Exception as e:
        print(f"Auth error: {e}")
    return None


def get_channel_id(token: str, channel_name: str) -> Optional[str]:
    """Get channel ID by name (from cached response if available)"""
    # For now, use the known channel ID
    return "C0AB1E24AJW"


def get_recent_messages(token: str, channel_id: str, oldest: str = None, limit: int = 10) -> List[Dict]:
    """Get recent messages from channel"""
    try:
        url = f'https://slack.com/api/conversations.history?channel={channel_id}&limit={limit}'
        if oldest:
            url += f'&oldest={oldest}'
        
        req = urllib.request.Request(
            url,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get('ok'):
                return data.get('messages', [])
            else:
                print(f"History error: {data.get('error')}")
    except Exception as e:
        print(f"Get messages error: {e}")
    return []


def send_reply(token: str, channel_id: str, text: str, thread_ts: str = None) -> bool:
    """Send a reply message"""
    try:
        payload = {
            'channel': channel_id,
            'text': text
        }
        if thread_ts:
            payload['thread_ts'] = thread_ts
        
        req = urllib.request.Request(
            'https://slack.com/api/chat.postMessage',
            data=json.dumps(payload).encode(),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get('ok', False)
    except Exception as e:
        print(f"Send error: {e}")
    return False


def is_command(text: str) -> bool:
    """Check if message is a command (supports full-width @)"""
    lower = text.lower()
    # Support both half-width @ and full-width ＠
    prefixes = ['@mekiki', '＠mekiki', '/mekiki', 'mekiki']
    return any(lower.startswith(p) for p in prefixes)


def parse_command(text: str) -> tuple:
    """Parse command from message text"""
    # Remove prefix (support both half-width @ and full-width ＠)
    for prefix in ['@mekiki', '＠mekiki', '/mekiki', 'mekiki']:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    parts = text.split()
    if parts:
        return parts[0], parts[1:]
    return None, []


# Global start time for uptime tracking
_start_time = time.time()


def execute_command(cmd: str, args: List[str], token: str, channel_id: str) -> str:
    """Execute a command and return response"""
    cmd = cmd.lower() if cmd else ''
    
    # === 基本コマンド ===
    if cmd == 'help':
        return """🤖 **MEKIKI Slack Commands**

*基本コマンド*
• `@mekiki help` - このヘルプを表示
• `@mekiki ping` - 疎通確認
• `@mekiki status` - 現在の状態を表示
• `@mekiki echo <text>` - テキストをエコー

*情報コマンド*
• `@mekiki time` - 現在時刻を表示
• `@mekiki version` - バージョン情報
• `@mekiki uptime` - 稼働時間を表示
• `@mekiki info` - システム情報

*ツールコマンド*
• `@mekiki tasks` - 現在のタスク一覧
• `@mekiki obsidian` - Obsidian参照リンク
• `@mekiki search <query>` - Web検索（準備中）
• `@mekiki orchestra <task>` - 🎭 Orchestra議論依頼

_全角＠にも対応しています_"""
    
    elif cmd == 'ping':
        return f"🏓 Pong! ({datetime.now().strftime('%H:%M:%S')})"
    
    elif cmd == 'status':
        return """🤖 **Antigravity Status**
• 状態: 🟢 Online
• モード: MEKIKI連携中
• Slackリスナー: 稼働中
• コマンド対応: 全角/半角＠対応"""
    
    elif cmd == 'echo':
        text = ' '.join(args) if args else "(empty)"
        return f"📢 {text}"
    
    # === 情報コマンド ===
    elif cmd == 'time':
        now = datetime.now()
        return f"🕐 現在時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    elif cmd == 'version':
        return """📦 **MEKIKI Version Info**
• App: MEKIKI OCR v1.0
• Slack Listener: v2.0 (全角＠対応)
• Python: 3.11+
• Antigravity: Active"""
    
    elif cmd == 'uptime':
        elapsed = time.time() - _start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        return f"⏱️ 稼働時間: {hours}時間 {minutes}分 {seconds}秒"
    
    elif cmd == 'info':
        return """ℹ️ **MEKIKI System Info**
• Orchestra: GPT/Gemini/Grok/Slack連携
• Obsidian: Vault連携中
• Skills: MEKIKI Operations
• 機能: HybridOCR, Canvas同期, Slack双方向"""
    
    # === ツールコマンド ===
    elif cmd == 'tasks':
        return """📋 **現在のタスク**
• ✅ Slack双方向通信実装
• ✅ 全角＠対応修正
• ✅ コマンド拡張

_詳細は Obsidian の project_sanctuary.md 参照_"""
    
    elif cmd == 'obsidian':
        return """📚 **Obsidian References**
• `project_sanctuary.md` - 聖域定義書
• `orchestra_system.md` - エージェント役割分担
• `GPT52_Session_Bridge.md` - GPT戦略

_Vault/00_Runbook/ に格納_"""
    
    elif cmd == 'search':
        query = ' '.join(args) if args else None
        if query:
            return f"🔍 検索機能は準備中です: `{query}`"
        return "🔍 使い方: `@mekiki search <検索クエリ>`"
    
    elif cmd == 'orchestra':
        task_description = ' '.join(args) if args else None
        if not task_description:
            return """🎭 **Orchestra System**
使い方: `@mekiki orchestra <タスク>`

例:
• `@mekiki orchestra HybridOCRの最適化方法を検討`
• `@mekiki orchestra Slack連携の改善案を議論`

_GPT/Gemini/Grok/Obsidianが連携してタスクを処理_"""
        
        # Execute orchestra discussion
        try:
            from app.sdk.orchestration.orchestra import discuss
            # Run discussion asynchronously (simplified version)
            send_reply(token, channel_id, f"🎭 Orchestra議論開始: `{task_description}`\n_処理中..._")
            
            result = discuss(task_description)
            
            # Extract key information from result
            if isinstance(result, dict):
                score = result.get('score', 'N/A')
                summary = result.get('summary', result.get('gpt_strategy', 'No summary'))[:500]
                return f"""🎭 **Orchestra 完了**

**スコア**: {score}/10
**サマリー**:
{summary}

_詳細はログを確認_"""
            else:
                return f"🎭 Orchestra結果: {str(result)[:500]}"
                
        except ImportError:
            return "❌ Orchestra モジュールが見つかりません"
        except Exception as e:
            return f"❌ Orchestra エラー: {str(e)[:200]}"
    
    else:
        return f"❓ 不明なコマンド: `{cmd}`\n`@mekiki help` でコマンド一覧を確認"


def save_last_ts(ts: str):
    """Save last processed timestamp"""
    ts_file = Path.home() / ".gemini" / "antigravity" / "slack_last_ts.txt"
    ts_file.parent.mkdir(parents=True, exist_ok=True)
    ts_file.write_text(ts)


def load_last_ts() -> Optional[str]:
    """Load last processed timestamp"""
    ts_file = Path.home() / ".gemini" / "antigravity" / "slack_last_ts.txt"
    if ts_file.exists():
        return ts_file.read_text().strip()
    return None


def run_listener():
    """Main listener loop"""
    print("🎧 Slack Listener Starting...")
    
    token = load_token()
    if not token:
        print("❌ Failed to load token")
        return
    
    bot_user_id = get_bot_user_id(token)
    print(f"✅ Bot User ID: {bot_user_id}")
    
    channel_id = get_channel_id(token, CHANNEL_NAME)
    print(f"✅ Channel ID: {channel_id}")
    
    last_ts_str = load_last_ts()
    if not last_ts_str:
        # Set current time as baseline
        last_ts_str = str(time.time())
        save_last_ts(last_ts_str)
    
    last_ts = float(last_ts_str)
    print(f"📡 Listening for messages (since {last_ts_str})...")
    print("   Press Ctrl+C to stop\n")
    
    # Send startup message
    send_reply(token, channel_id, "🎧 Antigravity Listener Online! `@mekiki help` でコマンド確認")
    
    poll_count = 0
    try:
        while True:
            poll_count += 1
            messages = get_recent_messages(token, channel_id, oldest=str(last_ts), limit=10)
            
            if poll_count % 12 == 1:  # Log every minute (12 * 5s)
                print(f"🔄 Polling #{poll_count} - {len(messages)} messages")
            
            # Process new messages (oldest first)
            for msg in reversed(messages):
                msg_ts = msg.get('ts', '')
                msg_text = msg.get('text', '')
                msg_user = msg.get('user', '')
                
                # Skip bot's own messages
                if msg_user == bot_user_id:
                    continue
                
                # Skip already processed (compare as float)
                try:
                    msg_ts_float = float(msg_ts)
                except ValueError:
                    continue
                
                if msg_ts_float <= last_ts:
                    continue
                
                print(f"📨 New message: {msg_text[:50]}...")
                
                # Check if it's a command
                if is_command(msg_text):
                    cmd, args = parse_command(msg_text)
                    if cmd:
                        print(f"   Command: {cmd} {args}")
                        response = execute_command(cmd, args, token, channel_id)
                        send_reply(token, channel_id, response, thread_ts=msg_ts)
                
                # Update last timestamp
                last_ts = msg_ts_float
                save_last_ts(str(last_ts))
            
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n🛑 Listener stopped")
        send_reply(token, channel_id, "🛑 Antigravity Listener Offline")


if __name__ == "__main__":
    run_listener()
