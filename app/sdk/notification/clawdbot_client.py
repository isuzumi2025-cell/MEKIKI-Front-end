"""
ClawdbotClient - Python wrapper for Clawdbot CLI

Enables MEKIKI to send Slack notifications via the configured Clawdbot instance.
Requires Clawdbot CLI to be installed and configured (see walkthrough.md).

Usage:
    client = ClawdbotClient()
    await client.send_message("#general", "Hello from MEKIKI!")
"""
import subprocess
import shutil
import asyncio
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ClawdbotClient:
    """Wrapper for Clawdbot CLI commands."""
    
    # Default paths for Clawdbot binary (WSL environment)
    DEFAULT_NODE_PATH = "/home/raiko/.nvm/versions/node/v22.12.0/bin/node"
    DEFAULT_CLAWDBOT_PATH = "/home/raiko/.nvm/versions/node/v22.12.0/bin/clawdbot"
    DEFAULT_PROFILE = "clean"
    
    def __init__(self, profile: str = None):
        """
        Initialize ClawdbotClient.
        
        Args:
            profile: Clawdbot profile to use (default: "clean")
        """
        self.profile = profile or self.DEFAULT_PROFILE
        self._clawdbot_available: Optional[bool] = None
    
    def _build_command(self, *args) -> list:
        """Build the full command with WSL prefix and profile flag."""
        # Use WSL to run the command in Linux environment
        cmd = [
            "wsl",
            self.DEFAULT_NODE_PATH,
            self.DEFAULT_CLAWDBOT_PATH,
            "--profile", self.profile,
            *args
        ]
        return cmd
    
    def is_available(self) -> bool:
        """Check if Clawdbot is available and configured."""
        if self._clawdbot_available is not None:
            return self._clawdbot_available
        
        try:
            result = subprocess.run(
                self._build_command("--version"),
                capture_output=True,
                text=True,
                timeout=10
            )
            self._clawdbot_available = result.returncode == 0
        except Exception as e:
            logger.warning(f"Clawdbot not available: {e}")
            self._clawdbot_available = False
        
        return self._clawdbot_available
    
    def send_message(self, channel: str, text: str, thread_ts: str = None) -> bool:
        """
        Send a message to a Slack channel.
        
        Args:
            channel: Slack channel name or ID (e.g., "#general" or "C01234567")
            text: Message text to send
            thread_ts: Optional thread timestamp for replies
            
        Returns:
            True if message was sent successfully
        """
        if not self.is_available():
            logger.warning("Clawdbot not available, skipping notification")
            return False
        
        try:
            cmd = self._build_command(
                "message", "send",
                "--target", f"slack:{channel}",
                "--message", text
            )
            
            if thread_ts:
                cmd.extend(["--thread", thread_ts])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Message sent to {channel}")
                return True
            else:
                logger.error(f"Failed to send message: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Clawdbot command timed out")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def send_message_async(self, channel: str, text: str, thread_ts: str = None):
        """
        Send a message asynchronously (non-blocking).
        
        Args:
            channel: Slack channel name or ID
            text: Message text to send
            thread_ts: Optional thread timestamp
        """
        import threading
        thread = threading.Thread(
            target=self.send_message,
            args=(channel, text, thread_ts),
            daemon=True
        )
        thread.start()
    
    def upload_file(self, channel: str, file_path: str, comment: str = None) -> bool:
        """
        Upload a file to a Slack channel.
        
        Args:
            channel: Slack channel name or ID
            file_path: Path to the file to upload
            comment: Optional comment for the file
            
        Returns:
            True if file was uploaded successfully
        """
        if not self.is_available():
            logger.warning("Clawdbot not available, skipping file upload")
            return False
        
        # Convert Windows path to WSL path if needed
        file_path_obj = Path(file_path)
        if file_path_obj.drive:
            # Convert C:\path\to\file to /mnt/c/path/to/file
            wsl_path = f"/mnt/{file_path_obj.drive[0].lower()}{file_path_obj.as_posix()[2:]}"
        else:
            wsl_path = str(file_path)
        
        try:
            cmd = self._build_command(
                "file", "upload",
                "--target", f"slack:{channel}",
                "--file", wsl_path
            )
            
            if comment:
                cmd.extend(["--comment", comment])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"File uploaded to {channel}: {file_path}")
                return True
            else:
                logger.error(f"Failed to upload file: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Clawdbot file upload timed out")
            return False
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False


# Singleton instance for easy access
_client: Optional[ClawdbotClient] = None


def get_clawdbot_client() -> ClawdbotClient:
    """Get the singleton ClawdbotClient instance."""
    global _client
    if _client is None:
        _client = ClawdbotClient()
    return _client


def notify_slack(channel: str, text: str, blocking: bool = False) -> bool:
    """
    Convenience function to send a Slack notification.
    
    Args:
        channel: Slack channel name or ID
        text: Message text
        blocking: If True, wait for message to be sent. If False, send asynchronously.
        
    Returns:
        True if message was queued/sent successfully
    """
    client = get_clawdbot_client()
    if blocking:
        return client.send_message(channel, text)
    else:
        client.send_message_async(channel, text)
        return True
