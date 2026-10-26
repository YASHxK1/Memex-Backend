# Docker

These files build and run the Memex FastAPI backend from the repository root. Docker Compose runs the backend in embedded Qdrant mode by default and stores Qdrant data and downloaded model files in the persistent `memex-data` volume.

## Start

From this directory:

```bash
cp .env.example .env
# Edit .env and set MEMEX_API_TOKEN to a long random secret.
docker compose up --build -d
```

The first start downloads the configured embedding model and can take a while. Check startup with `docker compose logs -f` and liveness at `http://localhost:8000/health`. The service listens on port 8000; set `MEMEX_PORT` in `.env` to change the host port. Send the configured token as `Authorization: Bearer <token>` for `/v1/*` endpoints.

## Configuration and persistence

All application settings can be supplied as `MEMEX_*` variables in `.env`; the sample lists the supported settings and defaults. `MEMEX_API_TOKEN` is required. Embedded Qdrant data and the Hugging Face model cache are kept in the `memex-data` Docker volume across container rebuilds and restarts. To remove all persisted data, run `docker compose down -v`.

For Qdrant server mode, set `MEMEX_QDRANT_MODE=server` and set `MEMEX_QDRANT_URL` to the server's URL reachable from the container. The default URL in the sample (`http://qdrant:6333`) assumes a Compose service named `qdrant` on the same Docker network; otherwise use the appropriate host or service address. Embedded mode is intended for one backend process using that data volume.

To build without Compose, run these commands from the repository root:

```bash
docker build -f docker/Dockerfile -t memex-backend:local .
docker run --rm -p 8000:8000 \
  -e MEMEX_API_TOKEN='replace-with-a-long-random-secret' \
  -v memex-data:/data \
  memex-backend:local
```
