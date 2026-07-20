FROM python:3.11-slim

WORKDIR /app

# Node/npm are required at runtime: PreviewAgent shells out to `npm`/`npx`
# to install dependencies and run the generated project's Vite dev server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# HOST=0.0.0.0 is set via docker-compose.yml, not baked in here — inside a
# container this only exposes the app to whatever ports compose publishes,
# not the whole network, unlike running HOST=0.0.0.0 directly on the host.
CMD ["python", "-m", "app.main"]
