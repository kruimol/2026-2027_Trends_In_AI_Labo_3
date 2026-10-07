# Studiecoach MCP-server in HTTP-modus, klaar om op een poort te serveren.
# We gebruiken de officiële uv-image met Python 3.11, zodat we dezelfde tooling
# hebben als lokaal.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# uv-instellingen: bytecode compileren (sneller opstarten) en bestanden kopiëren
# in plaats van hardlinken (betrouwbaarder in Docker-lagen).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Eerst alleen de afhankelijkheidsbestanden kopiëren en installeren. Zo blijft
# deze (trage) laag in de cache zolang de dependencies niet wijzigen.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Daarna pas de eigenlijke code en de startdata. Alleen wat de server nodig heeft.
COPY context_memory.py server.py seed_geheugen.json ./

# Draai in HTTP-modus en bind op alle interfaces binnen de container, zodat de
# poort van buiten de container bereikbaar is. Het geheugen schrijven we naar
# /app/data, een map die je als volume kan aankoppelen om data te bewaren.
ENV STUDIECOACH_TRANSPORT=http \
    STUDIECOACH_HOST=0.0.0.0 \
    STUDIECOACH_PORT=8000 \
    STUDIECOACH_GEHEUGEN=/app/data/geheugen.json

RUN mkdir -p /app/data
EXPOSE 8000

# uv run start de server in de door uv beheerde virtuele omgeving.
CMD ["uv", "run", "--no-dev", "server.py"]
