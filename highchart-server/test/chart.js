try {
  // Ensure container exists
  const container = document.getElementById('container');
  if (!container) {
    throw new Error('Chart container not found');
  }

  Highcharts.chart('container', {
    chart: { type: 'bar' },
    title: { text: 'Sample Chart' },
    xAxis: { categories: ['A', 'B', 'C'] },
    series: [{
      name: 'Data',
      data: [10, 20, 30]
    }]
  });
} catch (error) {
  console.error('Chart creation error:', error);
  if (window.__chartError === null) {
    window.__chartError = error.message;
  }
  throw error;
}