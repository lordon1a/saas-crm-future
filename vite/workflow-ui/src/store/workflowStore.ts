import { create } from 'zustand'
import type { WorkflowItem, Execution, Stage, WorkflowNodeData } from '../types'

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

  searchQuery: '',
  setSearchQuery: (searchQuery) => set({ searchQuery }),

  selectedNodeId: null,
  selectedNodeData: null,
  setSelectedNode: (id, data = null) => set({ selectedNodeId: id, selectedNodeData: data }),

  stages: [],
  setStages: (stages) => set({ stages }),
}))
