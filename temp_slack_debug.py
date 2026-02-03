"""Check messages and respond to commands"""
import subprocess
import json
import urllib.request

result = subprocess.run(['wsl', 'cat', '/home/raiko/.clawdbot/clawdbot.json'], capture_output=True, text=True)
config = json.loads(result.stdout)
token = config['channels']['slack']['botToken']
channel_id = "C0AB1E24AJW"
bot_user_id = "U0ABUKG3WQG"

print("=== Recent messages ===")
req = urllib.request.Request(
    f'https://slack.com/api/conversations.history?channel={channel_id}&limit=10',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())
    if data.get('messages'):
        for msg in data['messages']:
            user = msg.get('user', 'bot')
            text = msg.get('text', '')[:60]
            ts = msg.get('ts', '')
            is_bot = "(BOT)" if user == bot_user_id else "(USER)"
            is_cmd = "[CMD]" if 'mekiki' in text.lower() else ""
            print(f"  {is_bot} {is_cmd} {text}")
            
            if user != bot_user_id and 'mekiki' in text.lower() and 'ping' in text.lower():
                print(f"\n>>> Responding to ping...")
                payload = json.dumps({
                    'channel': channel_id,
                    'text': '🏓 Pong! アプリ統合テスト成功！',
                    'thread_ts': ts
                }).encode()
                req2 = urllib.request.Request(
                    'https://slack.com/api/chat.postMessage',
                    data=payload,
                    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    r = json.loads(resp2.read().decode())
                    print(f"Reply sent: {r.get('ok')}")
                break
