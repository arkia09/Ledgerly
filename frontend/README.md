# Ledgerly frontend

React + TypeScript + Vite frontend for the local Ledgerly Django API. Uses a warm paper-and-brown palette, responsive navigation, dashboard, customer ledger, upload/review flow and reports. No hosted font or analytics services are used.

## Requirements

- Node.js 20.19+ or 22.12+ recommended. Node 24.12.0 is supported by Vite 6.
- Django backend running at `http://127.0.0.1:8000`.

## Run in PowerShell

From the project root:

```powershell
Set-Location .\frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://127.0.0.1:5173`. The Vite server uses port 5173 with `strictPort`, matching the backend CORS configuration. Start Django separately from `backend`:

```powershell
Set-Location ..\backend
python manage.py runserver 8000
```

Set `VITE_API_BASE_URL` in `.env` if the backend API uses another address. Restart Vite after changing `.env`.

## Features

- Overview cards and customers with outstanding balances.
- Customer search and per-customer transaction history.
- Image upload and editable extraction review table, including customer matching and struck-out rows.
- Balance and aging reports using the backend PNG endpoints and JSON bucket totals.
- Local/private status, warm paper styling, responsive layout and no external font dependency.

The upload extraction call is synchronous and may take several minutes on CPU. Keep the tab open while it runs. The review form only creates ledger entries after confirmation.
