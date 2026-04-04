const express = require("express");
const puppeteer = require("puppeteer");
const fs = require("fs/promises");
const path = require("path");
const os = require("os");

const app = express();
const PORT = 3000;

app.use(express.text({ type: "*/*", limit: "2mb" }));
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

// Serve Highcharts statically as a proxy
app.use("/assets/highcharts", express.static(path.join(__dirname, "node_modules/highcharts")));

function buildHtmlShell() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Highcharts Render</title>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      background: #ffffff;
    }

    #container {
      width: 800px;
      height: 600px;
      margin: 0;
      padding: 0;
      overflow: hidden;
    }

    *, *::before, *::after {
      animation-duration: 0.01s !important;
      animation-delay: 0s !important;
      transition-duration: 0.01s !important;
      transition-delay: 0s !important;
    }
  </style>
</head>
<body>
  <div id="container"></div>
</body>
</html>`;
}

async function renderChartToPng(userCode) {
  let browser;
  let tempFilePath;

  try {
    tempFilePath = path.join(
      os.tmpdir(),
      `highcharts-${Date.now()}-${Math.random().toString(36).slice(2)}.html`
    );

    await fs.writeFile(tempFilePath, buildHtmlShell(), "utf8");

    browser = await puppeteer.launch({
      headless: true,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--allow-file-access-from-files",
        "--disable-web-security"
      ]
    });

    const page = await browser.newPage();

    page.on("console", msg => console.log("BROWSER LOG:", msg.text()));
    page.on("pageerror", err => console.error("PAGE ERROR:", err));
    page.on("requestfailed", req =>
      console.error("REQUEST FAILED:", req.url())
    );

    page.on("console", (msg) => {
      console.log("[browser console]", msg.text());
    });

    page.on("pageerror", (err) => {
      console.error("[browser pageerror]", err);
    });

    page.on("requestfailed", (req) => {
      console.error(
        "[request failed]",
        req.url(),
        req.failure() ? req.failure().errorText : "unknown error"
      );
    });

    await page.setViewport({ width: 800, height: 600, deviceScaleFactor: 2 });
    await page.emulateMediaType("screen");

    const fileUrl = `file://${tempFilePath.replace(/\\/g, "/")}`;
    await page.goto(fileUrl, { waitUntil: "load" });

    await page.addScriptTag({
      path: path.join(__dirname, "node_modules/highcharts/highcharts.js")
    });

    await page.waitForFunction(() => !!window.Highcharts, { timeout: 10000 });

    await page.evaluate((code) => {
      window.__chartReady = false;
      window.__chartError = null;
      window.__chart = null;

      // Debug logging
      console.log('Starting chart creation...');
      console.log('Highcharts available:', typeof Highcharts);
      console.log('Container exists:', !!document.getElementById('container'));

      Highcharts.setOptions({
        chart: {
          animation: false
        },
        plotOptions: {
          series: {
            animation: false
          }
        }
      });

      const originalChart = Highcharts.chart;

      Highcharts.chart = function (...args) {
        let optionsIndex = 0;

        if (
          typeof args[0] === "string" ||
          (typeof Element !== "undefined" && args[0] instanceof Element)
        ) {
          optionsIndex = 1;
        }

        const options = args[optionsIndex] || {};
        options.chart = options.chart || {};
        options.chart.events = options.chart.events || {};

        const userLoad = options.chart.events.load;
        const userRender = options.chart.events.render;

        options.chart.events.load = function (e) {
          window.__chartReady = true;
          if (typeof userLoad === "function") {
            userLoad.call(this, e);
          }
        };

        options.chart.events.render = function (e) {
          window.__chartReady = true;
          if (typeof userRender === "function") {
            userRender.call(this, e);
          }
        };

        args[optionsIndex] = options;

        const chart = originalChart.apply(this, args);
        window.__chart = chart;
        
        // Fallback: manually trigger ready if events don't fire
        setTimeout(() => {
          if (!window.__chartReady && !window.__chartError) {
            console.log('Manually setting chart ready');
            window.__chartReady = true;
          }
        }, 1000);
        
        return chart;
      };

      try {
        eval(code);
      } catch (err) {
        window.__chartError = String(err && err.stack ? err.stack : err);
        throw err;
      }
    }, userCode);

    

    await page.waitForFunction(() => {
      const container = document.querySelector("#container");
      const svg = container && container.querySelector("svg");
      console.log('Waiting for chart...', {
        chartReady: window.__chartReady,
        chart: !!window.__chart,
        svg: !!svg,
        chartError: window.__chartError,
        container: !!container
      });
      // More lenient condition - just check if chart exists or there's an error
      return !!(window.__chart || window.__chartError);
    }, { timeout: 15000 });

    // Check if there was an error during chart creation
    const hasError = await page.evaluate(() => !!window.__chartError);
    if (hasError) {
      const errorMsg = await page.evaluate(() => window.__chartError);
      throw new Error(`Chart creation failed: ${errorMsg}`);
    }

    await page.waitForFunction(() => {
      const svg = document.querySelector("#container svg");
      if (!svg || typeof svg.getBBox !== "function") {
        return false;
      }

      const box = svg.getBBox();
      return box.width > 0 && box.height > 0;
    }, { timeout: 15000 });

    await page.evaluate(() => {
      const el = document.querySelector("#container");
      if (el) {
        el.scrollIntoView({ block: "start", inline: "start" });
      }
    });

    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));

    const clip = await page.evaluate(() => {
      const el = document.querySelector("#container");
      const rect = el.getBoundingClientRect();

      return {
        x: Math.max(0, Math.floor(rect.left)),
        y: Math.max(0, Math.floor(rect.top)),
        width: Math.ceil(rect.width),
        height: Math.ceil(rect.height)
      };
    });

    return await page.screenshot({
      type: "png",
      clip
    });
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (tempFilePath) {
      await fs.unlink(tempFilePath).catch(() => {});
    }
  }
}

