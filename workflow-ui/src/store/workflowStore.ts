import { create } from 'zustand'
import type { WorkflowItem, Execution, Stage, WorkflowNodeData } from '../types'

// Execution log entry for live output panel
export interface ExecutionLogEntry {
  id: string
  nodeId: string
  nodeName: string
  nodeType: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  startedAt: string
  completedAt?: string
  durationMs?: number
  output?: unknown
  error?: string
}

// Node execution result for real-time display
export interface NodeExecutionResult {
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  output?: Record<string, unknown>
  error?: string
  startedAt?: Date
  completedAt?: Date
}

interface ExecutionState {
  isRunning: boolean
  currentNodeId: string | null
  nodeResults: Record<string, NodeExecutionResult>
}

interface WorkflowStore {
  // Workflow list
  workflows: WorkflowItem[]
  setWorkflows: (workflows: WorkflowItem[]) => void

  // Selected workflow
  selectedWorkflow: WorkflowItem | null
  setSelectedWorkflow: (workflow: WorkflowItem | null) => void

  // UI state
  activeTab: 'canvas' | 'history'
  setActiveTab: (tab: 'canvas' | 'history') => void

  isBuilderOpen: boolean
  setBuilderOpen: (open: boolean) => void

  isSaving: boolean
  setIsSaving: (saving: boolean) => void

  // Executions
  executions: Execution[]
  setExecutions: (executions: Execution[]) => void

  // Live execution state (real-time node status)
  executionState: ExecutionState
  setExecutionState: (state: Partial<ExecutionState>) => void
  clearExecutionState: () => void

  // Live execution output (legacy - still used for history)
  isExecuting: boolean
  setIsExecuting: (executing: boolean) => void
  executionLogs: ExecutionLogEntry[]
  addExecutionLog: (log: ExecutionLogEntry) => void
  updateExecutionLog: (id: string, update: Partial<ExecutionLogEntry>) => void
  clearExecutionLogs: () => void

  // Search
  searchQuery: string
  setSearchQuery: (query: string) => void

  // Selected node for properties panel
  selectedNodeId: string | null
  selectedNodeData: WorkflowNodeData | null
  setSelectedNode: (id: string | null, data?: WorkflowNodeData | null) => void

  // Pipeline stages (for stage_select fields)
  stages: Stage[]
  setStages: (stages: Stage[]) => void
}

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  workflows: [],
  setWorkflows: (workflows) => set({ workflows }),

  selectedWorkflow: null,
  setSelectedWorkflow: (selectedWorkflow) => set({ selectedWorkflow }),

  activeTab: 'canvas',
  setActiveTab: (activeTab) => set({ activeTab }),

  isBuilderOpen: false,
  setBuilderOpen: (isBuilderOpen) => set({ isBuilderOpen }),

  isSaving: false,
  setIsSaving: (isSaving) => set({ isSaving }),

  executions: [],
  setExecutions: (executions) => set({ executions }),

  // Execution state
  executionState: {
    isRunning: false,
    currentNodeId: null,
    nodeResults: {}
  },
  setExecutionState: (newState) => set((state) => ({
    executionState: { ...state.executionState, ...newState }
  })),
  clearExecutionState: () => set({
    executionState: {
      isRunning: false,
      currentNodeId: null,
      nodeResults: {}
    }
  }),

  isExecuting: false,
  setIsExecuting: (isExecuting) => set({ isExecuting }),

  executionLogs: [],
  addExecutionLog: (log) => set((state) => ({
    executionLogs: [...state.executionLogs, log]
  })),
  updateExecutionLog: (id, update) => set((state) => ({
    executionLogs: state.executionLogs.map((log) =>
      log.id === id ? { ...log, ...update } : log
    )
  })),
  clearExecutionLogs: () => set({ executionLogs: [] }),

  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),

  selectedNodeId: null,
  selectedNodeData: null,
  setSelectedNode: (id, data = null) => set({ selectedNodeId: id, selectedNodeData: data }),

  stages: [],
  setStages: (stages) => set({ stages }),
}))
