const express = require("express");
const puppeteer = require("puppeteer");
const fs = require("fs/promises");
const path = require("path");
const os = require("os");

const app = express();
const PORT = process.env.PORT || 3000;

// ─── Config ────────────────────────────────────────────────────────────────
const POOL_SIZE = parseInt(process.env.POOL_SIZE || "4", 10); // parallel browsers
const PAGE_TIMEOUT_MS = parseInt(process.env.PAGE_TIMEOUT_MS || "30000", 10);
const MAX_QUEUE_SIZE = parseInt(process.env.MAX_QUEUE_SIZE || "50", 10);

// ─── Middleware ─────────────────────────────────────────────────────────────
app.use(express.text({ type: "*/*", limit: "2mb" }));
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

// Serve Highcharts statically
app.use(
  "/assets/highcharts",
  express.static(path.join(__dirname, "node_modules/highcharts"))
);

// ─── HTML Shell ─────────────────────────────────────────────────────────────
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

// ─── Browser Pool ───────────────────────────────────────────────────────────
class BrowserPool {
  constructor(size) {
    this.size = size;
    this.workers = []; // { browser, busy, queue }
    this.ready = false;
  }

  async init() {
    console.log(`[pool] Launching ${this.size} browsers...`);
    const launches = [];
    for (let i = 0; i < this.size; i++) {
      launches.push(this._launchWorker(i));
    }
    this.workers = await Promise.all(launches);
    this.ready = true;
    console.log(`[pool] All ${this.size} browsers ready.`);
  }

  async _launchWorker(id) {
    const browser = await puppeteer.launch({
      headless: true,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--disable-web-security",
        "--disable-extensions",
        "--single-process",
      ],
    });

    browser.on("disconnected", () => {
      console.warn(`[pool] Worker ${id} disconnected — restarting...`);
      this._restartWorker(id);
    });

    return { id, browser, busy: false, queue: [] };
  }

  async _restartWorker(id) {
    try {
      this.workers[id] = await this._launchWorker(id);
      console.log(`[pool] Worker ${id} restarted.`);
    } catch (err) {
      console.error(`[pool] Failed to restart worker ${id}:`, err);
      // retry after 2s
      setTimeout(() => this._restartWorker(id), 2000);
    }
  }

  // Pick the least-busy worker
  _pickWorker() {
    let best = null;
    for (const w of this.workers) {
      if (!best || w.queue.length < best.queue.length) {
        best = w;
      }
    }
    return best;
  }

  /**
   * Run `fn(browser)` on a pooled browser.
   * Returns a Promise that resolves with fn's result.
   */
  run(fn) {
    return new Promise((resolve, reject) => {
      const worker = this._pickWorker();
      if (!worker) {
        return reject(new Error("Browser pool not ready"));
      }

      const task = { fn, resolve, reject };
      worker.queue.push(task);
      this._drain(worker);
    });
  }

  async _drain(worker) {
    if (worker.busy || worker.queue.length === 0) return;
    worker.busy = true;

    const task = worker.queue.shift();
    try {
      const result = await task.fn(worker.browser);
      task.resolve(result);
    } catch (err) {
      task.reject(err);
    } finally {
      worker.busy = false;
      // Process next task in this worker's queue
      setImmediate(() => this._drain(worker));
    }
  }

  async shutdown() {
    console.log("[pool] Shutting down browsers...");
    await Promise.all(
      this.workers.map((w) => w.browser.close().catch(() => {}))
    );
  }

  get queueDepth() {
    return this.workers.reduce((s, w) => s + w.queue.length, 0);
  }
}

const pool = new BrowserPool(POOL_SIZE);

