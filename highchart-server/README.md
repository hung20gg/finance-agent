# Highcharts Rendering Server

A Node.js service that renders Highcharts configurations into images (PNG) using Puppeteer.

## Features

- **Highcharts Integration**: Full support for Highcharts JavaScript configurations.
- **Puppeteer Rendering**: Uses a headless browser to ensure accurate chart rendering.
- **REST API**: Simple endpoint to submit JS configurations and receive image data.
- **Dockerized**: Ready for containerized deployment.

## Getting Started

### Local Setup
1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the server:
   ```bash
   node server.js
   ```
The server typically runs on port `3000`.

### Docker
To build and run via Docker:
```bash
docker build -t highchart-server .
docker run -p 3000:3000 highchart-server
```

## Usage

Send a POST request with the Highcharts options to the server. The server will render the chart in a headless browser and return the image as a response.

Refer to `server.js` for detailed API specifications and `proxy.js` for proxy configurations if needed.
