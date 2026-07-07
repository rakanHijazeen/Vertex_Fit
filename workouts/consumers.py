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

        self.current_rep_count = 0
        self.language = "ar"  # Clean fallback tracking variable initial state

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
            # Normalize the incoming string (e.g., handles "AR", "ar ", etc.)
            raw_lang = str(data.get("language", "ar")).strip().lower()
            
            # Match safely
            self.language = "ar" if "ar" in raw_lang else "en"
            
            await self.init_gemini_live_session(exercise_name, self.language)
            return

        if action_type == "user_ready":
            try:
                await self.send(json.dumps({"type": "ready_ack", "msg": "starting_live"}))
            except Exception:
                pass

            if self.google_ws is not None:
                # Select the prompt language dynamically based on user choice
                if self.language == "ar":
                    phase2_text = (
                        "انتهت المرحلة الأولى فوراً. اللاعب بدأ تكرارات التمرين الآن (المرحلة الثانية). "
                        "تحول إلى وضع التتبع الحركي اللحظي الصارم وتجاهل أي تعليمات إعداد سابقة. "
                        "طبق قوانين الـ VISUAL TRUTH بدقة. قيم الفريمات القادمة بناءً على هذا."
                    )
                else:
                    phase2_text = (
                        "Phase 1 has ended immediately. The user has started their repetitions now (Phase 2). "
                        "Switch to strict real-time motion tracking mode and ignore any previous setup instructions. "
                        "Apply the VISUAL TRUTH rules strictly. Evaluate the incoming frames based on this."
                    )

                ready_prompt = {
                    "clientContent": {
                        "turns": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "text": phase2_text                                   
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

            # 2. Extract and cache the dynamic rep count sent from the frontend
            self.current_rep_count = data.get("rep_count", 0)

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
                # Format the rep update text dynamically based on the session language
                if self.language == "ar":
                    rep_text = f"العدّة الحالية المكتملة المسجلة من حساسات الحركة: {self.current_rep_count}."
                else:
                    rep_text = f"Current completed rep count recorded by motion tracking: {self.current_rep_count}."

                pulse_prompt = {
                    "clientContent": {
                        "turns": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "text": rep_text
                                    }
                                ]
                            }
                        ],
                        "turnComplete": True
                    }
                }
                await self.google_ws.send(json.dumps(pulse_prompt))
                await asyncio.sleep(3.0)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Visual pulse heartbeat loop error: {e}")        

    async def init_gemini_live_session(self, exercise_name, language):
        # Fallback to "General Workout" if exercise_name is empty or null
        final_exercise = exercise_name if exercise_name and exercise_name.strip() != "" else "General Workout"
        # Map the language code to a clear output directive for the model
        output_language_directive = (
            "Speak exclusively in natural, friendly, and motivating colloquial Jordanian Arabic." 
            if language == "ar" else 
            "Speak exclusively in natural, casual, and motivating English."
        )

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
                                    "You are an encouraging, highly observant personal trainer analyzing a live video stream.\n"
                                    f"The current exercise is: {final_exercise}.\n"
                                    f"CRITICAL OUTPUT LANGUAGE RULE: {output_language_directive}\n\n"
                                    
                                    "PHASE 1 (Setup):\n"
                                    "- Guide the user into the correct starting position using a warm, natural tone(be specific).\n\n"
                                    
                                    "PHASE 2 (Live Set Coaching):\n"
                                    "You will receive periodic background updates with the exact current completed rep count (e.g., 'العدّة الحالية المكتملة: 3'). Use this number as your ground-truth reference.\n\n"
                                    
                                    "0. THE ZERO-REP RULE (CRITICAL SILENCE):\n"
                                    "   If the current completed rep count is 0, REMAIN COMPLETELY SILENT unless there is a severe form mistake. "
                                    "   Do NOT offer any motivational words, hype, or praise before the user completes their very first rep. "
                                    "   Only start cheering them on or tracking progress once the rep count updates to 1 or higher.\n\n"

                                    "1. NO ROBOTIC REPETITION:\n"
                                    "   Do not repeat the exact same feedback cue word-for-word. Vary your phrasing naturally so you sound like a real person.\n\n"
                                    
                                    "2. CRITICAL CORRECTIONS (Priority Over Hype):\n"
                                    "   If a mistake is blatant and continuous, immediately skip praise and offer a brief, helpful coaching cue (strictly under 5 words):\n"
                                    "   - Rushing the descent: Cue them to control the eccentric phase (e.g., 'اتحكم بالنزلة' / 'Control the weight').\n"
                                    "   - Back swinging: Cue them to stabilize their core (e.g., 'ثبت ضهرك' / 'Keep your back still').\n"
                                    "   - Elbows drifting: Cue them to lock their arms in place (e.g., 'كوعك ثابت' / 'Lock those elbows').\n\n"
                                    
                                    "3. INTEGRATED REP MOTIVATION:\n"
                                    "   If form is solid, celebrate their progress every 2 or 3 reps by weaving the incoming rep count directly into a motivational phrase:\n"
                                    "   - Arabic Examples: 'وحش، هانت، كمل للرابعة!' or 'كفو ستة، كمان ثنتين بطل!'\n"
                                    "   - English Examples: 'Nice, 3 reps down, let's get 4!' or 'Looking strong at 6, two more!'\n"
                                    "   - Use authentic gym hype words like 'وحش!', 'كفو!', 'بطل!', 'Let's go!', 'Beast mode!'.\n\n"
                                    
                                    "4. AUDIO CONSTRAINT:\n"
                                    "   Keep all spoken interventions strictly under 5 words per breath so you don't break the user's focus or rhythm."
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

            # Start Phase 1 in the requested language
            p1_text = (
                "ابدأ المرحلة الأولى: وجّهني لوضعية البداية الصحيحة للتمرين بالتفصيل الممل." 
                if language == "ar" else 
                "Start Phase 1: Guide me into the correct starting position for the exercise in detail."
            )

            # Explicitly fire Phase 1 prompt as soon as the session is established
            phase1_prompt = {
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": p1_text}]}],
                    "turnComplete": True,
                }
            }
            await self.google_ws.send(json.dumps(phase1_prompt))
            
            status_msg = "تم تفعيل المدرب المباشر" if language == "ar" else "Live coach initialized."
            await self.send(json.dumps({"type": "init_status", "msg": status_msg}))
            
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