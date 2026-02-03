"""
UnifiedAgentClient - Switchable backend for Clawdbot and OpenClaw

Allows switching between Clawdbot (stable Slack notifications) and
OpenClaw (autonomous task spawning) at runtime.

Usage:
    from app.sdk.integration.notification.agent_client import (
        UnifiedAgentClient, AgentBackend
    )
    
    client = UnifiedAgentClient()  # Defaults to Clawdbot
    client.notify("Hello from MEKIKI!")
    
    client.switch(AgentBackend.OPENCLAW)  # Switch to OpenClaw
    client.spawn_task("Debug HybridOCR issue")  # OpenClaw-only feature
"""
import json
import subprocess
import urllib.request
import urllib.error
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


class AgentBackend(Enum):
    """Available agent backends."""
    CLAWDBOT = "clawdbot"
    OPENCLAW = "openclaw"


class UnifiedAgentClient:
    """
    Unified client for Clawdbot and OpenClaw backends.
    
    Supports switching between backends at runtime while maintaining
    a consistent API for common operations.
    """
    
    # Configuration paths (WSL paths)
    CLAWDBOT_CONFIG = "/home/raiko/.clawdbot/clawdbot.json"
    OPENCLAW_CONFIG = "/home/raiko/.openclaw/openclaw.json"
    
    # Default ports
    PORTS = {
        AgentBackend.CLAWDBOT: 8080,
        AgentBackend.OPENCLAW: 8081,
    }
    
    # Slack API
    SLACK_API_BASE = "https://slack.com/api"
    DEFAULT_CHANNEL = "context"
    
    def __init__(self, backend: AgentBackend = None):
        """
        Initialize UnifiedAgentClient.
        
        Args:
            backend: Initial backend to use. Defaults to environment
                     variable AGENT_BACKEND or CLAWDBOT.
        """
        if backend is None:
            env_backend = os.getenv("AGENT_BACKEND", "clawdbot").lower()
            backend = AgentBackend(env_backend)
        
        self.backend = backend
        self.port = self.PORTS[backend]
        self.base_url = f"http://localhost:{self.port}"
        self._bot_token: Optional[str] = None
        self._available: Dict[AgentBackend, Optional[bool]] = {
            AgentBackend.CLAWDBOT: None,
            AgentBackend.OPENCLAW: None,
        }
        
        logger.info(f"UnifiedAgentClient initialized with {backend.value}")
    
    def switch(self, backend: AgentBackend) -> bool:
        """
        Switch to a different backend.
        
        Args:
            backend: The backend to switch to
            
        Returns:
            True if switch was successful and backend is available
        """
        old_backend = self.backend
        self.backend = backend
        self.port = self.PORTS[backend]
        self.base_url = f"http://localhost:{self.port}"
        
        available = self.is_available()
        if available:
            logger.info(f"🔄 Switched from {old_backend.value} to {backend.value}")
        else:
            logger.warning(f"⚠️ Switched to {backend.value} but it may not be available")
        
        return available
    
    @property
    def current_backend(self) -> str:
        """Get current backend name."""
        return self.backend.value
    
    def _load_token(self, force_reload: bool = False) -> Optional[str]:
        """Load bot token from config file."""
        if self._bot_token and not force_reload:
            return self._bot_token
        
        config_path = (
            self.CLAWDBOT_CONFIG if self.backend == AgentBackend.CLAWDBOT
            else self.OPENCLAW_CONFIG
        )
        
        try:
            result = subprocess.run(
                ["wsl", "cat", config_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                config = json.loads(result.stdout)
                self._bot_token = (
                    config.get("channels", {})
                    .get("slack", {})
                    .get("botToken")
                )
                return self._bot_token
        except Exception as e:
            logger.warning(f"Failed to load token from {config_path}: {e}")
        
        return None
    
    def is_available(self, backend: AgentBackend = None) -> bool:
        """
        Check if the specified (or current) backend is available.
        
        Args:
            backend: Backend to check. Defaults to current backend.
            
        Returns:
            True if backend is available
        """
        target = backend or self.backend
        
        if self._available[target] is not None:
            return self._available[target]
        
        if target == AgentBackend.CLAWDBOT:
            # Check Clawdbot via Slack token validation
            token = self._load_token()
            if not token:
                self._available[target] = False
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
                    self._available[target] = data.get("ok", False)
            except Exception as e:
                logger.warning(f"Clawdbot check failed: {e}")
                self._available[target] = False
        
        elif target == AgentBackend.OPENCLAW:
            # Check OpenClaw via its API endpoint
            try:
                # OpenClaw is installed via nvm/npm, so we need to source nvm environment
                cmd = [
                    "wsl", "bash", "-c", 
                    "source ~/.nvm/nvm.sh && openclaw --version"
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self._available[target] = result.returncode == 0
            except Exception as e:
                logger.warning(f"OpenClaw check failed: {e}")
                self._available[target] = False
        
        return self._available[target]
    
    def notify(self, message: str, channel: str = None) -> bool:
        """
        Send a notification (both backends support this).
        
        Args:
            message: Message text to send
            channel: Slack channel (default: context)
            
        Returns:
            True if sent successfully
        """
        token = self._load_token()
        if not token:
            logger.warning(f"No token available for {self.backend.value}")
            return False
        
        target_channel = channel or self.DEFAULT_CHANNEL
        if target_channel.startswith("#"):
            target_channel = target_channel[1:]
        
        try:
            payload = {
                "channel": target_channel,
                "text": message
            }
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
                    logger.info(f"[{self.backend.value}] Message sent to #{target_channel}")
                    return True
                else:
                    logger.error(f"Failed to send: {result.get('error')}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def spawn_task(
        self,
        task: str,
        allow_spawn: bool = False,
        max_api_calls: int = 10,
        timeout: int = 60,
        priority: str = "low"
    ) -> Optional[Dict[str, Any]]:
        """
        Spawn an autonomous task (OpenClaw only).
        
        Args:
            task: Task description to execute
            allow_spawn: Allow child agent spawning (default: False for safety)
            max_api_calls: Maximum API calls for this task
            timeout: Task timeout in seconds
            priority: Task priority ("low", "normal", "high")
            
        Returns:
            Task result dict or None if failed/not available
        """
        if self.backend != AgentBackend.OPENCLAW:
            logger.warning("spawn_task requires OpenClaw backend. "
                          f"Current: {self.backend.value}")
            return None
        
        if not self.is_available(AgentBackend.OPENCLAW):
            logger.error("OpenClaw is not available")
            return None
        
        try:
            # Call OpenClaw CLI to spawn task
            # Construct the openclaw command string to run inside bash
            openclaw_cmd = [
                "openclaw", "task", "spawn",
                "--task", f"'{task}'",  # Quote the task string
                "--max-calls", str(max_api_calls),
                "--timeout", str(timeout),
                "--priority", priority,
            ]
            if not allow_spawn:
                openclaw_cmd.append("--no-spawn")
            
            # Join into a single string for bash -c
            full_cmd_str = "source ~/.nvm/nvm.sh && " + " ".join(openclaw_cmd)
            
            cmd = ["wsl", "bash", "-c", full_cmd_str]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 10
            )
            
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    return {"status": "completed", "output": result.stdout}
            else:
                logger.error(f"Task spawn failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"Task timed out after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error spawning task: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of both backends.
        
        Returns:
            Dict with availability status for each backend
        """
        return {
            "current": self.backend.value,
            "port": self.port,
            "backends": {
                "clawdbot": {
                    "available": self.is_available(AgentBackend.CLAWDBOT),
                    "port": self.PORTS[AgentBackend.CLAWDBOT],
                },
                "openclaw": {
                    "available": self.is_available(AgentBackend.OPENCLAW),
                    "port": self.PORTS[AgentBackend.OPENCLAW],
                }
            }
        }


# Singleton instance
_unified_client: Optional[UnifiedAgentClient] = None


def get_agent_client() -> UnifiedAgentClient:
    """Get the singleton UnifiedAgentClient instance."""
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedAgentClient()
    return _unified_client


def notify(message: str, channel: str = None) -> bool:
    """
    Send a notification using the current backend.
    
    Args:
        message: Message to send
        channel: Optional channel override
        
    Returns:
        True if sent successfully
    """
    return get_agent_client().notify(message, channel)


def switch_backend(backend: str) -> bool:
    """
    Switch to a different backend.
    
    Args:
        backend: "clawdbot" or "openclaw"
        
    Returns:
        True if switch successful
    """
    return get_agent_client().switch(AgentBackend(backend))
