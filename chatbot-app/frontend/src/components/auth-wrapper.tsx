'use client';

import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useEffect, useState } from 'react';

export default function AuthWrapper({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isLocalDev, setIsLocalDev] = useState(false);
  const [hasCognitoConfig, setHasCognitoConfig] = useState(false);
  const [isConfigured, setIsConfigured] = useState(false);

  useEffect(() => {
    // Initialize Amplify config on client side
    const initializeAmplify = async () => {
      await import('../lib/amplify-config');
      
      // Check if we're in local development
      const localDev = typeof window !== 'undefined' &&
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

      // Check if Cognito config is available
      const cognitoConfig = !!(process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID &&
        process.env.NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID);

      setIsLocalDev(localDev);
      setHasCognitoConfig(cognitoConfig);
      setIsConfigured(true);
    };

    initializeAmplify();
  }, []);

  // Show loading until configuration is complete
  if (!isConfigured) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // In local development or without Cognito config, skip authentication
  if (isLocalDev || !hasCognitoConfig) {
    return (
      <div className="min-h-screen">
        <div className="flex justify-between items-center p-4 bg-white dark:bg-gray-900 border-b">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">Strands Chatbot</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {isLocalDev ? 'Local Development' : 'Guest Mode'}
            </span>
          </div>
        </div>
        {children}
      </div>
    );
  }

  // In production with Cognito config, use Authenticator
  return (
    <Authenticator
      variation="modal"
      components={{
        Header() {
          return (
            <div className="text-center p-4">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Strands Chatbot
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mt-2">
                Sign in to access your AI assistant
              </p>
            </div>
          );
        },
      }}
    >
      {({ signOut, user }) => (
        <div className="min-h-screen">
          <div className="flex justify-between items-center p-4 bg-white dark:bg-gray-900 border-b">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold">Strands Chatbot</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Welcome, {user?.signInDetails?.loginId}
              </span>
              <button
                onClick={signOut}
                className="px-3 py-1 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
          {children}
        </div>
      )}
    </Authenticator>
  );
}