import os
import boto3
from django.conf import settings
from botocore.client import Config
from botocore.exceptions import NoCredentialsError

class S3Service:
    @staticmethod
    def upload_workout_video(file_obj, user_id, filename):
        # Force regional endpoint strings explicitly
        regional_endpoint = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com"

        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            endpoint_url=f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com", # Forces client to use the right region pool
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'} # Ensures bucket.s3.region layout
            )
        )
        
        s3_path = f"workouts/user_{user_id}/{filename}"
        
        try:
            # 1. Stream file straight to Stockholm
            s3_client.upload_fileobj(
                file_obj,
                settings.AWS_STORAGE_BUCKET_NAME,
                s3_path,
                ExtraArgs={
                    "ContentType": "video/mp4",  # Forces browser inline streaming
                    "ContentDisposition": "inline" # Explicitly tells browser not to download it
                }
            )
            
            # 2. Generate region-locked pre-signed URL
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': s3_path
                },
                ExpiresIn=3600
            )
            
            return presigned_url
            
        except NoCredentialsError:
            return None
        except Exception as e:
            print(f"S3 Upload Error: {str(e)}")
            return None