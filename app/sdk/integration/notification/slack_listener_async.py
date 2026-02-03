"""
Slack Listener (Asyncio Version)
非同期処理でGUIとの統合を改善

Usage:
    # main.pyから呼び出し
    from app.sdk.notification.slack_listener_async import start_async_listener
    start_async_listener()
"""
import asyncio
import subprocess
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import threading

# Config
POLL_INTERVAL = 5  # seconds
CHANNEL_NAME = "context"
CHANNEL_ID = "C0AB1E24AJW"
BOT_USER_ID = "U0ABUKG3WQG"


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


def send_message(token: str, channel_id: str, text: str, thread_ts: str = None) -> bool:
    """Send a message to Slack"""
    try:
        payload = {"channel": channel_id, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            'https://slack.com/api/chat.postMessage',
            data=data,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result.get('ok', False)
    except Exception as e:
        print(f"Send error: {e}")
    return False


def get_messages(token: str, channel_id: str, oldest: str = None) -> List[Dict]:
    """Get recent messages from channel"""
    try:
        url = f'https://slack.com/api/conversations.history?channel={channel_id}&limit=10'
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
    except Exception as e:
        print(f"Get messages error: {e}")
    return []


def is_command(text: str) -> bool:
    """Check if message is a command"""
    lower = text.lower()
    prefixes = ['@mekiki', '＠mekiki', '/mekiki', 'mekiki']
    return any(lower.startswith(p) for p in prefixes)


def parse_command(text: str) -> tuple:
    """Parse command from message"""
    for prefix in ['@mekiki', '＠mekiki', '/mekiki', 'mekiki']:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break
    parts = text.split()
    if parts:
        return parts[0].lower(), parts[1:]
    return None, []


def execute_command(cmd: str, args: List[str]) -> str:
    """Execute command and return response"""
    if cmd == 'help':
        return """🤖 **MEKIKI Commands**
• help, ping, status, echo
• time, version, uptime, info
• tasks, obsidian, orchestra"""
    elif cmd == 'ping':
        return f"🏓 Pong! ({datetime.now().strftime('%H:%M:%S')})"
    elif cmd == 'status':
        return "🤖 Status: Online (asyncio mode)"
    elif cmd == 'time':
        return f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    elif cmd == 'echo':
        return ' '.join(args) if args else "(empty)"
    else:
        return f"❓ Unknown: {cmd}"


class AsyncSlackListener:
    """Asyncio-based Slack listener"""
    
    def __init__(self):
        self.token = None
        self.running = False
        self.last_ts = 0.0
        self._thread = None
        self._loop = None
    
    def start(self):
        """Start listener in background thread with its own event loop"""
        if self.running:
            return
        
        self.token = load_token()
        if not self.token:
            print("❌ Failed to load Slack token")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run_in_thread, daemon=True)
        self._thread.start()
        print("🎧 Async Slack Listener started")
    
    def _run_in_thread(self):
        """Run asyncio event loop in thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._listen())
        except Exception as e:
            print(f"Listener error: {e}")
        finally:
            self._loop.close()
    
    async def _listen(self):
        """Main async listener loop"""
        self.last_ts = float(datetime.now().timestamp())
        
        # Send startup message
        send_message(self.token, CHANNEL_ID, "🎧 Antigravity Listener Online (async)!")
        
        poll_count = 0
        while self.running:
            try:
                poll_count += 1
                # Use executor to run blocking HTTP calls
                messages = await self._loop.run_in_executor(
                    None, 
                    lambda: get_messages(self.token, CHANNEL_ID, str(self.last_ts))
                )
                
                if poll_count % 12 == 1:
                    print(f"🔄 Poll #{poll_count} - {len(messages)} msgs")
                
                # Process messages (oldest first)
                for msg in reversed(messages):
                    msg_ts = msg.get('ts', '')
                    msg_text = msg.get('text', '')
                    msg_user = msg.get('user', '')
                    
                    # Skip bot's own messages
                    if msg_user == BOT_USER_ID:
                        continue
                    
                    try:
                        msg_ts_float = float(msg_ts)
                    except ValueError:
                        continue
                    
                    if msg_ts_float <= self.last_ts:
                        continue
                    
                    print(f"📨 New: {msg_text[:40]}...")
                    
                    if is_command(msg_text):
                        cmd, args = parse_command(msg_text)
                        if cmd:
                            print(f"   Cmd: {cmd}")
                            response = execute_command(cmd, args)
                            await self._loop.run_in_executor(
                                None,
                                lambda: send_message(self.token, CHANNEL_ID, response, msg_ts)
                            )
                    
                    self.last_ts = msg_ts_float
                
            except Exception as e:
                print(f"Poll error: {e}")
            
            await asyncio.sleep(POLL_INTERVAL)
    
    def stop(self):
        """Stop the listener"""
        self.running = False
        if self.token:
            send_message(self.token, CHANNEL_ID, "🛑 Listener Offline")


# Global instance
_listener = None


def start_async_listener():
    """Start the global async listener (call from main.py)"""
    global _listener
    if _listener is None:
        _listener = AsyncSlackListener()
    _listener.start()
    return _listener


def stop_async_listener():
    """Stop the global async listener"""
    global _listener
    if _listener:
        _listener.stop()
        _listener = None


if __name__ == "__main__":
    listener = AsyncSlackListener()
    listener.start()
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
