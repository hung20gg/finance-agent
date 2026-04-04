#!/bin/bash

# Create index on pub_date field in Qdrant collection

# Configuration (can be overridden by environment variables)
QDRANT_HOST="${QDRANT_HOST:-http://127.0.0.1:6333}"
COLLECTION_NAME="${COLLECTION_NAME:-news_embedding}"

echo "=== Creating Index on pub_date Field ==="
echo "   Qdrant Host: $QDRANT_HOST"
echo "   Collection: $COLLECTION_NAME"

# Create index on pub_date field
curl -X PUT "$QDRANT_HOST/collections/$COLLECTION_NAME/index" \
  -H "Content-Type: application/json" \
  -d '{
    "field_name": "pub_date",
    "field_schema": "integer"
  }'

echo ""
echo "✅ Index creation request sent"
