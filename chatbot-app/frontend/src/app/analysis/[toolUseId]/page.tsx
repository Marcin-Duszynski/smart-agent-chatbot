'use client';

import React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AnalysisContent } from '@/components/AnalysisContent';

interface Props {
  params: Promise<{
    toolUseId: string;
  }>;
}

export default function AnalysisPage({ params }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toolUseId = React.use(params).toolUseId;
  const sessionId = searchParams.get('sessionId');

  const handleGoBack = () => {
    router.push('/');
  };

  if (!sessionId) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-semibold mb-2">Session Required</h3>
          <p className="text-muted-foreground">A session ID is required to view this analysis.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <AnalysisContent
        toolUseId={toolUseId}
        sessionId={sessionId}
        onClose={handleGoBack}
        showBackButton={true}
      />
    </div>
  );
}