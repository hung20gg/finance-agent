#!/usr/bin/env bash

set -euo pipefail

# ==============================
# CONFIG
# ==============================

DB_NAME="postgres"
DB_USERNAME="postgres"
DB_PASSWORD="12345678"
MAX_CONNECTIONS=200

# ==============================
# CLEANUP & PRE-INSTALL
# ==============================

echo "🔍 Checking for existing PostgreSQL on port 5432..."
if command -v lsof >/dev/null 2>&1; then
    if sudo lsof -Pi :5432 -sTCP:LISTEN -t >/dev/null ; then
        echo "⚠️ Port 5432 is in use. Killing the process..."
        sudo lsof -t -i:5432 | xargs sudo kill -9 || true
    fi
fi

if dpkg -l | grep -q "postgresql-[0-9]"; then
    echo "🗑️ Existing PostgreSQL installation detected. Purging for a fresh start..."
    sudo apt-get purge -y postgresql* || true
    sudo apt-get autoremove -y
    sudo apt-get autoclean -y
fi

# ==============================
# INSTALL POSTGRESQL
# ==============================

echo "📦 Installing PostgreSQL..."
sudo apt update
sudo apt install -y postgresql

# Detect version
PG_VERSION=$(ls /etc/postgresql | sort -nr | head -n1)
PG_CONF_DIR="/etc/postgresql/${PG_VERSION}/main"

echo "🔍 Detected PostgreSQL version: ${PG_VERSION}"

# ==============================
# SET max_connections
# ==============================

echo "⚙️ Setting max_connections=${MAX_CONNECTIONS}..."

PG_CONF="${PG_CONF_DIR}/postgresql.conf"

# Replace if exists, otherwise append
if grep -q "^#*max_connections" "$PG_CONF"; then
  sudo sed -i "s/^#*max_connections.*/max_connections = ${MAX_CONNECTIONS}/" "$PG_CONF"
else
  echo "max_connections = ${MAX_CONNECTIONS}" | sudo tee -a "$PG_CONF"
fi

# ==============================
# ENABLE PASSWORD AUTH
# ==============================

echo "🔐 Configuring authentication..."

PG_HBA="${PG_CONF_DIR}/pg_hba.conf"

sudo sed -i 's/^\s*local\s\+all\s\+all\s\+peer/local all all md5/' "$PG_HBA"

if ! grep -q "127.0.0.1/32" "$PG_HBA"; then
  echo "host all all 127.0.0.1/32 md5" | sudo tee -a "$PG_HBA"
fi

if ! grep -q "::1/128" "$PG_HBA"; then
  echo "host all all ::1/128 md5" | sudo tee -a "$PG_HBA"
fi

# ==============================
# RESTART SERVICE
# ==============================

echo "🔄 Restarting PostgreSQL..."
sudo systemctl restart postgresql

# ==============================
# VERIFY max_connections
# ==============================

echo "🔍 Verifying max_connections..."
sudo -u postgres psql -tAc "SHOW max_connections;"

# ==============================
# CREATE USER + SET PASSWORD
# ==============================

echo "👤 Creating user..."

sudo -u postgres psql -v ON_ERROR_STOP=1 <<EOF
DO \$\$
BEGIN
IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USERNAME}') THEN
  CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}' SUPERUSER;
END IF;
END
\$\$;

ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USERNAME};
EOF

# ==============================
# DONE
# ==============================

echo ""
echo "✅ PostgreSQL setup complete!"
echo "-----------------------------------"
echo "User: ${DB_USERNAME}"
echo "Database: ${DB_NAME}"
echo "Max connections: ${MAX_CONNECTIONS}"
echo ""
echo "Connect with:"
echo "psql -U ${DB_USERNAME} -d ${DB_NAME} -h localhost -W"
echo ""
echo "Service status:"
echo "sudo systemctl status postgresql"