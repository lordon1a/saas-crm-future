/**
 * WebSocket Execution Service
 * ==========================
 * Real-time workflow execution updates
 * 
 * Reference: ../n8n-master/packages/core/src/WebSocketManager.ts
 */

import { useWorkflowStore } from './workflowStore'
import { workflowApi } from '../api/workflows'

export interface ExecutionUpdate {
  type: 'node_started' | 'node_finished' | 'node_error' | 'execution_complete' | 'execution_failed'
  executionId: number
  nodeId?: string
  data?: {
    status?: string
    output?: Record<string, unknown>
    error?: string
    duration_ms?: number
    progress?: number
  }
}

export interface ExecutionState {
  executionId: number | null
  isRunning: boolean
  currentNodeId: string | null
  nodeResults: Map<string, {
    status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
    output?: Record<string, unknown>
    error?: string
    startedAt?: Date
    completedAt?: Date
  }>
}

type ExecutionCallback = (update: ExecutionUpdate) => void

class ExecutionSocket {
  private socket: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private callbacks: Set<ExecutionCallback> = new Set()
  private state: ExecutionState = {
    executionId: null,
    isRunning: false,
    currentNodeId: null,
    nodeResults: new Map()
  }
  private pollingInterval: ReturnType<typeof setInterval> | null = null

  constructor() {
    // Bind methods
    this.connect = this.connect.bind(this)
    this.disconnect = this.disconnect.bind(this)
    this.handleMessage = this.handleMessage.bind(this)
    this.handleOpen = this.handleOpen.bind(this)
    this.handleClose = this.handleClose.bind(this)
    this.handleError = this.handleError.bind(this)
  }

  /**
   * Connect to WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/execution`
      
      try {
        this.socket = new WebSocket(wsUrl)
        
        this.socket.onopen = (e) => {
          console.log('[ExecutionSocket] Connected')
          this.reconnectAttempts = 0
          this.handleOpen(e)
          resolve()
        }
        
        this.socket.onmessage = this.handleMessage
        this.socket.onclose = this.handleClose
        this.socket.onerror = this.handleError
        
      } catch (error) {
        console.error('[ExecutionSocket] Connection failed:', error)
        reject(error)
      }
    })
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval)
      this.pollingInterval = null
    }
    
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
    
    this.state = {
      executionId: null,
      isRunning: false,
      currentNodeId: null,
      nodeResults: new Map()
    }
  }

  /**
   * Subscribe to execution updates
   */
  subscribe(callback: ExecutionCallback): () => void {
    this.callbacks.add(callback)
    return () => this.callbacks.delete(callback)
  }

  /**
   * Start polling for execution updates (fallback when WebSocket not available)
   */
  startPolling(executionId: number): void {
    this.state.executionId = executionId
    this.state.isRunning = true
    
    // Poll every 500ms
    this.pollingInterval = setInterval(async () => {
      if (!this.state.isRunning) {
        if (this.pollingInterval) {
          clearInterval(this.pollingInterval)
          this.pollingInterval = null
        }
        return
      }
      
      try {
        const result = await workflowApi.execute(executionId)
        
        // Process results
        result.node_results.forEach(node => {
          this.state.nodeResults.set(node.node_id, {
            status: node.status,
            output: node.output,
            error: node.error,
            startedAt: new Date(node.started_at),
            completedAt: node.completed_at ? new Date(node.completed_at) : undefined
          })
          
          this.notifyCallbacks({
            type: node.status === 'failed' ? 'node_error' : 
                  node.status === 'running' ? 'node_started' : 'node_finished',
            executionId,
            nodeId: node.node_id,
            data: {
              status: node.status,
              output: node.output,
              error: node.error,
              duration_ms: node.duration_ms
            }
          })
        })
        
        if (result.status === 'success' || result.status === 'failed') {
          this.state.isRunning = false
          this.notifyCallbacks({
            type: result.status === 'failed' ? 'execution_failed' : 'execution_complete',
            executionId,
            data: {
              status: result.status,
              progress: 100
            }
          })
          
          if (this.pollingInterval) {
            clearInterval(this.pollingInterval)
            this.pollingInterval = null
          }
        }
        
        // Update store
        const store = useWorkflowStore.getState()
        store.setExecutionState({
          isRunning: this.state.isRunning,
          currentNodeId: this.state.currentNodeId,
          nodeResults: Object.fromEntries(this.state.nodeResults)
        })
        
      } catch (error) {
        console.error('[ExecutionSocket] Polling error:', error)
      }
    }, 500)
  }

  /**
   * Stop polling
   */
  stopPolling(): void {
    this.state.isRunning = false
    
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval)
      this.pollingInterval = null
    }
  }

  /**
   * Handle WebSocket open
   */
  private handleOpen(_event: Event): void {
    console.log('[ExecutionSocket] WebSocket opened')
  }

  /**
   * Handle WebSocket close
   */
  private handleClose(event: CloseEvent): void {
    console.log('[ExecutionSocket] WebSocket closed:', event.code, event.reason)
    
    // Attempt reconnect
    if (this.state.isRunning && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
      
      console.log(`[ExecutionSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
      
      setTimeout(() => {
        this.connect().catch(console.error)
      }, delay)
    }
  }

  /**
   * Handle WebSocket error
   */
  private handleError(event: Event): void {
    console.error('[ExecutionSocket] WebSocket error:', event)
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as ExecutionUpdate
      
      // Update local state
      if (data.nodeId) {
        this.state.currentNodeId = data.nodeId
        
        const existing = this.state.nodeResults.get(data.nodeId) || {
          status: 'pending' as const
        }
        
        this.state.nodeResults.set(data.nodeId, {
          ...existing,
          ...(data.type === 'node_started' && { status: 'running' as const, startedAt: new Date() }),
          ...(data.type === 'node_finished' && { status: 'success' as const, completedAt: new Date() }),
          ...(data.type === 'node_error' && { status: 'failed' as const, error: data.data?.error, completedAt: new Date() }),
          ...(data.data?.output && { output: data.data.output })
        })
      }
      
      if (data.type === 'execution_complete' || data.type === 'execution_failed') {
        this.state.isRunning = false
        this.state.currentNodeId = null
      }
      
      // Update global store
      const store = useWorkflowStore.getState()
      store.setExecutionState({
        isRunning: this.state.isRunning,
        currentNodeId: this.state.currentNodeId,
        nodeResults: Object.fromEntries(this.state.nodeResults)
      })
      
      // Notify callbacks
      this.notifyCallbacks(data)
      
    } catch (error) {
      console.error('[ExecutionSocket] Failed to parse message:', error)
    }
  }

  /**
   * Notify all subscribers
   */
  private notifyCallbacks(update: ExecutionUpdate): void {
    this.callbacks.forEach(callback => {
      try {
        callback(update)
      } catch (error) {
        console.error('[ExecutionSocket] Callback error:', error)
      }
    })
  }

  /**
   * Send message to server
   */
  send(data: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data))
    }
  }

  /**
   * Get current execution state
   */
  getState(): ExecutionState {
    return { ...this.state }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN
  }
}

// Singleton instance
export const executionSocket = new ExecutionSocket()
