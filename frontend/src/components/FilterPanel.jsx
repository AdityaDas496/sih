import React from 'react';
import { StatisticsCards } from './StatisticsCards';
import { Legend } from './Legend';

export function FilterPanel({ 
  filters, 
  updateFilter, 
  stats, 
  facilitiesGeoJSON, 
  eventsGeoJSON, 
  onSelectLocation, 
  onSelectEvent 
}) {
  return (
    <div className="sidebar-panel">
      <div>
        <div className="panel-section-title">Map Theme & Basemap</div>
        <div className="filter-group" style={{ marginBottom: '12px' }}>
          <label className="filter-label">Basemap Provider</label>
          <select 
            className="filter-select"
            value={filters.activeBasemap || 'osm'}
            onChange={(e) => updateFilter('activeBasemap', e.target.value)}
          >
            <option value="osm">🗺️ OpenStreetMap Standard</option>
            <option value="satellite">🛰️ Esri Satellite Imagery</option>
            <option value="topo">⛰️ Esri World Topographic</option>
            <option value="gray">⬜ Esri Light Gray Canvas</option>
          </select>
        </div>
      </div>

      <div>
        <div className="panel-section-title">Classification Filters</div>
        <div className="filter-group" style={{ marginBottom: '10px' }}>
          <label className="filter-label">Fire Type</label>
          <select 
            className="filter-select"
            value={filters.fire_type}
            onChange={(e) => updateFilter('fire_type', e.target.value)}
          >
            <option value="ALL">All Fire Types</option>
            <option value="INDUSTRIAL">Industrial</option>
            <option value="FOREST">Forest</option>
            <option value="OTHER_NATURAL">Other Natural</option>
          </select>
        </div>

        <div className="filter-group" style={{ marginBottom: '10px' }}>
          <label className="filter-label">Event Severity</label>
          <select 
            className="filter-select"
            value={filters.severity}
            onChange={(e) => updateFilter('severity', e.target.value)}
          >
            <option value="ALL">All Severities</option>
            <option value="HIGH">High (FRP ≥ 15 MW)</option>
            <option value="MEDIUM">Medium (FRP ≥ 5 MW)</option>
            <option value="LOW">Low</option>
          </select>
        </div>

        <div className="filter-group" style={{ marginBottom: '10px' }}>
          <label className="filter-label">Nearest Industry Type</label>
          <select 
            className="filter-select"
            value={filters.facility_type}
            onChange={(e) => updateFilter('facility_type', e.target.value)}
          >
            <option value="ALL">All Industry Types</option>
            <option value="steel">Steel Plants</option>
            <option value="cement">Cement Plants</option>
            <option value="coal_power">Coal Power Stations</option>
          </select>
        </div>

        <div className="filter-group" style={{ marginBottom: '12px' }}>
          <div style={{ display: 'flex', justify_content: 'space-between', fontSize: '11px', color: '#455a64' }}>
            <span>Min Classification Confidence</span>
            <span>{Math.round(filters.min_confidence * 100)}%</span>
          </div>
          <input 
            type="range" 
            min="0.0" 
            max="0.99" 
            step="0.05"
            value={filters.min_confidence}
            onChange={(e) => updateFilter('min_confidence', parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: '#37474f', cursor: 'pointer' }}
          />
        </div>
      </div>

      <div>
        <div className="panel-section-title">Map Layers & Options</div>
        <label className="toggle-row">
          <span>Show Industrial Facilities</span>
          <input 
            type="checkbox" 
            checked={filters.showFacilities} 
            onChange={(e) => updateFilter('showFacilities', e.target.checked)} 
          />
        </label>
        <label className="toggle-row">
          <span>Marker Clustering</span>
          <input 
            type="checkbox" 
            checked={filters.useClustering} 
            onChange={(e) => updateFilter('useClustering', e.target.checked)} 
          />
        </label>
        <label className="toggle-row">
          <span>Near Industry Only (&le; 1 km)</span>
          <input 
            type="checkbox" 
            checked={filters.nearIndustryOnly} 
            onChange={(e) => updateFilter('nearIndustryOnly', e.target.checked)} 
          />
        </label>
      </div>

      <div>
        <div className="panel-section-title">Summary Statistics</div>
        <StatisticsCards stats={stats} />
      </div>

      <Legend showFacilities={filters.showFacilities} />
    </div>
  );
}
