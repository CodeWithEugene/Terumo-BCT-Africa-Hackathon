# Putting the demo online

The app has two parts, and each goes to a host that suits it:

| Part | Host | Why |
| --- | --- | --- |
| Web app (`frontend/`) | Vercel | Static files. Rebuilds on every push to `main`. |
| Backend (`backend/`) | Render | A Python server with a database file, which Vercel does not run. |

The browser only ever talks to the Vercel address. Vercel passes `/api`, `/fhir` and `/export` on to the
backend (`frontend/vercel.json`), so the sign-in cookie stays on one site.

## 1. Backend on Render
1. Sign in at render.com with GitHub. **New → Blueprint**, pick this repo. Render reads `render.yaml`.
2. When asked for `SP_ALLOWED_ORIGINS`, leave it empty for now. Press **Apply**.
3. The first build takes about 5 minutes: it installs Python packages and builds the database from
   `data/raw`. The build needs about 600 MB of memory and the server about 300 MB at rest.
4. Copy the service address, for example `https://sanguis-providus-api.onrender.com`. Open
   `<address>/api/health` and check it says `"status":"ok"`.
5. If the address is not exactly `https://sanguis-providus-api.onrender.com`, change the three
   `destination` lines in `frontend/vercel.json` to match, commit and push.

## 2. Web app on Vercel
1. Sign in at vercel.com with GitHub. **Add New → Project**, import this repo.
2. Set **Root Directory** to `frontend`. Leave the rest as detected (Vite). Press **Deploy**.
3. Copy the Vercel address, for example `sanguis-providus.vercel.app`.

From now on every push to `main` redeploys both parts.

## 3. Join them
1. In Render: the service → **Environment** → set `SP_ALLOWED_ORIGINS` to the Vercel address with no
   `https://`, for example `sanguis-providus.vercel.app`. Save. The service restarts.
2. Open the Vercel address, press **Take the guided tour**, and accept one order to check sign-in and
   saving both work.
3. Put the Vercel address in `README.md` under "Live demo".

## Settings the backend reads
| Name | Value |
| --- | --- |
| `SP_SESSION_SECRET` | Long random text. Render generates it. |
| `SP_COOKIE_SECURE` | `1` |
| `SP_ALLOWED_ORIGINS` | The Vercel address, no `https://` |
| `SP_DEMO_LOGINS` | `1` shows the three test accounts |

## Good to know
- Decisions made on the hosted demo are kept until the next deploy, which rebuilds the database.
- The Oracle sync is run from a laptop that holds the wallet. The hosted demo does not need it.
- For the recorded video, run the app locally (`python scripts/dev.py`). It is the fastest and safest.
