'use client';

import React, { useEffect, useState } from 'react';
import { ArrowLeft, Brain } from 'lucide-react';
import { Button } from './ui/button';
import { Markdown } from './ui/Markdown';
import { ChartRenderer } from './ChartRenderer';
import { getApiUrl } from '@/config/environment';

interface AnalysisData {
  content: string;
  title?: string;
  sessionId: string;
  toolUseId: string;
  chartIds?: string[];
}

interface AnalysisContentProps {
  toolUseId: string;
  sessionId: string;
  onClose?: () => void;
  showBackButton?: boolean;
}

export function AnalysisContent({ 
  toolUseId, 
  sessionId, 
  onClose, 
  showBackButton = true 
}: AnalysisContentProps) {
  const [analysisData, setAnalysisData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadAnalysis = async () => {
      try {
        setLoading(true);
        
        if (!sessionId) {
          throw new Error('Session ID is required');
        }
        
        const apiUrl = getApiUrl(`sessions/${sessionId}/analysis/${toolUseId}`);
        const response = await fetch(apiUrl);
        
        if (!response.ok) {
          throw new Error(`Failed to load analysis: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data.success || !data.analysis) {
          throw new Error('Analysis data not found');
        }
        
        setAnalysisData({
          content: data.analysis.content || '',
          title: data.analysis.title || 'Agent Analysis',
          sessionId,
          toolUseId,
          chartIds: data.analysis.charts?.chart_ids || []
        });
      } catch (err) {
        console.error('Error loading analysis:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    if (toolUseId && sessionId) {
      loadAnalysis();
    }
  }, [toolUseId, sessionId]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <h3 className="text-lg font-semibold mb-2">Loading Analysis</h3>
          <p className="text-muted-foreground">Please wait while we load your analysis...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="text-red-500 mb-4">
            <Brain className="h-16 w-16 mx-auto mb-4 opacity-50" />
          </div>
          <h3 className="text-lg font-semibold mb-2">Analysis Not Found</h3>
          <p className="text-muted-foreground mb-4">{error}</p>
          {onClose && (
            <Button onClick={onClose} variant="outline">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Go Back
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (!analysisData) {
    return null;
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      {showBackButton && (
        <div className="flex-shrink-0 border-b bg-background">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
            {onClose && (
              <Button 
                onClick={onClose} 
                variant="ghost" 
                size="sm"
                className="flex items-center gap-2"
              >
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            )}
            <div className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-blue-500" />
              <h1 className="text-lg font-semibold">{analysisData.title}</h1>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="space-y-6">
            {/* Analysis Content */}
            <div className="prose prose-slate dark:prose-invert max-w-none">
              <Markdown 
                size="base" 
                sessionId={analysisData.sessionId} 
                toolUseId={analysisData.toolUseId}
              >
                {analysisData.content}
              </Markdown>
            </div>
            
            {/* Charts */}
            {analysisData.chartIds && analysisData.chartIds.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-foreground">Visual Analysis</h3>
                {analysisData.chartIds.map((chartId: string) => (
                  <div key={chartId} className="border rounded-lg p-4 bg-card">
                    <ChartRenderer chartId={chartId} sessionId={analysisData.sessionId} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}