import { useCallback, useRef, forwardRef, useImperativeHandle, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type ReactFlowInstance,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  MarkerType,
  ConnectionLineType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import WorkflowNode from './WorkflowNode'
import { useWorkflowStore } from '../store/workflowStore'
import { NODE_CONFIGS } from '../constants/nodeConfigs'
import type { CanvasData, WorkflowNodeData } from '../types'

const nodeTypes: NodeTypes = { workflowStep: WorkflowNode }

const VERTICAL_GAP = 180

function makeEdgeStyle(sourceHandle?: string | null) {
  if (sourceHandle === 'true') {
    return {
      stroke: '#22c55e', strokeWidth: 2.5, strokeLinecap: 'round' as const,
      strokeDasharray: undefined,
    }
  }
  if (sourceHandle === 'false') {
    return {
      stroke: '#ef4444', strokeWidth: 2.5, strokeLinecap: 'round' as const,
      strokeDasharray: '6 3',
    }
  }
  return { stroke: '#94a3b8', strokeWidth: 2, strokeLinecap: 'round' as const }
}

function makeEdgeDefaults(sourceHandle?: string | null): Partial<Edge> {
  const style = makeEdgeStyle(sourceHandle)
  const color = sourceHandle === 'true' ? '#22c55e' : sourceHandle === 'false' ? '#ef4444' : '#94a3b8'
  const label = sourceHandle === 'true' ? 'TRUE' : sourceHandle === 'false' ? 'FALSE' : undefined
  return {
    type: 'smoothstep' as const,
    style,
    markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
    label,
    labelStyle: { fontSize: 10, fontWeight: 700, fill: color },
    labelBgStyle: { fill: '#ffffff', fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
    labelBgBorderRadius: 3,
    animated: sourceHandle === 'true',
  }
}

const EDGE_DEFAULTS = makeEdgeDefaults()

function makeTriggerPlaceholder(): Node {
  return {
    id: 'trigger',
    type: 'workflowStep',
    position: { x: 250, y: 80 },
    data: { nodeType: 'trigger', subtype: '', label: '', isEmpty: true, hasNextStep: false },
  }
}

export interface WorkflowCanvasHandle {
  getCanvasData: () => CanvasData
  loadFromWorkflow: (canvasData: CanvasData) => void
  addNode: (subtype: string, parentNodeId?: string) => void
  updateNodeData: (nodeId: string, patch: Record<string, unknown>) => void
  clearCanvas: () => void
  fitView: () => void
}

const WorkflowCanvas = forwardRef<WorkflowCanvasHandle, object>((_props, ref) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([makeTriggerPlaceholder()])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const rfInstance = useRef<ReactFlowInstance | null>(null)
  const { setSelectedNode } = useWorkflowStore()

  // ── Listen for internal events from WorkflowNode ──
  useEffect(() => {
    const onRequestAdd = (e: Event) => {
      const { parentId } = (e as CustomEvent).detail as { parentId: string }
      // Open the palette-style add menu or just add a placeholder
      // For now, we'll dispatch to show a picker in the parent App
      window.dispatchEvent(new CustomEvent('wf:show-add-menu', { detail: { parentId } }))
    }

    const onRequestDelete = (e: Event) => {
      const { nodeId } = (e as CustomEvent).detail as { nodeId: string }
      if (nodeId === 'trigger') {
        // Reset trigger to empty placeholder instead of deleting it
        setNodes((prev) => prev.map((n) => n.id === 'trigger'
          ? { ...n, data: { nodeType: 'trigger', subtype: '', label: '', isEmpty: true, hasNextStep: false } }
          : n
        ))
        setEdges((prev) => prev.filter((e) => e.source !== 'trigger' && e.target !== 'trigger'))
        setSelectedNode(null)
        return
      }
      setNodes((prev) => {
        // Find parent of this node (node connected to it as source)
        const parentEdge = edges.find((edge) => edge.target === nodeId)
        if (parentEdge) {
          // Remove hasNextStep for parent if this was its only child
          const otherChildren = edges.filter((edge) => edge.source === parentEdge.source && edge.target !== nodeId)
          if (otherChildren.length === 0) {
            return prev
              .filter((n) => n.id !== nodeId)
              .map((n) => n.id === parentEdge.source ? { ...n, data: { ...n.data, hasNextStep: false } } : n)
          }
        }
        return prev.filter((n) => n.id !== nodeId)
      })
      setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelectedNode(null)
    }

    window.addEventListener('wf:request-add-node', onRequestAdd)
    window.addEventListener('wf:request-delete-node', onRequestDelete)
    return () => {
      window.removeEventListener('wf:request-add-node', onRequestAdd)
      window.removeEventListener('wf:request-delete-node', onRequestDelete)
    }
  }, [setNodes, setEdges, edges, setSelectedNode])

  const onConnect = useCallback(
    (params: Connection) => {
      if (params.source === params.target) return
      const edgeAttrs = makeEdgeDefaults(params.sourceHandle)
      setEdges((eds) => addEdge({
        ...params,
        ...edgeAttrs,
        id: `e-${params.source}-${params.sourceHandle ?? 'out'}-${params.target}`,
      }, eds))
    },
    [setEdges]
  )

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode(node.id, node.data as WorkflowNodeData)
    },
    [setSelectedNode]
  )

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [setSelectedNode])

  // ── Drag & Drop from palette ──
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const subtype = event.dataTransfer.getData('application/reactflow/subtype')
      if (!subtype || !rfInstance.current) return

      const position = rfInstance.current.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      const config = NODE_CONFIGS[subtype]
      if (!config) return

      const nodeType = config.color
      const newId = `step-${Date.now()}`

      const newNode: Node = {
        id: newId,
        type: 'workflowStep',
        position,
        data: {
          nodeType,
          subtype,
          label: config.title,
          isEmpty: false,
          hasNextStep: false,
          config: {},
        },
      }

      // If dropping a trigger, always replace the existing trigger node
      if (nodeType === 'trigger') {
        setNodes((prev) => {
          const existingTrigger = prev.find((n) => (n.data as WorkflowNodeData).nodeType === 'trigger')
          if (existingTrigger) {
            return prev.map((n) =>
              n.id === existingTrigger.id
                ? { ...n, data: { ...n.data, nodeType: 'trigger', subtype, label: config.title, isEmpty: false, config: {} } }
                : n
            )
          }
          return [...prev, newNode]
        })
      } else {
        setNodes((prev) => [...prev, newNode])
      }
    },
    [setNodes]
  )

  // ── Imperative handle for parent App ──
  useImperativeHandle(ref, () => ({
    getCanvasData: () => ({
      nodes: nodes.map((n) => ({
        id: n.id,
        position: n.position,
        data: n.data as WorkflowNodeData,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? undefined,
        targetHandle: e.targetHandle ?? undefined,
      })),
    }),

    loadFromWorkflow: (canvasData: CanvasData) => {
      if (!canvasData?.nodes?.length) {
        setNodes([makeTriggerPlaceholder()])
        setEdges([])
        return
      }
      setNodes(canvasData.nodes.map((n) => ({ ...n, type: 'workflowStep' })))
      setEdges(
        (canvasData.edges || []).map((e) => ({
          ...e,
          ...makeEdgeDefaults(e.sourceHandle),
        }))
      )
      setTimeout(() => rfInstance.current?.fitView({ padding: 0.3, duration: 300 }), 100)
    },

    addNode: (subtype: string, parentNodeId?: string) => {
      const config = NODE_CONFIGS[subtype]
      if (!config) return

      setNodes((prev) => {
        const parentId = parentNodeId ?? prev[prev.length - 1]?.id
        const parent = prev.find((n) => n.id === parentId)

        // If setting trigger, always replace existing trigger node
        if (config.color === 'trigger') {
          const existingTrigger = prev.find((n) => (n.data as WorkflowNodeData).nodeType === 'trigger')
          if (existingTrigger) {
            return prev.map((n) =>
              n.id === existingTrigger.id
                ? { ...n, data: { ...n.data, subtype, label: config.title, isEmpty: false, config: {} } }
                : n
            )
          }
        }

        const pos = parent
          ? { x: parent.position.x, y: parent.position.y + VERTICAL_GAP }
          : { x: 250, y: 80 }

        const newId = `step-${Date.now()}`
        const updated = prev.map((n) =>
          n.id === parentId ? { ...n, data: { ...n.data, hasNextStep: true } } : n
        )

        setEdges((eds) =>
          parent
            ? [...eds, { id: `e-${parentId}-out-${newId}`, source: parentId, target: newId, ...EDGE_DEFAULTS }]
            : eds
        )

        return [
          ...updated,
          {
            id: newId,
            type: 'workflowStep',
            position: pos,
            data: {
              nodeType: config.color,
              subtype,
              label: config.title,
              isEmpty: false,
              hasNextStep: false,
              config: {},
            },
          },
        ]
      })
    },

    updateNodeData: (nodeId: string, patch: Record<string, unknown>) => {
      setNodes((prev) =>
        prev.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n))
      )
    },

    clearCanvas: () => {
      setNodes([makeTriggerPlaceholder()])
      setEdges([])
      setSelectedNode(null)
      setTimeout(() => rfInstance.current?.fitView({ padding: 0.5, duration: 200 }), 80)
    },

    fitView: () => rfInstance.current?.fitView({ padding: 0.3, duration: 300 }),
  }))

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onDragOver={onDragOver}
        onDrop={onDrop}
        nodeTypes={nodeTypes}
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={true}
        deleteKeyCode="Delete"
        defaultViewport={{ x: 80, y: 40, zoom: 0.9 }}
        onInit={(instance) => { rfInstance.current = instance }}
        onContextMenu={(e) => e.preventDefault()}
        snapToGrid
        snapGrid={[20, 20]}
        connectionLineStyle={{ stroke: '#ef4444', strokeWidth: 3 }}
        connectionLineType={ConnectionLineType.Bezier}
        defaultEdgeOptions={EDGE_DEFAULTS}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.2} color="#e2e8f0" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeStrokeWidth={2}
          nodeColor={(n) => {
            const d = n.data as WorkflowNodeData
            return d.nodeType === 'trigger' ? '#3b82f6'
              : d.nodeType === 'condition' ? '#f59e0b'
              : '#22c55e'
          }}
          pannable
          zoomable
          style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}
        />
      </ReactFlow>
    </div>
  )
})

WorkflowCanvas.displayName = 'WorkflowCanvas'

export default WorkflowCanvas
