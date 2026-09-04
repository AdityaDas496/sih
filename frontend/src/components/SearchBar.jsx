import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Search, X, MapPin } from 'lucide-react';

export function SearchBar({ facilitiesGeoJSON, eventsGeoJSON, onSelectLocation, onSelectEvent }) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Compute search results
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || q.length < 2) return [];

    const matches = [];

    // 1. Search Facilities (1,118 plants)
    if (facilitiesGeoJSON && facilitiesGeoJSON.features) {
      for (const feat of facilitiesGeoJSON.features) {
        const p = feat.properties;
        const name = (p.facility_name || '').toLowerCase();
        const type = (p.facility_type || '').toLowerCase();
        const id = (p.facility_id || '').toLowerCase();

        if (name.includes(q) || type.includes(q) || id.includes(q)) {
          const coords = feat.geometry?.coordinates || [0, 0];
          matches.push({
            id: `fac-${p.facility_id}`,
            category: 'FACILITY',
            title: p.facility_name,
            subtitle: `${(p.facility_type || '').replace('_', ' ')} • Plant`,
            icon: '/icons/industrial.svg',
            lat: coords[1],
            lon: coords[0],
            feature: feat
          });

          if (matches.length >= 6) break;
        }
      }
    }

    // 2. Search Fire Events
    if (eventsGeoJSON && eventsGeoJSON.features && matches.length < 10) {
      for (const feat of eventsGeoJSON.features) {
        const p = feat.properties;
        const facName = (p.nearest_facility_name || '').toLowerCase();
        const detId = (p.detection_id || '').toLowerCase();
        const fireType = (p.fire_type || '').toLowerCase();

        if (facName.includes(q) || detId.includes(q) || fireType.includes(q)) {
          const coords = feat.geometry?.coordinates || [p.longitude, p.latitude];
          let icon = '/icons/fire.svg';
          if (p.fire_type === 'INDUSTRIAL') icon = '/icons/industrial.svg';
          else if (p.fire_type === 'FOREST') icon = '/icons/forest.svg';

          matches.push({
            id: `evt-${p.detection_id}`,
            category: 'EVENT',
            title: `${p.fire_type} Fire (${p.detection_id})`,
            subtitle: `Near ${p.nearest_facility_name || 'Location'} • ${p.acq_date}`,
            icon: icon,
            lat: coords[1],
            lon: coords[0],
            feature: feat
          });

          if (matches.length >= 10) break;
        }
      }
    }

    return matches;
  }, [query, facilitiesGeoJSON, eventsGeoJSON]);

  const handleSelect = (item) => {
    setQuery(item.title);
    setIsOpen(false);

    if (onSelectLocation) {
      onSelectLocation({
        lat: item.lat,
        lon: item.lon,
        zoom: 15,
        title: item.title
      });
    }

    if (item.category === 'EVENT' && onSelectEvent) {
      onSelectEvent(item.feature);
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <Search size={14} style={{ position: 'absolute', left: '10px', color: '#65727b' }} />
        <input 
          type="text"
          className="filter-input"
          style={{ 
            paddingLeft: '30px', 
            paddingRight: query ? '26px' : '10px',
            height: '32px',
            borderRadius: '4px',
            fontSize: '12px',
            background: '#ffffff',
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
          }}
          placeholder="Search Plant or Location"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
        />
        {query && (
          <button
            onClick={() => {
              setQuery('');
              setIsOpen(false);
            }}
            style={{
              position: 'absolute',
              right: '6px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#748087',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* Autocomplete Dropdown List */}
      {isOpen && results.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          zIndex: 1400,
          background: '#ffffff',
          border: '1px solid #c7cdd1',
          borderRadius: '4px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.16)',
          marginTop: '4px',
          maxHeight: '260px',
          overflowY: 'auto'
        }}>
          {results.map((item) => (
            <div
              key={item.id}
              onClick={() => handleSelect(item)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '8px 10px',
                borderBottom: '1px solid #f0f4f8',
                cursor: 'pointer',
                transition: 'background 0.15s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#f5f7f9'}
              onMouseLeave={(e) => e.currentTarget.style.background = '#ffffff'}
            >
              <img src={item.icon} alt="" style={{ width: '20px', height: '20px', objectFit: 'contain' }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: '#263238', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.title}
                </div>
                <div style={{ fontSize: '10px', color: '#65727b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.subtitle}
                </div>
              </div>
              <MapPin size={12} style={{ color: '#1976d2', flexShrink: 0 }} />
            </div>
          ))}
        </div>
      )}

      {isOpen && query.trim().length >= 2 && results.length === 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          zIndex: 1400,
          background: '#ffffff',
          border: '1px solid #c7cdd1',
          borderRadius: '4px',
          padding: '10px',
          fontSize: '11px',
          color: '#748087',
          textAlign: 'center',
          boxShadow: '0 4px 16px rgba(0,0,0,0.16)',
          marginTop: '4px'
        }}>
          No plants or events found matching "{query}"
        </div>
      )}
    </div>
  );
}