// ─── Chart Rendering ─────────────────────────────────────────────────────────
async function renderChartToPng(userCode) {
  let tempFilePath;

  try {
    tempFilePath = path.join(
      os.tmpdir(),
      `highcharts-${Date.now()}-${Math.random().toString(36).slice(2)}.html`
    );

    await fs.writeFile(tempFilePath, buildHtmlShell(), "utf8");
    const fileUrl = `file://${tempFilePath.replace(/\\/g, "/")}`;

    return await pool.run(async (browser) => {
      const page = await browser.newPage();

      try {
        page.on("pageerror", (err) =>
          console.error("[browser pageerror]", err)
        );
        page.on("requestfailed", (req) =>
          console.error("[request failed]", req.url(), req.failure()?.errorText)
        );

        page.setDefaultTimeout(PAGE_TIMEOUT_MS);
        await page.setViewport({ width: 800, height: 600, deviceScaleFactor: 2 });
        await page.emulateMediaType("screen");

        await page.goto(fileUrl, { waitUntil: "load", timeout: PAGE_TIMEOUT_MS });

        await page.addScriptTag({
          path: path.join(__dirname, "node_modules/highcharts/highcharts.js"),
        });

        await page.waitForFunction(() => !!window.Highcharts, {
          timeout: 10000,
        });

        await page.evaluate((code) => {
          window.__chartReady = false;
          window.__chartError = null;
          window.__chart = null;

          Highcharts.setOptions({
            chart: { animation: false },
            plotOptions: { series: { animation: false } },
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
              if (typeof userLoad === "function") userLoad.call(this, e);
            };

            options.chart.events.render = function (e) {
              window.__chartReady = true;
              if (typeof userRender === "function") userRender.call(this, e);
            };

            args[optionsIndex] = options;
            const chart = originalChart.apply(this, args);
            window.__chart = chart;

            // Fallback
            setTimeout(() => {
              if (!window.__chartReady && !window.__chartError) {
                window.__chartReady = true;
              }
            }, 1000);

            return chart;
          };

          try {
            eval(code); // eslint-disable-line no-eval
          } catch (err) {
            window.__chartError = String(err?.stack ?? err);
            throw err;
          }
        }, userCode);

        await page.waitForFunction(
          () => !!(window.__chart || window.__chartError),
          { timeout: PAGE_TIMEOUT_MS }
        );

        const chartError = await page.evaluate(() => window.__chartError);
        if (chartError) {
          throw new Error(`Chart creation failed: ${chartError}`);
        }

        await page.waitForFunction(
          () => {
            const svg = document.querySelector("#container svg");
            if (!svg || typeof svg.getBBox !== "function") return false;
            const box = svg.getBBox();
            return box.width > 0 && box.height > 0;
          },
          { timeout: PAGE_TIMEOUT_MS }
        );

        await page.evaluate(() => {
          const el = document.querySelector("#container");
          if (el) el.scrollIntoView({ block: "start", inline: "start" });
        });

        await page.evaluate(
          () => new Promise((r) => requestAnimationFrame(r))
        );
        await page.evaluate(
          () => new Promise((r) => requestAnimationFrame(r))
        );

        const clip = await page.evaluate(() => {
          const rect = document
            .querySelector("#container")
            .getBoundingClientRect();
          return {
            x: Math.max(0, Math.floor(rect.left)),
            y: Math.max(0, Math.floor(rect.top)),
            width: Math.ceil(rect.width),
            height: Math.ceil(rect.height),
          };
        });

        return await page.screenshot({ type: "png", clip });
      } finally {
        await page.close().catch(() => {});
      }
    });
  } finally {
    if (tempFilePath) {
      await fs.unlink(tempFilePath).catch(() => {});
    }
  }
}

// ─── Routes ──────────────────────────────────────────────────────────────────
app.post("/render", async (req, res) => {
  console.log(`[${new Date().toISOString()}] /render  queue=${pool.queueDepth}`);

  if (!pool.ready) {
    return res.status(503).json({ error: "Server is warming up, try again shortly." });
  }

  const userCode = req.body;
  if (!userCode || !userCode.trim()) {
    return res.status(400).send("Missing JS code");
  }

  if (pool.queueDepth >= MAX_QUEUE_SIZE) {
    return res.status(503).json({ error: "Server overloaded, please retry." });
  }

  // Per-request timeout to avoid hanging clients
  const timeoutHandle = setTimeout(() => {
    if (!res.headersSent) {
      res.status(504).json({ error: "Render timed out" });
    }
  }, PAGE_TIMEOUT_MS + 5000);

  try {
    const png = await renderChartToPng(userCode);
    clearTimeout(timeoutHandle);
    if (!res.headersSent) {
      res.setHeader("Content-Type", "image/png");
      res.send(png);
    }
  } catch (err) {
    clearTimeout(timeoutHandle);
    console.error("Render failed:", err);
    if (!res.headersSent) {
      res.status(500).json({
        error: "Render failed",
        details: String(err?.stack ?? err),
      });
    }
  }
});

// GET /chart — view chart HTML
app.get("/chart", (req, res) => {
  const userCode = req.query.code || "";
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(`<!DOCTYPE html>
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
</html>`);
});

// POST /chart — view chart HTML (large payloads)
app.post("/chart", (req, res) => {
  const userCode = req.body || "";
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(`<!DOCTYPE html>
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
</html>`);
});

// Health check
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    poolSize: POOL_SIZE,
    queueDepth: pool.queueDepth,
    ready: pool.ready,
  });
});

// ─── Startup ─────────────────────────────────────────────────────────────────
async function start() {
  await pool.init();

  app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
    console.log(
      `Pool: ${POOL_SIZE} browsers | Max queue: ${MAX_QUEUE_SIZE} | Timeout: ${PAGE_TIMEOUT_MS}ms`
    );
  });
}

start().catch((err) => {
  console.error("Failed to start server:", err);
  process.exit(1);
});

// ─── Graceful shutdown ───────────────────────────────────────────────────────
async function shutdown(signal) {
  console.log(`[${signal}] Shutting down gracefully...`);
  await pool.shutdown();
  process.exit(0);
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

process.on("uncaughtException", (err) => {
  console.error("Uncaught Exception:", err);
  process.exit(1);
});

process.on("unhandledRejection", (reason) => {
  console.error("Unhandled Rejection:", reason);
  process.exit(1);
});