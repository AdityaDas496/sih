import React from 'react';

export function LoadingOverlay({ message = "Loading GIS datasets & model predictions..." }) {
  return (
    <div className="loading-overlay">
      <div className="spinner"></div>
      <span>{message}</span>
    </div>
  );
}
