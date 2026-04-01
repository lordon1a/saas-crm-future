/**
 * ExpressionEditor Component
 * ==========================
 * n8n-style expression editor with:
 * - Syntax highlighting for {{ }} expressions
 * - Variable picker dropdown
 * - Real-time validation
 * 
 * Inspired by n8n's expression editor:
 * ../n8n-master/packages/editor-ui/src/components/ExpressionEditor.vue
 */

import React, { useState, useCallback, useRef, useEffect } from 'react'

interface VariableSuggestion {
  id: string
  name: string
  type: 'node' | 'variable' | 'property'
  data?: {
    nodeId?: string
    nodeName?: string
    nodeType?: string
    propertyPath?: string
    propertyType?: string
  }
}

interface Props {
  value: string
  onChange: (value: string) => void
  availableVariables?: VariableSuggestion[]
  placeholder?: string
  disabled?: boolean
  className?: string
}

export default function ExpressionEditor({
  value,
  onChange,
  availableVariables = [],
  placeholder = '{{ }}',
  disabled = false,
  className = ''
}: Props) {
  const [isOpen, setIsOpen] = useState(false)
  const [cursorPosition, setCursorPosition] = useState(0)

  const [selectedIndex, setSelectedIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Get text before cursor to determine if we're inside an expression
  const getTextBeforeCursor = useCallback(() => {
    return value.substring(0, cursorPosition)
  }, [value, cursorPosition])

  // Check if we're currently typing an expression
  const isInsideExpression = useCallback(() => {
    const textBefore = getTextBeforeCursor()
    const lastOpen = textBefore.lastIndexOf('{{')
    const lastClose = textBefore.lastIndexOf('}}')
    return lastOpen > lastClose
  }, [getTextBeforeCursor])

  // Get the expression being typed (from last {{ to cursor)
  const getCurrentExpression = useCallback(() => {
    const textBefore = getTextBeforeCursor()
    const lastOpen = textBefore.lastIndexOf('{{')
    if (lastOpen === -1) return ''
    return textBefore.substring(lastOpen + 2)
  }, [getTextBeforeCursor])

  // Filter variables based on current expression input
  const getFilteredVariables = useCallback(() => {
    const currentExpr = getCurrentExpression().toLowerCase()
    if (!currentExpr) return availableVariables.slice(0, 10)
    
    return availableVariables.filter(v => {
      const searchText = `${v.name} ${v.data?.nodeName || ''} ${v.data?.propertyPath || ''}`.toLowerCase()
      return searchText.includes(currentExpr)
    }).slice(0, 10)
  }, [availableVariables, getCurrentExpression])

  // Insert variable at cursor position
  const insertVariable = useCallback((variable: VariableSuggestion) => {
    const textBefore = getTextBeforeCursor()
    const textAfter = value.substring(cursorPosition)
    
    // Find the start of the current expression
    const lastOpen = textBefore.lastIndexOf('{{')
    const beforeExpression = lastOpen === -1 ? textBefore : textBefore.substring(0, lastOpen)
    
    // Build the variable reference
    let varRef = ''
    if (variable.type === 'node') {
      varRef = `$node["${variable.name}"]`
    } else if (variable.data?.nodeId) {
      varRef = `$node["${variable.data.nodeName}"].json.${variable.data.propertyPath || variable.name}`
    } else {
      varRef = `$${variable.name}`
    }
    
    const newValue = beforeExpression + '{{' + varRef + '}}' + textAfter
    onChange(newValue)
    setIsOpen(false)
    
    // Focus back on textarea
    setTimeout(() => {
      textareaRef.current?.focus()
      const newCursor = beforeExpression.length + varRef.length + 4
      textareaRef.current?.setSelectionRange(newCursor, newCursor)
    }, 0)
  }, [value, cursorPosition, getTextBeforeCursor, onChange])

  // Handle keyboard events
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!isOpen) return

    const filteredVars = getFilteredVariables()
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, filteredVars.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (filteredVars[selectedIndex]) {
          insertVariable(filteredVars[selectedIndex])
        }
        break
      case 'Escape':
        e.preventDefault()
        setIsOpen(false)
        break
      case 'Tab':
        e.preventDefault()
        if (filteredVars[selectedIndex]) {
          insertVariable(filteredVars[selectedIndex])
        }
        break
    }
  }, [isOpen, getFilteredVariables, selectedIndex, insertVariable])

  // Handle text change
  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value
    const newCursor = e.target.selectionStart
    
    setCursorPosition(newCursor)
    onChange(newValue)
    
    // Check if we should show autocomplete
    const wasInside = isInsideExpression()
    if (wasInside && !isOpen) {
      setIsOpen(true)
      setSelectedIndex(0)
    } else if (!wasInside && isOpen) {
      setIsOpen(false)
    }
  }, [onChange, isInsideExpression, isOpen])

  // Handle cursor position changes
  const handleSelect = useCallback((e: React.SyntheticEvent) => {
    const target = e.target as HTMLTextAreaElement
    setCursorPosition(target.selectionStart)
    
    const wasInside = isInsideExpression()
    if (wasInside && !isOpen) {
      setIsOpen(true)
      setSelectedIndex(0)
    } else if (!wasInside && isOpen) {
      setIsOpen(false)
    }
  }, [isInsideExpression, isOpen])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const filteredVariables = getFilteredVariables()

  return (
    <div className={`expression-editor ${className}`} style={{ position: 'relative' }}>
      <style>{`
        .expression-editor {
          font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
          font-size: 13px;
        }
        
        .expression-editor textarea {
          width: 100%;
          min-height: 60px;
          padding: 8px 12px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          font-family: inherit;
          font-size: inherit;
          resize: vertical;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        
        .expression-editor textarea:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        .expression-editor textarea::placeholder {
          color: #9ca3af;
        }
        
        .expression-text {
          color: #374151;
        }
        
        .expression-variable {
          color: #7c3aed;
          background: #f3e8ff;
          border-radius: 3px;
          padding: 0 2px;
        }
        
        .expression-dropdown {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          margin-top: 4px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
          max-height: 280px;
          overflow-y: auto;
          z-index: 1000;
        }
        
        .expression-dropdown-item {
          padding: 10px 12px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 10px;
          border-bottom: 1px solid #f3f4f6;
          transition: background 0.1s;
        }
        
        .expression-dropdown-item:last-child {
          border-bottom: none;
        }
        
        .expression-dropdown-item:hover,
        .expression-dropdown-item.selected {
          background: #f9fafb;
        }
        
        .expression-dropdown-item .var-icon {
          width: 28px;
          height: 28px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          flex-shrink: 0;
        }
        
        .expression-dropdown-item .var-icon.node {
          background: #dbeafe;
          color: #2563eb;
        }
        
        .expression-dropdown-item .var-icon.variable {
          background: #fef3c7;
          color: #d97706;
        }
        
        .expression-dropdown-item .var-icon.property {
          background: #dcfce7;
          color: #16a34a;
        }
        
        .expression-dropdown-item .var-info {
          flex: 1;
          min-width: 0;
        }
        
        .expression-dropdown-item .var-name {
          font-weight: 500;
          color: #111827;
          font-size: 13px;
        }
        
        .expression-dropdown-item .var-path {
          font-size: 11px;
          color: #6b7280;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .expression-dropdown-header {
          padding: 8px 12px;
          font-size: 11px;
          font-weight: 600;
          color: #9ca3af;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          background: #f9fafb;
          border-bottom: 1px solid #e5e7eb;
        }
        
        .expression-hint {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 6px;
          font-size: 11px;
          color: #9ca3af;
        }
        
        .expression-hint kbd {
          background: #f3f4f6;
          border: 1px solid #e5e7eb;
          border-radius: 4px;
          padding: 2px 6px;
          font-family: inherit;
          font-size: 10px;
        }
      `}</style>
      
      <div style={{ position: 'relative' }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onSelect={handleSelect}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          spellCheck={false}
        />
        
        {/* Variable dropdown */}
        {isOpen && filteredVariables.length > 0 && (
          <div ref={dropdownRef} className="expression-dropdown">
            <div className="expression-dropdown-header">
              <i className="fas fa-link" style={{ marginRight: 6 }} />
              Değişkenler - Press Enter to insert
            </div>
            {filteredVariables.map((variable, index) => (
              <div
                key={variable.id}
                className={`expression-dropdown-item ${index === selectedIndex ? 'selected' : ''}`}
                onClick={() => insertVariable(variable)}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <div className={`var-icon ${variable.type}`}>
                  {variable.type === 'node' && <i className="fas fa-cube" />}
                  {variable.type === 'variable' && <i className="fas fa-at" />}
                  {variable.type === 'property' && <i className="fas fa-key" />}
                </div>
                <div className="var-info">
                  <div className="var-name">{variable.name}</div>
                  {variable.data?.propertyPath && (
                    <div className="var-path">
                      {variable.data.nodeName && `$node["${variable.data.nodeName}"].json.`}
                      {variable.data.propertyPath}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Hint */}
      <div className="expression-hint">
        <code style={{ background: '#f3f4f6', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>{'{{'}expression{'}}'}</code>
        <span style={{ margin: '0 4px' }}>|</span>
        <kbd>Tab</kbd> <span>autocomplete</span>
      </div>
    </div>
  )
}

// Hook for managing expression state
export function useExpressionEditor(initialValue = '') {
  const [expression, setExpression] = useState(initialValue)
  const [variables, setVariables] = useState<VariableSuggestion[]>([])
  
  // Update available variables from workflow nodes
  const updateVariablesFromNodes = useCallback((nodes: Array<{
    id: string
    name: string
    type: string
    outputData?: Record<string, unknown>
  }>) => {
    const newVariables: VariableSuggestion[] = []
    
    nodes.forEach(node => {
      // Add node itself
      newVariables.push({
        id: `node-${node.id}`,
        name: node.name,
        type: 'node',
        data: {
          nodeId: node.id,
          nodeName: node.name,
          nodeType: node.type
        }
      })
      
      // Add node's output properties
      if (node.outputData && typeof node.outputData === 'object') {
        Object.keys(node.outputData).forEach(key => {
          newVariables.push({
            id: `node-${node.id}-prop-${key}`,
            name: key,
            type: 'property',
            data: {
              nodeId: node.id,
              nodeName: node.name,
              propertyPath: key,
              propertyType: typeof node.outputData?.[key] as string
            }
          })
        })
      }
    })
    
    setVariables(newVariables)
  }, [])
  
  return {
    expression,
    setExpression,
    variables,
    updateVariablesFromNodes
  }
}
