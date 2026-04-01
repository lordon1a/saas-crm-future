"""
Directed Graph Implementation for Workflow Execution
==================================================
Based on n8n's partial-execution-utils/directed-graph.ts

This module provides graph traversal utilities with cycle detection
for workflow execution ordering.

Reference: ../n8n-master/packages/core/src/execution-engine/partial-execution-utils/directed-graph.ts
"""
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NodeConnectionState(Enum):
    """Connection states for node execution"""
    NOT_EXECUTED = "not_executed"
    EXECUTING = "executing"
    EXECUTED = "executed"
    WAITING = "waiting"  # For pause/resume


@dataclass
class DirectedGraphNode:
    """Represents a node in the workflow graph"""
    id: str
    name: str
    type: str  # 'trigger', 'action', 'condition', 'output'
    data: Dict[str, Any] = field(default_factory=dict)
    connections: Dict[str, List['Connection']] = field(default_factory=dict)  # input/output connections
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class Connection:
    """Represents a connection between two nodes"""
    node: str  # Node ID
    type: str  # 'main', 'error', 'choice'
    index: int = 0  # For multiple connections of same type


@dataclass
class GraphMetadata:
    """Metadata about the graph structure"""
    node_count: int = 0
    edge_count: int = 0
    has_cycles: bool = False
    strongly_connected_components: List[List[str]] = field(default_factory=list)
    topological_order: List[str] = field(default_factory=list)
    execution_order: List[List[str]] = field(default_factory=list)  # Parallel groups


