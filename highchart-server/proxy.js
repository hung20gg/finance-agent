const express = require("express");
const path = require("path");

const app = express();
const PORT = 3001;

app.use("/assets/highcharts", express.static(path.join(__dirname, "node_modules/highcharts")));

app.get("/chart", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");

  res.send(`
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Chart</title>
  <script src="/assets/highcharts/highcharts.js"></script>
  <style>
    html, body { margin: 0; padding: 0; background: white; }
    #container { width: 100%; height: 460px; }
  </style>
</head>
<body>
  <div id="container"></div>
  <script>
    Highcharts.chart('container', {
      chart: { type: 'bar' },
      title: { text: 'Revenue by Quarter 2025' },
      xAxis: {
        categories: ['Q1 2025', 'Q2 2025', 'Q3 2025', 'Q4 2025', 'Full Year 2025']
      },
      yAxis: { title: { text: 'Revenue' } },
      series: [{
        name: 'Revenue',
        data: [37621.7, 35910.5, 36407.4, 46176.5, 156116]
      }]
    });
  </script>
</body>
</html>
  `);
});

app.listen(PORT, () => {
  console.log(`Chart server at http://localhost:${PORT}`);
});