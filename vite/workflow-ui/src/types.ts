export type NodeType = 'trigger' | 'condition' | 'action'

export interface NodeConfig {
  label: string
  title: string
  icon: string        // FontAwesome class (without fa- prefix for palette, with for node)
  faIcon: string      // Full FontAwesome class e.g. "fa-user-plus"
  color: NodeType
  iconBg: string      // icon box background color
  iconColor: string   // icon foreground color
  fields: FieldConfig[]
}

export interface FieldConfig {
  key: string
  label: string
  type: 'text' | 'number' | 'select' | 'textarea' | 'stage_select'
  options?: { value: string; label: string }[]
  default?: string | number | boolean
  placeholder?: string
}

export interface WorkflowNodeData extends Record<string, unknown> {
  nodeType?: NodeType
  subtype: string
  label?: string
  description?: string
  isEmpty?: boolean
  hasNextStep?: boolean
  config?: Record<string, string | number | boolean>
}

export interface WorkflowItem {
  id: number
  name: string
  description?: string
  is_active: boolean
  trigger_type: string
  trigger_config?: Record<string, unknown>
  condition_logic?: string
  run_count: number
  last_run_at: string | null
  created_at?: string
  updated_at?: string
  conditions_count: number
  actions_count: number
  canvas_data?: CanvasData
  conditions?: Condition[]
  actions?: Action[]
}

export interface Condition {
  id?: number
  field_name: string
  operator: string
  value: string
  order_index: number
}

export interface Action {
  id?: number
  action_type: string
  action_config: Record<string, unknown>
  delay_minutes: number
  order_index: number
}

export interface CanvasData {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
}

export interface CanvasNode {
  id: string
  position: { x: number; y: number }
  data: WorkflowNodeData
}

export interface CanvasEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
}

export interface Execution {
  id: number
  status: 'completed' | 'failed' | 'pending' | 'running'
  entity_type: string
  entity_id: number
  entity_name?: string
  trigger_type?: string
  triggered_by?: string
  started_at: string
  completed_at?: string
  error_message?: string
  actions_executed?: unknown[]
}

export interface Stage {
  id: number
  name: string
}
