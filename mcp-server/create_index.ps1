#!/usr/bin/env pwsh
# Create index on pub_date field in Qdrant collection

# Configuration (can be overridden by environment variables)
$QDRANT_HOST = if ($env:QDRANT_HOST) { $env:QDRANT_HOST } else { "http://127.0.0.1:6333" }
$COLLECTION_NAME = if ($env:COLLECTION_NAME) { $env:COLLECTION_NAME } else { "news_embedding" }

Write-Host "=== Creating Index on pub_date Field ==="
Write-Host "   Qdrant Host: $QDRANT_HOST"
Write-Host "   Collection: $COLLECTION_NAME"

# Create index on pub_date field
Invoke-RestMethod `
    -Method Put `
    -Uri "$QDRANT_HOST/collections/$COLLECTION_NAME/index" `
    -ContentType "application/json" `
    -Body '{
        "field_name": "pub_date",
        "field_schema": "integer"
    }'

Write-Host ""
Write-Host "✅ Index creation request sent"
