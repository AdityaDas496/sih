import { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../services/api';

export function useFireData() {
  const [filters, setFilters] = useState({
    fire_type: 'ALL',
    severity: 'ALL',
    facility_type: 'ALL',
    min_confidence: 0.0,
    activeBasemap: 'osm',
    showFacilities: false,
    useClustering: true,
    nearIndustryOnly: false
  });

  const [backendConnected, setBackendConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [eventsGeoJSON, setEventsGeoJSON] = useState({ type: 'FeatureCollection', features: [] });
  const [facilitiesGeoJSON, setFacilitiesGeoJSON] = useState({ type: 'FeatureCollection', features: [] });
  const [statistics, setStatistics] = useState({
    total_detected_events: 0,
    industrial_count: 0,
    forest_count: 0,
    other_natural_count: 0,
    high_severity_count: 0,
    medium_severity_count: 0,
    low_severity_count: 0
  });

  const [selectedEvent, setSelectedEvent] = useState(null);

  // Initial connection check & facilities load
  const initData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const health = await api.getHealth();
      setBackendConnected(health.status === 'ok');

      const [facGeoJSON, stats] = await Promise.all([
        api.getFacilitiesGeoJSON(),
        api.getStatistics()
      ]);

      setFacilitiesGeoJSON(facGeoJSON);
      setStatistics(stats);
    } catch (err) {
      console.error('Backend connection error:', err);
      setBackendConnected(false);
      setError('Unable to connect to backend server. Ensure backend is running at http://localhost:8000');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch detection events whenever filters change
  const fetchDetections = useCallback(async () => {
    setIsLoading(true);
    try {
      const geojson = await api.getDetectionsGeoJSON({
        fire_type: filters.fire_type,
        severity: filters.severity,
        facility_type: filters.facility_type,
        min_confidence: filters.min_confidence,
        limit: 5000
      });
      
      setEventsGeoJSON(geojson);
      setError(null);
    } catch (err) {
      console.error('Error fetching detection events:', err);
      setError('Failed to fetch fire detection events.');
    } finally {
      setIsLoading(false);
    }
  }, [filters.fire_type, filters.severity, filters.facility_type, filters.min_confidence]);

  useEffect(() => {
    initData();
  }, [initData]);

  useEffect(() => {
    if (backendConnected) {
      fetchDetections();
    }
  }, [backendConnected, fetchDetections]);

  // Client-side filtering for immediate toggles (nearIndustryOnly, etc.)
  const filteredFeatures = useMemo(() => {
    if (!eventsGeoJSON || !eventsGeoJSON.features) return [];
    
    let features = eventsGeoJSON.features;

    if (filters.nearIndustryOnly) {
      features = features.filter(f => f.properties.distance_to_nearest_industry_km <= 1.0);
    }

    return features;
  }, [eventsGeoJSON, filters.nearIndustryOnly]);

  // Compute live filtered statistics
  const filteredStats = useMemo(() => {
    const total = filteredFeatures.length;
    let ind = 0, forst = 0, nat = 0, high = 0;

    filteredFeatures.forEach(f => {
      const type = f.properties.fire_type;
      const sev = f.properties.severity;
      if (type === 'INDUSTRIAL') ind++;
      else if (type === 'FOREST') forst++;
      else if (type === 'OTHER_NATURAL') nat++;

      if (sev === 'HIGH') high++;
    });

    return {
      total,
      industrial: ind,
      forest: forst,
      natural: nat,
      highSeverity: high
    };
  }, [filteredFeatures]);

  const updateFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  return {
    filters,
    updateFilter,
    backendConnected,
    isLoading,
    error,
    eventsGeoJSON: { ...eventsGeoJSON, features: filteredFeatures },
    facilitiesGeoJSON,
    statistics,
    filteredStats,
    selectedEvent,
    setSelectedEvent,
    refreshData: initData
  };
}
