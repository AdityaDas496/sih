import React, { useState } from 'react';
import { Header } from './components/Header';
import { FilterPanel } from './components/FilterPanel';
import { MapView } from './components/MapView';
import { EventDetailDrawer } from './components/EventDetailDrawer';
import { LoadingOverlay } from './components/LoadingOverlay';
import { ErrorBanner } from './components/ErrorBanner';
import { useFireData } from './hooks/useFireData';

export function App() {
  const {
    filters,
    updateFilter,
    backendConnected,
    isLoading,
    error,
    eventsGeoJSON,
    facilitiesGeoJSON,
    filteredStats,
    selectedEvent,
    setSelectedEvent,
    refreshData
  } = useFireData();

  const [targetLocation, setTargetLocation] = useState(null);

  const eventCount = eventsGeoJSON?.features?.length || 0;

  return (
    <div className="app-container">
      {/* Header with Centered Search Bar */}
      <Header 
        onRefresh={refreshData}
        isLoading={isLoading}
        facilitiesGeoJSON={facilitiesGeoJSON}
        eventsGeoJSON={eventsGeoJSON}
        onSelectLocation={setTargetLocation}
        onSelectEvent={setSelectedEvent}
      />

      {/* Floating Filter Sidebar */}
      <FilterPanel 
        filters={filters} 
        updateFilter={updateFilter} 
        stats={filteredStats}
        facilitiesGeoJSON={facilitiesGeoJSON}
        eventsGeoJSON={eventsGeoJSON}
        onSelectLocation={setTargetLocation}
        onSelectEvent={setSelectedEvent}
      />

      {/* Main Interactive Leaflet Map */}
      <MapView 
        eventsGeoJSON={eventsGeoJSON}
        facilitiesGeoJSON={facilitiesGeoJSON}
        showFacilities={filters.showFacilities}
        useClustering={filters.useClustering}
        activeBasemap={filters.activeBasemap}
        targetLocation={targetLocation}
        onSelectEvent={setSelectedEvent}
      />

      {/* Slide-out Event Detail Drawer */}
      <EventDetailDrawer 
        event={selectedEvent} 
        onClose={() => setSelectedEvent(null)} 
      />

      {/* Feedback Overlays */}
      {isLoading && <LoadingOverlay message="Loading satellite events & model predictions..." />}

      {error && !isLoading && (
        <ErrorBanner message={error} onRetry={refreshData} />
      )}

      {!isLoading && backendConnected && eventCount === 0 && (
        <div style={{
          position: 'absolute',
          bottom: '20px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 1200
        }}>
          <div className="empty-notice">
            No fire events match the selected filters.
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
