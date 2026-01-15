import boto3
from django.conf import settings

# CHANGED: Added bucket_name parameter
def generate_presigned_url(filename, file_type, bucket_name):
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
        region_name=settings.AWS_REGION
    )
    
    presigned_url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': bucket_name, # CHANGED: Uses the passed bucket variable
            'Key': filename,
            'ContentType': file_type
        },
        ExpiresIn=3600
    )
    return presigned_url