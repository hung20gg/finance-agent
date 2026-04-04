import streamlit as st
from app import render_chart_html

st.set_page_config(page_title="Test Highchart Render", layout="wide")

st.title("Test Highcharts Config")
st.write("Paste your Highcharts JS/JSON configuration below to test the rendering live.")

DEFAULT_CONFIG = """Highcharts.chart('container', {
    chart: {
        type: 'bar'
    },
    title: {
        text: 'Revenue by Quarter 2025'
    },
    xAxis: {
        categories: ['Q1 2025', 'Q2 2025', 'Q3 2025', 'Q4 2025', 'Full Year 2025']
    },
    yAxis: {
        title: {
            text: 'Revenue'
        }
    },
    series: [{
        name: 'Revenue',
        data: [37621.7, 35910.5, 36407.4, 46176.5, 156116]
    }]
});"""

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Highcharts Config")
    config_input = st.text_area(
        "Enter the JS object configuration:",
        value=DEFAULT_CONFIG,
        height=450
    )

with col2:
    st.subheader("Rendered Preview")
    # Streamlit buttons reload the page, but we can also just render right away
    if st.button("Render Chart", type="primary"):
        render_chart_html(config_input)
    elif config_input:
        # Default behavior on load or text change
        render_chart_html(config_input)
