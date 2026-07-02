import os
from django.conf import settings
from django.apps import apps
from . import vlm_config

# Correct import path for the modern google-genai SDK
try:
    from google.genai import Client
    from google.genai import types
except ImportError:
    raise ImportError(
        "The modern 'google-genai' package is missing. Run: pip install google-genai"
    )

class GeminiVLMService:
    def __init__(self):
        api_key = getattr(settings, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing from environment variables or settings.py configuration.")
            
        self.client = Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def analyze_workout_video(self, video_url: str) -> str:
        """
        Passes a secure S3 storage location path or public stream URL to Gemini Flash for deep
        form, tempo, and range of motion breakdown analysis.
        """
        # 💡 Pull the system instruction directly from our clean import wrapper
        system_instruction = getattr(vlm_config, "VLM_SYSTEM_INSTRUCTION", "Analyze the workout execution form, tracking reps and safety parameters.")
        
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            )
            
            # Using the modern client generation syntax
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[video_url],
                config=config
            )
            
            return response.text
            
        except Exception as e:
            print(f"[VLM Engine Error]: Failed to analyze asset at {video_url}. Details: {str(e)}")
            return "### 🚨 Analysis Failure\nAn unexpected server anomaly occurred while trying to process the workout video metrics."