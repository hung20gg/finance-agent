#!/usr/bin/env bash

set -euo pipefail

# ==============================
# CONFIG
# ==============================

PG_VERSION="16.2"
INSTALL_DIR="${HOME}/pgsql"
DATA_DIR="${INSTALL_DIR}/data"
LOG_FILE="${DATA_DIR}/logfile"
PORT="5432"

DB_USERNAME="postgres"
DB_PASSWORD="12345678"

# ==============================
# DOWNLOAD + BUILD
# ==============================

echo "⬇️ Downloading PostgreSQL ${PG_VERSION}..."

cd /tmp
curl -LO https://ftp.postgresql.org/pub/source/v${PG_VERSION}/postgresql-${PG_VERSION}.tar.gz

echo "📦 Extracting..."
tar -xzf postgresql-${PG_VERSION}.tar.gz
cd postgresql-${PG_VERSION}

echo "⚙️ Building (this may take a few minutes)..."
./configure --prefix="${INSTALL_DIR}"
make -j$(nproc)
make install

# ==============================
# INIT DATABASE
# ==============================

echo "🗄️ Initializing database..."
mkdir -p "${DATA_DIR}"
"${INSTALL_DIR}/bin/initdb" -D "${DATA_DIR}"

# ==============================
# CONFIGURE AUTH (PASSWORD)
# ==============================

echo "🔐 Configuring authentication..."

# Replace peer/trust with md5

sed -i 's/trust/md5/g' "${DATA_DIR}/pg_hba.conf" || true
sed -i 's/peer/md5/g' "${DATA_DIR}/pg_hba.conf" || true

# Ensure localhost access exists

cat >> "${DATA_DIR}/pg_hba.conf" <<EOF

# Allow password auth

host all all 127.0.0.1/32 md5
host all all ::1/128 md5
EOF

# Listen on localhost

echo "listen_addresses = 'localhost'" >> "${DATA_DIR}/postgresql.conf"
echo "port = ${PORT}" >> "${DATA_DIR}/postgresql.conf"

# ==============================
# START SERVER
# ==============================

echo "🚀 Starting PostgreSQL..."
"${INSTALL_DIR}/bin/pg_ctl" -D "${DATA_DIR}" -l "${LOG_FILE}" start

sleep 3

# ==============================
# CREATE USER + SET PASSWORD
# ==============================

echo "👤 Creating user..."

"${INSTALL_DIR}/bin/psql" -v ON_ERROR_STOP=1 postgres <<EOF
DO $$
BEGIN
IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USERNAME}') THEN
CREATE ROLE ${DB_USERNAME} LOGIN PASSWORD '${DB_PASSWORD}' SUPERUSER;
END IF;
END
$$;

ALTER DATABASE postgres OWNER TO ${DB_USERNAME};
EOF

# ==============================
# DONE
# ==============================

echo ""
echo "✅ PostgreSQL is ready!"
echo "-----------------------------------"
echo "User: ${DB_USERNAME}"
echo "Database: postgres"
echo "Port: ${PORT}"
echo ""
echo "Connect with:"
echo "${INSTALL_DIR}/bin/psql -U ${DB_USERNAME} -d postgres -h localhost -p ${PORT}"
echo ""
echo "Stop server:"
echo "${INSTALL_DIR}/bin/pg_ctl -D ${DATA_DIR} stop"
echo ""
echo "Logs:"
echo "${LOG_FILE}"
