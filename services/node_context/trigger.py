"""
Trigger Context
=============
Reference: ../n8n-master/packages/core/src/execution-engine/node-execution-context/supply-data-context.ts

Context for trigger nodes (polling, scheduled, webhook triggers).
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from .base import BaseNodeContext

logger = logging.getLogger(__name__)


class TriggerContext(BaseNodeContext):
    """
    Context for trigger/scheduled nodes.
    
    Provides:
    - Data emission
    - Error emission
    - Trigger control (stop, etc.)
    """

    def __init__(
        self,
        node_data: Dict[str, Any],
        execution_data: Dict[str, Any],
        workflow_id: int,
        workflow_settings: Dict[str, Any] = None
    ):
        """
        Initialize trigger context.
        
        Args:
            node_data: Node definition
            execution_data: Execution data
            workflow_id: Workflow ID
            workflow_settings: Workflow settings
        """
        super().__init__(node_data, execution_data, workflow_id, workflow_settings)
        self._data_items: List[Dict[str, Any]] = []
        self._response_data: Dict[str, Any] = {}
    
    def emit(self, data: Any) -> None:
        """
        Emit data to workflow.
        
        Args:
            data: Data to emit (will be wrapped in {json: data}
        """
        if isinstance(data, list):
            items = [{'json': item} for item in data]
        elif isinstance(data, dict):
            items = [{'json': data}]
        else:
            items = [{'json': {'data': data}}]
        
        self._data_items.extend(items)
    
    def emitError(self, error: Exception) -> None:
        """
        Emit an error.
        
        Args:
            error: Exception to emit
        """
        self._data_items.append({
            'json': {'error': str(error)},
            'error': True
        })
    
    def emitBatch(self, items: List[Any]) -> None:
        """
        Emit a batch of items.
        
        Args:
            items: List of items to emit
        """
        for item in items:
            self.emit(item)
    
    def getDataItems(self) -> List[Dict[str, Any]]:
        """
        Get all emitted data items.
        
        Returns:
            List of emitted items
        """
        return self._data_items.copy()
    
    def hasEmittedData(self) -> bool:
        """
        Check if any data has been emitted.
        
        Returns:
            True if data has been emitted
        """
        return len(self._data_items) > 0
    
    # ─── Response Data (for webhook/trigger) ───
    
    def sendResponse(
        self,
        response_code: int = 200,
        response_body: Any = None,
        response_headers: Dict[str, str] = None
    ) -> None:
        """
        Send HTTP response for webhook triggers.
        
        Args:
            response_code: HTTP status code
            response_body: Response body
            response_headers: Response headers
        """
        self._response_data = {
            'statusCode': response_code,
            'body': response_body,
            'headers': response_headers or {}
        }
    
    def getResponseData(self) -> Dict[str, Any]:
        """
        Get configured response data.
        
        Returns:
            Response configuration
        """
        return self._response_data.copy()
    
    # ─── Time-based triggers ───
    
    def getDateTime(self) -> datetime:
        """
        Get current datetime for trigger.
        
        Returns:
            Current datetime
        """
        return datetime.utcnow()
    
    # ─── Required abstract methods ───
    
    def getInputData(self, input_index: int = 0, item_index: int = 0) -> Any:
        """Get input data (triggers typically don't have input)"""
        return None
    
    def prepareOutputData(self, data: Any) -> List[Dict[str, Any]]:
        """Prepare output data"""
        return self._data_items.copy() if self._data_items else []


class PollingTriggerContext(TriggerContext):
    """
    Context for polling-based triggers.
    
    Handles:
    - Last poll timestamp tracking
    - Poll interval management
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_poll_time: Optional[datetime] = None
    
    def getLastPollTime(self) -> Optional[datetime]:
        """
        Get timestamp of last poll.
        
        Returns:
            Last poll datetime or None
        """
        return self._last_poll_time
    
    def setLastPollTime(self, poll_time: datetime = None) -> None:
        """
        Set timestamp of current poll.
        
        Args:
            poll_time: Poll time (defaults to now)
        """
        self._last_poll_time = poll_time or datetime.utcnow()
    
    def getItemsSinceLastPoll(self) -> List[Dict[str, Any]]:
        """
        Get items created/modified since last poll.
        
        Returns:
            List of new/modified items
        """
        # Override in subclass to filter by timestamp
        return self._data_items.copy()


class ScheduledTriggerContext(TriggerContext):
    """
    Context for scheduled triggers (cron-based).
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scheduled_time: Optional[datetime] = None
    
    def setScheduledTime(self, scheduled_time: datetime) -> None:
        """
        Set the scheduled execution time.
        
        Args:
            scheduled_time: Scheduled time
        """
        self._scheduled_time = scheduled_time
    
    def getScheduledTime(self) -> Optional[datetime]:
        """
        Get the scheduled execution time.
        
        Returns:
            Scheduled time
        """
        return self._scheduled_time
