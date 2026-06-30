from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .utils import S3Service

class WorkoutVideoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        exercise_id = request.data.get('exercise_id')
        video_file = request.data.get('video')

        if not video_file:
            return Response({"error": "No video file provided"}, status=status.HTTP_400_BAD_REQUEST)

        user_id = request.user.id
        filename = video_file.name

        # Trigger our S3 utility to upload the file stream straight to Stockholm
        video_url = S3Service.upload_workout_video(video_file, user_id, filename)

        if not video_url:
            return Response(
                {"error": "Failed to upload file to cloud storage"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Success! Return the response payload
        return Response({
            "status": "success",
            "message": "Video uploaded to AWS S3 successfully.",
            "exercise_id": exercise_id,
            "video_url": video_url
        }, status=status.HTTP_201_CREATED)