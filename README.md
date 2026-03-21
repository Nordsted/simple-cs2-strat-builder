# CS2 Chat Strat Builder

A lightweight web app for Counter-Strike 2 strategies in team chat. Users can choose a map, pick a side, select a strategy, and generate one combined console command with binds for numpad 1-9.

## Tech stack

- **Frontend:** static HTML, CSS, and vanilla JavaScript.
- **Backend:** Python standard library (`http.server`) with no web framework.
- **Database:** SQLite through the Python standard library.
- **Deploy:** one Docker container through `compose.yaml`.

This stack is intentionally small to keep CPU, RAM, and disk usage low, making it a good fit for Raspberry Pi deployments.

## Features

- Filter strategies by map and side (`T` or `CT`).
- Generate one chained CS2 command with `bind` commands for numpad 1-9.
- Copy the command to the clipboard.
- Open a selectable fallback view when clipboard access is unavailable.
- Save your own community strategies into SQLite.
- Maintain seed strategies per map through separate JSON files in `strats/`.

## Strategy maintenance

Built-in strategy seed data now lives in one file per map:

- `strats/ancient.json`
- `strats/anubis.json`
- `strats/dust2.json`
- `strats/inferno.json`
- `strats/mirage.json`
- `strats/nuke.json`
- `strats/overpass.json`
- `strats/train.json`
- `strats/vertigo.json`

The repository also keeps `strats/strats_baseline.json` as the source bundle used to refresh those per-map files.
That makes it easy to add or edit map-specific strategies without touching the backend code.

## Verification

The repository includes a GitHub Actions workflow at `.github/workflows/verify.yml` that:

- compiles the Python sources
- runs the unit test suite
- runs a local smoke test against the HTTP server
- validates Docker Compose and performs a containerized smoke test

You can run the same non-Docker checks locally with:

```bash
python3 -m py_compile app.py tests/test_app.py scripts/smoke_test.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/smoke_test.py
```

## Local development

```bash
python3 app.py
```

Then open `http://localhost:8080`.

## Run with Docker

```bash
docker compose up --build
```

The app is exposed on `http://localhost:8080`, and the SQLite database is stored in the Docker volume `cs2_strat_data`.

## Deploy on Railway with Railpack

This repository now includes a root `railway.json` that forces Railway to use the `RAILPACK` builder even though the project also keeps a local `Dockerfile` for Docker Compose deployments.

Railway will run the app with:

```bash
python3 app.py
```

and use `GET /healthz` as the deployment health check.

If you create a persistent Railway volume, set `DATABASE_PATH` to a file inside that mounted volume so community strategies survive redeploys.

## Raspberry Pi notes

The app avoids heavy frameworks and external runtime dependencies, so it remains simple to run on a Raspberry Pi both directly and in Docker.

## Future Steam login

You mentioned Steam login as a way to control who can add strategies. A good next step would be:

1. Steam OpenID login in the backend.
2. A user table in SQLite keyed by Steam ID.
3. Strategy ownership with private/public visibility.
4. Moderation or admin flows for shared strategies.

The current version stays intentionally simple, while keeping the data model and API shape easy to extend.
