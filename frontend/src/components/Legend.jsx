import React from 'react';

export function Legend({ showFacilities }) {
  return (
    <div className="legend-box">
      <div className="panel-section-title">Fire Type Legend & Icons</div>
      
      <div className="legend-item" style={{ gap: '10px' }}>
        <img src="/icons/industrial.svg" alt="Industrial Fire" style={{ width: '22px', height: '22px', objectFit: 'contain' }} />
        <span style={{ fontWeight: '600' }}>Industrial Fire</span>
      </div>

      <div className="legend-item" style={{ gap: '10px' }}>
        <img src="/icons/forest.svg" alt="Forest Fire" style={{ width: '22px', height: '22px', objectFit: 'contain' }} />
        <span style={{ fontWeight: '600' }}>Forest Fire</span>
      </div>

      <div className="legend-item" style={{ gap: '10px' }}>
        <img src="/icons/fire.svg" alt="Other Natural Fire" style={{ width: '22px', height: '22px', objectFit: 'contain' }} />
        <span style={{ fontWeight: '600' }}>Other Natural Fire</span>
      </div>

      {showFacilities && (
        <div className="legend-item" style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px dashed #cfd8dc', gap: '10px' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#1976d2', border: '1px solid #0d47a1', flexShrink: 0 }}></div>
          <span style={{ fontSize: '11px', color: '#546e7a' }}>Industrial Plant (Blue Dot)</span>
        </div>
      )}
    </div>
  );
}

