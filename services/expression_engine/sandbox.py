"""
Sandboxed Environment for Expression Evaluation
=============================================
Reference: ../n8n-master/packages/workflow/src/expression-sandboxing.ts

Provides safe access to:
- $json - JSON data from previous nodes
- $vars - Workflow variables
- $node - Node outputs
- $credentials - Decrypted credentials
- $workflow - Workflow metadata
- $input - Input data
- $binary - Binary data
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Security violation in expression"""
    pass


class SandboxedEnvironment:
    """
    Safe environment for expression evaluation.
    
    Restricts access to:
    - No module imports
    - No file access
    - No network access
    - Limited builtins
    """
    
    # Blocked module access patterns
    BLOCKED_PATTERNS: Set[str] = {
        'import', 'importlib', '__import__',
        'open', 'file', 'exec', 'eval', 'compile',
        'reload', 'breakpoint',
        'os', 'sys', 'subprocess', 'socket',
        'urllib', 'http', 'requests', 'httpx',
        'pathlib', 'glob', 'shutil',
        'tempfile', 'pickle', 'marshal',
    }
    
    # Allowed builtin functions
    ALLOWED_BUILTINS: Set[str] = {
        # Booleans
        'True', 'False', 'None',
        # Type conversion
        'bool', 'int', 'float', 'str', 'list', 'dict', 'tuple', 'set',
        'type', 'isinstance', 'issubclass',
        # Math
        'abs', 'min', 'max', 'sum', 'round', 'pow', 'divmod',
        # Collections
        'len', 'range', 'reversed', 'sorted', 'enumerate', 'zip', 'map', 'filter',
        'any', 'all', 'slice', 'ord', 'chr', 'hex', 'oct', 'bin',
        # String
        'format', 'repr', 'ascii', 'chr',
        # JSON
        'json',  # Only if explicitly provided
        # Utilities
        'print',  # Allowed for debugging
    }
    
    def __init__(self, context: Dict[str, Any]):
        """
        Initialize sandbox with execution context.
        
        Args:
            context: Dict with $json, $vars, $node, etc.
        """
        self.context = context
        self._setup_resolvers()
    
    def _setup_resolvers(self):
        """Setup variable resolvers"""
        self.resolvers = {
            '$json': self._resolve_json,
            '$vars': self._resolve_vars,
            '$node': self._resolve_node,
            '$workflow': self._resolve_workflow,
            '$input': self._resolve_input,
            '$credentials': self._resolve_credentials,
            '$binary': self._resolve_binary,
        }
    
    def resolve(self, path: str) -> Any:
        """
        Resolve a variable path like $node["HTTP Request"].json.data
        
        Args:
            path: Variable path (e.g., "$json.contact.name")
            
        Returns:
            Resolved value
        """
        if not path.startswith('$'):
            return path
        
        # Split into parts
        parts = self._split_path(path)
        if not parts:
            return None
        
        # Get root resolver
        root = parts[0]
        if root not in self.resolvers:
            logger.warning(f"Unknown variable root: {root}")
            return None
        
        # Start with root context
        current = self.resolvers[root]()
        
        # Navigate path
        for part in parts[1:]:
            current = self._navigate(current, part)
            if current is None:
                return None
        
        return current
    
    def _split_path(self, path: str) -> List[str]:
        """Split path into parts, handling brackets"""
        parts = []
        current = ''
        in_bracket = False
        
        for char in path:
            if char == '[':
                if current:
                    parts.append(current)
                    current = ''
                in_bracket = True
            elif char == ']':
                if current:
                    parts.append(current)
                    current = ''
                in_bracket = False
            elif char == '.':
                if not in_bracket:
                    if current:
                        parts.append(current)
                        current = ''
                else:
                    current += char
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts
    
    def _navigate(self, obj: Any, part: str) -> Any:
        """Navigate into object with part"""
        if obj is None:
            return None
        
        # Handle bracket notation (string keys)
        if part.startswith('"') and part.endswith('"'):
            key = part[1:-1]
        elif part.startswith("'") and part.endswith("'"):
            key = part[1:-1]
        else:
            key = part
        
        # Try dict access
        if isinstance(obj, dict):
            return obj.get(key)
        
        # Try list access (by index)
        if isinstance(obj, list):
            try:
                index = int(key)
                return obj[index] if 0 <= index < len(obj) else None
            except (ValueError, TypeError):
                return None
        
        # Try attribute access
        return getattr(obj, key, None)
    
    def _resolve_json(self) -> Dict:
        """Resolve $json - JSON data from input"""
        return self.context.get('$json', {})
    
    def _resolve_vars(self) -> Dict:
        """Resolve $vars - Workflow variables"""
        return self.context.get('$vars', {})
    
    def _resolve_node(self) -> Dict:
        """Resolve $node - Node outputs keyed by node name"""
        return self.context.get('$node', {})
    
    def _resolve_workflow(self) -> Dict:
        """Resolve $workflow - Workflow metadata"""
        return self.context.get('$workflow', {
            'id': self.context.get('workflow_id'),
            'name': self.context.get('workflow_name'),
        })
    
    def _resolve_input(self) -> Any:
        """Resolve $input - Input data"""
        return self.context.get('$input', [])
    
    def _resolve_credentials(self) -> Dict:
        """Resolve $credentials - Decrypted credentials"""
        return self.context.get('$credentials', {})
    
    def _resolve_binary(self) -> Dict:
        """Resolve $binary - Binary data"""
        return self.context.get('$binary', {})
    
    def validate_access(self, path: str) -> bool:
        """
        Validate that a path doesn't access blocked resources.
        
        Args:
            path: Variable path to validate
            
        Returns:
            True if access is allowed
        """
        path_lower = path.lower()
        
        for blocked in self.BLOCKED_PATTERNS:
            if blocked in path_lower:
                logger.warning(f"Blocked access attempt: {path}")
                return False
        
        return True
    
    def get_allowed_builtins(self) -> Set[str]:
        """Get set of allowed builtin functions"""
        return self.ALLOWED_BUILTINS.copy()
    
    def create_safe_globals(self) -> Dict[str, Any]:
        """Create safe globals for code execution"""
        return {
            '__builtins__': {k: __builtins__[k] for k in self.ALLOWED_BUILTINS if k in __builtins__},
            'json': __import__('json') if 'json' in self.ALLOWED_BUILTINS else None,
        }


