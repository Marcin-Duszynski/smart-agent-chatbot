import { useCallback, useRef, useState, useEffect } from 'react'
import { Message, Tool } from '@/types/chat'
import { StreamEvent, ChatUIState } from '@/types/events'
import { getApiUrl } from '@/config/environment'
import logger from '@/utils/logger'

interface UseChatAPIProps {
  backendUrl: string
  setUIState: React.Dispatch<React.SetStateAction<ChatUIState>>
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setAvailableTools: React.Dispatch<React.SetStateAction<Tool[]>>
  handleStreamEvent: (event: StreamEvent) => void
  handleLegacyEvent: (data: any) => void
}

interface UseChatAPIReturn {
  loadTools: () => Promise<void>
  toggleTool: (toolId: string) => Promise<void>
  clearChat: () => Promise<boolean>
  sendMessage: (messageToSend: string, files?: File[], onSuccess?: () => void, onError?: (error: string) => void) => Promise<void>
  cleanup: () => void
  sessionId: string | null
  isLoadingTools: boolean
}

export const useChatAPI = ({
  backendUrl,
  setUIState,
  setMessages,
  setAvailableTools,
  handleStreamEvent,
  handleLegacyEvent
}: UseChatAPIProps) => {
  
  const abortControllerRef = useRef<AbortController | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  // Clear session ID on page load/refresh to start fresh session
  useEffect(() => {
    // Always clear existing session ID on page load to start fresh
    sessionStorage.removeItem('chat-session-id')
    setSessionId(null)
  }, [])

  // Save session ID to sessionStorage when it changes
  useEffect(() => {
    if (sessionId) {
      sessionStorage.setItem('chat-session-id', sessionId)
    }
  }, [sessionId])

  const loadTools = useCallback(async () => {
    try {
      const startTime = performance.now()

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      }

      // Include session ID in headers if available
      if (sessionId) {
        headers['X-Session-ID'] = sessionId
      }

      const url = getApiUrl('tools')
      logger.network('GET', url, { 'X-Session-ID': sessionId || 'new' })

      const response = await fetch(url, {
        method: 'GET',
        headers,
        signal: AbortSignal.timeout(5000)
      })

      const duration = performance.now() - startTime
      logger.apiResponse(response.status, url, Math.round(duration))

      if (response.ok) {
        // Extract session ID from response headers
        const responseSessionId = response.headers.get('X-Session-ID')

        if (responseSessionId && responseSessionId !== sessionId) {
          logger.api('Session ID created/updated', { sessionId: responseSessionId })
          setSessionId(responseSessionId)
        }

        const data = await response.json()
        // Combine regular tools and MCP servers from unified API response
        const allTools = [...(data.tools || []), ...(data.mcp_servers || [])]
        logger.api('Tools loaded', { count: allTools.length, tools: allTools.map((t: any) => t.name) })
        setAvailableTools(allTools)
      } else {
        logger.error('Failed to load tools:', response.status)
        setAvailableTools([])
      }
    } catch (error) {
      logger.error('Error loading tools:', error)
      setAvailableTools([])
    }
  }, [setAvailableTools, sessionId])

  const toggleTool = useCallback(async (toolId: string) => {
    try {
      const startTime = performance.now()

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      }

      // Include session ID in headers if available
      if (sessionId) {
        headers['X-Session-ID'] = sessionId
      }

      const url = getApiUrl(`tools/${toolId}/toggle`)
      logger.network('POST', url, { toolId, 'X-Session-ID': sessionId })

      const response = await fetch(url, {
        method: 'POST',
        headers
      })

      const duration = performance.now() - startTime
      logger.apiResponse(response.status, url, Math.round(duration))

      if (response.ok) {
        // Extract session ID from response headers
        const responseSessionId = response.headers.get('X-Session-ID')

        if (responseSessionId && responseSessionId !== sessionId) {
          setSessionId(responseSessionId)
        }

        const result = await response.json()

        if (result.success) {
          logger.api('Tool toggled', { toolId, enabled: result.enabled })
          setAvailableTools(prev => prev.map(tool =>
            tool.id === toolId
              ? { ...tool, enabled: result.enabled }
              : tool
          ))
        }
      }
    } catch (error) {
      logger.error('Failed to toggle tool:', error)
    }
  }, [setAvailableTools, sessionId])

  const clearChat = useCallback(async () => {
    try {
      const startTime = performance.now()

      const url = getApiUrl('conversation/clear')
      logger.network('POST', url, { action: 'clearChat', 'X-Session-ID': sessionId })

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(sessionId && { 'X-Session-ID': sessionId })
        }
      })

      const duration = performance.now() - startTime
      logger.apiResponse(response.status, url, Math.round(duration))

      if (response.ok) {
        logger.api('Chat cleared', { sessionId })
        setMessages([])

        // Clear session ID to start fresh session
        setSessionId(null)
        sessionStorage.removeItem('chat-session-id')

        return true
      }
    } catch (error) {
      logger.error('Failed to clear chat:', error)
      // Reset state even if request fails
      setMessages([])
      setSessionId(null)
      sessionStorage.removeItem('chat-session-id')
    }
    return false
  }, [setMessages, sessionId])

  const sendMessage = useCallback(async (
    messageToSend: string,
    files?: File[],
    onSuccess?: () => void,
    onError?: (error: string) => void
  ) => {
    // Abort any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    const startTime = performance.now()

    try {
      let response: Response
      let url: string

      if (files && files.length > 0) {
        // Use multimodal endpoint for file uploads
        const formData = new FormData()
        formData.append('message', messageToSend)

        // Add all files to form data
        files.forEach((file) => {
          formData.append('files', file)
        })

        const headers: Record<string, string> = {}
        if (sessionId) {
          headers['X-Session-ID'] = sessionId
        }

        url = getApiUrl('stream/multimodal')
        logger.network('POST', url, {
          message: messageToSend.substring(0, 50) + '...',
          files: files.map(f => `${f.name} (${f.size} bytes)`),
          'X-Session-ID': sessionId
        })

        response = await fetch(url, {
          method: 'POST',
          headers,
          body: formData,
          signal: abortControllerRef.current.signal
        })
      } else {
        // Use regular text endpoint
        url = getApiUrl('stream/chat')
        logger.network('POST', url, {
          message: messageToSend.substring(0, 50) + '...',
          'X-Session-ID': sessionId
        })

        response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(sessionId && { 'X-Session-ID': sessionId })
          },
          body: JSON.stringify({ message: messageToSend }),
          signal: abortControllerRef.current.signal
        })
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      logger.apiResponse(response.status, url)

      // Extract session ID from response headers
      const responseSessionId = response.headers.get('X-Session-ID')

      if (responseSessionId && responseSessionId !== sessionId) {
        logger.api('Session ID created/updated', { sessionId: responseSessionId })
        setSessionId(responseSessionId)
      }

      logger.api('SSE stream started', { url })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No response body reader available')
      }

      let buffer = ''
      let eventCount = 0

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          logger.api('SSE stream completed', { eventCount })
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            continue
          }

          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.substring(6))

              // Handle new simplified events
              if (eventData.type && [
                'reasoning', 'response', 'tool_use', 'tool_result', 'tool_progress', 'complete', 'init', 'thinking', 'error',
                'spending_analysis_start', 'spending_analysis_step', 'spending_analysis_result',
                'spending_analysis_progress', 'spending_analysis_complete', 'spending_analysis_chart'
              ].includes(eventData.type)) {
                eventCount++
                logger.streamEvent(eventData.type, {
                  toolName: eventData.name,
                  step: eventData.step,
                  hasResult: !!eventData.result
                })
                handleStreamEvent(eventData as StreamEvent)
              } else {
                // Handle other event types
                logger.streamEvent('legacy', { eventType: eventData.type || 'unknown' })
                handleLegacyEvent(eventData)
              }
            } catch (parseError) {
              logger.error('Error parsing SSE data:', parseError)
            }
          }
        }
      }

      const totalDuration = performance.now() - startTime
      logger.timing('Total request duration', Math.round(totalDuration))

      setUIState(prev => ({ ...prev, isConnected: true }))
      onSuccess?.()
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        logger.api('Request aborted by user')
        return // Request was aborted, don't show error
      }

      logger.error('Error sending message:', error)
      setUIState(prev => ({ ...prev, isConnected: false, isTyping: false }))

      const errorMessage = `Connection error: ${error instanceof Error ? error.message : 'Unknown error'}`
      setMessages(prev => [...prev, {
        id: Date.now(),
        text: errorMessage,
        sender: 'bot',
        timestamp: new Date().toLocaleTimeString()
      }])

      onError?.(errorMessage)
    }
  }, [handleStreamEvent, handleLegacyEvent, setUIState, setMessages, sessionId])

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }, [])

  return {
    loadTools,
    toggleTool,
    clearChat,
    sendMessage,
    cleanup,
    sessionId,
    isLoadingTools: false
  }
}