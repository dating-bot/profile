# pgvector (как раньше) + PostGIS для geography / поиска «рядом»
FROM pgvector/pgvector:pg17

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-17-postgis-3 \
        postgresql-17-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

USER postgres
