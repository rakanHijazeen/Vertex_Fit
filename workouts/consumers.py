import asyncio
import json
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


class LiveCoachingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.google_ws = None
        self.gemini_task = None
        self.phase1_triggered = False
        self.setup_complete_sent = False
        self.api_key = getattr(settings, "GEMINI_API_KEY", None)

        if not self.api_key:
            await self.send(json.dumps({"type": "error", "message": "GEMINI_API_KEY is not configured."}))
            await self.close()
            return

        self.uri = (
            "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta"
            ".GenerativeService.BidiGenerateContent?key="
            f"{self.api_key}"
        )

    async def disconnect(self, code):
        if self.gemini_task is not None:
            self.gemini_task.cancel()
            try:
                await self.gemini_task
            except asyncio.CancelledError:
                pass

        if self.google_ws is not None:
            try:
                await self.google_ws.close()
            except Exception:
                pass

        await super().disconnect(code)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(json.dumps({"type": "error", "message": "Invalid JSON payload."}))
            return

        action_type = data.get("type")

        if action_type == "session_init":
            exercise_name = data.get("exercise_name", "Workout")
            await self.init_gemini_live_session(exercise_name)
            return

        if action_type == "user_ready":
            try:
                await self.send(json.dumps({"type": "ready_ack", "msg": "starting_live"}))
            except Exception:
                pass

            if self.google_ws is not None:
                ready_prompt = {
                    "clientContent": {
                        "turns": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "text": (
                                            "بلش التمرين. قبل ما تبدأ، أعطني وصف سريع للي شايفه بالكاميرا عشان أتأكد إنك شايفني. "                                            "انتبه لأي تقوس بالظهر أو انحراف بالركب أو بطء بالتنفيذ، نبّهني فوراً بكلمتين، وحفزني بناءً على مستوى التعب "
                                            "راقب حركتي ونبهني اذا عملت اخطاء وإذا التكنيك سليم، شجعني بكلمة وحدة كل تكرار لضمان الاستمرارية. "
                                            "لا توقف مراقبة، الجلسة مستمرة."                                        
                                        )                                    
                                    }
                                ],
                            }
                        ],
                        "turnComplete": True,
                    }
                }
                try:
                    await self.google_ws.send(json.dumps(ready_prompt))
                    print("◼ Sent Phase 2 transition command to Gemini.")
                except Exception as exc:
                    print(f"❌ Failed to send Phase 2 prompt to Gemini: {exc}")
            return

        if action_type == "realtime_frame":
            if self.google_ws is None:
                await self.send(json.dumps({"type": "error", "message": "Gemini connection is not ready."}))
                return

            frame_data = data.get("frame")
            print(f"DEBUG: Attempting to send frame of size {len(frame_data) if frame_data else 0}")

            if not frame_data:
                print("DEBUG: Frame data is empty!")
                return

            gemini_payload = {
                "realtimeInput": {
                    "video": {
                        "mimeType": "image/jpeg",
                        "data": frame_data,
                    }
                }
            }

            try:
                await self.google_ws.send(json.dumps(gemini_payload))
            except Exception as exc:
                print(f"❌ Failed to send frame to Gemini: {exc}")
                try:
                    await self.send(json.dumps({"type": "error", "message": "Failed to send frame to Gemini."}))
                except Exception:
                    pass
                try:
                    await self.google_ws.close()
                except Exception:
                    pass
                self.google_ws = None
            return

    async def init_gemini_live_session(self, exercise_name):
        # Fallback to "General Workout" if exercise_name is empty or null
        final_exercise = exercise_name if exercise_name and exercise_name.strip() != "" else "General Workout"
        try:
            self.google_ws = await websockets.connect(self.uri)
            self.phase1_triggered = False

            setup_packet = {
                "setup": {
                    "model": "models/gemini-3.1-flash-live-preview",
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": (
                                    "You are a 2-Phase Jordanian Bodybuilding Coach. "
                                    f"The current exercise is: {final_exercise}. "
                                    "1. When initialized with an exercise (e.g., Squats, Curls), immediately load the specific "
                                    "biomechanical model for that movement. "
                                    "2.(Phase 2) VISUAL TRUTH: Only report on physical movement you see in the video frames. "
                                    "If the user is standing still, say NOTHING. Do not count reps unless you physically "
                                    "see the movement phases. If you are unsure, stay silent. "
                                    "3. PRIORITIZE visual analysis of the back (spine neutrality) and knees (alignment/tracking) "
                                    "as the primary safety focus regardless of the exercise. "
                                    "4. If an exercise doesn't heavily involve the knees (like Curls), shift the priority "
                                    "to strict elbow/shoulder stabilization and back posture. "
                                    "Even if form is perfect, provide brief, high-energy rhythm reinforcement "
                                    "every 3 seconds to confirm you are actively watching the video feed. "
                                    "If you see form errors, prioritize that feedback over rhythm."
                                    "5. Keep all mid-set feedback in conversational Jordanian Arabic, under 5 words, "
                                    "and trigger it immediately upon detecting form deviation."
                                )
                            }
                        ]
                    },
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {
                                    "voiceName": "Aoede"
                                }
                            }
                        }
                    },
                }
            }

            await self.google_ws.send(json.dumps(setup_packet))
            self.gemini_task = asyncio.create_task(self.receive_from_gemini())
            await self.send(json.dumps({"type": "init_status", "msg": "تم تفعيل المدرب المباشر"}))

        except Exception as exc:
            print(f"❌ Gemini connection failed: {exc}")
            await self.send(json.dumps({"type": "error", "message": "Failed to connect to the live coach."}))
            await self.close()

    async def receive_from_gemini(self):
        if self.google_ws is None:
            return

        try:
            async for response in self.google_ws:
                if not response:
                    continue

                if isinstance(response, (bytes, bytearray)):
                    try:
                        response = response.decode("utf-8", errors="ignore")
                    except Exception:
                        continue

                try:
                    data = json.loads(response)
                except json.JSONDecodeError:
                    continue

                # Treat the first valid JSON message from Gemini as the setup handshake.
                if not self.phase1_triggered:
                    if not self.setup_complete_sent:
                        try:
                            await self.send(json.dumps({"type": "setup_complete", "msg": "تم الإعداد، اضغط بدء التمرين عندما تكون جاهزًا."}))
                        except Exception:
                            pass
                        self.setup_complete_sent = True

                    phase1_prompt = {
                        "clientContent": {
                            "turns": [
                                {
                                    "role": "user",
                                    "parts": [
                                        {
                                            "text": "ابدأ الجلسة وعلمني وضعية البداية الصحيحة للتمرين بالتفصيل."
                                        }
                                    ],
                                }
                            ],
                            "turnComplete": True,
                        }
                    }

                    try:
                        await self.google_ws.send(json.dumps(phase1_prompt))
                        self.phase1_triggered = True
                        print("◼ Sent initial Phase 1 trigger to Gemini.")
                    except Exception as exc:
                        print(f"❌ Failed to send initial Phase 1 prompt: {exc}")
                    continue

                try:
                    received_keys = list(data.keys())
                    print(f"◼ Gemini response keys: {received_keys}")
                except Exception:
                    pass

                server_content = data.get("serverContent") or {}
                if "groundingMetadata" in data:
                    print("✅ Gemini is referencing visual grounding metadata!")
                parts = server_content.get("modelTurn", {}).get("parts", [])
                for part in parts:
                    text = part.get("text") or part.get("displayText")
                    if text:
                        try:
                            await self.send(json.dumps({"type": "coach_text", "text": text}))
                        except Exception:
                            pass

                    inline_data = part.get("inlineData")
                    if inline_data and inline_data.get("data"):
                        payload = inline_data["data"]
                        print(f"◼ Forwarding audio chunk, size={len(payload)}")
                        try:
                            await self.send(json.dumps({"type": "audio_chunk", "payload": payload}))
                        except Exception:
                            pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"❌ Receive loop error: {exc}")
            