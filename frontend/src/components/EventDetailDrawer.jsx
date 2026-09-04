import React from 'react';
import { X, ExternalLink, MapPin, Factory, Calendar, Activity } from 'lucide-react';

export function EventDetailDrawer({ event, onClose }) {
  if (!event) return null;

  const props = event.properties || event;
  const coords = event.geometry?.coordinates || [props.longitude, props.latitude];
  const lon = coords[0];
  const lat = coords[1];

  const fireTypeClass = (props.fire_type || '').toLowerCase();
  const severityClass = (props.severity || '').toLowerCase();
  const confPct = props.classification_confidence ? (props.classification_confidence * 100).toFixed(1) : 'N/A';

  const gmapsUrl = `https://www.google.com/maps/@?api=1&map_action=map&center=${lat},${lon}&zoom=17&basemap=satellite`;
  const firmsUrl = `https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@${lon},${lat},12z`;
  const earthUrl = `https://earth.google.com/web/@${lat},${lon},1500a,1200d,35y,0h,0t,0r`;

  return (
    <div className="detail-drawer">
      <div className="drawer-header">
        <div>
          <div className="drawer-title">Event {props.detection_id || 'Detail'}</div>
          <div style={{ fontSize: '11px', color: '#65727b', marginTop: '2px' }}>
            VIIRS Detection • {props.acq_date} {props.acq_time} UTC
          </div>
        </div>
        <button className="drawer-close" onClick={onClose} title="Close Panel">
          <X size={18} />
        </button>
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        <span className={`badge ${fireTypeClass}`}>{props.fire_type || 'N/A'}</span>
        <span className={`badge ${severityClass}`}>{props.severity || 'N/A'}</span>
      </div>

      <table className="detail-table">
        <tbody>
          <tr>
            <td className="label">Classification Confidence</td>
            <td className="val" style={{ color: '#1976d2' }}>{confPct}%</td>
          </tr>
          <tr>
            <td className="label">Latitude / Longitude</td>
            <td className="val">{lat.toFixed(5)}, {lon.toFixed(5)}</td>
          </tr>
          <tr>
            <td className="label">Fire Radiative Power (FRP)</td>
            <td className="val">{props.frp ? `${props.frp} MW` : 'N/A'}</td>
          </tr>
          <tr>
            <td className="label">Brightness Temp (Ch 21/22)</td>
            <td className="val">{props.brightness ? `${props.brightness} K` : 'N/A'}</td>
          </tr>
          <tr>
            <td className="label">Brightness Temp (Ch 31)</td>
            <td className="val">{props.bright_t31 ? `${props.bright_t31} K` : 'N/A'}</td>
          </tr>
          <tr>
            <td className="label">Satellite / Instrument</td>
            <td className="val">{props.satellite || 'VIIRS'} / {props.instrument || 'VIIRS'}</td>
          </tr>
          <tr>
            <td className="label">Nearest Facility</td>
            <td className="val">{props.nearest_facility_name || 'None detected'}</td>
          </tr>
          <tr>
            <td className="label">Facility Type</td>
            <td className="val" style={{ textTransform: 'capitalize' }}>
              {props.nearest_facility_type ? props.nearest_facility_type.replace('_', ' ') : 'N/A'}
            </td>
          </tr>
          <tr>
            <td className="label">Distance to Industry</td>
            <td className="val">
              {props.distance_to_nearest_industry_km !== undefined ? `${props.distance_to_nearest_industry_km} km` : 'N/A'}
            </td>
          </tr>
          <tr>
            <td className="label">WorldCover Class</td>
            <td className="val">{props.worldcover_class !== undefined ? props.worldcover_class : 'N/A'}</td>
          </tr>
          <tr>
            <td className="label">Thermal Anomaly Score</td>
            <td className="val">{props.anomaly_score !== undefined ? props.anomaly_score : 'N/A'}</td>
          </tr>
        </tbody>
      </table>

      {props.contributing_factors && (
        <div style={{ background: '#f5f7f9', border: '1px solid #d9e2ec', borderRadius: '3px', padding: '9px', fontSize: '11px' }}>
          <strong style={{ color: '#334e68' }}>Contributing Factors:</strong>
          <p style={{ margin: '4px 0 0', color: '#486581', lineHeight: '1.4' }}>{props.contributing_factors}</p>
        </div>
      )}

      <div>
        <div style={{ fontSize: '11px', fontWeight: '700', color: '#52606d', marginBottom: '6px' }}>
          External Verification Maps
        </div>
        <div className="external-links">
          <a href={gmapsUrl} target="_blank" rel="noopener noreferrer" className="ext-link">
            Google Satellite <ExternalLink size={10} style={{ marginLeft: '2px' }} />
          </a>
          <a href={firmsUrl} target="_blank" rel="noopener noreferrer" className="ext-link">
            NASA FIRMS <ExternalLink size={10} style={{ marginLeft: '2px' }} />
          </a>
          <a href={earthUrl} target="_blank" rel="noopener noreferrer" className="ext-link">
            Google Earth <ExternalLink size={10} style={{ marginLeft: '2px' }} />
          </a>
        </div>
      </div>
    </div>
  );
}
