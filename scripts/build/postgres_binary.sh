#!/usr/bin/env bash

set -euo pipefail

# ==============================
# CONFIG
# ==============================

DB_NAME="postgres"

# ==============================
# CHECK ENV VARS
# ==============================

if [[ -z "${DB_USERNAME:-}" || -z "${DB_PASSWORD:-}" ]]; then
echo "❌ ERROR: Please set DB_USERNAME and DB_PASSWORD"
echo "Example:"
echo "export DB_USERNAME=myuser"
echo "export DB_PASSWORD=mypassword"
exit 1
fi

# ==============================
# INSTALL POSTGRESQL
# ==============================

echo "📦 Installing PostgreSQL..."
sudo apt update
sudo apt install -y postgresql

# Detect version (e.g. 14, 15, 16)

PG_VERSION=$(ls /etc/postgresql | sort -nr | head -n1)
PG_CONF_DIR="/etc/postgresql/${PG_VERSION}/main"

echo "🔍 Detected PostgreSQL version: ${PG_VERSION}"

# ==============================
# ENABLE PASSWORD AUTH
# ==============================

echo "🔐 Configuring authentication..."

PG_HBA="${PG_CONF_DIR}/pg_hba.conf"

# Replace peer with md5 for local connections

sudo sed -i 's/^\s*local\s+all\s+all\s+peer/local all all md5/' "$PG_HBA"

# Ensure host lines exist

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
# CREATE USER + SET PASSWORD
# ==============================

echo "👤 Creating user..."

sudo -u postgres psql -v ON_ERROR_STOP=1 <<EOF
DO $$
BEGIN
IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USERNAME}') THEN
CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}' SUPERUSER;
END IF;
END
$$;

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
echo ""
echo "Connect with:"
echo "psql -U ${DB_USERNAME} -d ${DB_NAME} -h localhost -W"
echo ""
echo "Service status:"
echo "sudo systemctl status postgresql"
