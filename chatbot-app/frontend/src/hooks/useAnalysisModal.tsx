'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

interface AnalysisModalState {
  isOpen: boolean;
  toolUseId: string | null;
  sessionId: string | null;
}

interface AnalysisModalContextType {
  state: AnalysisModalState;
  openModal: (toolUseId: string, sessionId: string) => void;
  closeModal: () => void;
}

const AnalysisModalContext = createContext<AnalysisModalContextType | null>(null);

export function AnalysisModalProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AnalysisModalState>({
    isOpen: false,
    toolUseId: null,
    sessionId: null,
  });

  const openModal = useCallback((toolUseId: string, sessionId: string) => {
    setState({ isOpen: true, toolUseId, sessionId });
    
    const newUrl = `/analysis/${toolUseId}?sessionId=${sessionId}`;
    window.history.pushState({ modal: true, toolUseId, sessionId }, '', newUrl);
  }, []);

  const closeModal = useCallback(() => {
    setState({ isOpen: false, toolUseId: null, sessionId: null });
    
    if (window.history.state?.modal) {
      window.history.back();
    }
  }, []);

  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      if (event.state?.modal) {
        setState({
          isOpen: true,
          toolUseId: event.state.toolUseId,
          sessionId: event.state.sessionId,
        });
      } else {
        setState({
          isOpen: false,
          toolUseId: null,
          sessionId: null,
        });
      }
    };

    window.addEventListener('popstate', handlePopState);
    
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  const contextValue = {
    state,
    openModal,
    closeModal
  };

  return (
    <AnalysisModalContext.Provider value={contextValue}>
      {children}
    </AnalysisModalContext.Provider>
  );
}

export function useAnalysisModal() {
  const context = useContext(AnalysisModalContext);
  if (!context) {
    throw new Error('useAnalysisModal must be used within AnalysisModalProvider');
  }
  return context;
}