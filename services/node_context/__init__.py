"""
Node Execution Context System
============================
Reference: ../n8n-master/packages/core/src/execution-engine/node-execution-context/

Provides context for node execution with:
- Parameter access with expression evaluation
- Credential management
- HTTP requests with authentication
- Binary data handling
"""

from .base import BaseNodeContext
from .execute import ExecuteContext
from .webhook import WebhookContext
from .trigger import TriggerContext
from .credentials import CredentialsManager

__all__ = [
    'BaseNodeContext',
    'ExecuteContext', 
    'WebhookContext',
    'TriggerContext',
    'CredentialsManager',
]
