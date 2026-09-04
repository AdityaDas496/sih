import React from 'react';

export function StatisticsCards({ stats }) {
  return (
    <div className="kpis-grid">
      <div className="kpi-card full-width">
        <div className="kpi-num">{stats.total.toLocaleString()}</div>
        <div className="kpi-label">Classified Fire Events</div>
      </div>
      <div className="kpi-card ind">
        <div className="kpi-num">{stats.industrial.toLocaleString()}</div>
        <div className="kpi-label">Industrial</div>
      </div>
      <div className="kpi-card for">
        <div className="kpi-num">{stats.forest.toLocaleString()}</div>
        <div className="kpi-label">Forest</div>
      </div>
      <div className="kpi-card nat">
        <div className="kpi-num">{stats.natural.toLocaleString()}</div>
        <div className="kpi-label">Other Natural</div>
      </div>
      <div className="kpi-card high">
        <div className="kpi-num">{stats.highSeverity.toLocaleString()}</div>
        <div className="kpi-label">High Severity</div>
      </div>
    </div>
  );
}
