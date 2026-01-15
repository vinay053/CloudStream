import json,boto3,uuid,re
from django.shortcuts import render,redirect
from django.http import JsonResponse,Http404
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from UserLogin.db_utils import create_video_entry,get_video_by_id,get_user_videos,get_table,get_all_videos,toggle_subscription, get_subscriber_count, is_subscribed,update_reaction, get_user_reaction, get_video_stats
from UserLogin.s3_utils import generate_presigned_url
from boto3.dynamodb.conditions import Key


# 1. View to render the HTML page
def Welcome(request):
    return render(request, 'welcome.html')

# 2. API to generate the S3 Key
@csrf_exempt
def get_upload_url(request):
    if request.method == 'POST':
        # Security Check
        if 'user_email' not in request.session:
             return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            data = json.loads(request.body)
            user_email = request.session['user_email']
            
            # Inputs
            title = data.get('title', 'Untitled')
            original_filename = data.get('filename')
            file_type = data.get('file_type')
            channel=request.session['channel_name']
            
            # 1. Sanitize Filename (Fixes the "Space/Colon" bug)
            # Turns "My Video: 2026.mp4" -> "My_Video__2026.mp4"
            clean_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', original_filename)
            
            # 2. Generate Unique Keys
            unique_uuid = uuid.uuid4()
            video_s3_key = f"{unique_uuid}_{clean_filename}"
            thumb_s3_key = f"thumbnails/{unique_uuid}.jpg" # Where the image will go

            # 3. Save to DB (Includes Thumbnail Key now)
            # Ensure your db_utils.py is updated to accept this extra argument!
            create_video_entry(user_email, title, video_s3_key, thumb_s3_key,channel)
            
            # 4. Generate TWO Presigned URLs
            
            # URL A: Video -> Raw Bucket (Private)
            video_url = generate_presigned_url(
                video_s3_key, 
                file_type, 
                settings.AWS_RAW_BUCKET
            )
            
            # URL B: Thumbnail -> Processed Bucket (Public)
            thumb_url = generate_presigned_url(
                thumb_s3_key, 
                'image/jpeg', 
                settings.AWS_PROCESSED_BUCKET 
            )
            
            return JsonResponse({
                'video_upload_url': video_url,
                'thumb_upload_url': thumb_url,
                'video_id': str(unique_uuid)
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'POST method required'}, status=400)

def watch_video(request, video_id):
    # 1. Fetch Video Metadata from DynamoDB
    # We need to scan/query because we don't have the user's email in the URL
    # (In a real app, you'd put the username in the URL too, but this works for now)
    
    table = get_table()
    
    # We use the GSI (Global Secondary Index) if you have one, 
    # OR we scan. Since we don't have a GSI yet, we have to SCAN (Not efficient, but works for prototype)
    response = table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('video_id').eq(video_id)
    )
    
    items = response.get('Items', [])
    if not items:
        raise Http404("Video not found")
        
    video_data = items[0]
    
    # 2. Check if it's actually ready
    if video_data.get('status') != 'READY':
        return render(request, 'processing.html') # Optional: Make a "Still Processing" page

    bucket_name = video_data['processed_bucket']
    object_key = video_data['processed_s3_key']

    import urllib.parse
    safe_key = urllib.parse.quote(object_key)
    video_url = f"https://{bucket_name}.s3.amazonaws.com/{safe_key}"

    creator_email = video_data['PK'].split('#')[1]
    
    sub_count = get_subscriber_count(creator_email)

    user_is_subscribed = False
    if 'user_email' in request.session:
        user_is_subscribed = is_subscribed(request.session['user_email'], creator_email)

    context = {
        'video_url': video_url,
        'title': video_data.get('title', 'Unknown Video'),
        'description': video_data.get('description', ''),
        'likes': video_data.get('likes', 0),
        'dislikes': video_data.get('dislikes', 0),
        'user_reaction': get_user_reaction, # 'LIKE', 'DISLIKE' or None
        'creator_email': creator_email, # Need this for the API call
        'sub_count': int(sub_count),
        'is_subscribed': user_is_subscribed
    }
    
    return render(request, 'watch.html', context)
    
    return render(request, 'watch.html', context)
def Dashboard(request):
    if 'user_email' not in request.session:
        return redirect('login')
    
    user_email = request.session['user_email']
    
    # 1. Fetch Videos from DB
    my_videos = get_user_videos(user_email)
    
    context = {
        'channel_name': request.session.get('channel_name', 'My Channel'),
        'email': user_email,
        'videos': my_videos # Pass the list to the HTML
    }
    return render(request, 'dashboard.html', context)

def home_view(request):
    # Fetch all content
    all_videos = get_all_videos()
    
    context = {
        'videos': all_videos,
        # Check if user is logged in (to show "Login" vs "Logout" button)
        'user_email': request.session.get('user_email') 
    }
    return render(request, 'home.html', context)

@csrf_exempt
def subscribe_view(request):
    if request.method == 'POST':
        if 'user_email' not in request.session:
            return JsonResponse({'error': 'Please login to subscribe'}, status=403)
            
        data = json.loads(request.body)
        subscriber = request.session['user_email']
        creator = data.get('creator_email')
        
        if subscriber == creator:
            return JsonResponse({'error': 'Cannot subscribe to yourself'}, status=400)
            
        # Run the toggle logic
        now_subscribed = toggle_subscription(subscriber, creator)
        
        # Get new count to show on frontend
        new_count = get_subscriber_count(creator)
        
        return JsonResponse({
            'subscribed': now_subscribed,
            'new_count': int(new_count)
        })
    return JsonResponse({'error': 'POST only'}, status=405)

@csrf_exempt
def reaction_view(request):
    if request.method == 'POST':
        if 'user_email' not in request.session:
            return JsonResponse({'error': 'Login required'}, status=403)
            
        data = json.loads(request.body)
        user_email = request.session['user_email']
        
        video_id = data.get('video_id')
        action = data.get('action') # 'LIKE', 'DISLIKE', 'NONE'
        
        # We need the Video's PK/SK to update counters. 
        # For security/simplicity, we can pass the creator_email from frontend
        creator_email = data.get('creator_email') 
        
        video_pk = f"USER#{creator_email}"
        video_sk = f"VIDEO#{video_id}"
        
        # Update DB
        update_reaction(user_email, video_pk, video_sk, video_id, action)
        
        # Return new stats
        new_stats = get_video_stats(video_pk, video_sk)
        return JsonResponse(new_stats)
        
    return JsonResponse({'error': 'POST only'}, status=400)