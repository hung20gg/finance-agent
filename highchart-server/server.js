const express = require("express");
const puppeteer = require("puppeteer");
const fs = require("fs/promises");
const path = require("path");
const os = require("os");

const app = express();
const PORT = 3000;

app.use(express.text({ type: "*/*", limit: "2mb" }));

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

    #chart-container {
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
  <div id="chart-container"></div>
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
      const container = document.querySelector("#chart-container");
      const svg = container && container.querySelector("svg");
      return !!(window.__chartReady && window.__chart && svg);
    }, { timeout: 10000 });

    await page.waitForFunction(() => {
      const svg = document.querySelector("#chart-container svg");
      if (!svg || typeof svg.getBBox !== "function") {
        return false;
      }

      const box = svg.getBBox();
      return box.width > 0 && box.height > 0;
    }, { timeout: 10000 });

    await page.evaluate(() => {
      const el = document.querySelector("#chart-container");
      if (el) {
        el.scrollIntoView({ block: "start", inline: "start" });
      }
    });

    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));

    const clip = await page.evaluate(() => {
      const el = document.querySelector("#chart-container");
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
  const userCode = req.body;

  if (!userCode || !userCode.trim()) {
    return res.status(400).send("Missing JS code");
  }

  try {
    const png = await renderChartToPng(userCode);
    res.setHeader("Content-Type", "image/png");
    res.send(png);
  } catch (err) {
    console.error(err);
    res.status(500).json({
      error: "Render failed",
      details: String(err && err.stack ? err.stack : err)
    });
  }
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});