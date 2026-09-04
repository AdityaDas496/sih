# FireWatch India — GIS Operations Web Application

Professional GIS-based web application for visualizing satellite thermal anomaly detections, Person 1 ML fire type classifications, and industrial facility context.

Built with **React 18**, **Vite**, **Leaflet / React-Leaflet**, **Leaflet MarkerCluster**, and **Lucide Icons**.

---

## 🎨 Design Principles & Aesthetics

Designed specifically as an **operations/GIS dashboard**:
- **Map-Centric**: The interactive map is the primary visual workspace.
- **Restrained & Professional**: White `#ffffff` and grey `#f5f6f7` floating control panels, clean slate `#263238` typography, zero neon or gaming bloat.
- **Strict Data Integrity**: All fire event locations are rendered strictly from original satellite VIIRS `[longitude, latitude]` coordinates (`Point`).
- **Explicit Terminology**: Model probability is explicitly labeled **"Classification confidence"** (never "Accuracy").
- **Canonical Fire Types**: Displays strictly **`Industrial`**, **`Forest`**, and **`Other Natural`** (stripping internal weak-label `_proxy` strings).

---

## 📁 Project Structure

```
frontend/
├── README.md
├── package.json
├── vite.config.js
├── index.html
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── index.css
    ├── config.js
    ├── services/
    │   └── api.js
    ├── hooks/
    │   └── useFireData.js
    └── components/
        ├── Header.jsx
        ├── FilterPanel.jsx
        ├── StatisticsCards.jsx
        ├── Legend.jsx
        ├── MapView.jsx
        ├── EventDetailDrawer.jsx
        ├── LoadingOverlay.jsx
        └── ErrorBanner.jsx
```

---

## 🚀 Setup & Installation

### 1. Requirements
- Node.js v18+
- NPM / Yarn

### 2. Installation

From the `frontend/` directory:

```bash
npm install
```

---

## ⚙️ Environment Variables

Set environment variables in a `.env` file inside `frontend/`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If `VITE_API_BASE_URL` is omitted, the frontend automatically defaults to `http://localhost:8000`.

---

## 💻 Running Development Server

Start the local development server:

```bash
npm run dev
```

Open your browser to: **[http://localhost:3000](http://localhost:3000)** (or the URL printed by Vite).

---

## 📦 Production Build

To build the optimized production distribution bundle:

```bash
npm run build
```

The output files will be compiled into `frontend/dist/`.

To preview the production build locally:

```bash
npm run preview
```

---

## 🛰️ Map Features & Controls

1. **Initial Extent**: Centered on India (`[20.5937, 78.9629]`, Zoom 5).
2. **Basemap Selector** (Top Right):
   - Carto Light (GIS operations standard)
   - Esri World Imagery (Satellite view)
   - OpenStreetMap
   - Carto Dark
3. **Marker Visuals**:
   - **Industrial Fire**: Red (`#d32f2f`)
   - **Forest Fire**: Green (`#388e3c`)
   - **Other Natural Fire**: Blue (`#1976d2`)
   - **High Severity**: Larger 10px marker with bold stroke
   - **Medium / Low Severity**: 7px / 5px markers
4. **Industrial Facilities Overlay**: Toggleable factory markers displaying facility name, industry type (Steel, Cement, Coal Power), and status.
5. **Interactive Event Detail Drawer**: Click any event marker to slide out complete attributes:
   - Event ID & Fire Type Badge
   - Classification Confidence %
   - Acquisition Date & Time
   - Fire Radiative Power (MW) & Brightness Temperature (K)
   - Satellite & Instrument
   - Distance to nearest industry & facility name/type
   - WorldCover landcover class & description
   - Direct verification links to Google Satellite, NASA FIRMS, and Google Earth.
