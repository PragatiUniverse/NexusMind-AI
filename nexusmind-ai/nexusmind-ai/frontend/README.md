# NexusMind AI frontend
Single-file UI (no build step). Run: `cd frontend && python3 -m http.server 5173` then open http://localhost:5173
It talks to the backend at http://localhost:8000. To change it, set `window.NEXUS_API = "https://your-api"` in a script tag before the main script.
Overview, Graph, Contradiction Radar and Detective use embedded SYNTHETIC demo data; Hypothesis Studio, Reports and Settings call the live API.
