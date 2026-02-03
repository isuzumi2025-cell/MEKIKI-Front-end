"""
Notification SDK - Slack integration via Clawdbot
"""
from .clawdbot_client import (
    ClawdbotClient,
    get_clawdbot_client,
    notify_slack,
)

__all__ = [
    "ClawdbotClient",
    "get_clawdbot_client",
    "notify_slack",
]
