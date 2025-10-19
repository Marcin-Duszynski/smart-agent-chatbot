"use client"

import AuthWrapper from "@/components/auth-wrapper"
import { ChatInterface } from "@/components/ChatInterface"
import { AnalysisModalProvider, useAnalysisModal } from "@/hooks/useAnalysisModal"
import { Modal } from "@/components/ui/Modal"
import { AnalysisContent } from "@/components/AnalysisContent"
import { SidebarProvider } from "@/components/ui/sidebar"

// Modal component that uses the analysis modal context
function AnalysisModalContainer() {
  const { state, closeModal } = useAnalysisModal()

  if (!state.isOpen || !state.toolUseId || !state.sessionId) {
    return null
  }

  return (
    <Modal isOpen={state.isOpen} onClose={closeModal}>
      <AnalysisContent
        toolUseId={state.toolUseId}
        sessionId={state.sessionId}
        onClose={closeModal}
        showBackButton={false}
      />
    </Modal>
  )
}

// Wrapper component to ensure proper provider initialization
function EmbedAppContent() {
  return (
    <AnalysisModalProvider>
      <ChatInterface mode="embedded" />
      <AnalysisModalContainer />
    </AnalysisModalProvider>
  )
}

export default function EmbedPage() {
  return (
    <AuthWrapper>
      <div className="h-screen gradient-subtle text-foreground transition-all duration-300">
        <SidebarProvider defaultOpen={false}>
          <EmbedAppContent />
        </SidebarProvider>
      </div>
    </AuthWrapper>
  )
}
