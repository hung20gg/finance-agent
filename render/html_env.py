from pandas import options
from pydantic import BaseModel, Field
import os
import sys
import time
import subprocess
from typing import ClassVar, Optional, Dict, Any, Union
from pathlib import Path
from uuid import uuid4

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from PIL import Image
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

from env import EnvConfig, Env

class HtmlEnvConfig(EnvConfig):
    """
    Configuration for the HTML environment.
    """
    module_name: str = Field(default='html_env', description="Code type: either python or html")
    html_template: str = Field(default='highchart', description="HTML template to use for rendering.")
    cache_folder: str = Field(default=os.path.join(CURRENT_DIR, '..', '..', 'temp', 'html'), description="Folder to cache HTML files")
    viewport_width: int = Field(default=800, description="Viewport width for rendering")
    viewport_height: int = Field(default=600, description="Viewport height for rendering")
    render_wait_time: float = Field(default=0.1, description="Time to wait for rendering to complete (seconds)")
    animation_speed_multiplier: float = Field(default=0.1, description="Speed multiplier for animations (0.1 = 10x faster)")

class HtmlEnv(Env):
    """
    Represents an HTML environment that can execute actions based on the provided configuration.
    """
    config: HtmlEnvConfig
    template: str = Field(default=None, description="Template to use for rendering charts.")

    selenium_driver: ClassVar[Optional[Any]] = None
    
    def __init__(self, config: HtmlEnvConfig):
        super().__init__(config=config)
        self._initialize_selenium()
        with open(os.path.join(CURRENT_DIR, 'template', f'{self.config.html_template}.html'), 'r') as f:
            self.template = f.read()
    
    def _initialize_selenium(self):
        """Initialize Selenium with WebDriver manager for automatic driver downloads"""
        try:
            
            
            driver_path = ChromeDriverManager().install()

            start = time.time()
            # Configure Chrome options
            options = Options()
            # options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--allow-file-access-from-files")
            options.add_argument("--disable-web-security")
            # options.add_argument(f"--window-size={self.config.viewport_width},{self.config.viewport_height}")

            logger.info(f"Initializing Selenium basic in {time.time() - start:.2f} seconds")
            
            # next_start = time.time()

            # # Performance optimizations for faster rendering
            options.add_argument("--disable-gpu")
           
            
            # # Set page load strategy to reduce waiting time
            # options.page_load_strategy = 'eager'  # Don't wait for all resources
            
            # # Set timeouts
            # options.add_argument("--timeout=5000")

            # Initialize Chrome
            HtmlEnv.selenium_driver = webdriver.Chrome(
                service=ChromeService(driver_path),
                options=options
            )

            HtmlEnv.selenium_driver.set_page_load_timeout(5)
            HtmlEnv.selenium_driver.implicitly_wait(1)
            HtmlEnv.selenium_driver.set_window_size(self.config.viewport_width, self.config.viewport_height)

            logger.info(f"Setting up Chrome in {time.time() - start:.2f} seconds")
                
            
        except Exception as e:
            print(f"Error initializing Selenium: {e}")
    
    def render_with_selenium(self, html_file_path: str, image_file_path: str) -> bool:
        """Render HTML to image using Selenium WebDriver with optimized waiting"""
        if not HtmlEnv.selenium_driver:
            print("Selenium WebDriver is not initialized. Trying to initialize now...")
            self._initialize_selenium()
            if not HtmlEnv.selenium_driver:
                print("Failed to initialize Selenium WebDriver.")
                return False, None
        
        try:
            # Create the file URL
            file_url = f"file://{os.path.abspath(html_file_path).replace(os.sep, '/')}"
            
            # Navigate to the HTML file
            HtmlEnv.selenium_driver.get(file_url)

