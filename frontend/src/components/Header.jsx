import React from 'react';
import { Flame, RefreshCw } from 'lucide-react';
import { SearchBar } from './SearchBar';

export function Header({ 
  onRefresh, 
  isLoading, 
  facilitiesGeoJSON, 
  eventsGeoJSON, 
  onSelectLocation, 
  onSelectEvent 
}) {
  return (
    <header className="header">
      <div className="brand">
        <Flame className="brand-icon" />
        <div className="brand-text">
          <h1>VIKRAMAN</h1>
          <p>Satellite Thermal Anomaly Classification & Industrial GIS Context</p>
        </div>
      </div>

      <div style={{ flex: 1, maxWidth: '400px', margin: '0 20px', pointerEvents: 'auto' }}>
        <SearchBar 
          facilitiesGeoJSON={facilitiesGeoJSON}
          eventsGeoJSON={eventsGeoJSON}
          onSelectLocation={onSelectLocation}
          onSelectEvent={onSelectEvent}
        />
      </div>

      <div className="header-controls">
        <button 
          onClick={onRefresh} 
          disabled={isLoading}
          style={{
            background: '#ffffff',
            border: '1px solid #cbd1d5',
            borderRadius: '3px',
            padding: '6px 10px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '11px',
            fontWeight: '600',
            color: '#37474f',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)'
          }}
          title="Refresh Data"
        >
          <RefreshCw size={13} className={isLoading ? "spinner" : ""} />
          Refresh
        </button>
      </div>
    </header>
  );
}

