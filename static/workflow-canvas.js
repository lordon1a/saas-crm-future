/**
 * Workflow Canvas - ReactFlow Integration
 * Visual workflow builder using ReactFlow via CDN
 */

// ═══════════════════════════════════════════════════════════════════════════════
// PART A: NODE_CONFIGS - Configuration for all node types
// ═══════════════════════════════════════════════════════════════════════════════

const NODE_CONFIGS = {
    // TRIGGERS
    contact_created: {
        label: 'Tetikleyici',
        title: 'Yeni Kişi Oluşturuldu',
        icon: '👤',
        color: 'trigger',
        fields: []
    },
    deal_created: {
        label: 'Tetikleyici',
        title: 'Yeni Anlaşma Oluşturuldu',
        icon: '💰',
        color: 'trigger',
        fields: []
    },
    deal_stage_changed: {
        label: 'Tetikleyici',
        title: 'Anlaşma Aşaması Değişti',
        icon: '🔄',
        color: 'trigger',
        fields: [
            { key: 'from_stage_id', label: 'Önceki Aşama', type: 'stage_select', default: null },
            { key: 'to_stage_id', label: 'Yeni Aşama', type: 'stage_select', default: null }
        ]
    },
    deal_won: {
        label: 'Tetikleyici',
        title: 'Anlaşma Kazanıldı',
        icon: '🏆',
        color: 'trigger',
        fields: []
    },
    deal_lost: {
        label: 'Tetikleyici',
        title: 'Anlaşma Kaybedildi',
        icon: '❌',
        color: 'trigger',
        fields: []
    },
    contact_no_activity: {
        label: 'Tetikleyici',
        title: 'Kişi Hareketsiz',
        icon: '⏰',
        color: 'trigger',
        fields: [
            { key: 'days', label: 'Gün Sayısı', type: 'number', default: 30, placeholder: '30' },
            { key: 'min_lead_score', label: 'Min Lead Skoru', type: 'number', default: 0, placeholder: '0' }
        ]
    },
    task_completed: {
        label: 'Tetikleyici',
        title: 'Görev Tamamlandı',
        icon: '✅',
        color: 'trigger',
        fields: []
    },
    deal_close_date_approaching: {
        label: 'Tetikleyici',
        title: 'Kapanış Tarihi Yaklaşıyor',
        icon: '📅',
        color: 'trigger',
        fields: [
            { key: 'days_before', label: 'Kaç Gün Önce', type: 'number', default: 3, placeholder: '3' }
        ]
    },

    // CONDITIONS
    check_field: {
        label: 'Koşul',
        title: 'Alan Kontrolü',
        icon: '📋',
        color: 'condition',
        fields: [
            { key: 'field_name', label: 'Alan Adı', type: 'text', default: '', placeholder: 'lead_score' },
            { key: 'operator', label: 'Operatör', type: 'select', default: 'equals', options: [
                { value: 'equals', label: 'Eşittir' },
                { value: 'not_equals', label: 'Eşit Değil' },
                { value: 'greater_than', label: 'Büyüktür' },
                { value: 'less_than', label: 'Küçüktür' },
                { value: 'contains', label: 'İçerir' }
            ]},
            { key: 'value', label: 'Değer', type: 'text', default: '', placeholder: 'Değer' }
        ]
    },
    check_score: {
        label: 'Koşul',
        title: 'Skor Kontrolü',
        icon: '📊',
        color: 'condition',
        fields: [
            { key: 'min_score', label: 'Minimum Skor', type: 'number', default: 50, placeholder: '50' },
            { key: 'max_score', label: 'Maksimum Skor', type: 'number', default: 100, placeholder: '100' }
        ]
    },

    // ACTIONS
    create_task: {
        label: 'Aksiyon',
        title: 'Görev Oluştur',
        icon: '📝',
        color: 'action',
        fields: [
            { key: 'title', label: 'Görev Başlığı', type: 'text', default: '{{contact.first_name}} ile takip', placeholder: 'Görev başlığı' },
            { key: 'due_in_days', label: 'Kaç Gün Sonra', type: 'number', default: 2, placeholder: '2' },
            { key: 'assign_to', label: 'Atanacak Kişi', type: 'select', default: 'contact_owner', options: [
                { value: 'contact_owner', label: 'Kişi Sahibi' },
                { value: 'deal_owner', label: 'Anlaşma Sahibi' }
            ]}
        ]
    },
    send_email: {
        label: 'Aksiyon',
        title: 'E-posta Gönder',
        icon: '📧',
        color: 'action',
        fields: [
            { key: 'subject', label: 'Konu', type: 'text', default: '', placeholder: 'E-posta konusu' },
            { key: 'body', label: 'İçerik', type: 'textarea', default: '', placeholder: 'E-posta içeriği' }
        ]
    },
    notify_owner: {
        label: 'Aksiyon',
        title: 'Sahibi Bilgilendir',
        icon: '🔔',
        color: 'action',
        fields: [
            { key: 'message', label: 'Mesaj', type: 'textarea', default: '', placeholder: 'Bildirim mesajı ({{contact.full_name}} kullanabilirsiniz)' }
        ]
    },
    update_deal_stage: {
        label: 'Aksiyon',
        title: 'Anlaşma Aşamasını Güncelle',
        icon: '🔄',
        color: 'action',
        fields: [
            { key: 'stage_id', label: 'Yeni Aşama', type: 'stage_select', default: null }
        ]
    },
    update_contact_field: {
        label: 'Aksiyon',
        title: 'Kişi Alanını Güncelle',
        icon: '✏️',
        color: 'action',
        fields: [
            { key: 'field_name', label: 'Alan Adı', type: 'text', default: '', placeholder: 'lead_score' },
            { key: 'field_value', label: 'Yeni Değer', type: 'text', default: '', placeholder: 'Değer' }
        ]
    },
    create_note: {
        label: 'Aksiyon',
        title: 'Not Ekle',
        icon: '📌',
        color: 'action',
        fields: [
            { key: 'note_content', label: 'Not İçeriği', type: 'textarea', default: '', placeholder: 'Not içeriği' }
        ]
    },
    wait: {
        label: 'Aksiyon',
        title: 'Bekle',
        icon: '⏳',
        color: 'action',
        fields: [
            { key: 'delay_minutes', label: 'Dakika', type: 'number', default: 60, placeholder: '60' }
        ]
    }
};

