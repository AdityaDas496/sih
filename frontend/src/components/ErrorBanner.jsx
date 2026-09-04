import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export function ErrorBanner({ message, onRetry }) {
  return (
    <div style={{
      position: 'absolute',
      top: '70px',
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 1300,
      background: '#fff5f5',
      border: '1px solid #feb2b2',
      borderRadius: '6px',
      padding: '10px 18px',
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      boxShadow: '0 2px 10px rgba(0,0,0,0.12)',
      fontSize: '12px',
      color: '#c53030'
    }}>
      <AlertTriangle size={18} />
      <span>{message}</span>
      {onRetry && (
        <button 
          onClick={onRetry}
          style={{
            background: '#c53030',
            color: '#fff',
            border: 'none',
            borderRadius: '3px',
            padding: '5px 10px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          <RefreshCw size={12} /> Retry
        </button>
      )}
    </div>
  );
}
