from google import genai
from google.genai import types
from django.conf import settings
from .models import ChatThread, ChatMessage, WorkoutSession  

class PersonalAIContextService:
    def __init__(self, user):
        self.user = user
        
        # Initialize the Gemini API client with the provided API key and set the model name for personalized coaching
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash" 

    def _compile_user_context(self):
        """
        Gathers user profile metrics and historical workout analysis reports 
        to inject into the LLM system instructions for deep personalization.
        """
        # 1. Fetch profile metrics safely
        profile_str = "No profile metrics recorded yet."
        if hasattr(self.user, 'profile'):
            p = self.user.profile

        goal_mapping = {
            'BULK': 'Bulking / Gain Muscle',
            'CUT': 'Cutting / Lose Fat',
            'MAINTAIN': 'Maintenance'
        }
        readable_goal = goal_mapping.get(p.fitness_goal, 'Maintenance')

        # Construct a clear summary of height, target weight, goals, and gender
        gender_info = p.gender if p.gender else "Not specified"
        height_info = f"{p.height} cm" if p.height else "Not specified"
        weight_info = f"{p.target_weight} kg" if p.target_weight else "Not specified"
        
        profile_str = f"Gender: {gender_info} | Current Fitness Goal: {readable_goal} | Height: {height_info} | Target Weight: {weight_info}"
        
        # 2. Fetch the last 5 historical workout feedback records
        recent_sessions = WorkoutSession.objects.filter(user=self.user).order_by('-timestamp')[:5]
        
        reports_summary = ""
        if recent_sessions.exists():
            for i, session in enumerate(recent_sessions, 1):
                reports_summary += f"\n--- Session {i} ---\n"
                reports_summary += f"Exercise: {session.exercise.name if session.exercise else 'Unknown'}\n"
                reports_summary += f"AI Feedback Report:\n{session.vlm_feedback}\n"
        else:
            reports_summary = "No recent workout sessions or feedback reports found."

        # 3. Construct the comprehensive system prompt guidelines
        system_instruction = (
            "You are the Vertex Fit AI Personal Coaching Assistant. Your goal is to provide highly personalized "
            "fitness, biomechanical programming, and form execution advice based strictly on the user's recent "
            "workout analysis reports and background profile metrics.\n\n"
            f"=== USER PROFILE ===\n{profile_str}\n\n"
            f"=== RECENT WORKOUT PERFORMANCE REPORTS ===\n{reports_summary}\n\n"
            "INSTRUCTIONS:\n"
            "- Speak naturally, supportively, and directly like an elite human personal trainer.\n"
            "- Reference their past workout history and specific form errors discovered in their reports when answering questions.\n"
            "- If they ask about a workout session or feedback you don't see in the context, politely ask them to upload a video or track a set live first.\n"
            "- Keep answers concise, actionable, and safety-oriented."
        )
        return system_instruction

    def get_response(self, thread_id, user_message_text):
        """
        Main interface method: Appends historical log records, creates a conversational state tracking thread, 
        dispatches the message to Gemini API, and saves responses back to the local relational database.
        """
        # Retrieve or fail the target conversational thread context
        thread = ChatThread.objects.get(id=thread_id, user=self.user)
        
        # Save incoming client-side string payload to local persistent store
        ChatMessage.objects.create(thread=thread, role='user', content=user_message_text)

        # Re-compile contextual environment parameters dynamically
        system_prompt = self._compile_user_context()

        # Rebuild structured history array utilizing strict modern types schema wrappers
        raw_history = ChatMessage.objects.filter(thread=thread).order_by('timestamp')
        formatted_history = []
        for msg in raw_history:
            formatted_history.append(
                types.Content(
                    role='user' if msg.role == 'user' else 'model',
                    parts=[types.Part.from_text(text=msg.content)]
                )
            )

        # Pop the tail message to pass cleanly as an independent text execution target payload
        latest_message = formatted_history.pop() if formatted_history else None
        latest_text = user_message_text

        # Create interactive modern client chat sequence runtime
        chat = self.client.chats.create(
            model=self.model_name,
            history=formatted_history,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
            )
        )
        
        # Dispatch transaction to endpoint
        response = chat.send_message(latest_text)
        ai_response_text = response.text

        # Persist LLM completion down to local message history record rows
        ChatMessage.objects.create(thread=thread, role='model', content=ai_response_text)

        return ai_response_text