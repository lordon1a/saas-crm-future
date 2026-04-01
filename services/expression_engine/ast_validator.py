"""
AST Validator for Expression Security
===================================
Reference: n8n expression-sandboxing.ts

Validates Python AST to prevent:
- Import statements
- Function definitions
- Class definitions
- Attribute access on restricted modules
"""

import ast
import logging
from typing import List, Set, Any

logger = logging.getLogger(__name__)


class BlockedConstructError(Exception):
    """Raised when blocked construct is detected"""
    pass


class ASTValidator:
    """
    Validates AST for security violations.
    
    Reference: n8n uses escope for JS analysis,
    here we use Python's ast module.
    """
    
    # Blocked node types
    BLOCKED_NODE_TYPES: Set[str] = {
        'Import',           # import statements
        'ImportFrom',       # from x import y
        'FunctionDef',      # def f(): ...
        'AsyncFunctionDef', # async def f(): ...
        'Lambda',          # lambda x: x
        'ClassDef',        # class Foo: ...
        'Decorator',       # @property
        'For',             # for x in y: ...
        'AsyncFor',        # async for
        'While',           # while x: ...
        'If',              # if x: ...
        'Try',             # try: ...
        'TryStar',         # try: ... except* ...
        'With',            # with x: ...
        'AsyncWith',       # async with
        'Raise',           # raise
        'Assert',          # assert
        'Yield',           # yield
        'YieldFrom',       # yield from
        'Await',           # await
        'Global',          # global x
        'Nonlocal',        # nonlocal x
        'Pass',            # pass (allowed as statement)
        'Break',           # break (allowed as statement)
        'Continue',        # continue (allowed as statement)
    }
    
    # Restricted names/attributes
    RESTRICTED_NAMES: Set[str] = {
        'import', 'importlib', '__import__',
        'exec', 'eval', 'compile', 'execfile',
        'open', 'file', 'input', 'raw_input',
        '__import__', 'reload', 'breakpoint',
    }
    
    # Restricted module access patterns
    RESTRICTED_PATTERNS: Set[str] = {
        'os', 'sys', 'subprocess', 'socket',
        'urllib', 'requests', 'httpx', 'aiohttp',
        'pathlib', 'glob', 'shutil', 'tempfile',
        'pickle', 'marshal', 'builtins',
        'ctypes', 'cffi', 'winreg',
    }
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, code: str) -> bool:
        """
        Validate code doesn't contain blocked constructs.
        
        Args:
            code: Python code string
            
        Returns:
            True if valid
            
        Raises:
            BlockedConstructError: If blocked construct found
        """
        self.errors = []
        
        try:
            tree = ast.parse(code, mode='eval')
        except SyntaxError as e:
            self.errors.append(f"Syntax error: {e}")
            raise BlockedConstructError(str(e))
        
        self._check_node(tree.body)
        
        if self.errors:
            error_msg = '; '.join(self.errors)
            raise BlockedConstructError(error_msg)
        
        return True
    
    def _check_node(self, node: ast.AST):
        """Recursively check AST node"""
        node_type = type(node).__name__
        
        # Check if blocked
        if node_type in self.BLOCKED_NODE_TYPES:
            self.errors.append(f"Blocked construct: {node_type}")
            return
        
        # Check for restricted names in Name nodes
        if isinstance(node, ast.Name):
            if node.id in self.RESTRICTED_NAMES:
                self.errors.append(f"Blocked name: {node.id}")
        
        # Check for restricted patterns in Attribute nodes
        if isinstance(node, ast.Attribute):
            if node.attr in self.RESTRICTED_NAMES:
                self.errors.append(f"Blocked attribute: {node.attr}")
            
            # Check if accessing restricted module
            if isinstance(node.value, ast.Name):
                if node.value.id in self.RESTRICTED_PATTERNS:
                    self.errors.append(f"Blocked module access: {node.value.id}.{node.attr}")
        
        # Check for __builtins__ access
        if isinstance(node, ast.Attribute) and node.attr == '__builtins__':
            self.errors.append("Blocked: __builtins__ access")
        
        # Recursively check child nodes
        for child in ast.iter_child_nodes(node):
            self._check_node(child)
    
    def get_errors(self) -> List[str]:
        """Get list of validation errors"""
        return self.errors.copy()


class ExpressionSecurityValidator:
    """
    High-level security validator for expressions.
    
    Provides:
    - AST-based validation
    - Pattern matching for common attacks
    - Size limits
    """
    
    MAX_EXPRESSION_LENGTH = 1000
    MAX_DEPTH = 10
    
    def __init__(self):
        self.validator = ASTValidator()
    
    def validate(self, expression: str) -> bool:
        """
        Validate expression for security.
        
        Args:
            expression: n8n expression string
            
        Returns:
            True if valid
        """
        # Check length
        if len(expression) > self.MAX_EXPRESSION_LENGTH:
            raise SecurityError(f"Expression too long: {len(expression)} > {self.MAX_EXPRESSION_LENGTH}")
        
        # Check for blocked patterns
        blocked_patterns = [
            r'import\s+', r'from\s+\w+\s+import',
            r'__import__', r'eval\s*\(', r'exec\s*\(',
            r'compile\s*\(', r'open\s*\(',
            r'subprocess\.', r'os\.system',
            r'shelve\.', r'marshal\.', r'pickle\.',
        ]
        
        import re
        for pattern in blocked_patterns:
            if re.search(pattern, expression, re.IGNORECASE):
                raise SecurityError(f"Blocked pattern found: {pattern}")
        
        # Parse and validate AST
        # Note: Full AST validation is complex for expressions
        # For now, we do pattern-based validation
        
        return True
    
    def validate_code_block(self, code: str) -> bool:
        """
        Validate code block (for Code node).
        
        More strict validation since this runs arbitrary code.
        """
        # Length check
        if len(code) > self.MAX_EXPRESSION_LENGTH * 10:
            raise SecurityError(f"Code block too long")
        
        # AST validation
        self.validator.validate(code)
        
        return True


class SecurityError(Exception):
    """Security validation error"""
    pass
