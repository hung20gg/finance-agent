import sys
sys.path.append('.')

from strategy.text2chart.utils import render_highchart_image

print('Testing chart rendering...')
test_code = '''Highcharts.chart('container', {
    chart: {type: 'bar'},
    title: {text: 'Test Chart'},
    xAxis: {categories: ['A', 'B', 'C']},
    series: [{
        name: 'Data',
        data: [1, 2, 3]
    }]
});'''

try:
    img = render_highchart_image(test_code)
    print('Success! Chart rendered.')
except Exception as e:
    print(f'Error: {e}')