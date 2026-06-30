from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .utils import S3Service
from .models import WorkoutSession, Exercise

# From your upcoming background workers module (Step 4.2):
from .tasks import process_vlm_coaching_analysis

class WorkoutVideoUploadView(APIView):
    """
    Handles automated multipart streams recorded directly from the device camera,
    uploads them to S3, and hands off processing to the background worker loop.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser] # Needed to receive binary streams from the mobile client

    def post(self, request, format=None):
        exercise_id = request.data.get('exercise_id')
        video_file = request.data.get('video') # The phone passes the automated capture payload here

        if not video_file:
            return Response({"error": "No recorded video stream received from device camera."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not exercise_id:
            return Response({"error": "Exercise ID parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Confirm the intended exercise exists in the system database
        try:
            exercise = Exercise.objects.get(id=exercise_id)
        except Exercise.DoesNotExist:
            return Response({"error": "Specified exercise configuration does not exist"}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        filename = video_file.name

        # 1. Stream the captured video bytes directly to your private S3 bucket
        video_url = S3Service.upload_workout_video(video_file, user.id, filename)

        if not video_url:
            return Response(
                {"error": "Failed to persist recorded file stream to cloud storage."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 2. Build the stable, permanent path key template for secure internal tracking
        s3_storage_path = f"workouts/user_{user.id}/{filename}"

        # 3. Create a record in PostgreSQL tracking this specific workout set session
        # type: ignore (Stops Pylance from complaining about dynamic Django model attributes)
        workout_session = WorkoutSession.objects.create(
            user=user,
            exercise=exercise,
            video_url=s3_storage_path, # Saves the stable canonical route structure 
            rep_count=0,               # Initial placeholder state before VLM analysis runs
            vlm_feedback="Form analysis is processing in the background..."
        )

        # 4. Safely hand over execution asynchronously to background workers (Step 4.2)
        process_vlm_coaching_analysis.delay(workout_session_id=workout_session.id)

        # 5. Return success instantly so the phone app can show a loading/success animation
        return Response({
            "status": "success",
            "message": "Camera recording successfully synchronized. Analysis initiated.",
            "session_id": workout_session.id,
            "exercise": exercise.name,
            "temporary_stream_url": video_url
        }, status=status.HTTP_201_CREATED)


class WorkoutSessionDetailView(APIView):
    """
    Enforces absolute privacy protection. Fetches analytics metadata and generates
    a short-lived secure streaming link ONLY if the authenticated user owns the record.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id, format=None):
        try:
            # STRICT OWNERSHIP FILTER: Enforces user isolation directly at the query level
            workout_session = WorkoutSession.objects.get(id=session_id, user=request.user)
        except WorkoutSession.DoesNotExist:
            # Mask database contents with a standard 404 to block malicious endpoint enumeration
            return Response({"error": "Workout session not found."}, status=status.HTTP_404_NOT_FOUND)

        # Generate a secure, 60-minute expiring pre-signed S3 URL for streaming back to the user's phone
        fresh_stream_url = S3Service.generate_presigned_url(workout_session.video_url)

        return Response({
            "session_id": workout_session.id,
            "exercise": workout_session.exercise.name,
            "rep_count": workout_session.rep_count,
            "vlm_feedback": workout_session.vlm_feedback,
            "stream_url": fresh_stream_url,  # Secure, expiring access target
            "timestamp": workout_session.timestamp
        }, status=status.HTTP_200_OK)