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

def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
        region_name=settings.AWS_REGION
    )

def generate_presigned_url(filename, file_type, bucket_name):
    s3 = get_s3_client()
    presigned_url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': bucket_name,
            'Key': filename,
            'ContentType': file_type
        },
        ExpiresIn=3600
    )
    return presigned_url

def upload_public_file(file_obj, key, bucket_name, content_type=None):
    s3 = get_s3_client()
    try:
        extra_args = {'ACL': 'public-read'}
        if content_type:
            extra_args['ContentType'] = content_type
            
        s3.upload_fileobj(
            file_obj,
            bucket_name,
            key,
            ExtraArgs=extra_args
        )
        return f"https://{bucket_name}.s3.amazonaws.com/{key}"
    except Exception as e:
        print(f"S3 Upload Error: {e}")
        return None