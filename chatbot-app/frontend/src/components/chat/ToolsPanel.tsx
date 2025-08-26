import React from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Cog, ToggleLeft, ToggleRight } from 'lucide-react'
import { Tool } from '@/types/chat'
import { getToolIconById, getCategoryColor } from '@/utils/chat'

interface ToolsPanelProps {
  availableTools: Tool[]
  onToggleTool: (toolId: string) => void
}

export const ToolsPanel: React.FC<ToolsPanelProps> = ({ availableTools, onToggleTool }) => {
  return (
    <div className="w-80 border-l border-slate-200 bg-white/50 backdrop-blur-sm">
      <div className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Tools</h2>
        <ScrollArea className="h-[calc(100vh-200px)]">
          <div className="space-y-3">
            {availableTools.length === 0 ? (
              <div className="text-center py-8">
                <Cog className="h-8 w-8 mx-auto mb-2 text-gray-400" />
                <p className="text-sm text-gray-500">No tools available</p>
              </div>
            ) : (
              availableTools.map((tool) => {
                const IconComponent = getToolIconById(tool.id)
                return (
                  <div
                    key={tool.id}
                    className={`p-4 rounded-xl border transition-all duration-200 ${
                      tool.enabled 
                        ? 'bg-white border-green-200 shadow-sm' 
                        : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="p-2 bg-slate-100 rounded-lg">
                          <IconComponent className="h-4 w-4 text-gray-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-medium text-sm text-gray-900 truncate">
                              {tool.name}
                            </h3>
                            <Badge 
                              variant="outline" 
                              className={`text-xs px-2 py-0.5 ${getCategoryColor(tool.category)}`}
                            >
                              {tool.category}
                            </Badge>
                          </div>
                          <p className="text-xs text-gray-500 line-clamp-2 mb-3">
                            {tool.description}
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onToggleTool(tool.id)}
                        className="ml-2 p-1 h-auto"
                      >
                        {tool.enabled ? (
                          <ToggleRight className="h-5 w-5 text-green-600" />
                        ) : (
                          <ToggleLeft className="h-5 w-5 text-gray-400" />
                        )}
                      </Button>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