// ═══════════════════════════════════════════════════════════════════════════════
// PART B: Custom Node React Component
// ═══════════════════════════════════════════════════════════════════════════════

const { useState, useCallback, useEffect, useRef } = React;
const RF = window.ReactFlow || {};
const ReactFlow = RF.default || RF.ReactFlow || RF;
const { Background, Controls, MiniMap, useNodesState, useEdgesState, addEdge, Handle, Position } = RF;

function WorkflowNodeComponent({ id, data, selected }) {
    const config = NODE_CONFIGS[data.subtype] || {};
    
    const handleDoubleClick = () => {
        if (window.WorkflowCanvas) {
            window.WorkflowCanvas.openProperties(id, data);
        }
    };
    
    const handleDelete = (e) => {
        e.stopPropagation();
        if (window.WorkflowCanvas) {
            window.WorkflowCanvas.deleteNode(id);
        }
    };
    
    // Get first config value for summary (max 1 line, truncated)
    const configSummary = data.config && Object.keys(data.config).length > 0
        ? `${Object.keys(data.config)[0]}: ${String(Object.values(data.config)[0]).substring(0, 30)}`
        : '';
    
    return React.createElement('div', {
        className: `wf-node ${config.color} ${selected ? 'selected' : ''}`,
        onDoubleClick: handleDoubleClick
    }, [
        // Top handle (target) - hidden for triggers
        data.type !== 'trigger' && React.createElement(Handle, {
            key: 'handle-top',
            type: 'target',
            position: Position.Top,
            style: { width: 12, height: 12, background: '#ffffff', border: '2px solid #9ca3af', borderRadius: '50%' }
        }),
        
        // Delete button (appears on hover)
        React.createElement('button', {
            key: 'delete',
            onClick: handleDelete,
            className: 'wf-node-delete-btn',
            title: 'Sil'
        }, '✕'),
        
        // Header with colored background
        React.createElement('div', { key: 'header', className: `wf-node-header ${config.color}` }, [
            React.createElement('div', { 
                key: 'icon',
                className: `wf-node-icon-box ${config.color}` 
            }, config.icon),
            React.createElement('div', { key: 'meta', className: 'wf-node-meta' }, [
                React.createElement('div', { key: 'type', className: 'wf-node-type' }, config.label),
                React.createElement('div', { key: 'name', className: 'wf-node-name' }, config.title)
            ])
        ]),
        
        // Body (config summary if exists)
        configSummary && React.createElement('div', { key: 'body', className: 'wf-node-body' },
            React.createElement('div', { className: 'wf-node-config-summary' }, configSummary)
        ),
        
        // Bottom handle(s) (source)
        data.type === 'condition' ? [
            React.createElement(Handle, {
                key: 'handle-yes',
                type: 'source',
                position: Position.Bottom,
                id: 'yes',
                style: { background: '#ffffff', left: '30%', width: 12, height: 12, border: '2px solid #22c55e', borderRadius: '50%' }
            }),
            React.createElement('div', {
                key: 'label-yes',
                style: { position: 'absolute', bottom: -20, left: '30%', transform: 'translateX(-50%)', fontSize: 10, color: '#22c55e', fontWeight: 600 }
            }, 'Evet'),
            React.createElement(Handle, {
                key: 'handle-no',
                type: 'source',
                position: Position.Bottom,
                id: 'no',
                style: { background: '#ffffff', left: '70%', width: 12, height: 12, border: '2px solid #ef4444', borderRadius: '50%' }
            }),
            React.createElement('div', {
                key: 'label-no',
                style: { position: 'absolute', bottom: -20, left: '70%', transform: 'translateX(-50%)', fontSize: 10, color: '#ef4444', fontWeight: 600 }
            }, 'Hayır')
        ] : React.createElement(Handle, {
            key: 'handle-bottom',
            type: 'source',
            position: Position.Bottom,
            style: { background: '#ffffff', width: 12, height: 12, border: '2px solid #9ca3af', borderRadius: '50%' }
        })
    ]);
}

