"""
Execute Context
==============
Reference: ../n8n-master/packages/core/src/execution-engine/node-execution-context/execute-context.ts

Context for regular node execution.
Provides HTTP requests, binary data handling, and helper functions.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
import requests
from urllib.parse import urljoin

from .base import BaseNodeContext

logger = logging.getLogger(__name__)


class ExecuteContext(BaseNodeContext):
    """
    Context for executing regular action nodes.
    
    Provides:
    - HTTP request with authentication
    - Binary data handling
    - Input/output data management
    """
    
    def __init__(
        self,
        node_data: Dict[str, Any],
        execution_data: Dict[str, Any],
        workflow_id: int,
        workflow_settings: Dict[str, Any] = None,
        input_index: int = 0
    ):
        """
        Initialize execute context.
        
        Args:
            node_data: Node definition
            execution_data: Execution data
            workflow_id: Workflow ID
            workflow_settings: Workflow settings
            input_index: Which input to use (for multiple inputs)
        """
        super().__init__(node_data, execution_data, workflow_id, workflow_settings)
        self._input_index = input_index
    
    # ─── HTTP Requests ───
    
    def httpRequest(self, options: Dict[str, Any]) -> Any:
        """
        Make HTTP request with automatic authentication.
        
        Args:
            options: Request options
                - method: HTTP method (GET, POST, etc.)
                - url: Request URL
                - headers: Request headers
                - body: Request body
                - timeout: Timeout in seconds
                - credentialType: Type of credential to use
                
        Returns:
            Response data
        """
        method = options.get('method', 'GET').upper()
        url = options.get('url', '')
        headers = options.get('headers', {})
        body = options.get('body')
        timeout = options.get('timeout', 30)
        credential_type = options.get('credentialType')
        
        # Add authentication if credential specified
        if credential_type:
            creds = self.getCredentials(credential_type)
            headers = self._add_auth_headers(headers, creds, credential_type)
        
        # Make request
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
                timeout=timeout
            )
            response.raise_for_status()
            
            # Try to parse JSON
            try:
                return response.json()
            except ValueError:
                return response.text
                
        except requests.exceptions.Timeout:
            raise NodeExecutionError(f"Request timed out after {timeout}s: {url}")
        except requests.exceptions.ConnectionError as e:
            raise NodeExecutionError(f"Connection failed: {e}")
        except requests.exceptions.HTTPError as e:
            raise NodeExecutionError(f"HTTP error {response.status_code}: {e}")
    
    def httpRequestWithCredentials(self, options: Dict[str, Any]) -> Any:
        """
        HTTP request using node's attached credentials.
        
        Args:
            options: Request options (credential type auto-detected from node)
            
        Returns:
            Response data
        """
        # Detect credential type from node parameters
        cred_type = self._detect_credential_type()
        if cred_type:
            options['credentialType'] = cred_type
        
        return self.httpRequest(options)
    
    def _add_auth_headers(
        self, 
        headers: Dict[str, str], 
        credentials: Dict[str, Any],
        cred_type: str
    ) -> Dict[str, str]:
        """
        Add authentication headers based on credential type.
        
        Args:
            headers: Existing headers
            credentials: Decrypted credentials
            cred_type: Type of credential
            
        Returns:
            Headers with authentication added
        """
        headers = headers.copy() if headers else {}
        
        if cred_type == 'httpBasicAuth':
            import base64
            user = credentials.get('user', '')
            password = credentials.get('password', '')
            auth_str = base64.b64encode(f'{user}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {auth_str}'
        
        elif cred_type == 'httpHeaderAuth':
            header_name = credentials.get('name', 'X-API-Key')
            header_value = credentials.get('value', '')
            headers[header_name] = header_value
        
        elif cred_type == 'apiKeyAuth':
            header_name = credentials.get('name', 'X-API-Key')
            header_value = credentials.get('value', '')
            location = credentials.get('location', 'header')
            
            if location == 'header':
                headers[header_name] = header_value
            # TODO: Support query param
        
        elif cred_type == 'oAuth2Api':
            access_token = credentials.get('access_token', '')
            token_type = credentials.get('token_type', 'Bearer')
            headers['Authorization'] = f'{token_type} {access_token}'
        
        return headers
    
    def _detect_credential_type(self) -> Optional[str]:
        """Detect credential type from node parameters"""
        # Look for credential parameters
        for key, value in self._parameters.items():
            if key.endswith('_id') and isinstance(value, int):
                # Likely a credential ID
                cred_type = key[:-3]  # Remove '_id'
                return cred_type
        return None
    
    # ─── Binary Data ───
    
    def getBinaryData(self, key: str = 'input') -> Optional[bytes]:
        """
        Get binary data for processing.
        
        Args:
            key: Binary data key ('input', 'data', etc.)
            
        Returns:
            Binary data as bytes or None
        """
        binary_data = self._execution_data.get('binaryData', {})
        
        if key in binary_data:
            data = binary_data[key]
            if isinstance(data, dict):
                # n8n binary format
                return data.get('data', '')
            return data
        
        return None
    
    def setBinaryData(self, key: str, data: bytes, mime_type: str = 'application/octet-stream') -> None:
        """
        Set binary data for output.
        
        Args:
            key: Binary data key
            data: Binary data
            mime_type: MIME type
        """
        if 'binaryData' not in self._execution_data:
            self._execution_data['binaryData'] = {}
        
        self._execution_data['binaryData'][key] = {
            'data': data,
            'mimeType': mime_type,
            'fileName': key
        }
    
    def binaryToString(self, binary_data: bytes, encoding: str = 'utf-8') -> str:
        """
        Convert binary data to string.
        
        Args:
            binary_data: Binary data
            encoding: Target encoding
            
        Returns:
            Decoded string
        """
        return binary_data.decode(encoding)
    
    # ─── Input/Output ───
    
    def getInputData(self, input_index: int = 0, item_index: int = 0) -> Any:
        """
        Get input data for processing.
        
        Args:
            input_index: Input index (0 for first input)
            item_index: Item index within input
            
        Returns:
            Input data
        """
        input_data = self._execution_data.get('inputData', [])
        
        if input_index >= len(input_data):
            return None
        
        items = input_data[input_index]
        if isinstance(items, list) and item_index < len(items):
            return items[item_index]
        
        return items
    
    def getInputItems(self, input_index: int = 0) -> List[Dict[str, Any]]:
        """
        Get all input items as list.
        
        Args:
            input_index: Input index
            
        Returns:
            List of input items
        """
        input_data = self._execution_data.get('inputData', [])
        
        if input_index >= len(input_data):
            return []
        
        items = input_data[input_index]
        if isinstance(items, list):
            return items
        
        return [items] if items else []
    
    def prepareOutputData(self, data: Any) -> List[Dict[str, Any]]:
        """
        Prepare data for output to next node.
        
        Args:
            data: Output data (dict, list, or string)
            
        Returns:
            Formatted output as list of {json: data} items
        """
        if isinstance(data, list):
            return [{'json': item} for item in data]
        elif isinstance(data, dict):
            return [{'json': data}]
        else:
            return [{'json': {'result': data}}]
    
    def getWorkflowId(self) -> int:
        """Get current workflow ID"""
        return self._workflow_id
    
    # ─── Helpers ───
    
    def helpers(self) -> 'NodeHelpers':
        """Get helper class instance"""
        return NodeHelpers(self)
    
    def evaluateExpression(self, expression: str, item_index: int = 0) -> Any:
        """
        Evaluate expression with item context.
        
        Args:
            expression: n8n expression string
            item_index: Item index for $item context
            
        Returns:
            Evaluated result
        """
        from services.expression_engine import evaluate_expression
        
        # Build item context
        items = self.getInputItems(self._input_index)
        item = items[item_index] if item_index < len(items) else (items[0] if items else {})
        
        context = self._get_expression_context()
        context['$item'] = item
        context['$index'] = item_index
        context['$json'] = item.get('json', {}) if isinstance(item, dict) else item
        
        return evaluate_expression(expression, context)
    
    def jsonParse(self, json_str: str) -> Any:
        """
        Safe JSON parsing.
        
        Args:
            json_str: JSON string
            
        Returns:
            Parsed object
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise NodeExecutionError(f"JSON parse error: {e}")
    
    def returnJsonArray(self, *args) -> List[Dict[str, Any]]:
        """
        Convert arguments to JSON array format.
        
        Args:
            *args: Items to wrap
            
        Returns:
            List of {json: item} items
        """
        return [{'json': arg} for arg in args]
    
    def copyInputItems(self, items: List[Dict], properties: List[str]) -> List[Dict]:
        """
        Copy items with specified properties only.
        
        Args:
            items: Input items
            properties: Properties to copy
            
        Returns:
            Filtered items
        """
        result = []
        for item in items:
            if isinstance(item, dict) and 'json' in item:
                filtered = {k: v for k, v in item['json'].items() if k in properties}
                result.append({'json': filtered})
        return result


class NodeHelpers:
    """
    Helper functions for nodes.
    
    Reference: n8n IExecuteFunctions helpers
    """
    
    def __init__(self, context: ExecuteContext):
        self._context = context
    
    def httpRequest(self, options: Dict[str, Any]) -> Any:
        """HTTP request wrapper"""
        return self._context.httpRequest(options)
    
    def jsonParse(self, json_str: str) -> Any:
        """JSON parse wrapper"""
        return self._context.jsonParse(json_str)
    
    def returnJsonArray(self, *args) -> List[Dict[str, Any]]:
        """Return JSON array wrapper"""
        return self._context.returnJsonArray(*args)


class NodeExecutionError(Exception):
    """Node execution error"""
    pass
