'use client';

import useSWR from 'swr';
import { useCallback, useMemo } from 'react';
import { getApiUrl } from '@/config/environment';

export interface AgentAnalysisArtifact {
  id: string;
  title: string;
  content: string;
  isVisible: boolean;
  userClosedToolIds: string[]; // Track which tool execution IDs user has closed
  status: 'streaming' | 'idle';
  currentStep?: string;
  stepDescription?: string;
  chartIds: string[];
  boundingBox: {
    top: number;
    left: number;
    width: number;
    height: number;
  };
}

export const initialAgentAnalysisData: AgentAnalysisArtifact = {
  id: 'init',
  title: '',
  content: '',
  status: 'idle',
  isVisible: false,
  userClosedToolIds: [],
  currentStep: undefined,
  stepDescription: undefined,
  chartIds: [],
  boundingBox: {
    top: 0,
    left: 0,
    width: 0,
    height: 0,
  },
};

type Selector<T> = (state: AgentAnalysisArtifact) => T;

export function useAgentAnalysisSelector<Selected>(selector: Selector<Selected>) {
  const { data: localAgentAnalysis } = useSWR<AgentAnalysisArtifact>('agent-analysis', null, {
    fallbackData: initialAgentAnalysisData,
  });

  const selectedValue = useMemo(() => {
    if (!localAgentAnalysis) return selector(initialAgentAnalysisData);
    return selector(localAgentAnalysis);
  }, [localAgentAnalysis, selector]);

  return selectedValue;
}

export function useAgentAnalysis() {
  const { data: localAgentAnalysis, mutate: setLocalAgentAnalysis } = useSWR<AgentAnalysisArtifact>(
    'agent-analysis',
    null,
    {
      fallbackData: initialAgentAnalysisData,
    },
  );

  const agentAnalysis = useMemo(() => {
    if (!localAgentAnalysis) return initialAgentAnalysisData;
    return localAgentAnalysis;
  }, [localAgentAnalysis]);

  const setAgentAnalysis = useCallback(
    (updaterFn: AgentAnalysisArtifact | ((current: AgentAnalysisArtifact) => AgentAnalysisArtifact)) => {
      setLocalAgentAnalysis((current: AgentAnalysisArtifact | undefined) => {
        const analysisToUpdate = current || initialAgentAnalysisData;

        let newState;
        if (typeof updaterFn === 'function') {
          newState = updaterFn(analysisToUpdate);
        } else {
          newState = updaterFn;
        }


        return newState;
      });
    },
    [setLocalAgentAnalysis],
  );

  const loadAnalysisFromMemory = useCallback(async (
    toolUseId: string, 
    sessionId: string, 
    toolName: string
  ) => {
    try {
      // Use the new session memory API
      const apiUrl = getApiUrl(`sessions/${sessionId}/analysis/${toolUseId}`);
      
      const response = await fetch(apiUrl);
      if (!response.ok) {
        throw new Error(`Failed to load analysis: ${response.statusText}`);
      }
      const data = await response.json();
      
      if (!data.success || !data.analysis) {
        throw new Error('Analysis data not found in response');
      }
      
      setAgentAnalysis(prev => ({
        ...prev,
        id: toolUseId, // Use toolUseId instead of sessionId for unique identification
        content: data.analysis.content || '',
        status: 'idle',
        title: 'Agent Analysis'
      }));
    } catch (error) {
      console.error('Error loading analysis from memory:', error);
      // Set error state
      setAgentAnalysis(prev => ({
        ...prev,
        id: toolUseId, // Use toolUseId for consistency
        content: 'Failed to load analysis. Please try again.',
        status: 'idle',
        title: 'Analysis Error'
      }));
    }
  }, [setAgentAnalysis]);

  const clearAnalysis = useCallback(() => {
    setAgentAnalysis(initialAgentAnalysisData);
  }, [setAgentAnalysis]);

  const resetAnalysisForNewSession = useCallback(() => {
    setAgentAnalysis({
      id: 'init',
      title: '',
      content: '',
      status: 'idle',
      isVisible: false,
      userClosedToolIds: [],
      currentStep: undefined,
      stepDescription: undefined,
      chartIds: [],
      boundingBox: {
        top: 0,
        left: 0,
        width: 0,
        height: 0,
      }
    });
  }, [setAgentAnalysis]);

  const clearContentOnly = useCallback(() => {
    setAgentAnalysis(prev => ({
      ...prev,
      content: '',
      chartIds: [],
      status: 'streaming' // Always start with streaming (loading) state
    }));
  }, [setAgentAnalysis]);

  return useMemo(
    () => ({
      agentAnalysis,
      setAgentAnalysis,
      loadAnalysisFromMemory,
      clearAnalysis,
      resetAnalysisForNewSession,
      clearContentOnly,
    }),
    [agentAnalysis, setAgentAnalysis, loadAnalysisFromMemory, clearAnalysis, resetAnalysisForNewSession, clearContentOnly],
  );
}
