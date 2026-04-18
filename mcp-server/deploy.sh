docker build -t mcp-server .

docker stop mcp-server || true
docker rm mcp-server || true

docker run -d --name mcp-server -p 9004:9004 --network kltn --env-file .env.prod  mcp-server


