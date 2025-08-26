import React from 'react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Bot, Brain } from 'lucide-react'
import { Message } from '@/types/chat'
import { ReasoningState } from '@/types/events'
import { Markdown } from '@/components/ui/Markdown'
import { ToolExecutionContainer } from './ToolExecutionContainer'

interface AssistantTurnProps {
  messages: Message[]
  currentReasoning?: ReasoningState | null
  availableTools?: Array<{
    id: string
    name: string
    tool_type?: string
  }>
  sessionId?: string
}

export const AssistantTurn: React.FC<AssistantTurnProps> = ({ messages, currentReasoning, availableTools = [], sessionId }) => {
  if (!messages || messages.length === 0) {
    return null
  }

  // Sort messages by timestamp to maintain chronological order
  const sortedMessages = [...messages].sort((a, b) => {
    // Extract timestamp for comparison - use id as fallback since it's based on Date.now()
    const timeA = a.timestamp ? new Date(a.timestamp).getTime() : a.id
    const timeB = b.timestamp ? new Date(b.timestamp).getTime() : b.id
    return timeA - timeB
  })

  // Group consecutive text messages together while preserving tool message positions
  const groupedContent: Array<{
    type: 'text' | 'tool'
    content: string | Message
    images?: any[]
    key: string
    toolUseId?: string
  }> = []

  let currentTextGroup = ''
  let currentTextImages: any[] = []
  let textGroupStartId = 0
  let currentToolUseId: string | undefined = undefined

  const flushTextGroup = () => {
    if (currentTextGroup.trim()) {
      groupedContent.push({
        type: 'text',
        content: currentTextGroup,
        images: currentTextImages,
        key: `text-group-${textGroupStartId}`,
        toolUseId: currentToolUseId
      })
      currentTextGroup = ''
      currentTextImages = []
      currentToolUseId = undefined
    }
  }

  sortedMessages.forEach((message) => {
    if (message.isToolMessage) {
      // Flush any accumulated text before adding tool message
      flushTextGroup()
      groupedContent.push({
        type: 'tool',
        content: message,
        key: `tool-${message.id}`
      })
    } else if (message.text) {
      // Accumulate text messages
      if (!currentTextGroup) {
        textGroupStartId = message.id
      }
      currentTextGroup += message.text
      if (message.images && message.images.length > 0) {
        currentTextImages.push(...message.images)
      }
      // Track toolUseId for this text message
      if (message.toolUseId && !currentToolUseId) {
        currentToolUseId = message.toolUseId
      }
    }
  })

  // Flush any remaining text
  flushTextGroup()

  return (
    <div className="flex justify-start mb-8">
      <div className="flex items-start space-x-4 max-w-4xl w-full">
        {/* Single Avatar for the entire turn */}
        <Avatar className="h-9 w-9 flex-shrink-0 mt-2">
          <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-white">
            <Bot className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
        
        {/* Turn Content */}
        <div className="flex-1 space-y-4 pt-1">
          {/* Reasoning Step - Show when AI is thinking */}
          {currentReasoning && currentReasoning.text && (
            <div className="animate-fade-in">
              <div className={`reasoning-step p-4 rounded-lg border-l-4 ${
                currentReasoning.isActive 
                  ? 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-400' 
                  : 'bg-gradient-to-r from-gray-50 to-slate-50 border-gray-400'
              }`}>
                <div className="flex items-center gap-3 mb-2">
                  <Brain className={`h-5 w-5 ${
                    currentReasoning.isActive 
                      ? 'text-blue-500 animate-pulse' 
                      : 'text-gray-500'
                  }`} />
                  <span className={`text-sm font-semibold ${
                    currentReasoning.isActive 
                      ? 'text-blue-700' 
                      : 'text-gray-700'
                  }`}>
                    {currentReasoning.isActive ? 'AI is thinking...' : 'AI Reasoning Process'}
                  </span>
                </div>
                <p className={`text-sm italic leading-relaxed ${
                  currentReasoning.isActive 
                    ? 'text-blue-600' 
                    : 'text-gray-600'
                }`}>
                  {currentReasoning.text}
                </p>
              </div>
            </div>
          )}

          {/* Render messages in chronological order */}
          {groupedContent.map((item) => (
            <div key={item.key} className="animate-fade-in">
              {item.type === 'tool' ? (
                <ToolExecutionContainer 
                  toolExecutions={(item.content as Message).toolExecutions || []} 
                  availableTools={availableTools}
                  sessionId={sessionId}
                />
              ) : (
                <div className="chat-chart-content">
                  <Markdown sessionId={sessionId} toolUseId={item.toolUseId}>{item.content as string}</Markdown>
                  
                  {/* Generated Images for this text group */}
                  {item.images && item.images.length > 0 && (
                    <div className="mt-4 space-y-3">
                      {item.images.map((image, idx) => (
                        <div key={idx} className="relative group">
                          <img
                            src={`data:image/${image.format};base64,${image.data}`}
                            alt={`Generated image ${idx + 1}`}
                            className="max-w-full h-auto rounded-xl border border-slate-200 shadow-sm"
                            style={{ maxHeight: '400px' }}
                          />
                          <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Badge variant="secondary" className="text-xs bg-black/70 text-white border-0">
                              {image.format.toUpperCase()}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
