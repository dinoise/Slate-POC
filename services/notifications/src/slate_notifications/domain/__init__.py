"""Domain layer — channel definitions and internal event types."""

from .channel_config import CHANNEL_CONFIGS, ChannelConfig, ChannelTarget
from .channels import Channel
from .events import NotificationPayload

__all__ = ["CHANNEL_CONFIGS", "Channel", "ChannelConfig", "ChannelTarget", "NotificationPayload"]
