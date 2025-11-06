FROM python:3.12-slim

# Instala dependências básicas pro runner SRE
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq iputils-ping && \
    rm -rf /var/lib/apt/lists/*

# Copia projeto
WORKDIR /app
COPY . /app

# Instala o bot localmente
RUN pip install -e . && pip install "psycopg[binary]==3.2.*"

# Comando de start padrão
CMD ["bash", "scripts/sre-cron.sh"]
