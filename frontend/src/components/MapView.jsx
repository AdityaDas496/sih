import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet.markercluster';

import { MAP_DEFAULTS, COLOR_SCHEME, SEVERITY_SCALE } from '../config';

export function MapView({ 
  eventsGeoJSON, 
  facilitiesGeoJSON, 
  showFacilities, 
  useClustering, 
  activeBasemap = 'osm',
  targetLocation,
  onSelectEvent 
}) {
  const mapRef = useRef(null);
  const leafletMapInstance = useRef(null);
  const eventsLayerRef = useRef(null);
  const facilitiesLayerRef = useRef(null);
  const tileLayersRef = useRef({});

  // Initialize Leaflet Map Instance
  useEffect(() => {
    if (leafletMapInstance.current || !mapRef.current) return;

    // Free, Public High-Definition Basemaps (NO API KEY REQUIRED)
    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    });

    const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 18,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP'
    });

    const esriTopo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase'
    });

    const esriGray = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
    });

    tileLayersRef.current = {
      osm,
      satellite: esriSatellite,
      topo: esriTopo,
      gray: esriGray
    };

    const map = L.map(mapRef.current, {
      center: MAP_DEFAULTS.center,
      zoom: MAP_DEFAULTS.zoom,
      minZoom: MAP_DEFAULTS.minZoom,
      zoomControl: false,
      layers: [osm]
    });

    // Zoom-in / Zoom-out Control at Bottom Right Corner
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Native Leaflet Basemap Layer Control (positioned below header)
    const baseMaps = {
      "OpenStreetMap Standard": osm,
      "Esri Satellite Imagery": esriSatellite,
      "Esri World Topographic": esriTopo,
      "Esri Light Gray Canvas": esriGray
    };

    L.control.layers(baseMaps, null, { position: 'topright', collapsed: false }).addTo(map);

    leafletMapInstance.current = map;

    return () => {
      if (leafletMapInstance.current) {
        leafletMapInstance.current.remove();
        leafletMapInstance.current = null;
      }
    };
  }, []);

  // Update active basemap dynamically
  useEffect(() => {
    const map = leafletMapInstance.current;
    if (!map || !tileLayersRef.current) return;

    const layers = tileLayersRef.current;
    
    // Remove all tile layers
    Object.values(layers).forEach(layer => {
      if (map.hasLayer(layer)) {
        map.removeLayer(layer);
      }
    });

    // Add selected layer
    const selectedLayer = layers[activeBasemap] || layers.osm;
    selectedLayer.addTo(map);
  }, [activeBasemap]);

  // Fly to target location when selected from search bar
  useEffect(() => {
    const map = leafletMapInstance.current;
    if (!map || !targetLocation) return;

    map.flyTo([targetLocation.lat, targetLocation.lon], targetLocation.zoom || 15, {
      animate: true,
      duration: 1.5
    });
  }, [targetLocation]);

  // Global handler for Leaflet popup button click
  useEffect(() => {
    window.handleSelectEventById = (detectionId) => {
      if (!eventsGeoJSON || !eventsGeoJSON.features) return;
      const feat = eventsGeoJSON.features.find(f => String(f.properties.detection_id) === String(detectionId));
      if (feat && onSelectEvent) {
        onSelectEvent(feat);
      }
    };
    return () => {
      delete window.handleSelectEventById;
    };
  }, [eventsGeoJSON, onSelectEvent]);

  // Render Industrial Facilities Layer
  useEffect(() => {
    const map = leafletMapInstance.current;
    if (!map) return;

    if (facilitiesLayerRef.current) {
      map.removeLayer(facilitiesLayerRef.current);
      facilitiesLayerRef.current = null;
    }

    if (!showFacilities || !facilitiesGeoJSON || !facilitiesGeoJSON.features) return;

    const layer = L.geoJSON(facilitiesGeoJSON, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 4,
          fillColor: '#1976d2',
          color: '#0d47a1',
          weight: 1.2,
          opacity: 0.9,
          fillOpacity: 0.8
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        layer.bindPopup(`
          <div style="font-family: sans-serif; font-size: 12px;">
            <strong style="color: #1976d2;">Industrial Facility</strong>
            <div style="font-weight: 700; margin-top: 4px; color: #263238; font-size: 13px;">${p.facility_name}</div>
            <div style="font-size: 11px; color: #546e7a; margin-top: 2px;">
              Type: <b>${(p.facility_type || '').replace('_', ' ')}</b>
            </div>
            ${p.status ? `<div style="font-size: 11px; color: #546e7a;">Status: ${p.status}</div>` : ''}
          </div>
        `);
      }
    });

    layer.addTo(map);
    facilitiesLayerRef.current = layer;
  }, [facilitiesGeoJSON, showFacilities]);

  // Render Fire Event Markers & Marker Clustering
  useEffect(() => {
    const map = leafletMapInstance.current;
    if (!map) return;

    if (eventsLayerRef.current) {
      map.removeLayer(eventsLayerRef.current);
      eventsLayerRef.current = null;
    }

    if (!eventsGeoJSON || !eventsGeoJSON.features || eventsGeoJSON.features.length === 0) return;

    const geoJsonLayer = L.geoJSON(eventsGeoJSON, {
      pointToLayer: (feature, latlng) => {
        const p = feature.properties;
        const fireType = p.fire_type || 'OTHER_NATURAL';
        const severity = p.severity || 'LOW';

        let iconUrl = '/icons/fire.svg';
        if (fireType === 'INDUSTRIAL') {
          iconUrl = '/icons/industrial.svg';
        } else if (fireType === 'FOREST') {
          iconUrl = '/icons/forest.svg';
        } else {
          iconUrl = '/icons/fire.svg';
        }

        let size = 26;
        if (severity === 'HIGH') size = 32;
        else if (severity === 'MEDIUM') size = 26;
        else size = 20;

        const customIcon = L.icon({
          iconUrl: iconUrl,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
          popupAnchor: [0, -size / 2]
        });

        return L.marker(latlng, { icon: customIcon });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties;
        const confPct = p.classification_confidence ? (p.classification_confidence * 100).toFixed(1) : 'N/A';
        const typeClass = (p.fire_type || '').toLowerCase();
        
        layer.bindPopup(`
          <div class="popup-title">
            <span>${p.fire_type || 'FIRE EVENT'}</span>
            <span class="badge ${typeClass}">${p.fire_type}</span>
          </div>
          <div class="popup-row">
            <span class="popup-label">Classification Confidence</span>
            <span class="popup-val" style="color: #1976d2;">${confPct}%</span>
          </div>
          <div class="popup-row">
            <span class="popup-label">Severity</span>
            <span class="popup-val">${p.severity || 'N/A'}</span>
          </div>
          <div class="popup-row">
            <span class="popup-label">FRP / Brightness</span>
            <span class="popup-val">${p.frp} MW / ${p.brightness} K</span>
          </div>
          <div class="popup-row">
            <span class="popup-label">Date & Time</span>
            <span class="popup-val">${p.acq_date} ${p.acq_time}</span>
          </div>
          <div class="popup-row">
            <span class="popup-label">Nearest Industry</span>
            <span class="popup-val">${p.nearest_facility_name || 'N/A'} (${p.distance_to_nearest_industry_km} km)</span>
          </div>
          <button class="popup-btn" onclick="window.handleSelectEventById('${p.detection_id}')">View Full Details &rarr;</button>
        `);

        layer.on('click', () => {
          if (onSelectEvent) onSelectEvent(feature);
        });
      }
    });

    if (useClustering && L.markerClusterGroup) {
      const clusterGroup = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        disableClusteringAtZoom: 12
      });
      clusterGroup.addLayer(geoJsonLayer);
      clusterGroup.addTo(map);
      eventsLayerRef.current = clusterGroup;
    } else {
      geoJsonLayer.addTo(map);
      eventsLayerRef.current = geoJsonLayer;
    }
  }, [eventsGeoJSON, useClustering, onSelectEvent]);

  return (
    <div className="map-container" ref={mapRef} id="map"></div>
  );
}
