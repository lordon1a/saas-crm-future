-- Migration: Add Workflow Execution Tables for Enterprise Features
-- 
-- Features:
-- - Partial execution (resume from failure)
-- - Concurrent workflow execution
-- - Execution history and debugging
--
-- Reference: ../n8n-master/packages/core/src/execution-engine/

-- 1. Workflow Executions Table
-- Tracks each workflow execution run
CREATE TABLE IF NOT EXISTS workflow_executions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflow_automations(id) ON DELETE CASCADE,
    
    -- Execution status
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    -- Values: 'new', 'running', 'paused', 'success', 'failed', 'cancelled'
    
    -- Execution mode
    mode VARCHAR(20) NOT NULL DEFAULT 'trigger',
    -- Values: 'trigger', 'webhook', 'scheduled', 'test', 'dry_run'
    
    -- Checkpoint data for partial execution (JSONB for PostgreSQL)
    checkpoint_data JSONB DEFAULT NULL,
    -- Stores: node_states, execution_data, waiting_on_nodes
    
    -- Run data (all node outputs)
    run_data JSONB DEFAULT NULL,
    -- Stores: {node_id: {output, status, started_at, completed_at}}
    
    -- Error info
    error_message TEXT DEFAULT NULL,
    error_node_id VARCHAR(100) DEFAULT NULL,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    paused_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    
    -- Retry info
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Context
    trigger_type VARCHAR(50) DEFAULT NULL,
    trigger_event_id VARCHAR(100) DEFAULT NULL,
    
    -- Indices for common queries
    CONSTRAINT workflow_executions_workflow_id_fkey 
        FOREIGN KEY (workflow_id) REFERENCES workflow_automations(id) ON DELETE CASCADE
);

CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_workflow_executions_started_at ON workflow_executions(started_at DESC);
CREATE INDEX idx_workflow_executions_workflow_status ON workflow_executions(workflow_id, status);

-- 2. Workflow Execution Data Table
-- Stores individual node execution data
CREATE TABLE IF NOT EXISTS workflow_execution_data (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER NOT NULL REFERENCES workflow_executions(id) ON DELETE CASCADE,
    node_id VARCHAR(100) NOT NULL,
    
    -- Input data (what this node received)
    input_data JSONB DEFAULT NULL,
    
    -- Output data (what this node produced)
    output_data JSONB DEFAULT NULL,
    
    -- Node configuration at execution time
    node_config JSONB DEFAULT NULL,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    -- Values: 'pending', 'running', 'success', 'failed', 'skipped'
    
    -- Error info
    error_message TEXT DEFAULT NULL,
    
    -- Execution order
    execution_order INTEGER DEFAULT 0,
    
    -- Checkpoint (can resume from this node)
    is_checkpoint BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT workflow_execution_data_execution_id_fkey 
        FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE CASCADE
);

CREATE INDEX idx_workflow_execution_data_execution_id ON workflow_execution_data(execution_id);
CREATE INDEX idx_workflow_execution_data_node_id ON workflow_execution_data(node_id);
CREATE INDEX idx_workflow_execution_data_execution_node ON workflow_execution_data(execution_id, node_id);

-- 3. Workflow Execution History Table
-- Lightweight history for recent executions (for performance)
CREATE TABLE IF NOT EXISTS workflow_execution_history (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL,
    execution_id INTEGER NOT NULL,
    
    -- Summary
    status VARCHAR(20) NOT NULL,
    duration_ms INTEGER DEFAULT 0,
    
    -- Node summary
    nodes_executed INTEGER DEFAULT 0,
    nodes_failed INTEGER DEFAULT 0,
    
    -- When
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_execution_history_workflow_id ON workflow_execution_history(workflow_id);
CREATE INDEX idx_workflow_execution_history_created_at ON workflow_execution_history(created_at DESC);

-- 4. Workflow Execution Locks Table
-- For concurrent execution coordination
CREATE TABLE IF NOT EXISTS workflow_execution_locks (
    workflow_id INTEGER PRIMARY KEY REFERENCES workflow_automations(id) ON DELETE CASCADE,
    locked_by_execution_id INTEGER DEFAULT NULL,
    locked_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    lock_type VARCHAR(20) DEFAULT 'exclusive',
    -- Values: 'exclusive', 'shared'
    
    max_concurrent INTEGER DEFAULT 1
);

-- 5. Add columns to existing workflow_automations table
-- These enhance the existing table for enterprise features
ALTER TABLE workflow_automations 
    ADD COLUMN IF NOT EXISTS static_data JSONB DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS concurrency_limit INTEGER DEFAULT 1;

-- 6. Workflow Credentials Table (encrypted)
CREATE TABLE IF NOT EXISTS workflow_credentials (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    -- Types: 'httpBasicAuth', 'httpHeaderAuth', 'oAuth2Api', 'apiKeyAuth', etc.
    
    -- Encrypted data (AES-256-GCM)
    encrypted_data TEXT NOT NULL,
    
    -- For key rotation
    encryption_version INTEGER DEFAULT 1,
    encrypted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Access control
    created_by INTEGER DEFAULT NULL,
    shared_with JSONB DEFAULT NULL,
    -- [{type: 'user', id: 123}, {type: 'workflow', id: 456}]
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT workflow_credentials_workspace_type_name_unique UNIQUE (workspace_id, type, name)
);

CREATE INDEX idx_workflow_credentials_workspace_id ON workflow_credentials(workspace_id);
CREATE INDEX idx_workflow_credentials_type ON workflow_credentials(type);

-- Comments for documentation
COMMENT ON TABLE workflow_executions IS 'Tracks each workflow execution run - equivalent to n8n execution table';
COMMENT ON TABLE workflow_execution_data IS 'Stores individual node execution data - equivalent to n8n executionData table';
COMMENT ON TABLE workflow_credentials IS 'Encrypted credentials storage - equivalent to n8n credentials table';
COMMENT ON COLUMN workflow_executions.checkpoint_data IS 'JSONB snapshot for resume capability - n8n recreateNodeExecutionStack()';
