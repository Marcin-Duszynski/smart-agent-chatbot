import React from 'react'
import { TrendingUp, BarChart3, LoaderIcon, ExternalLink } from 'lucide-react'
import { useAgentAnalysis } from '@/hooks/useAgentAnalysis'
import { useAnalysisModal } from '@/hooks/useAnalysisModal'

interface AgentAnalysisToolResultProps {
  type: 'create' | 'update' | 'complete'
  result?: { 
    title?: string
    summary?: string
    status?: 'streaming' | 'idle'
  }
  toolUseId?: string
  toolName?: string
  sessionId?: string
  isReadonly?: boolean
}

export const AgentAnalysisToolResult: React.FC<AgentAnalysisToolResultProps> = ({
  type,
  result,
  toolUseId,
  toolName,
  sessionId,
  isReadonly = false
}) => {
  const { setAgentAnalysis, loadAnalysisFromMemory } = useAgentAnalysis()
  const { openModal } = useAnalysisModal()

  const getActionText = () => {
    switch (type) {
      case 'create':
        return 'Analysis Started'
      case 'update':
        return 'Analysis Updated'
      case 'complete':
        return 'Analysis Complete'
      default:
        return 'Analysis'
    }
  }

  const getIcon = () => {
    if (result?.status === 'streaming') {
      return <LoaderIcon className="w-5 h-5 animate-spin text-blue-500" />
    }
    return type === 'complete' ? <BarChart3 className="w-5 h-5 text-green-600" /> : <TrendingUp className="w-5 h-5 text-blue-600" />
  }

  const handleClick = async (event: React.MouseEvent) => {
    if (isReadonly) {
      return
    }

    // If we have a toolUseId and this is a completed analysis, open modal
    if (toolUseId && type === 'complete' && sessionId) {
      // Check if user wants to open in new tab (Cmd/Ctrl + click)
      if (event.metaKey || event.ctrlKey) {
        window.open(`/analysis/${toolUseId}?sessionId=${sessionId}`, '_blank')
      } else {
        // Open modal instead of navigating
        openModal(toolUseId, sessionId)
      }
      return
    }

    // Fallback to existing behavior for non-complete analyses
    const rect = event.currentTarget.getBoundingClientRect()
    const boundingBox = {
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    }

    setAgentAnalysis(prev => ({
      ...prev,
      id: toolUseId || prev.id,
      title: result?.title || 'Agent Analysis',
      isVisible: true,
      status: result?.status || 'idle',
      boundingBox
    }))
  }

  return (
    <button
      type="button"
      className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-blue-50 hover:bg-blue-100 border border-blue-200 hover:border-blue-300 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed group"
      onClick={handleClick}
      disabled={isReadonly}
    >
      {getIcon()}
      <span className="font-medium text-gray-900">
        {type === 'complete' ? 'View Analysis' : getActionText()}
      </span>
      {type === 'complete' && (
        <>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
            Ready
          </span>
          <ExternalLink className="w-3 h-3 text-blue-400 group-hover:translate-x-0.5 transition-transform" />
        </>
      )}
      {type !== 'complete' && (
        <svg className="w-3 h-3 text-blue-400 group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      )}
    </button>
  )
}

interface AgentAnalysisToolCallProps {
  type: 'create' | 'update'
  args: {
    query?: string
    title?: string
  }
  isReadonly?: boolean
}

export const AgentAnalysisToolCall: React.FC<AgentAnalysisToolCallProps> = ({
  type,
  args,
  isReadonly = false
}) => {
  const { setAgentAnalysis } = useAgentAnalysis()

  const getActionText = () => {
    switch (type) {
      case 'create':
        return 'Creating agent analysis'
      case 'update':
        return 'Updating agent analysis'
      default:
        return 'Processing agent analysis'
    }
  }

  const handleClick = (event: React.MouseEvent) => {
    if (isReadonly) {
      return
    }

    const rect = event.currentTarget.getBoundingClientRect()
    const boundingBox = {
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    }

    setAgentAnalysis(prev => ({
      ...prev,
      title: args?.title || 'Agent Analysis',
      isVisible: true,
      status: 'streaming',
      boundingBox
    }))
  }

  return (
    <button
      type="button"
      className="cursor-pointer w-fit border py-2 px-3 rounded-xl flex flex-row items-start justify-between gap-3 hover:bg-accent/50 transition-colors"
      onClick={handleClick}
      disabled={isReadonly}
    >
      <div className="flex flex-row gap-3 items-start">
        <div className="text-zinc-500 mt-1">
          <TrendingUp />
        </div>
        <div className="text-left">
          <div className="font-medium">
            {getActionText()}
          </div>
          {args?.query && (
            <div className="text-sm text-muted-foreground">
              {args.query}
            </div>
          )}
        </div>
      </div>
      <div className="animate-spin mt-1">
        <LoaderIcon />
      </div>
    </button>
  )
}
