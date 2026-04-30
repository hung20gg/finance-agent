import requests
from PIL import Image
import io
from typing import Any, Dict, Optional


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
    return resize_image(image)


def render_matplotlib_image(
    py_code: str,
    globals_dict: Optional[Dict[str, Any]] = None,
) -> Image.Image:
    """
    Lazily imports matplotlib and renders a figure from provided code.
    """

    if not isinstance(py_code, str):
        raise TypeError("py_code must be a string.")

    # Lazy imports (only when function is called)
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless backend

        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        raise RuntimeError(
            "matplotlib and numpy must be installed to use this function."
        ) from e

    exec_globals: Dict[str, Any] = {
        "__builtins__": __builtins__,
        "plt": plt,
        "np": np,
    }

    if globals_dict:
        exec_globals.update(globals_dict)

    # Clean previous figures
    plt.close("all")

    try:
        exec(py_code, exec_globals)

        fig_numbers = plt.get_fignums()
        if not fig_numbers:
            raise ValueError("No matplotlib figure was created.")

        fig = plt.figure(fig_numbers[-1])

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)

        image = Image.open(buf).copy()
        buf.close()

        return resize_image(image)

    except Exception as e:
        raise RuntimeError(f"Failed to render matplotlib code: {e}") from e

    finally:
        plt.close("all")


def resize_image(image: Image.Image, max_size: int = 512) -> Image.Image:
    """
    Proportionally resize *image* so that its longest side is at most
    *max_size* pixels.  If the image already fits, it is returned unchanged.
    """
    w, h = image.size
    longest = max(w, h)
    if longest <= max_size:
        return image
    scale = max_size / longest
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return image.resize((new_w, new_h), Image.LANCZOS)


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
