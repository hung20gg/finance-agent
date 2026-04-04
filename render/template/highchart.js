Highcharts.chart('container', {
    chart: {
        type: 'bar'
    },
    title: {
        text: 'Sample Chart'
    },
    xAxis: {
        categories: ['A', 'B', 'C']
    },
    series: [{
        name: 'Data',
        data: [10, 20, 30]
    }]
});