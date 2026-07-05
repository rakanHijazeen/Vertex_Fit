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
        self.heartbeat_task = None  # Explicitly initialized to prevent AttributeError crashes
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
                                            "انتهت المرحلة الأولى فوراً. اللاعب بدأ تكرارات التمرين الآن (المرحلة الثانية). "
                                            "تحول إلى وضع التتبع الحركي اللحظي الصارم وتجاهل أي تعليمات إعداد سابقة. "
                                            "طبق قوانين الـ VISUAL TRUTH بدقة. قيم الفريمات القادمة بناءً على هذا."
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
                    # Start the heartbeat task if it hasn't been started yet
                    if self.heartbeat_task is None:
                        self.heartbeat_task = asyncio.create_task(self.run_evaluation_heartbeat())
                        print("◼ Visual heartbeat loop started successfully.")
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
                self.google_ws = None
            return

    async def run_evaluation_heartbeat(self):
        """
        Runs quietly in the background during Phase 2.
        Acts as the user's silent visual pulse, forcing Gemini to analyze 
        the streamed video frames without needing any voice input.
        """
        try:
            await asyncio.sleep(3.0)
            while self.google_ws is not None:
                pulse_prompt = {
                    "clientContent": {
                        "turnComplete": True
                    }
                }
                await self.google_ws.send(json.dumps(pulse_prompt))
                await asyncio.sleep(3.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Visual pulse heartbeat loop error: {e}")        

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
                                    "You are an encouraging but highly observant Jordanian personal trainer analyzing a live video stream. "
                                    f"The current exercise is: {final_exercise}.\n\n"
                                    
                                    "PHASE 1 (Setup):\n"
                                    "- Guide the user into the correct starting position using natural, friendly Jordanian Arabic.\n\n"
                                    
                                    "PHASE 2 (Live Set Coaching - SEPARATED LOGIC):\n"
                                    "You must independenty evaluate form errors and positive motivation. Do not blend the rules.\n\n"
                                    
                                    "1. CRITICAL CORRECTIONS (Absolute Priority Over Hype):\n"
                                    "   Only speak up if a mistake is blatant and continuous. If you see an error, skip praise completely and issue a brief, natural cue:\n"
                                    "   - If they rush the descent: Tell them to slow down (e.g., 'نزل براحتك', 'اتحكم بالنزلة').\n"
                                    "   - If their back is visibly swinging excessively: Tell them to stabilize (e.g., 'ثبت ضهرك', 'بدون مرجحة').\n"
                                    "   - If their elbows drift completely out of position: Cue them to lock them in (e.g., 'كوعك ثابت', 'خلي كوعك بجنبك').\n\n"
                                    
                                    "2. PERIODIC MOTIVATION:\n"
                                    "   If the form is solid and no error from Rule 1 is occurring, you may occasionally cheer them on. "
                                    "   Use powerful Jordanian words like 'وحش!', 'كفو!', or 'بطل!'. "
                                    "   CRITICAL: Only drop a hype word once every 3 or 4 repetitions. Do not shout a motivation word on every single heartbeat pulse.\n\n"
                                    
                                    "3. CONSTRAINTS:\n"
                                    "   Keep all spoken interventions warm, encouraging, and strictly under 4 words. Never combine a praise word and a correction in the same breath."
                                )
                            }
                        ]
                    },
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {
                                    "voiceName": "Puck" # Deep male voice with a Jordanian accent, suitable for a personal trainer persona
                                }
                            }
                        }
                    },
                }
            }

            await self.google_ws.send(json.dumps(setup_packet))
            self.gemini_task = asyncio.create_task(self.receive_from_gemini())

            # Explicitly fire Phase 1 prompt as soon as the session is established
            phase1_prompt = {
                "clientContent": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "ابدأ المرحلة الأولى: وجّهني لوضعية البداية الصحيحة للتمرين بالتفصيل."
                                }
                            ],
                        }
                    ],
                    "turnComplete": True,
                }
            }
            await self.google_ws.send(json.dumps(phase1_prompt))
            
            await self.send(json.dumps({"type": "init_status", "msg": "تم تفعيل المدرب المباشر - جاري تهيئة وضعية الإعداد"}))

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

                server_content = data.get("serverContent") or {}
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
                        try:
                            await self.send(json.dumps({"type": "audio_chunk", "payload": payload}))
                        except Exception:
                            pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"❌ Receive loop error: {exc}")