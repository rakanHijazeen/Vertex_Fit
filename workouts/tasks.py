from background_task import background
from .models import WorkoutSession
from .vlm_service import GeminiVLMService
from .utils import S3Service

@background
def process_vlm_coaching_analysis(workout_session_id):
    """
    Background worker task that retrieves the workout session, generates a 
    temporary secure streaming link for the Gemini API, executes the biomechanical 
    analysis, and saves the markdown results directly to PostgreSQL.
    """
    try:
        # 1. Pull the tracking session out of the database
        session = WorkoutSession.objects.get(id=workout_session_id)
        
        # 2. Update status to processing so the frontend template shows the loading state
        session.status = 'processing'
        session.save()
        
        print(f"🔄 [VLM Worker]: Initiating coaching analysis for Session #{session.id} ({session.exercise.name})...")

        # 3. IMPORTANT: Generate a temporary pre-signed URL so the Gemini API endpoint 
        # can actually read/download the video file securely from your private S3 bucket.
        secure_video_url = S3Service.generate_presigned_url(session.video_url)

        # 4. Initialize your isolated Gemini service abstraction wrapper
        vlm_service = GeminiVLMService()

        # 2. Grab the user object tied to this session 💡
        user = session.user
        
        # 5. Hand over processing to Gemini with exact ground-truth values to block hallucinations
        ai_analysis_markdown = vlm_service.analyze_workout_video(
            user=user,
            video_url=secure_video_url,
            exercise_name=session.exercise.name,
            target_reps=session.rep_count,
            language=session.report_language
        )

        # 6. Save the compiled markdown analysis data and mark the queue record complete
        session.vlm_feedback = ai_analysis_markdown
        session.status = 'completed'
        session.save()
        
        print(f"✅ [VLM Worker]: Analysis successfully saved for Session #{session.id}!")

    except WorkoutSession.DoesNotExist:
        print(f"❌ [VLM Worker Error]: WorkoutSession with ID {workout_session_id} could not be resolved.")
        
    except Exception as e:
        print(f"❌ [VLM Worker Error]: Pipeline breakdown: {str(e)}")
        # Graceful fallback error status mapping so the UI stops infinite polling if something crashes
        try:
            session = WorkoutSession.objects.get(id=workout_session_id)
            session.vlm_feedback = "### 🚨 Analysis Failure\nAn unexpected server anomaly occurred while trying to process the workout metrics."
            session.status = 'failed'
            session.save()
        except:
            pass