"""
Expression Evaluator - n8n Expression class port
===============================================
Reference: ../n8n-master/packages/workflow/src/expression.ts

Supports n8n-style expressions:
- {{ $json.property }}
- {{ $node["NodeName"].json.field }}
- {{ $vars.name }}
- {{ $credentials.api_key }}
- {{ $workflow.id }}
- {{ $input.item.json }}
"""

import re
import logging
from typing import Any, Dict, Optional, List, Union
from datetime import datetime
import math
import random

from .sandbox import SandboxedEnvironment
from .ast_validator import ASTValidator

logger = logging.getLogger(__name__)


class ExpressionEvaluator:
    """
    Main expression evaluator class.
    
    Evaluates n8n-style expressions like:
    {{ $json.contact.firstName }}
    {{ $node["HTTP Request"].json.data[0].id }}
    {{ $vars.counter + 1 }}
    """
    
    # Regex pattern to find expressions
    EXPRESSION_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
    
    def __init__(self, context: Dict[str, Any]):
        """
        Initialize evaluator with execution context.
        
        Args:
            context: Dictionary containing:
                - $json: JSON data from previous nodes
                - $vars: Workflow variables
                - $node: Node outputs (keyed by node name)
                - $credentials: Decrypted credentials
                - $workflow: Workflow metadata
                - $input: Input data
                - $binary: Binary data
        """
        self.context = context
        self.sandbox = SandboxedEnvironment(context)
    
    def evaluate(self, expression: str) -> Any:
        """
        Evaluate a single expression.
        
        Args:
            expression: String like "$json.contact.firstName" or "1 + 2"
            
        Returns:
            Evaluated result
        """
        expression = expression.strip()
        
        # Handle simple literals
        if expression.startswith('"') and expression.endswith('"'):
            return expression[1:-1]
        if expression.startswith("'") and expression.endswith("'"):
            return expression[1:-1]
        if expression.isdigit():
            return int(expression)
        if expression.replace('.', '', 1).isdigit():
            return float(expression)
        if expression.lower() == 'true':
            return True
        if expression.lower() == 'false':
            return False
        if expression.lower() == 'null' or expression.lower() == 'none':
            return None
        
        # Parse and evaluate complex expression
        try:
            return self._evaluate_expression(expression)
        except Exception as e:
            logger.error(f"Expression evaluation failed: {expression} - {e}")
            raise ExpressionError(f"Failed to evaluate: {expression}", str(e))
    
    def _evaluate_expression(self, expression: str) -> Any:
        """Internal expression evaluation"""
        # Resolve variable references
        resolved = self._resolve_expression(expression)
        
        # Handle operators
        return self._apply_operators(resolved)
    
    def _resolve_expression(self, expr: str) -> Any:
        """Resolve expression with variable references"""
        expr = expr.strip()
        
        # Direct variable access: $json, $vars, $node, etc.
        if expr.startswith('$'):
            return self.sandbox.resolve(expr)
        
        # String literal
        if (expr.startswith('"') and expr.endswith('"')) or \
           (expr.startswith("'") and expr.endswith("'")):
            return expr[1:-1]
        
        # Number
        try:
            if '.' in expr:
                return float(expr)
            return int(expr)
        except ValueError:
            pass
        
        # Binary operations
        return expr
    
    def _apply_operators(self, expr: str) -> Any:
        """Apply operators in expression"""
        expr = expr.strip()
        
        # Handle string concatenation
        if '+' in expr and not self._is_simple_number(expr):
            parts = expr.split('+')
            if all(p.strip().startswith('"') for p in parts):
                return ''.join(self._apply_operators(p.strip()) for p in parts)
        
        # Handle comparisons
        for op in ['==', '!=', '<=', '>=', '<', '>', '&&', '||']:
            if op in expr:
                parts = expr.split(op, 1)
                if len(parts) == 2:
                    left = self._apply_operators(parts[0])
                    right = self._apply_operators(parts[1])
                    return self._compare(left, op, right)
        
        # Handle arithmetic
        for op in ['+', '-', '*', '/']:
            # Be careful with negative numbers and subtraction
            if op == '-' and expr[0] == '-':
                return -self._apply_operators(expr[1:])
            pattern = rf'([\w.$]+)\s*\{op}\s*([\w.$]+)'
            match = re.match(pattern, expr)
            if match:
                left = self._resolve_single(match.group(1))
                right = self._resolve_single(match.group(2))
                if op == '+':
                    return left + right
                elif op == '-':
                    return left - right
                elif op == '*':
                    return left * right
                elif op == '/':
                    if right == 0:
                        raise ExpressionError("Division by zero")
                    return left / right
        
        # Function calls
        if '(' in expr and expr.endswith(')'):
            return self._evaluate_function(expr)
        
        # Simple resolve
        return self._resolve_single(expr)
    
    def _resolve_single(self, value: str) -> Any:
        """Resolve a single value"""
        value = value.strip()
        
        # String literal
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        
        # Boolean
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        if value.lower() == 'null' or value.lower() == 'none':
            return None
        
        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # Variable reference
        if value.startswith('$'):
            return self.sandbox.resolve(value)
        
        # String with dots (like "hello.world")
        return value
    
    def _is_simple_number(self, expr: str) -> bool:
        """Check if expression is just numbers and operators"""
        cleaned = expr.replace(' ', '').replace('.', '')
        return cleaned.replace('+', '').replace('-', '').replace('*', '').replace('/', '').isdigit()
    
    def _compare(self, left: Any, op: str, right: Any) -> bool:
        """Compare two values with operator"""
        if op == '==':
            return left == right
        elif op == '!=':
            return left != right
        elif op == '<':
            return left < right
        elif op == '>':
            return left > right
        elif op == '<=':
            return left <= right
        elif op == '>=':
            return left >= right
        elif op == '&&':
            return bool(left) and bool(right)
        elif op == '||':
            return bool(left) or bool(right)
        return False
    
    def _evaluate_function(self, expr: str) -> Any:
        """Evaluate function call"""
        # Extract function name and arguments
        match = re.match(r'(\w+)\((.*)\)$', expr.strip())
        if not match:
            return expr
        
        func_name = match.group(1)
        args_str = match.group(2)
        
        # Parse arguments
        args = self._parse_arguments(args_str)
        args = [self._apply_operators(arg.strip()) for arg in args]
        
        # Call function
        return self._call_function(func_name, args)
    
    def _parse_arguments(self, args_str: str) -> List[str]:
        """Parse function arguments"""
        if not args_str.strip():
            return []
        
        args = []
        current = ''
        depth = 0
        in_string = False
        string_char = None
        
        for char in args_str:
            if char in '"\'' and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif not in_string:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                elif char == ',' and depth == 0:
                    args.append(current)
                    current = ''
                    continue
            
            current += char
        
        if current.strip():
            args.append(current)
        
        return args
    
    def _call_function(self, name: str, args: List[Any]) -> Any:
        """Call a built-in function"""
        # Date functions
        if name == 'Date':
            if args and args[0] == 'now':
                return datetime.utcnow().isoformat()
            return datetime.utcnow()
        
        if name == 'now':
            return datetime.utcnow().isoformat()
        
        # Math functions
        if name == 'Math':
            return MathProxy()
        
        # String functions
        if name == 'String':
            if args:
                return str(args[0])
            return ''
        
        if name == 'toString':
            return str(args[0]) if args else ''
        
        # Array functions
        if name == 'Array':
            return list(args) if args else []
        
        if name == 'items':
            # Special: convert to items array
            if args:
                return [{'json': item} for item in args[0]] if isinstance(args[0], list) else [args[0]]
            return []
        
        # Object functions
        if name == 'Object':
            return ObjectProxy()
        
        # JSON functions
        if name == 'json':
            import json
            if args:
                return json.loads(args[0]) if isinstance(args[0], str) else args[0]
            return {}
        
        # Unknown function - return as string
        logger.warning(f"Unknown function: {name}")
        return f"{name}({', '.join(str(a) for a in args)})"
    
    def evaluate_template(self, template: str) -> str:
        """
        Evaluate a template string with multiple expressions.
        
        Args:
            template: String like "Hello {{ $json.name }}, you have {{ $vars.count }} items"
            
        Returns:
            String with expressions replaced by their values
        """
        def replace_match(match):
            try:
                result = self.evaluate(match.group(1))
                return str(result) if result is not None else ''
            except Exception as e:
                logger.error(f"Failed to evaluate expression in template: {match.group(1)}")
                return '{{' + match.group(1) + '}}'
        
        return self.EXPRESSION_PATTERN.sub(replace_match, template)


