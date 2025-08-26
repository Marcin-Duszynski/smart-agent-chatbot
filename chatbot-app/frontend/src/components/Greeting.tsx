'use client';

import React from 'react';

export function Greeting() {
  return (
    <div className="w-full flex flex-col justify-center items-center min-h-[60vh]">
      <div className="mb-6 animate-fade-in">
        <img 
          src="/strands.svg" 
          alt="Strands Logo" 
          width="80" 
          height="80" 
          className="mx-auto mb-4"
        />
      </div>
      <div className="text-2xl font-semibold text-slate-900 mb-2 animate-fade-in">
        Hello! I'm <span className="text-emerald-500">Strands</span>
      </div>
      <div className="text-xl text-slate-500 animate-fade-in-delay">
        What can I help you with today?
      </div>
    </div>
  );
}
