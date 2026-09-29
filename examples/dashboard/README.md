# Dashboard example

A tiny standard-library HTTP server that wraps every `apibaseball` method
behind a local `/api/*` route, plus a static page
([public/index.html](public/index.html), shared with the TypeScript example)
that lets you trigger each method from the browser and inspect the raw
response. The API key never reaches the browser — all requests go through
the server.

## Run it

From the `pyton/` directory, install the SDK in editable mode:

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

Then start the example:

```bash
APIBASEBALL_KEY=your-api-key .venv/bin/python examples/dashboard/server.py
```

Open http://localhost:3000 and click "Ruleaza toate metodele" (or run
methods individually) to exercise the SDK.

## Notes

- `PORT` is optional and defaults to `3000`.
- No third-party packages are needed; the server uses `http.server`.
