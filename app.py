import sys
import os

# Allow importing from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from app import create_gradio_interface

demo = create_gradio_interface()

if __name__ == "__main__":
    demo.launch()
