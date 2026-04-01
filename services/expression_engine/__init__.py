"""
Expression Engine for Workflow Execution
========================================
n8n-style expression evaluation with security sandboxing.

Reference: ../n8n-master/packages/workflow/src/expression.ts
           ../n8n-master/packages/workflow/src/expression-sandboxing.ts

Supports:
- {{ $json.property }} - JSON data access
- {{ $vars.name }} - Variable access
- {{ $node["NodeName"].json.field }} - Node output access
- {{ $credentials.api_key }} - Credential access
- {{ $workflow.id }} - Workflow metadata
- {{ $input.item.json }} - Input data access
- Operators: +, -, *, /, ==, !=, &&, ||, !
- Functions: Date.now(), Math.random(), String methods
"""

from .evaluator import ExpressionEvaluator
from .sandbox import SandboxedEnvironment
from .ast_validator import ASTValidator

__all__ = ['ExpressionEvaluator', 'SandboxedEnvironment', 'ASTValidator']
