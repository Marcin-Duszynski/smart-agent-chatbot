import React from 'react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Bot } from 'lucide-react'

export const TypingIndicator: React.FC = () => (
  <div className="flex justify-start">
    <div className="flex items-start space-x-3">
      <Avatar className="h-8 w-8 flex-shrink-0">
        <AvatarFallback className="bg-gradient-to-br from-blue-600 to-purple-600 text-white">
          <Bot className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <div className="bg-white rounded-2xl rounded-tl-md px-4 py-3 shadow-sm border border-slate-200">
        <div className="flex items-center space-x-3 text-gray-500">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
          </div>
          <span className="text-sm font-medium">AI is thinking...</span>
        </div>
      </div>
    </div>
  </div>
)