#             WebDriverWait(HtmlEnv.selenium_driver, 30).until(
#                 lambda d: d.execute_script("return document.readyState") == "complete"
#             )
#             # wait until Highcharts lib is present
#             WebDriverWait(HtmlEnv.selenium_driver, 30).until(
#                 lambda d: d.execute_script("return !!window.Highcharts")
# )
            
            # Force complete all animations and rendering
            time.sleep(self.config.render_wait_time)
            
            # Take screenshot immediately after content is ready
            HtmlEnv.selenium_driver.save_screenshot(image_file_path)
            
            # Check if the screenshot is fully white
            return self._is_image_render_success(image_file_path)

            
        except Exception as e:
            print(f"Selenium rendering failed: {e}")
            return False, None

    def _is_image_render_success(self, image_file_path: str) -> tuple[bool, Image.Image]:
        """Check if the screenshot image is fully white (indicating rendering failure)"""
        try:
            # Open the image and convert to RGB if necessary
            with Image.open(image_file_path) as img:
                # Convert to RGB to ensure consistent color space
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize image to 533x400 (2/3 of original 800x600)
                # img = img.resize((533, 400), Image.Resampling.LANCZOS)
                
                # Convert to numpy array for efficient processing
                img_array = np.array(img)
                
                # Check if all pixels are white (255, 255, 255)
                # Allow for slight variations due to compression/rendering artifacts
                white_threshold = 250  # Consider pixels with RGB values >= 250 as "white"
                is_white = np.all(img_array >= white_threshold)

                return not is_white, img

        except Exception as e:
            print(f"Error checking if image is white: {e}")
            # If we can't analyze the image, assume it's valid
            return False, None

    def step(self, action: dict, run_name: str = '', tag: str = '') -> Dict[str, Any]:
        """
        Perform an action in the HTML environment.

        :param action: The action to perform. { code: str, language: str }
        :return: Result of the action.
        """
        if not run_name:
            run_name = str(uuid4())
            
        if action['language'] not in ['html', 'javascript', 'html5']:
            raise ValueError(f"Unsupported language: {action['language']}. Expected 'html', 'javascript', or 'html5'.")
        
        # Create folders for code and images
        os.makedirs(os.path.join(self.config.cache_folder, 'code', run_name), exist_ok=True)
        os.makedirs(os.path.join(self.config.cache_folder, 'images', run_name), exist_ok=True)
        
        run_time = time.strftime("%Y%m%d-%H%M%S")
        html_file_path = os.path.join(self.config.cache_folder, 'code', run_name, f"render_{tag}_{run_time}.html")
        image_file_path = os.path.join(self.config.cache_folder, 'images', run_name, f"render_{tag}_{run_time}.png")

        code = action['code'].strip()

        # Add common HTML fixes to ensure proper rendering
        if "<html" not in code and action['language'] == 'html':
            html_code = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rendered HTML</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script> 
    <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        /* Force all animations to be instant */
        *, *::before, *::after {{
            animation-duration: 0.01s !important;
            animation-delay: 0s !important;
            transition-duration: 0.01s !important;
            transition-delay: 0s !important;
        }}
    </style>
</head>
<body>
{action['code']}
</body>
</html>"""

        # Add template if specified
        elif action['language'] == 'javascript':
            html_code = self.template.replace('{$chart_config$}', code)

        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(html_code)

        # Render with Selenium
        success, image_rendered = self.render_with_selenium(html_file_path, image_file_path)
        
        return {
            'success': success,
            'code': code,
            'code_file_path': html_file_path,
            'image_file_path': image_file_path,
            'image_rendered': image_rendered,
            'run_name': run_name,
        }
    
    def __del__(self):
        """Clean up resources when the object is destroyed"""
        if HtmlEnv.selenium_driver:
            try:
                HtmlEnv.selenium_driver.quit()
                HtmlEnv.selenium_driver = None
            except:
                pass


if __name__ == "__main__":
    # Simple HTML example to test rendering
    with open(os.path.join(CURRENT_DIR, 'template', 'highchart.js'), 'r') as f:
        code = f.read()
        
    action = {
        'code': code,
        'language': 'javascript'  # Use 'javascript' to apply the template
    }
    env = HtmlEnv(config=HtmlEnvConfig())
    result = env.step(action, run_name='test_run', tag='test_tag')
    print(f"Image saved to: {result['image_file_path']}")