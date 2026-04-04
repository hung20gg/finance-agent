import requests
from PIL import Image
import io

from .state import EvaluationFeedback

SERVER_URL = "http://localhost:3000/render"


def extract_critique_and_score(raw_response: str) -> EvaluationFeedback:
    """
    Extracts the critique and score from the raw response.
    
    :param raw_response: The raw response string.
    :return: A dictionary containing the critique and score.
    """
    # Assuming the response is formatted as "Critique: <critique> Score: <score>"
    critique = raw_response
    final_score = 0

    if '### Critique' in raw_response and '### Score' in raw_response:
        critique = raw_response.split('### Critique')[1].split('### Score')[0].strip()
        score = raw_response.split('### Score')[1].strip()

        if len(critique) > 0 and critique[0] == ':':
            critique = critique[1:].strip()
        if len(score) > 0 and score[0] == ':':
            score = score[1:].strip()

        if score.isdigit():
            final_score = int(score)
        
        elif '\\boxed{' in score:
            score = score.split('\\boxed{')[1].split('}')[0]
            if score.isdigit():
                final_score = int(score)
    
    return EvaluationFeedback(
        critique=critique,
        score=final_score
    )


def render_highchart_image(js_code: str) -> Image.Image:
    print("Sending JS code to rendering server...")
    print(js_code)
    response = requests.post(
        SERVER_URL,
        data=js_code,
        headers={"Content-Type": "text/plain"},
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"Render failed: {response.text}")

    # Convert bytes → PIL Image (in memory)
    image = Image.open(io.BytesIO(response.content))
    return image


# example usage
if __name__ == "__main__":
    js_code = """
    Highcharts.chart('chart-container', {
        chart: { type: 'bar' },
        title: { text: 'In-Memory Chart' },
        xAxis: { categories: ['A', 'B', 'C'] },
        series: [{
            data: [10, 20, 30]
        }]
    });
    """

    img = render_highchart_image(js_code)

    # use immediately
    img.show()           # preview
    # img.save("test.png")  # optional