class DirectedGraph:
    """
    Directed Graph for workflow execution.
    
    Provides:
    - Graph building from nodes/edges
    - Cycle detection and handling
    - Topological sorting for execution order
    - Finding subgraphs for partial execution
    - Reachability queries
    """
    
    def __init__(self):
        self.nodes: Dict[str, DirectedGraphNode] = {}
        self.adjacency: Dict[str, List[Connection]] = defaultdict(list)  # outgoing edges
        self.reverse_adjacency: Dict[str, List[Connection]] = defaultdict(list)  # incoming edges
        self.metadata = GraphMetadata()
    
    @classmethod
    def from_canvas_data(cls, canvas_data: Dict) -> 'DirectedGraph':
        """
        Build graph from n8n-style canvas data.
        
        Args:
            canvas_data: {
                "nodes": [{"id": "node_1", "data": {...}}],
                "edges": [{"source": "node_1", "target": "node_2", "sourceHandle": "output"}]
            }
        """
        graph = cls()
        
        # Add nodes
        for node_data in canvas_data.get('nodes', []):
            node = DirectedGraphNode(
                id=node_data['id'],
                name=node_data.get('name', node_data['id']),
                type=node_data.get('type', 'unknown'),
                data=node_data.get('data', {})
            )
            graph.add_node(node)
        
        # Add edges
        for edge_data in canvas_data.get('edges', []):
            source = edge_data['source']
            target = edge_data['target']
            handle = edge_data.get('sourceHandle', 'output')
            
            graph.add_edge(
                source=source,
                target=target,
                connection_type=handle if handle else 'main'
            )
        
        # Calculate metadata
        graph._calculate_metadata()
        
        return graph
    
    def add_node(self, node: DirectedGraphNode) -> None:
        """Add a node to the graph"""
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = []
        if node.id not in self.reverse_adjacency:
            self.reverse_adjacency[node.id] = []
    
    def add_edge(self, source: str, target: str, connection_type: str = 'main') -> None:
        """Add an edge between two nodes"""
        if source not in self.nodes:
            raise ValueError(f"Source node {source} not in graph")
        if target not in self.nodes:
            raise ValueError(f"Target node {target} not in graph")
        
        conn = Connection(node=target, type=connection_type)
        self.adjacency[source].append(conn)
        
        # Reverse connection for reverse traversal
        rev_conn = Connection(node=source, type=connection_type)
        self.reverse_adjacency[target].append(rev_conn)
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get nodes grouped by execution order.
        Nodes in the same group can be executed in parallel.
        
        Returns:
            List of groups, each group is a list of node IDs
        """
        # Topological sort with level assignment
        levels: Dict[str, int] = {}
        in_degree: Dict[str, int] = {nid: len(self.reverse_adjacency.get(nid, [])) for nid in self.nodes}
        
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        for node_id in queue:
            levels[node_id] = 0
        
        while queue:
            node_id = queue.popleft()
            current_level = levels.get(node_id, 0)
            
            for conn in self.adjacency.get(node_id, []):
                target = conn.node
                levels[target] = max(levels.get(target, 0), current_level + 1)
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        # Keep isolated/cyclic nodes represented to avoid dropping them silently.
        for node_id in self.nodes:
            levels.setdefault(node_id, 0)
        
        # Group by level
        max_level = max(levels.values()) if levels else 0
        groups: List[List[str]] = [[] for _ in range(max_level + 1)]
        for node_id, level in levels.items():
            groups[level].append(node_id)
        
        return groups
    
    def find_start_nodes(self, start_node_id: Optional[str] = None) -> List[str]:
        """
        Find starting nodes (nodes with no incoming edges).
        
        Args:
            start_node_id: If provided, start from this node and find
                          ancestors in the subgraph
        """
        if start_node_id:
            # Find all ancestors of start_node
            visited: Set[str] = set()
            queue = deque([start_node_id])
            
            while queue:
                node_id = queue.popleft()
                if node_id in visited:
                    continue
                visited.add(node_id)
                
                for conn in self.reverse_adjacency.get(node_id, []):
                    if conn.node not in visited:
                        queue.append(conn.node)
            
            return list(visited)
        else:
            # Return all nodes with no incoming edges
            return [
                node_id for node_id in self.nodes
                if len(self.reverse_adjacency.get(node_id, [])) == 0
            ]
    
    def find_subgraph(self, node_ids: List[str]) -> 'DirectedGraph':
        """
        Extract a subgraph containing only the specified nodes
        and edges between them.
        """
        subgraph = DirectedGraph()
        
        for node_id in node_ids:
            if node_id in self.nodes:
                subgraph.add_node(self.nodes[node_id])
        
        for node_id in node_ids:
            for conn in self.adjacency.get(node_id, []):
                if conn.node in node_ids:
                    subgraph.add_edge(node_id, conn.node, conn.type)
        
        subgraph._calculate_metadata()
        return subgraph
    
    def detect_cycles(self) -> Tuple[bool, List[List[str]]]:
        """
        Detect cycles using DFS.
        
        Returns:
            (has_cycle, cycle_paths) - List of cycles found
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []
        
        def dfs(node_id: str, path: List[str]) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            for conn in self.adjacency.get(node_id, []):
                if conn.node not in visited:
                    dfs(conn.node, path.copy())
                elif conn.node in rec_stack:
                    # Found cycle
                    cycle_start = path.index(conn.node)
                    cycle = path[cycle_start:] + [conn.node]
                    cycles.append(cycle)
            
            rec_stack.remove(node_id)
        
        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id, [])
        
        return len(cycles) > 0, cycles
    
    def handle_cycles(self) -> List[str]:
        """
        Find nodes that break cycles (articulation points).
        
        For workflows with cycles (loops), we need to break them
        for execution. Returns nodes that should NOT be executed
        when resuming from a certain point.
        """
        # For now, simple approach: detect and warn
        has_cycles, cycles = self.detect_cycles()
        
        if has_cycles:
            logger.warning(f"Workflow contains {len(cycles)} cycles")
            for cycle in cycles:
                logger.warning(f"  Cycle: {' -> '.join(cycle)}")
        
        return []
    
    def get_reachability(self, from_node: str) -> Set[str]:
        """
        Get all nodes reachable from a given node.
        
        Args:
            from_node: Starting node ID
            
        Returns:
            Set of all reachable node IDs
        """
        reachable: Set[str] = set()
        queue = deque([from_node])
        
        while queue:
            node_id = queue.popleft()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            
            for conn in self.adjacency.get(node_id, []):
                if conn.node not in reachable:
                    queue.append(conn.node)
        
        return reachable
    
    def get_executable_nodes(
        self,
        executed_nodes: Set[str],
        waiting_nodes: Set[str] = None
    ) -> List[str]:
        """
        Get nodes that can be executed next.
        
        Args:
            executed_nodes: Set of already executed node IDs
            waiting_nodes: Set of nodes waiting for data
            
        Returns:
            List of node IDs that can be executed
        """
        waiting_nodes = waiting_nodes or set()
        executable = []
        
        for node_id in self.nodes:
            if node_id in executed_nodes or node_id in waiting_nodes:
                continue
            
            # Check if all predecessors are executed
            predecessors = [conn.node for conn in self.reverse_adjacency.get(node_id, [])]
            
            if all(pred in executed_nodes for pred in predecessors):
                executable.append(node_id)
        
        return executable
    
    def _calculate_metadata(self) -> None:
        """Calculate graph metadata"""
        self.metadata.node_count = len(self.nodes)
        self.metadata.edge_count = sum(len(conns) for conns in self.adjacency.values())
        
        has_cycles, cycles = self.detect_cycles()
        self.metadata.has_cycles = has_cycles
        
        # Calculate topological order
        self.metadata.topological_order = self._topological_sort()
        
        # Calculate execution order (parallel groups)
        self.metadata.execution_order = self.get_execution_order()
    
    def _topological_sort(self) -> List[str]:
        """Kahn's algorithm for topological sorting"""
        in_degree: Dict[str, int] = {
            nid: len(self.reverse_adjacency.get(nid, [])) for nid in self.nodes
        }
        
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []
        
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            
            for conn in self.adjacency.get(node_id, []):
                target = conn.node
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)
        
        if len(result) != len(self.nodes):
            # Graph has cycles
            logger.warning("Cannot complete topological sort - graph contains cycles")
        
        return result
    
    def to_dict(self) -> Dict:
        """Serialize graph to dictionary"""
        return {
            'nodes': [
                {
                    'id': node.id,
                    'name': node.name,
                    'type': node.type,
                    'data': node.data
                }
                for node in self.nodes.values()
            ],
            'edges': [
                {
                    'source': source,
                    'target': conn.node,
                    'type': conn.type
                }
                for source, conns in self.adjacency.items()
                for conn in conns
            ],
            'metadata': {
                'node_count': self.metadata.node_count,
                'edge_count': self.metadata.edge_count,
                'has_cycles': self.metadata.has_cycles,
                'execution_order': self.metadata.execution_order
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# Partial Execution Support
# ─────────────────────────────────────────────────────────────────────────────

class PartialExecutionManager:
    """
    Manages partial execution state for resuming workflows.
    
    Reference: n8n partial-execution-utils/
    """
    
    def __init__(self, graph: DirectedGraph):
        self.graph = graph
        self.execution_data: Dict[str, Any] = {}
        self.node_states: Dict[str, NodeConnectionState] = {}
        self.waiting_on_nodes: Dict[str, Set[str]] = defaultdict(set)  # node -> waiting for these nodes
    
    def mark_node_started(self, node_id: str) -> None:
        """Mark a node as started"""
        self.node_states[node_id] = NodeConnectionState.EXECUTING
    
    def mark_node_completed(self, node_id: str, output_data: Dict = None) -> None:
        """Mark a node as completed"""
        self.node_states[node_id] = NodeConnectionState.EXECUTED
        if output_data:
            self.execution_data[node_id] = output_data
        
        # Check if any waiting nodes can proceed
        self._check_waiting_nodes()
    
    def mark_node_waiting(self, node_id: str, wait_for: List[str]) -> None:
        """Mark a node as waiting for other nodes"""
        self.node_states[node_id] = NodeConnectionState.WAITING
        for wait_node in wait_for:
            self.waiting_on_nodes[wait_node].add(node_id)
    
    def _check_waiting_nodes(self) -> None:
        """Check if any waiting nodes can now proceed"""
        newly_ready = []
        
        for node_id, state in self.node_states.items():
            if state == NodeConnectionState.WAITING:
                # Check if all dependencies are met
                dependencies = self.waiting_on_nodes.get(node_id, set())
                if all(self.node_states.get(dep) == NodeConnectionState.EXECUTED 
                       for dep in dependencies):
                    newly_ready.append(node_id)
        
        for node_id in newly_ready:
            self.node_states[node_id] = NodeConnectionState.NOT_EXECUTED
    
    def get_executable_nodes(self) -> List[str]:
        """Get nodes that can be executed next"""
        executed = {
            node_id for node_id, state in self.node_states.items()
            if state == NodeConnectionState.EXECUTED
        }
        
        return self.graph.get_executable_nodes(executed)
    
    def get_checkpoint_data(self) -> Dict:
        """Get current state for checkpointing"""
        return {
            'node_states': {n: s.value for n, s in self.node_states.items()},
            'execution_data': self.execution_data,
            'waiting_on_nodes': {k: list(v) for k, v in self.waiting_on_nodes.items()}
        }
    
    @classmethod
    def from_checkpoint(cls, graph: DirectedGraph, checkpoint: Dict) -> 'PartialExecutionManager':
        """Restore state from checkpoint"""
        manager = cls(graph)
        manager.node_states = {
            k: NodeConnectionState(v) for k, v in checkpoint.get('node_states', {}).items()
        }
        manager.execution_data = checkpoint.get('execution_data', {})
        manager.waiting_on_nodes = defaultdict(set, {
            k: set(v) for k, v in checkpoint.get('waiting_on_nodes', {}).items()
        })
        return manager


# ─────────────────────────────────────────────────────────────────────────────
# Graph Rewiring (for partial execution)
# ─────────────────────────────────────────────────────────────────────────────

def rewire_graph_for_partial_execution(
    graph: DirectedGraph,
    resume_from_node: str,
    executed_nodes: Set[str]
) -> DirectedGraph:
    """
    Rewire graph to allow execution from a specific node.
    
    Removes already-executed branches and reconnects edges
    to resume from the specified node.
    
    Reference: n8n partial-execution-utils/rewire-graph.ts
    """
    # Find all nodes that should be included
    included_nodes: Set[str] = set()
    
    # Start from resume node and find all reachable
    queue = deque([resume_from_node])
    while queue:
        node_id = queue.popleft()
        if node_id in included_nodes:
            continue
        included_nodes.add(node_id)
        
        # Add all outgoing edges
        for conn in graph.adjacency.get(node_id, []):
            if conn.node not in executed_nodes:
                queue.append(conn.node)
    
    # Also include any waiting nodes
    for node_id in list(included_nodes):
        for conn in graph.reverse_adjacency.get(node_id, []):
            if conn.node in graph.nodes and conn.node not in executed_nodes:
                included_nodes.add(conn.node)
    
    # Create subgraph
    return graph.find_subgraph(list(included_nodes))


def find_trigger_for_partial_execution(
    graph: DirectedGraph,
    target_node: str
) -> Optional[str]:
    """
    Find the trigger node that should fire for partial execution.
    
    Reference: n8n partial-execution-utils/find-trigger-for-partial-execution.ts
    """
    # Find all trigger nodes in the graph
    trigger_nodes = [
        node_id for node_id, node in graph.nodes.items()
        if node.type == 'trigger'
    ]
    
    if not trigger_nodes:
        return None
    
    # If target is directly reachable from a trigger, use that
    for trigger in trigger_nodes:
        reachable = graph.get_reachability(trigger)
        if target_node in reachable:
            return trigger
    
    # Otherwise, return the first trigger
    return trigger_nodes[0] if trigger_nodes else None
