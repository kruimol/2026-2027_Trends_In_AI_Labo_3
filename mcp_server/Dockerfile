# MCP-server in een container. Bouwt met uv en serveert op poort 8000.
# Gebaseerd op de officiële uv-image met Python 3.12 erin.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# uv-instellingen:
# - kopieer pakketten i.p.v. hardlinks (werkt betrouwbaar over container-lagen);
# - compileer bytecode voor een iets snellere start;
# - gebruik de Python uit de image (nooit een extra versie downloaden).
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# 1. Eerst alleen de dependency-bestanden -> betere build-cache bij codewijzigingen.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 2. Dan de rest van de broncode.
COPY . .

# De SQLite-databank in een aparte map zodat ze via een volume kan persisteren.
ENV MCP_DB_PATH=/data/trends_ai.sqlite
RUN mkdir -p /data
VOLUME ["/data"]

# In de container op alle interfaces luisteren (niet 127.0.0.1), anders is poort
# 8000 van buitenaf onbereikbaar.
ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8000
EXPOSE 8000

# Draai in de reeds gesyncte omgeving (geen netwerk/sync meer nodig bij het starten).
CMD ["uv", "run", "--no-sync", "python", "server.py"]
