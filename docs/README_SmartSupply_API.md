# SmartSupply API

Backend API dla aplikacji mobilnej SmartSupply. API dziala tylko do odczytu i posredniczy miedzy aplikacja Android a baza SQL Server `SmartSupply`.

## Instalacja

```powershell
cd backend\python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Konfiguracja

Skopiuj `backend\python\.env.example` do `backend\python\.env` i ustaw polaczenie do SQL Servera.

## Uruchomienie

```powershell
cd backend\python
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Dokumentacja endpointow bedzie dostepna pod:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Endpointy startowe

- `GET /health`
- `GET /towary/search?q=...`
- `GET /towary/{towar_id}/360`
- `GET /towary/{towar_id}/obroty`
- `GET /towary/{towar_id}/sprzedaz`
- `GET /towary/{towar_id}/zakupy`
- `GET /towary/{towar_id}/stany`
- `GET /towary/{towar_id}/prognozy`
- `GET /towary/{towar_id}/rekomendacje`
- `GET /towary/{towar_id}/segmentacja`
- `GET /towary/{towar_id}/klasyfikacja-popytu`
- `GET /towary/{towar_id}/lead-time`
- `GET /towary/{towar_id}/sezonowosc`
- `GET /towary/{towar_id}/zapas-bezpieczenstwa`
- `GET /towary/{towar_id}/przeswietlenie`

Endpoint `/towary/{towar_id}/przeswietlenie` zwraca jeden zbiorczy dokument JSON dla ekranu Androida. Zawiera sekcje: `towar`, `obroty`, `sprzedaz`, `zakupy`, `stany`, `prognozy`, `rekomendacje`, `segmentacja`, `klasyfikacja_popytu`, `lead_time`, `sezonowosc`, `zapas_bezpieczenstwa`.

Android powinien komunikowac sie z tym API, a nie bezposrednio z SQL Serverem.
