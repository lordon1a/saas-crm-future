"""
Webhook Context
=============
Reference: ../n8n-master/packages/core/src/execution-engine/node-execution-context/webhook-context.ts

Context for webhook trigger nodes.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseNodeContext

logger = logging.getLogger(__name__)


class WebhookContext(BaseNodeContext):
    """
    Context for webhook trigger nodes.
    
    Provides:
    - HTTP request access (headers, body, query params)
    - Webhook response methods
    """

    def __init__(
        self,
        node_data: Dict[str, Any],
        execution_data: Dict[str, Any],
        workflow_id: int,
        workflow_settings: Dict[str, Any] = None,
        request: Dict[str, Any] = None
    ):
        """
        Initialize webhook context.
        
        Args:
            node_data: Node definition
            execution_data: Execution data
            workflow_id: Workflow ID
            workflow_settings: Workflow settings
            request: HTTP request dict {headers, body, query, params}
        """
        super().__init__(node_data, execution_data, workflow_id, workflow_settings)
        self._request = request or {}
    
    def getRequestObject(self) -> Dict[str, Any]:
        """
        Get the raw HTTP request object.
        
        Returns:
            Request dict with headers, body, query, etc.
        """
        return self._request.copy()
    
    def getHeader(self, name: str, default: str = None) -> Optional[str]:
        """
        Get a request header.
        
        Args:
            name: Header name (case-insensitive)
            default: Default value if not found
            
        Returns:
            Header value
        """
        headers = self._request.get('headers', {})
        # Case-insensitive lookup
        name_lower = name.lower()
        for key, value in headers.items():
            if key.lower() == name_lower:
                return value
        return default
    
    def getBody(self, default: Any = None) -> Any:
        """
        Get request body.
        
        Args:
            default: Default if no body
            
        Returns:
            Parsed body (JSON, form data, or raw)
        """
        return self._request.get('body', default)
    
    def getQueryParam(self, name: str, default: str = None) -> Optional[str]:
        """
        Get a query parameter.
        
        Args:
            name: Parameter name
            default: Default if not found
            
        Returns:
            Parameter value
        """
        query = self._request.get('query', {})
        return query.get(name, default)
    
    def getQueryData(self) -> Dict[str, Any]:
        """
        Get all query parameters.
        
        Returns:
            Query parameters dict
        """
        return self._request.get('query', {}).copy()
    
    def getFormData(self) -> Dict[str, Any]:
        """
        Get form data from body.
        
        Returns:
            Form data dict
        """
        return self._request.get('form', {})
    
    def getMethod(self) -> str:
        """
        Get HTTP method.
        
        Returns:
            HTTP method (GET, POST, etc.)
        """
        return self._request.get('method', 'GET').upper()
    
    def getUrl(self) -> str:
        """
        Get request URL.
        
        Returns:
            Full URL
        """
        return self._request.get('url', '')
    
    def respond(
        self,
        response_code: int = 200,
        response_body: Any = None,
        response_headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Prepare webhook response.
        
        Args:
            response_code: HTTP status code
            response_body: Response body
            response_headers: Response headers
            
        Returns:
            Response dict for framework
        """
        response = {
            'statusCode': response_code,
            'body': response_body,
            'headers': response_headers or {}
        }
        
        # Store for later use
        self._execution_data['webhookResponse'] = response
        
        return response
    
    def respondWithError(
        self,
        message: str,
        response_code: int = 400
    ) -> Dict[str, Any]:
        """
        Prepare error response.
        
        Args:
            message: Error message
            response_code: HTTP status code
            
        Returns:
            Error response dict
        """
        return self.respond(
            response_code=response_code,
            response_body={'error': message}
        )
    
    # Required abstract methods
    
    def getInputData(self, input_index: int = 0, item_index: int = 0) -> Any:
        """Get input data (not typically used for webhooks)"""
        return {'json': self.getBody({})}
    
    def prepareOutputData(self, data: Any) -> List[Dict[str, Any]]:
        """Prepare output data"""
        if isinstance(data, list):
            return [{'json': item} for item in data]
        elif isinstance(data, dict):
            return [{'json': data}]
        else:
            return [{'json': {'result': data}}]
