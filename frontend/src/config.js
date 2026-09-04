export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const MAP_DEFAULTS = {
  center: [20.5937, 78.9629], // Geographic center of India
  zoom: 5,
  minZoom: 4,
  maxZoom: 18
};

export const COLOR_SCHEME = {
  INDUSTRIAL: '#d32f2f', // Crisp Red
  FOREST: '#388e3c',     // Forest Green
  OTHER_NATURAL: '#1976d2' // Muted Slate Blue
};

export const SEVERITY_SCALE = {
  HIGH: { radius: 10, weight: 2, opacity: 1.0, label: 'High Severity (FRP ≥ 15 MW)' },
  MEDIUM: { radius: 7, weight: 1.5, opacity: 0.85, label: 'Medium Severity (FRP ≥ 5 MW)' },
  LOW: { radius: 5, weight: 1, opacity: 0.70, label: 'Low Severity' }
};