class MathProxy:
    """Proxy for Math functions in expressions"""
    
    @staticmethod
    def random() -> float:
        return random.random()
    
    @staticmethod
    def floor(value: float) -> int:
        return math.floor(value)
    
    @staticmethod
    def ceil(value: float) -> int:
        return math.ceil(value)
    
    @staticmethod
    def round(value: float) -> int:
        return round(value)
    
    @staticmethod
    def abs(value: float) -> float:
        return abs(value)
    
    @staticmethod
    def min(*args) -> float:
        return min(*args)
    
    @staticmethod
    def max(*args) -> float:
        return max(*args)
    
    @staticmethod
    def pow(base: float, exp: float) -> float:
        return math.pow(base, exp)
    
    @staticmethod
    def sqrt(value: float) -> float:
        return math.sqrt(value)


class ObjectProxy:
    """Proxy for Object functions in expressions"""
    
    @staticmethod
    def keys(obj: Dict) -> List:
        return list(obj.keys()) if isinstance(obj, dict) else []
    
    @staticmethod
    def values(obj: Dict) -> List:
        return list(obj.values()) if isinstance(obj, dict) else []
    
    @staticmethod
    def entries(obj: Dict) -> List:
        return list(obj.items()) if isinstance(obj, dict) else []


class ExpressionError(Exception):
    """Expression evaluation error"""
    pass


# Convenience function
def evaluate_expression(expression: str, context: Dict[str, Any]) -> Any:
    """
    Evaluate a single expression with context.
    
    Args:
        expression: n8n-style expression
        context: Execution context
        
    Returns:
        Evaluated result
    """
    evaluator = ExpressionEvaluator(context)
    return evaluator.evaluate(expression)


def evaluate_template(template: str, context: Dict[str, Any]) -> str:
    """
    Evaluate a template with multiple expressions.
    
    Args:
        template: Template string
        context: Execution context
        
    Returns:
        Template with expressions replaced
    """
    evaluator = ExpressionEvaluator(context)
    return evaluator.evaluate_template(template)