// ═══════════════════════════════════════════════════════════════════════════════
// PART C: WorkflowApp React Component
// ═══════════════════════════════════════════════════════════════════════════════

function WorkflowApp() {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [reactFlowInstance, setReactFlowInstance] = useState(null);
    const autoSaveTimeoutRef = useRef(null);
    
    const nodeTypes = {
        workflowNode: WorkflowNodeComponent
    };
    
    // Auto-save when nodes or edges change (debounced)
    useEffect(() => {
        // Clear existing timeout
        if (autoSaveTimeoutRef.current) {
            clearTimeout(autoSaveTimeoutRef.current);
        }
        
        // Only auto-save if we have a workflow ID (editing existing workflow)
        if (window.WorkflowCanvas && window.WorkflowCanvas.currentWorkflowId && nodes.length > 0) {
            autoSaveTimeoutRef.current = setTimeout(() => {
                console.log('Auto-saving canvas positions...');
                window.WorkflowCanvas.autoSaveCanvasData();
            }, 2000); // 2 second debounce
        }
        
        return () => {
            if (autoSaveTimeoutRef.current) {
                clearTimeout(autoSaveTimeoutRef.current);
            }
        };
    }, [nodes, edges]);
    
    const onConnect = useCallback((params) => {
        const newEdge = {
            ...params,
            type: 'smoothstep',
            animated: false,
            style: { stroke: '#9ca3af', strokeWidth: 2 },
            markerEnd: { type: 'arrowclosed', color: '#9ca3af', width: 14, height: 14 }
        };
        setEdges((eds) => addEdge(newEdge, eds));
    }, [setEdges]);
    
    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);
    
    const onDrop = useCallback((event) => {
        event.preventDefault();
        
        const nodeType = event.dataTransfer.getData('application/reactflow-nodetype');
        const nodeSubtype = event.dataTransfer.getData('application/reactflow-nodesubtype');
        
        console.log('Drop event:', { nodeType, nodeSubtype, hasInstance: !!reactFlowInstance });
        
        if (!nodeType || !nodeSubtype) {
            console.log('Missing node type or subtype');
            return;
        }
        
        // Calculate position - if no instance yet, use default position
        let position = { x: 250, y: 100 };
        
        if (reactFlowInstance) {
            try {
                const reactFlowBounds = event.target.getBoundingClientRect();
                position = reactFlowInstance.project({
                    x: event.clientX - reactFlowBounds.left,
                    y: event.clientY - reactFlowBounds.top,
                });
            } catch (err) {
                console.warn('Could not calculate position, using default', err);
            }
        }
        
        console.log('Calculated position:', position);
        
        const newNode = {
            id: `node_${Date.now()}`,
            type: 'workflowNode',
            position,
            data: {
                type: nodeType,
                subtype: nodeSubtype,
                config: {}
            }
        };
        
        console.log('Adding new node:', newNode);
        setNodes((nds) => nds.concat(newNode));
    }, [reactFlowInstance, setNodes]);
    
    // Expose methods to global WorkflowCanvas object
    useEffect(() => {
        if (window.WorkflowCanvas) {
            window.WorkflowCanvas._setNodes = setNodes;
            window.WorkflowCanvas._setEdges = setEdges;
            window.WorkflowCanvas._getNodes = () => nodes;
            window.WorkflowCanvas._getEdges = () => edges;
        }
    }, [nodes, edges, setNodes, setEdges]);
    
    // Handle ReactFlow instance ready
    const onLoadHandler = useCallback((instance) => {
        console.log('ReactFlow instance loaded');
        setReactFlowInstance(instance);
    }, []);
    
    return React.createElement(ReactFlow, {
        nodes,
        edges,
        onNodesChange,
        onEdgesChange,
        onConnect,
        onDrop,
        onDragOver,
        onLoad: onLoadHandler,
        nodeTypes,
        defaultViewport: { x: 80, y: 80, zoom: 0.9 },
        fitView: false,
        style: { background: '#f8f8f8', width: '100%', height: '100%' }
    }, [
        React.createElement(Background, { key: 'bg', variant: 'dots', gap: 24, size: 1.5, color: '#d1d5db' }),
        React.createElement(Controls, { key: 'controls' })
    ]);
}

