import google.generativeai as genai
from ..utils.config import load_config

class GeminiClient:
    def __init__(self):
        config = load_config()
        genai.configure(api_key=config['google_api_key'])
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_response(self, prompt: str) -> str:
        response = self.model.generate_content(prompt)
        return response.text 