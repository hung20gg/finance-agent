curl -X POST http://localhost:3000/render \
  -H "Content-Type: text/plain" \
  --data-binary @chart.js \
  --output chart.png