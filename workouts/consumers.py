import json
import asyncio
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

# from google.auth import default # [Vertex AI]
# from google.auth.transport.requests import Request # [Vertex AI]

class LiveCoachingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.google_ws = None
        
        # --- [NEW] AI Studio Connection Logic (Free Tier) ---
        # Ensure GEMINI_API_KEY is set in your Django settings.py or .env
        self.api_key = settings.GEMINI_API_KEY
        self.uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={self.api_key}"
        
        # --- [OLD] Vertex AI Logic (Requires Billing/Prepayment) ---
        # os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(settings.BASE_DIR, "gcp-vertex-sa.json")
        # ... (rest of old logic)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            data = json.loads(text_data)
            if data.get("type") == "session_init":
                await self.init_gemini_live_session(data.get("exercise_name", "Workout"))
                return

            if data.get("type") == "realtime_frame" and self.google_ws:
                
                await self.google_ws.send(json.dumps({
                "realtimeInput": data["realtimeInput"]
            }))
                
    async def init_gemini_live_session(self, exercise_name):
        try:
            # --- [NEW] Direct Connection to AI Studio API ---
            self.google_ws = await websockets.connect(self.uri)
            
            setup_packet = {
                "setup": {
                    "model": "models/gemini-3.1-flash-live-preview", # Updated model
                    "system_instruction": {
                        "parts": [{"text": f"You are an expert Jordanian bodybuilding coach. Critically observe the user doing {exercise_name}. Provide immediate, brief real-time form adjustments or motivation in Jordanian Arabic dialect. Keep cues under 4 words."}]
                    },
                    "generation_config": {
                        "response_modalities": ["AUDIO"] # Set to AUDIO for voice feedback
                    }
                }
            }
            await self.google_ws.send(json.dumps(setup_packet))
            asyncio.create_task(self.receive_from_gemini())
            await self.send(json.dumps({"cue": "تم تفعيل المدرب المباشر، بلش التمرين يا وحش"}))
            
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            await self.close()

    async def receive_from_gemini(self):
        if not self.google_ws: return
        try:
            async for response in self.google_ws:
                data = json.loads(response)
                # --- [NEW] Gemini API camelCase response structure ---
                if "serverContent" in data:
                    parts = data["serverContent"].get("modelTurn", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            await self.send(json.dumps({"cue": part["text"]}))
        except Exception as e:
            print(f"❌ Receive loop error: {str(e)}")