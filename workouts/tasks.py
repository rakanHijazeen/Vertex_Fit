from background_task import background
from .models import WorkoutSession
from .utils import S3Service
from .vlm_service import GeminiVLMService

@background(schedule=0)
def process_vlm_coaching_analysis(workout_session_id: int):
    """
    Step 4.2 & 4.3: Async worker that fetches the video stream from S3,
    passes it to the Gemini VLM engine, and commits the form analysis to the DB.
    """
    try:
        # 1. Pull the fresh transactional row context from PostgreSQL
        session = WorkoutSession.objects.get(id=workout_session_id)
    except WorkoutSession.DoesNotExist:
        print(f"[Task Error]: WorkoutSession {workout_session_id} not found.")
        return

    # Update state to indicate processing has moved from view to worker
    session.vlm_feedback = "AI is currently analyzing your camera stream mechanics..."
    session.save()

    # 2. Generate a secure, temporary streaming link that Gemini can access
    # Uses the static s3 path key we safely stored during upload
    video_stream_url = S3Service.generate_presigned_url(session.video_url)
    
    if not video_stream_url:
        session.vlm_feedback = "🚨 System Error: Unable to generate secure cloud stream access."
        session.save()
        return

    # 3. Initialize VLM client and trigger the multi-modal generation pipeline
    vlm_engine = GeminiVLMService()
    ai_analysis_response = vlm_engine.analyze_workout_video(video_stream_url)

    # 4. Parse the response and update database state (Step 4.3)
    session.vlm_feedback = ai_analysis_response
    
    # Simple predictive fallback parser to update rep count metrics from AI text block
    # (Can be made more robust depending on your specific VLM system prompt structure)
    try:
        if "reps:" in ai_analysis_response.lower():
            # Basic parsing example if prompt returns "Reps: X"
            parts = ai_analysis_response.lower().split("reps:")
            rep_digit = "".join(filter(str.isdigit, parts[1].split()[0]))
            if rep_digit:
                session.rep_count = int(rep_digit)
    except Exception:
        pass # Fallback smoothly if AI format varies slightly

    # Save final analyzed metrics out to the database row
    session.save()
    print(f"[Task Success]: Successfully updated analysis for Session {workout_session_id}")