import os
from django.conf import settings
from django.apps import apps

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
            
        # Initialize the client directly using the clean class import
        self.client = Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def analyze_workout_video(self, video_url: str) -> str:
        """
        Passes a secure S3 storage location path or public stream URL to Gemini Flash for deep
        form, tempo, and range of motion breakdown analysis.
        """
        # 1. Safely resolve the app module to satisfy Pylance's None-checking
        app_config = apps.get_app_config('workouts')
        system_instruction = "Analyze the workout execution form, tracking reps and safety parameters."
        
        if app_config.module is not None:
            # Use getattr on the module to safely extract the config string dynamically
            system_instruction = getattr(app_config.module.vlm_config, "VLM_SYSTEM_INSTRUCTION", system_instruction)
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