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

    # 🛡️ DEFENSIVE FIX: Check if the string is empty or None. 
    # If it is missing, reconstruct it dynamically so boto3 doesn't blow up!
    s3_key = session.video_url
    if not s3_key:
        print("⚠️ Warning: session.video_url was None. Reconstructing key path dynamically...")
        # Rebuild using your app's standard path structure template
        s3_key = f"workouts/user_{session.user.id}/workout_video.mp4"

    # 2. Generate a secure, temporary streaming link that Gemini can access
    video_stream_url = S3Service.generate_presigned_url(s3_key)
    
    if not video_stream_url:
        session.vlm_feedback = "🚨 System Error: Unable to generate secure cloud stream access."
        session.save()
        return

    try:
        # 3. Initialize VLM client and trigger the multi-modal generation pipeline
        vlm_engine = GeminiVLMService()
        ai_analysis_response = vlm_engine.analyze_workout_video(video_stream_url)

        # 4. Parse the response and update database state (Step 4.3)
        session.vlm_feedback = ai_analysis_response
        
        # Simple predictive fallback parser to update rep count metrics from AI text block
        if "reps:" in ai_analysis_response.lower():
            parts = ai_analysis_response.lower().split("reps:")
            rep_digit = "".join(filter(str.isdigit, parts[1].split()[0]))
            if rep_digit:
                session.rep_count = int(rep_digit)
                
    except Exception as e:
        print(f"❌ VLM Processing Failure: {str(e)}")
        session.vlm_feedback = f"🚨 Form analysis failed during execution: {str(e)}"

    # Save final analyzed metrics out safely
    session.save()
    print(f"🎉 Session {workout_session_id} successfully synchronized and analyzed!")