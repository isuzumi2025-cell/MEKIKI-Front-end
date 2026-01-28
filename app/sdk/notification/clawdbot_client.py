"""
SlackNotificationClient - Direct Slack API client for MEKIKI notifications

Sends Slack notifications via direct API calls.
Configuration is read from ~/.clawdbot/clawdbot.json for compatibility.

Usage:
    client = SlackNotificationClient()
    client.send_message("#context", "Hello from MEKIKI!")
"""
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SlackNotificationClient:
    """Direct Slack API client for notifications."""
    
    # Default config path (WSL path)
    DEFAULT_CONFIG_PATH = "/home/raiko/.clawdbot/clawdbot.json"
    DEFAULT_CHANNEL = "context"
    SLACK_API_BASE = "https://slack.com/api"
    
    def __init__(self, channel: str = None):
        """
        Initialize SlackNotificationClient.
        
        Args:
            channel: Default Slack channel for notifications
        """
        self.default_channel = channel or self.DEFAULT_CHANNEL
        self._bot_token: Optional[str] = None
        self._available: Optional[bool] = None
    
    def _load_token(self) -> Optional[str]:
        """Load bot token from Clawdbot config file."""
        if self._bot_token:
            return self._bot_token
        
        try:
            result = subprocess.run(
                ["wsl", "cat", self.DEFAULT_CONFIG_PATH],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                config = json.loads(result.stdout)
                self._bot_token = config.get("channels", {}).get("slack", {}).get("botToken")
                return self._bot_token
        except Exception as e:
            logger.warning(f"Failed to load Slack token: {e}")
        
        return None
    
    def is_available(self) -> bool:
        """Check if Slack API is available with valid token."""
        if self._available is not None:
            return self._available
        
        token = self._load_token()
        if not token:
            self._available = False
            return False
        
        try:
            req = urllib.request.Request(
                f"{self.SLACK_API_BASE}/auth.test",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                self._available = data.get("ok", False)
        except Exception as e:
            logger.warning(f"Slack API not available: {e}")
            self._available = False
        
        return self._available
    
    def send_message(self, channel: str = None, text: str = "", thread_ts: str = None) -> bool:
        """
        Send a message to a Slack channel.
        
        Args:
            channel: Slack channel name (e.g., "context" or "#context")
            text: Message text to send
            thread_ts: Optional thread timestamp for replies
            
        Returns:
            True if message was sent successfully
        """
        token = self._load_token()
        if not token:
            logger.warning("No Slack token available, skipping notification")
            return False
        
        target_channel = channel or self.default_channel
        # Remove leading # if present
        if target_channel.startswith("#"):
            target_channel = target_channel[1:]
        
        try:
            payload = {
                "channel": target_channel,
                "text": text
            }
            if thread_ts:
                payload["thread_ts"] = thread_ts
            
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.SLACK_API_BASE}/chat.postMessage",
                data=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                if result.get("ok"):
                    logger.info(f"Message sent to #{target_channel}")
                    return True
                else:
                    error = result.get("error", "unknown")
                    logger.error(f"Failed to send message: {error}")
                    return False
                    
        except urllib.error.URLError as e:
            logger.error(f"Network error sending message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def upload_file(self, channel: str, filepath: str, comment: str = None) -> bool:
        """
        Upload a file to a Slack channel.
        
        Args:
            channel: Slack channel name
            filepath: Path to the file to upload
            comment: Optional initial comment
            
        Returns:
            True if file was uploaded successfully
        """
        token = self._load_token()
        if not token:
            logger.warning("No Slack token available, skipping upload")
            return False
        
        target_channel = channel or self.default_channel
        if target_channel.startswith("#"):
            target_channel = target_channel[1:]
        
        try:
            # Read file content
            with open(filepath, "rb") as f:
                file_content = f.read()
            
            filename = Path(filepath).name
            
            # Use multipart form data for file upload
            import urllib.parse
            
            # For simplicity, use subprocess to call curl for file uploads
            cmd = [
                "wsl", "curl", "-s",
                "-F", f"file=@{filepath}",
                "-F", f"channels={target_channel}",
                "-H", f"Authorization: Bearer {token}"
            ]
            if comment:
                cmd.extend(["-F", f"initial_comment={comment}"])
            cmd.append("https://slack.com/api/files.upload")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                response = json.loads(result.stdout)
                if response.get("ok"):
                    logger.info(f"File uploaded to #{target_channel}")
                    return True
                else:
                    logger.error(f"Upload failed: {response.get('error')}")
                    return False
            return False
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False


# Backward compatibility alias
ClawdbotClient = SlackNotificationClient


# Singleton instance
_client: Optional[SlackNotificationClient] = None


def get_clawdbot_client() -> SlackNotificationClient:
    """Get the singleton SlackNotificationClient instance."""
    global _client
    if _client is None:
        _client = SlackNotificationClient()
    return _client


def notify_slack(message: str, channel: str = None) -> bool:
    """
    Send a notification to Slack.
    
    Args:
        message: Message text to send
        channel: Optional channel override (default: #context)
        
    Returns:
        True if message was sent successfully
    """
    client = get_clawdbot_client()
    return client.send_message(channel=channel, text=message)

