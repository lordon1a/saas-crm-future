"""
Base Node Context
================
Reference: ../n8n-master/packages/core/src/execution-engine/node-execution-context/base-execute-context.ts

Base class for all node execution contexts.
Provides parameter access, credential management, and workflow data.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseNodeContext(ABC):
    """
    Base class for node execution contexts.
    
    Provides:
    - Node parameter access with expression evaluation
    - Credential loading and decryption
    - Workflow static data access
    - Logging
    """
    
    def __init__(
        self,
        node_data: Dict[str, Any],
        execution_data: Dict[str, Any],
        workflow_id: int,
        workflow_settings: Dict[str, Any] = None
    ):
        """
        Initialize base context.
        
        Args:
            node_data: Node definition with parameters
            execution_data: Execution data including input/output
            workflow_id: Workflow ID
            workflow_settings: Workflow-level settings
        """
        self._node = node_data
        self._node_id = node_data.get('id', '')
        self._node_name = node_data.get('name', self._node_id)
        self._node_type = node_data.get('type', '')
        self._parameters = node_data.get('parameters', {})
        self._execution_data = execution_data
        self._workflow_id = workflow_id
        self._workflow_settings = workflow_settings or {}
        self._credentials_cache: Dict[str, Any] = {}
    
    # ─── Parameter Access ───
    
    def getNodeParameter(self, param_name: str, default: Any = None) -> Any:
        """
        Get a single node parameter with expression evaluation.
        
        Args:
            param_name: Parameter name (supports dot notation like 'http.url')
            default: Default value if parameter not found
            
        Returns:
            Parameter value (evaluated if expression)
        """
        # Support dot notation
        parts = param_name.split('.')
        value = self._parameters
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
            
            if value is None:
                return default
        
        # Evaluate expression if string
        if isinstance(value, str) and '{{' in value:
            from services.expression_engine import evaluate_expression
            context = self._get_expression_context()
            value = evaluate_expression(value, context)
        
        return value
    
    def getNodeParameters(self) -> Dict[str, Any]:
        """
        Get all node parameters.
        
        Returns:
            Dictionary of all parameters
        """
        return self._parameters.copy()
    
    def _get_expression_context(self) -> Dict[str, Any]:
        """
        Build expression evaluation context.
        
        Returns:
            Context dict with $json, $vars, $node, etc.
        """
        context = {
            '$json': self._get_input_json(),
            '$vars': self._execution_data.get('vars', {}),
            '$workflow': {
                'id': self._workflow_id,
                'name': self._workflow_settings.get('name', ''),
            },
            '$input': self._get_input_data(),
            '$node': self._execution_data.get('nodeData', {}),
            '$binary': self._execution_data.get('binaryData', {}),
            '$credentials': self._credentials_cache,
        }
        return context
    
    def _get_input_json(self) -> Dict[str, Any]:
        """Get JSON data from input"""
        input_data = self._execution_data.get('inputData', [])
        if input_data and len(input_data) > 0:
            first_item = input_data[0]
            if isinstance(first_item, dict):
                return first_item.get('json', {})
        return {}
    
    def _get_input_data(self) -> List[Dict[str, Any]]:
        """Get input data array"""
        return self._execution_data.get('inputData', [])
    
    # ─── Credentials ───
    
    def getCredentials(self, credential_type: str) -> Dict[str, Any]:
        """
        Get decrypted credentials for this node.
        
        Args:
            credential_type: Type of credential (e.g., 'httpBasicAuth', 'apiKeyAuth')
            
        Returns:
            Dictionary of decrypted credential data
        """
        # Check cache
        if credential_type in self._credentials_cache:
            return self._credentials_cache[credential_type]
        
        # Get credential ID from parameters
        cred_id_param = f'{credential_type}_id'
        cred_id = self._parameters.get(cred_id_param)
        
        if not cred_id:
            logger.warning(f"No credential ID for type {credential_type} on node {self._node_name}")
            return {}
        
        # Load credentials
        from .credentials import CredentialsManager
        cred_manager = CredentialsManager()
        creds = cred_manager.get_credentials(cred_id, credential_type, self._workflow_id)
        
        # Cache for this execution
        self._credentials_cache[credential_type] = creds
        
        return creds
    
    def getCredentialParameter(self, credential_type: str, field: str, default: Any = None) -> Any:
        """
        Get a specific field from credentials.
        
        Args:
            credential_type: Type of credential
            field: Field name in credential
            default: Default value
            
        Returns:
            Credential field value
        """
        creds = self.getCredentials(credential_type)
        return creds.get(field, default)
    
    # ─── Workflow Data ───
    
    def getWorkflowStaticData(self, data_type: str = 'node') -> Dict[str, Any]:
        """
        Get persistent workflow data.
        
        Data persists across executions (unlike run data which is one-time).
        
        Args:
            data_type: 'node' for node-specific, 'workflow' for workflow-level
            
        Returns:
            Static data dictionary
        """
        if data_type == 'node':
            return self._workflow_settings.get('staticData', {}).get(self._node_id, {})
        else:
            return self._workflow_settings.get('staticData', {}).get('workflow', {})
    
    def setWorkflowStaticData(self, data: Dict[str, Any], data_type: str = 'node') -> None:
        """
        Set persistent workflow data.
        
        Args:
            data: Data to persist
            data_type: 'node' or 'workflow'
        """
        if data_type == 'node':
            static_data = self._workflow_settings.setdefault('staticData', {})
            static_data[self._node_id] = data
        else:
            static_data = self._workflow_settings.setdefault('staticData', {})
            static_data['workflow'] = data
    
    def getWorkflowId(self) -> int:
        """Get current workflow ID"""
        return self._workflow_id
    
    def getWorkflowName(self) -> str:
        """Get current workflow name"""
        return self._workflow_settings.get('name', '')
    
    # ─── Logging ───
    
    def log(self, level: str, message: str, **kwargs):
        """
        Log with node context.
        
        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **kwargs: Additional context
        """
        log_func = getattr(logger, level, logger.info)
        log_func(f"[{self._node_name}] {message}", **kwargs)
    
    def debug(self, message: str, **kwargs):
        self.log('debug', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.log('info', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log('warning', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log('error', message, **kwargs)
    
    # ─── Node Info ───
    
    def getNode(self) -> Dict[str, Any]:
        """Get node definition"""
        return self._node.copy()
    
    def getNodeId(self) -> str:
        """Get node ID"""
        return self._node_id
    
    def getNodeName(self) -> str:
        """Get node name"""
        return self._node_name
    
    def getNodeType(self) -> str:
        """Get node type"""
        return self._node_type
    
    # ─── Input/Output ───
    
    @abstractmethod
    def getInputData(self, input_index: int = 0, item_index: int = 0) -> Any:
        """
        Get input data for processing.
        
        Args:
            input_index: Input index (0 for first input)
            item_index: Item index within input
            
        Returns:
            Input data
        """
        pass
    
    @abstractmethod
    def prepareOutputData(self, data: Any) -> List[Dict[str, Any]]:
        """
        Prepare data for output.
        
        Args:
            data: Output data
            
        Returns:
            Formatted output as list of items
        """
        pass
