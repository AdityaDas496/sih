import { API_BASE_URL } from '../config';

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error (${response.status}): ${errorText || response.statusText}`);
  }

  return response.json();
}

export const api = {
  getHealth: async () => {
    return fetchJSON(`${API_BASE_URL}/health`);
  },

  getDetectionsGeoJSON: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.fire_type && filters.fire_type !== 'ALL') {
      params.append('fire_type', filters.fire_type);
    }
    if (filters.severity && filters.severity !== 'ALL') {
      params.append('severity', filters.severity);
    }
    if (filters.branch && filters.branch !== 'ALL') {
      params.append('branch', filters.branch);
    }
    if (filters.facility_type && filters.facility_type !== 'ALL') {
      params.append('facility_type', filters.facility_type);
    }
    if (filters.min_confidence && filters.min_confidence > 0) {
      params.append('min_confidence', filters.min_confidence);
    }
    if (filters.limit) {
      params.append('limit', filters.limit);
    }

    const queryStr = params.toString();
    const url = `${API_BASE_URL}/api/detections/geojson${queryStr ? `?${queryStr}` : ''}`;
    return fetchJSON(url);
  },

  getDetectionById: async (detectionId) => {
    return fetchJSON(`${API_BASE_URL}/api/detections/${detectionId}`);
  },

  getFacilitiesGeoJSON: async (facilityType = null) => {
    const queryStr = facilityType && facilityType !== 'ALL' ? `?facility_type=${facilityType}` : '';
    return fetchJSON(`${API_BASE_URL}/api/facilities/geojson${queryStr}`);
  },

  getStatistics: async () => {
    return fetchJSON(`${API_BASE_URL}/api/statistics`);
  }
};
