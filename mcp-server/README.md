Build the image

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t quanghung20gg/mcp-server-sql:v0.2 \
  . \
  --push
```


```
docker build -t quanghung20gg/mcp-server-sql:v0.2 .
docker push quanghung20gg/mcp-server-sql:v0.2
```