// ═══════════════════════════════════════════════════════════════════════════════
// PART D: WorkflowCanvas Global Object
// ═══════════════════════════════════════════════════════════════════════════════

window.WorkflowCanvas = {
    currentWorkflowId: null,
    reactRoot: null,
    _setNodes: null,
    _setEdges: null,
    _getNodes: null,
    _getEdges: null,
    
    /**
     * Initialize the workflow canvas
     */
    init() {
        console.log('WorkflowCanvas: Initializing...');
        
        // Check if ReactFlow is available
        if (!window.ReactFlow) {
            console.error('WorkflowCanvas: ReactFlow library not loaded');
            const container = document.getElementById('react-workflow-root');
            if (container) {
                container.innerHTML = '<div class="flex items-center justify-center h-full text-red-500"><p>ReactFlow kütüphanesi yüklenemedi. Lütfen sayfayı yenileyin.</p></div>';
            }
            return;
        }
        
        try {
            // Mount React app
            const container = document.getElementById('react-workflow-root');
            if (!container) {
                console.error('WorkflowCanvas: react-workflow-root not found');
                return;
            }
            
            this.reactRoot = ReactDOM.createRoot(container);
            this.reactRoot.render(React.createElement(WorkflowApp));
            
            // Setup drag events on palette items
            this.setupPaletteDrag();
            
            // Setup tab switching
            this.setupTabs();
            
            // Setup button handlers
            this.setupButtons();
            
            console.log('WorkflowCanvas: Initialized successfully');
        } catch (error) {
            console.error('WorkflowCanvas: Initialization failed', error);
            const container = document.getElementById('react-workflow-root');
            if (container) {
                container.innerHTML = '<div class="flex items-center justify-center h-full text-red-500"><p>ReactFlow yüklenemedi. Lütfen sayfayı yenileyin.</p></div>';
            }
        }
    },
    
    /**
     * Setup drag events for palette items
     */
    setupPaletteDrag() {
        const paletteItems = document.querySelectorAll('.node-palette-item');
        console.log('Setting up drag for', paletteItems.length, 'palette items');
        
        paletteItems.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                const nodeType = e.target.closest('.node-palette-item').dataset.nodeType;
                const nodeSubtype = e.target.closest('.node-palette-item').dataset.nodeSubtype;
                
                console.log('Drag started:', { nodeType, nodeSubtype });
                
                e.dataTransfer.setData('application/reactflow-nodetype', nodeType);
                e.dataTransfer.setData('application/reactflow-nodesubtype', nodeSubtype);
                e.dataTransfer.effectAllowed = 'move';
            });
        });
    },
    
    /**
     * Setup tab switching
     */
    setupTabs() {
        const canvasTab = document.getElementById('canvasTab');
        const historyTab = document.getElementById('historyTab');
        const canvasContent = document.getElementById('canvasTabContent');
        const historyContent = document.getElementById('historyTabContent');
        
        if (canvasTab) {
            canvasTab.addEventListener('click', () => {
                canvasTab.classList.add('text-brand-600', 'border-brand-600');
                canvasTab.classList.remove('text-slate-500', 'border-transparent');
                historyTab.classList.remove('text-brand-600', 'border-brand-600');
                historyTab.classList.add('text-slate-500', 'border-transparent');
                canvasContent.classList.remove('hidden');
                historyContent.classList.add('hidden');
            });
        }
        
        if (historyTab) {
            historyTab.addEventListener('click', () => {
                historyTab.classList.add('text-brand-600', 'border-brand-600');
                historyTab.classList.remove('text-slate-500', 'border-transparent');
                canvasTab.classList.remove('text-brand-600', 'border-brand-600');
                canvasTab.classList.add('text-slate-500', 'border-transparent');
                historyContent.classList.remove('hidden');
                canvasContent.classList.add('hidden');
                
                // Load executions when switching to history tab
                if (this.currentWorkflowId) {
                    this.loadExecutions(this.currentWorkflowId);
                }
            });
        }
    },
    
    /**
     * Setup button handlers
     */
    setupButtons() {
        const saveBtn = document.getElementById('saveWorkflow');
        const deleteBtn = document.getElementById('deleteWorkflow');
        const closeBtn = document.getElementById('closeBuilder');
        const closePropsBtn = document.getElementById('closeProperties');
        
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveWorkflow());
        }
        
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => this.deleteWorkflow());
        }
        
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                document.getElementById('workflowBuilder').classList.add('hidden');
                document.getElementById('emptyState').classList.remove('hidden');
                this.currentWorkflowId = null;
            });
        }
        
        if (closePropsBtn) {
            closePropsBtn.addEventListener('click', () => this.closeProperties());
        }
    },
    
    /**
     * Load workflow data onto canvas
     */
    loadWorkflow(workflowData) {
        console.log('WorkflowCanvas: Loading workflow', workflowData);
        
        this.currentWorkflowId = workflowData.id;
        
        // Show builder panel
        document.getElementById('workflowBuilder').classList.remove('hidden');
        document.getElementById('emptyState').classList.add('hidden');
        
        // Populate form fields
        document.getElementById('workflowId').value = workflowData.id || '';
        document.getElementById('workflowName').value = workflowData.name || '';
        document.getElementById('workflowActive').checked = workflowData.is_active !== false;
        
        let nodes = [];
        let edges = [];
        
        // Check if canvas_data exists (saved positions)
        if (workflowData.canvas_data && workflowData.canvas_data.nodes && workflowData.canvas_data.nodes.length > 0) {
            console.log('Loading from canvas_data');
            // Use saved canvas positions
            nodes = workflowData.canvas_data.nodes.map(node => ({
                id: node.id,
                type: 'workflowNode',
                position: node.position,
                data: node.data
            }));
            
            edges = workflowData.canvas_data.edges.map(edge => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
                sourceHandle: edge.sourceHandle,
                targetHandle: edge.targetHandle,
                type: 'smoothstep',
                animated: false,
                style: { stroke: '#9ca3af', strokeWidth: 2 },
                markerEnd: { type: 'arrowclosed', color: '#9ca3af', width: 14, height: 14 }
            }));
        } else {
            console.log('Auto-generating layout from workflow data');
            // Auto-generate layout from workflow data
            let yPosition = 50;
            
            // Add trigger node
            if (workflowData.trigger_type) {
                // Handle trigger_config - it might be a string or already an object
                let triggerConfig = {};
                if (workflowData.trigger_config) {
                    triggerConfig = typeof workflowData.trigger_config === 'string' 
                        ? JSON.parse(workflowData.trigger_config) 
                        : workflowData.trigger_config;
                }
                
                const triggerNode = {
                    id: 'trigger_1',
                    type: 'workflowNode',
                    position: { x: 300, y: yPosition },
                    data: {
                        type: 'trigger',
                        subtype: workflowData.trigger_type,
                        config: triggerConfig
                    }
                };
                nodes.push(triggerNode);
                yPosition += 150;
            }
            
            // Add condition nodes
            if (workflowData.conditions && workflowData.conditions.length > 0) {
                workflowData.conditions.forEach((cond, index) => {
                    const condNode = {
                        id: `condition_${index + 1}`,
                        type: 'workflowNode',
                        position: { x: 300, y: yPosition },
                        data: {
                            type: 'condition',
                            subtype: 'check_field',
                            config: {
                                field_name: cond.field_name,
                                operator: cond.operator,
                                value: cond.value
                            }
                        }
                    };
                    nodes.push(condNode);
                    
                    // Connect to previous node
                    if (index === 0 && nodes.length > 1) {
                        edges.push({
                            id: `edge_trigger_cond_${index}`,
                            source: 'trigger_1',
                            target: condNode.id,
                            type: 'smoothstep',
                            animated: false,
                            style: { stroke: '#9ca3af', strokeWidth: 2 },
                            markerEnd: { type: 'arrowclosed', color: '#9ca3af', width: 14, height: 14 }
                        });
                    } else if (index > 0) {
                        edges.push({
                            id: `edge_cond_${index - 1}_${index}`,
                            source: `condition_${index}`,
                            target: condNode.id,
                            sourceHandle: 'yes',
                            type: 'smoothstep',
                            animated: false,
                            style: { stroke: '#9ca3af', strokeWidth: 2 },
                            markerEnd: { type: 'arrowclosed', color: '#9ca3af', width: 14, height: 14 }
                        });
                    }
                    
                    yPosition += 150;
                });
            }
            
            // Add action nodes
            if (workflowData.actions && workflowData.actions.length > 0) {
                workflowData.actions.forEach((action, index) => {
                    // Handle action_config - it might be a string or already an object
                    let actionConfig = {};
                    if (action.action_config) {
                        actionConfig = typeof action.action_config === 'string' 
                            ? JSON.parse(action.action_config) 
                            : action.action_config;
                    }
                    
                    const actionNode = {
                        id: `action_${index + 1}`,
                        type: 'workflowNode',
                        position: { x: 300, y: yPosition },
                        data: {
                            type: 'action',
                            subtype: action.action_type,
                            config: actionConfig
                        }
                    };
                    nodes.push(actionNode);
                    
                    // Connect to previous node
                    const prevNode = nodes[nodes.length - 2];
                    if (prevNode) {
                        edges.push({
                            id: `edge_${prevNode.id}_${actionNode.id}`,
                            source: prevNode.id,
                            target: actionNode.id,
                            sourceHandle: prevNode.data.type === 'condition' ? 'yes' : undefined,
                            type: 'smoothstep',
                            animated: false,
                            style: { stroke: '#9ca3af', strokeWidth: 2 },
                            markerEnd: { type: 'arrowclosed', color: '#9ca3af', width: 14, height: 14 }
                        });
                    }
                    
                    yPosition += 150;
                });
            }
        }
        
        // Update React state
        if (this._setNodes && this._setEdges) {
            this._setNodes(nodes);
            this._setEdges(edges);
        }
    },
    
    /**
     * Get workflow data from canvas
     */
    getWorkflowData() {
        const nodes = this._getNodes ? this._getNodes() : [];
        const edges = this._getEdges ? this._getEdges() : [];
        
        // Find trigger node
        const triggerNode = nodes.find(n => n.data.type === 'trigger');
        if (!triggerNode) {
            throw new Error('En az bir tetikleyici node olmalı');
        }
        
        // Find condition nodes
        const conditionNodes = nodes.filter(n => n.data.type === 'condition');
        
        // Find action nodes
        const actionNodes = nodes.filter(n => n.data.type === 'action');
        if (actionNodes.length === 0) {
            throw new Error('En az bir aksiyon node olmalı');
        }
        
        // Build workflow data
        const workflowData = {
            name: document.getElementById('workflowName').value.trim(),
            is_active: document.getElementById('workflowActive').checked,
            trigger_type: triggerNode.data.subtype,
            trigger_config: triggerNode.data.config || {},
            condition_logic: 'AND',
            conditions: conditionNodes.map((node, index) => ({
                field_name: node.data.config.field_name || '',
                operator: node.data.config.operator || 'equals',
                value: node.data.config.value || '',
                order_index: index
            })),
            actions: actionNodes.map((node, index) => ({
                action_type: node.data.subtype,
                action_config: node.data.config || {},
                delay_minutes: node.data.config.delay_minutes || 0,
                order_index: index
            }))
        };
        
        return workflowData;
    },
    
    /**
     * Save workflow
     */
    async saveWorkflow() {
        try {
            const workflowData = this.getWorkflowData();
            
            if (!workflowData.name) {
                showToast('Workflow adı gerekli', 'error');
                return;
            }
            
            // Add canvas data (node positions and edges)
            const nodes = this._getNodes ? this._getNodes() : [];
            const edges = this._getEdges ? this._getEdges() : [];
            
            workflowData.canvas_data = {
                nodes: nodes.map(node => ({
                    id: node.id,
                    position: node.position,
                    data: node.data
                })),
                edges: edges.map(edge => ({
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                    sourceHandle: edge.sourceHandle,
                    targetHandle: edge.targetHandle
                }))
            };
            
            const url = this.currentWorkflowId 
                ? `/api/v1/workflows/${this.currentWorkflowId}`
                : '/api/v1/workflows';
            
            const method = this.currentWorkflowId ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    ...getCsrfHeaders()
                },
                body: JSON.stringify(workflowData)
            });
            
            if (response.ok) {
                const result = await response.json();
                showToast('Workflow kaydedildi', 'success');
                
                // Update current workflow ID if it was a new workflow
                if (!this.currentWorkflowId && result.id) {
                    this.currentWorkflowId = result.id;
                    document.getElementById('workflowId').value = result.id;
                }
                
                // Reload workflow list
                if (window.WorkflowBuilder) {
                    window.WorkflowBuilder.loadWorkflows();
                }
            } else {
                const error = await response.json();
                showToast(error.error || 'Kaydetme başarısız', 'error');
            }
        } catch (error) {
            console.error('Save workflow error:', error);
            showToast(error.message || 'Kaydetme başarısız', 'error');
        }
    },
    
    /**
     * Auto-save canvas data (positions only, without full workflow data)
     */
    async autoSaveCanvasData() {
        if (!this.currentWorkflowId) {
            console.log('No workflow ID, skipping auto-save');
            return;
        }
        
        try {
            const nodes = this._getNodes ? this._getNodes() : [];
            const edges = this._getEdges ? this._getEdges() : [];
            
            if (nodes.length === 0) {
                console.log('No nodes, skipping auto-save');
                return;
            }
            
            const canvas_data = {
                nodes: nodes.map(node => ({
                    id: node.id,
                    position: node.position,
                    data: node.data
                })),
                edges: edges.map(edge => ({
                    id: edge.id,
                    source: edge.source,
                    target: edge.target,
                    sourceHandle: edge.sourceHandle,
                    targetHandle: edge.targetHandle
                }))
            };
            
            const response = await fetch(`/api/v1/workflows/${this.currentWorkflowId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    ...getCsrfHeaders()
                },
                body: JSON.stringify({ canvas_data })
            });
            
            if (response.ok) {
                console.log('✓ Canvas positions auto-saved');
            } else {
                console.warn('Auto-save failed:', response.status);
            }
        } catch (error) {
            console.error('Auto-save error:', error);
        }
    },
    
    /**
     * Delete workflow
     */
    async deleteWorkflow() {
        if (!this.currentWorkflowId) return;
        
        if (!confirm('Bu workflow\'u silmek istediğinizden emin misiniz?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/workflows/${this.currentWorkflowId}`, {
                method: 'DELETE',
                headers: getCsrfHeaders()
            });
            
            if (response.ok) {
                showToast('Workflow silindi', 'success');
                
                // Close builder
                document.getElementById('workflowBuilder').classList.add('hidden');
                document.getElementById('emptyState').classList.remove('hidden');
                this.currentWorkflowId = null;
                
                // Reload workflow list
                if (window.WorkflowBuilder) {
                    window.WorkflowBuilder.loadWorkflows();
                }
            } else {
                const error = await response.json();
                showToast(error.error || 'Silme başarısız', 'error');
            }
        } catch (error) {
            console.error('Delete workflow error:', error);
            showToast('Silme başarısız', 'error');
        }
    },
    
    /**
     * Show new workflow (empty canvas)
     */
    showNewWorkflow() {
        this.currentWorkflowId = null;
        
        // Clear form
        document.getElementById('workflowId').value = '';
        document.getElementById('workflowName').value = '';
        document.getElementById('workflowActive').checked = true;
        
        // Clear canvas
        if (this._setNodes && this._setEdges) {
            this._setNodes([]);
            this._setEdges([]);
        }
        
        // Show builder panel
        document.getElementById('workflowBuilder').classList.remove('hidden');
        document.getElementById('emptyState').classList.add('hidden');
    },
    
    /**
     * Delete a node
     */
    deleteNode(nodeId) {
        if (this._setNodes) {
            this._setNodes((nodes) => nodes.filter(n => n.id !== nodeId));
        }
        if (this._setEdges) {
            this._setEdges((edges) => edges.filter(e => e.source !== nodeId && e.target !== nodeId));
        }
    },
    
    /**
     * Open properties panel for a node
     */
    async openProperties(nodeId, nodeData) {
        const panel = document.getElementById('propertiesPanel');
        const content = document.getElementById('propertiesContent');
        
        if (!panel || !content) return;
        
        const config = NODE_CONFIGS[nodeData.subtype];
        if (!config) return;
        
        // Build properties form
        let html = `<div class="space-y-4">`;
        html += `<div class="text-sm font-semibold text-slate-700 mb-3">${config.title}</div>`;
        
        // Template variable hint
        html += `<div class="text-xs text-slate-500 bg-slate-50 p-2 rounded mb-3">
            <strong>Kullanılabilir:</strong> {{contact.first_name}}, {{contact.full_name}}, {{deal.name}}
        </div>`;
        
        for (const field of config.fields) {
            const currentValue = nodeData.config?.[field.key] ?? field.default ?? '';
            
            html += `<div>`;
            html += `<label class="block text-xs font-medium text-slate-600 mb-1">${field.label}</label>`;
            
            if (field.type === 'text' || field.type === 'number') {
                html += `<input type="${field.type}" 
                    class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="${field.placeholder || ''}"
                    value="${currentValue}"
                    data-field-key="${field.key}"
                    onchange="WorkflowCanvas.updateNodeConfig('${nodeId}', '${field.key}', this.value)">`;
            } else if (field.type === 'textarea') {
                html += `<textarea rows="3"
                    class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="${field.placeholder || ''}"
                    data-field-key="${field.key}"
                    onchange="WorkflowCanvas.updateNodeConfig('${nodeId}', '${field.key}', this.value)">${currentValue}</textarea>`;
            } else if (field.type === 'select') {
                html += `<select 
                    class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    data-field-key="${field.key}"
                    onchange="WorkflowCanvas.updateNodeConfig('${nodeId}', '${field.key}', this.value)">`;
                for (const option of field.options) {
                    const selected = currentValue === option.value ? 'selected' : '';
                    html += `<option value="${option.value}" ${selected}>${option.label}</option>`;
                }
                html += `</select>`;
            } else if (field.type === 'stage_select') {
                // Fetch stages and render select
                html += `<select id="stage_select_${field.key}"
                    class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    data-field-key="${field.key}"
                    onchange="WorkflowCanvas.updateNodeConfig('${nodeId}', '${field.key}', this.value)">
                    <option value="">Seçiniz...</option>
                </select>`;
            }
            
            html += `</div>`;
        }
        
        html += `</div>`;
        
        content.innerHTML = html;
        panel.classList.remove('hidden');
        
        // Load stages if needed
        const stageSelects = content.querySelectorAll('select[id^="stage_select_"]');
        if (stageSelects.length > 0) {
            await this.loadStages(stageSelects, nodeData);
        }
    },
    
    /**
     * Load pipeline stages for select dropdowns
     */
    async loadStages(selectElements, nodeData) {
        try {
            const response = await fetch('/api/v1/pipeline/stages', {
                headers: getCsrfHeaders()
            });
            
            if (response.ok) {
                const data = await response.json();
                const stages = data.stages || [];
                
                selectElements.forEach(select => {
                    const fieldKey = select.dataset.fieldKey;
                    const currentValue = nodeData.config?.[fieldKey];
                    
                    stages.forEach(stage => {
                        const option = document.createElement('option');
                        option.value = stage.id;
                        option.textContent = stage.name;
                        if (currentValue == stage.id) {
                            option.selected = true;
                        }
                        select.appendChild(option);
                    });
                });
            }
        } catch (error) {
            console.error('Error loading stages:', error);
        }
    },
    
    /**
     * Update node config
     */
    updateNodeConfig(nodeId, fieldKey, value) {
        if (this._setNodes) {
            this._setNodes((nodes) => 
                nodes.map(node => {
                    if (node.id === nodeId) {
                        return {
                            ...node,
                            data: {
                                ...node.data,
                                config: {
                                    ...node.data.config,
                                    [fieldKey]: value
                                }
                            }
                        };
                    }
                    return node;
                })
            );
        }
    },
    
    /**
     * Close properties panel
     */
    closeProperties() {
        const panel = document.getElementById('propertiesPanel');
        if (panel) {
            panel.classList.add('hidden');
        }
    },
    
    /**
     * Load workflow executions
     */
    async loadExecutions(workflowId) {
        try {
            const response = await fetch(`/api/v1/workflows/${workflowId}/executions`, {
                headers: getCsrfHeaders()
            });
            
            if (response.ok) {
                const data = await response.json();
                const executions = data.executions || [];
                
                const listEl = document.getElementById('executionList');
                const countEl = document.getElementById('executionCount');
                
                if (countEl) {
                    countEl.textContent = `${executions.length} kayıt`;
                }
                
                if (!listEl) return;
                
                if (executions.length === 0) {
                    listEl.innerHTML = '<p class="text-sm text-slate-500 text-center py-8">Henüz çalışma kaydı yok</p>';
                    return;
                }
                
                listEl.innerHTML = executions.map(exec => {
                    const statusColor = exec.status === 'completed' ? 'green' : exec.status === 'failed' ? 'red' : 'yellow';
                    const statusText = exec.status === 'completed' ? 'Başarılı' : exec.status === 'failed' ? 'Hatalı' : 'Bekliyor';
                    
                    return `
                        <div class="bg-white border border-slate-200 rounded-lg p-3">
                            <div class="flex items-center justify-between mb-2">
                                <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-${statusColor}-100 text-${statusColor}-700">
                                    ${statusText}
                                </span>
                                <span class="text-xs text-slate-400">${this.formatTimeAgo(exec.started_at)}</span>
                            </div>
                            <div class="text-sm text-slate-700">${exec.entity_name || 'Bilinmeyen'}</div>
                            <div class="text-xs text-slate-500">${this.getTriggerName(exec.trigger_type || '')}</div>
                            ${exec.error_message ? `<div class="text-xs text-red-600 mt-1">${exec.error_message}</div>` : ''}
                        </div>
                    `;
                }).join('');
            }
        } catch (error) {
            console.error('Error loading executions:', error);
        }
    },
    
    /**
     * Format time ago
     */
    formatTimeAgo(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return 'Az önce';
        if (diffMins < 60) return `${diffMins} dakika önce`;
        
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours} saat önce`;
        
        const diffDays = Math.floor(diffHours / 24);
        return `${diffDays} gün önce`;
    },
    
    /**
     * Get trigger display name
     */
    getTriggerName(triggerType) {
        const names = {
            'deal_stage_changed': 'Aşama değişti',
            'deal_created': 'Yeni anlaşma',
            'deal_won': 'Anlaşma kazanıldı',
            'deal_lost': 'Anlaşma kaybedildi',
            'contact_created': 'Yeni kişi',
            'contact_no_activity': 'Kişi hareketsiz',
            'task_completed': 'Görev tamamlandı',
        };
        return names[triggerType] || triggerType;
    }
};