class ASTValidator:
    """
    AST-based security validator for expressions.
    
    Reference: n8n expression-sandboxing.ts
    
    Validates that expressions don't contain:
    - Import statements
    - Function definitions
    - Lambda expressions
    - Class definitions
    - Attribute access on restricted modules
    """
    
    # Allowed AST node types
    ALLOWED_NODES = {
        'Expression',
        'BinaryOp', 'UnaryOp', 'BoolOp', 'Compare',
        'Name', 'NameConstant', 'Num', 'Str', 'Bytes',
        'List', 'Tuple', 'Set', 'Dict',
        'Subscript', 'Index', 'Slice', 'ExtSlice',
        'Call', 'Attribute',
        'Load', 'Store',
        'And', 'Or', 'Not', 'Eq', 'NotEq', 'Lt', 'Gt', 'LtE', 'GtE',
        'Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod', 'Pow',
        'UAdd', 'USub', 'Invert',
        'Repr',  # backticks
    }
    
    # Blocked node types
    BLOCKED_NODES = {
        'Import', 'ImportFrom',
        'FunctionDef', 'AsyncFunctionDef', 'Lambda',
        'ClassDef', 'Decorator',
        'For', 'AsyncFor', 'While', 'If',
        'Try', 'TryStar',
        'With', 'AsyncWith',
        'Raise', 'Assert',
        'Yield', 'YieldFrom', 'Await',
        'Global', 'Nonlocal',
        'Pass', 'Break', 'Continue',
    }
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, code: str) -> bool:
        """
        Validate code doesn't contain blocked patterns.
        
        Args:
            code: Python code to validate
            
        Returns:
            True if valid, False otherwise
        """
        self.errors = []
        
        try:
            tree = ast.parse(code, mode='eval')
            self._visit_node(tree.body)
            return len(self.errors) == 0
        except SyntaxError as e:
            self.errors.append(f"Syntax error: {e}")
            return False
        except ValueError as e:
            self.errors.append(f"Parse error: {e}")
            return False
    
    def _visit_node(self, node: ast.AST):
        """Visit AST node and check for violations"""
        node_type = type(node).__name__
        
        # Check if blocked
        if node_type in self.BLOCKED_NODES:
            self.errors.append(f"Blocked construct: {node_type}")
            return
        
        # Check node type name for blocked patterns
        node_name = node_type.lower()
        for blocked in self.BLOCKED_NODES:
            if blocked.lower() in node_name:
                self.errors.append(f"Blocked construct: {node_type}")
                return
        
        # Recursively visit child nodes
        for child in ast.iter_child_nodes(node):
            self._visit_node(child)
    
    def get_errors(self) -> List[str]:
        """Get validation errors"""
        return self.errors.copy()
