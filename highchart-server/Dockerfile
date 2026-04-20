FROM ghcr.io/puppeteer/puppeteer:latest

WORKDIR /app

# Copy package manifests first (better layer caching)
COPY package*.json ./

# Fix ownership so pptruser can write
USER root
RUN chown -R pptruser:pptruser /app

# Switch to safe non-root user
USER pptruser

# Install production dependencies only
RUN npm install --omit=dev

# Copy application source
COPY . .

EXPOSE 3000

# Tunable at runtime via -e / environment:
#   POOL_SIZE       number of parallel browser workers (default 4)
#   MAX_QUEUE_SIZE  max pending render requests before 503 (default 50)
#   PAGE_TIMEOUT_MS per-render timeout in ms (default 30000)
#   PORT            server port (default 3000)

CMD ["node", "server.js"]