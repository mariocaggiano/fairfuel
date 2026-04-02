# ⛽ FairFuel

**Prezzi carburanti in Italia in tempo reale** — dati ufficiali MIMIT aggiornati ogni giorno.

🔗 **Frontend (Vercel):** `https://fairfuel.vercel.app`
🔗 **Backend API (Render):** `https://fairfuel-api.onrender.com`

---

## Funzionalità

- 🗺 Mappa interattiva con Leaflet + OpenStreetMap
- 🔍 Filtri per comune, provincia, brand, carburante, self/servito
- 📍 Ricerca per posizione GPS con raggio configurabile
- 💰 Lista ordinata dal più economico al più caro
- 🧭 Deep link navigazione verso Google Maps / Apple Maps
- ⏰ Aggiornamento automatico giornaliero alle 09:15 (dati MIMIT)
- 🔄 Aggiornamento manuale on-demand via pulsante

---

## Stack

- **Backend:** Python/Tornado + SQLite (deploy su Render free tier)
- **Frontend:** HTML/JS + Leaflet (deploy su Vercel)
- **Dati:** MIMIT Open Data (CSV giornaliero, separatore `|`)

---

## Deploy

### 1. Backend su Render
1. render.com → New → Blueprint
2. Connetti repo GitHub `fairfuel`
3. Render legge `render.yaml` e crea il servizio
4. Attendi primo build (~3 min)

### 2. Frontend su Vercel
1. vercel.com → Add New → Project
2. Root Directory: `frontend`
3. Env var: `FAIRFUEL_API_BASE` = `https://fairfuel-api.onrender.com`

### 3. CORS
Aggiungi URL Vercel a `CORS_ORIGINS` su Render.

---

## API Endpoints

| Metodo | Path | Descrizione |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Statistiche DB |
| GET | `/api/filters` | Brand, carburanti, province |
| GET | `/api/stations` | Ricerca distributori |
| POST | `/api/refresh` | Aggiornamento manuale |

---

## Fonte dati

Dati ufficiali **MIMIT** — separatore CSV `|` (da febbraio 2026), encoding UTF-8.

## Licenza

MIT — dati MIMIT soggetti a licenza CC BY 4.0