app.post("/render", async (req, res) => {
  console.log("Received /render request");

  const userCode = req.body;

  if (!userCode || !userCode.trim()) {
    console.log("Empty request body");
    return res.status(400).send("Missing JS code");
  }

  try {
    console.log("Rendering chart...");
    const png = await renderChartToPng(userCode);
    console.log("Render success");

    res.setHeader("Content-Type", "image/png");
    res.send(png);
  } catch (err) {
    console.error("Render failed:", err);
    res.status(500).json({
      error: "Render failed",
      details: String(err && err.stack ? err.stack : err)
    });
  }
});

// GET /chart endpoint to view chart HTML dynamically
// User provides JS code via "code" query param
app.get("/chart", (req, res) => {
  const userCode = req.query.code || "";
  
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Chart View</title>
  <script src="/assets/highcharts/highcharts.js"></script>
  <style>
    html, body { margin: 0; padding: 0; background: white; }
    #container { width: 100%; height: 100vh; }
  </style>
</head>
<body>
  <div id="container"></div>
  <script>
    document.addEventListener('DOMContentLoaded', function () {
        ${userCode}
    });
  </script>
</body>
</html>
  `);
});

// POST /chart endpoint to view chart HTML dynamically (for large config payloads)
app.post("/chart", (req, res) => {
  const userCode = req.body || "";
  
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Chart View</title>
  <script src="/assets/highcharts/highcharts.js"></script>
  <style>
    html, body { margin: 0; padding: 0; background: white; }
    #container { width: 100%; height: 100vh; }
  </style>
</head>
<body>
  <div id="container"></div>
  <script>
    document.addEventListener('DOMContentLoaded', function () {
        ${userCode}
    });
  </script>
</body>
</html>
  `);
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
  console.log('Server started successfully, waiting for requests...');
});

// Handle uncaught exceptions
process.on('uncaughtException', (err) => {
  console.error('Uncaught Exception:', err);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  process.exit(1);
});