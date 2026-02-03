"""Quick ping responder v2"""
import subprocess, json, urllib.request

result = subprocess.run(['wsl', 'cat', '/home/raiko/.clawdbot/clawdbot.json'], capture_output=True, text=True)
config = json.loads(result.stdout)
token = config['channels']['slack']['botToken']
channel_id = "C0AB1E24AJW"
bot_user_id = "U0ABUKG3WQG"

# Get recent messages
req = urllib.request.Request(
    f'https://slack.com/api/conversations.history?channel={channel_id}&limit=10',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())
    for msg in data.get('messages', []):
        text = msg.get('text', '')
        ts = msg.get('ts', '')
        user = msg.get('user', '')
        
        # Skip bot messages
        if user == bot_user_id:
            continue
            
        # Check for mekiki command
        lower = text.lower()
        if 'mekiki' in lower and user != bot_user_id:
            print(f"Found: {text[:50]}")
            
            # Determine response
            if 'help' in lower:
                resp_text = """🤖 **MEKIKI Commands v2.0**
• help, ping, status, echo
• time, version, uptime, info  
• tasks, obsidian, search, orchestra 🆕

`@mekiki orchestra <タスク>` で議論開始！"""
            elif 'ping' in lower:
                from datetime import datetime
                resp_text = f"🏓 Pong! ({datetime.now().strftime('%H:%M:%S')})"
            else:
                resp_text = "🤖 コマンドを受信しました！"
            
            # Send reply
            payload = json.dumps({'channel': channel_id, 'text': resp_text, 'thread_ts': ts}).encode()
            req2 = urllib.request.Request('https://slack.com/api/chat.postMessage', data=payload,
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
            with urllib.request.urlopen(req2, timeout=10) as r:
                print(f"Sent: {json.loads(r.read().decode()).get('ok')}")
            break
