import boto3
from boto3.dynamodb.conditions import Attr # Needed for the scan filter
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
import uuid
import time
import os

def get_table():
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        aws_session_token=settings.AWS_SESSION_TOKEN,
        region_name=settings.AWS_REGION
    )
    return dynamodb.Table(settings.DYNAMO_TABLE)

def create_user(email, password, channel_name):
    table = get_table()
    
    # Check if user already exists
    response = table.get_item(Key={'PK': f"USER#{email}", 'SK': 'PROFILE'})
    if 'Item' in response:
        return False, "User already exists"

    # Hash the password
    hashed_password = make_password(password)

    item = {
        'PK': f"USER#{email}",
        'SK': 'PROFILE',
        'channel_name': channel_name,
        'password': hashed_password, # Safe!
        'joined_at': int(time.time())
    }
    table.put_item(Item=item)
    return True, "User created successfully"

# 2. VERIFY LOGIN CREDENTIALS
def verify_user(email, password):
    table = get_table()
    
    response = table.get_item(Key={'PK': f"USER#{email}", 'SK': 'PROFILE'})
    item = response.get('Item')
    
    if not item:
        return False # User not found
    
    # Check password against the hash
    if check_password(password, item['password']):
        return item # Return user data on success
    
    return False # Wrong password

def get_user(email):
    table = get_table()
    response = table.get_item(Key={'PK': f"USER#{email}", 'SK': 'PROFILE'})
    return response.get('Item')

def create_video_entry(email, title, filename, thumbnail_key,channel, description=""): 
    table = get_table()
    video_id = str(uuid.uuid4())
    
    item = {
        'PK': f"USER#{email}",
        'SK': f"VIDEO#{video_id}",
        'title': title,
        'description': description,
        'raw_s3_key': filename,
        'channel_name':channel,
        # NEW FIELD: The public location of the thumbnail
        'thumbnail_key': thumbnail_key, 
        
        'status': 'PROCESSING',
        'video_id': video_id,
        'created_at': int(time.time())
    }
    table.put_item(Item=item)
    return video_id

def get_video_by_id(video_id):
    table = get_table()
    # Scans are slow in production, but fine for this prototype
    response = table.scan(
        FilterExpression=Attr('video_id').eq(video_id)
    )
    items = response.get('Items', [])
    if items:
        return items[0]
    return None

from boto3.dynamodb.conditions import Key

# ... existing imports and functions ...

def get_user_videos(email):
    table = get_table()
    
    # Query: "Find items where PK is USER#<email> AND SK starts with VIDEO#"
    response = table.query(
        KeyConditionExpression=Key('PK').eq(f"USER#{email}") & Key('SK').begins_with('VIDEO#')
    )
    
    # Sort them by creation time (newest first)
    # DynamoDB queries are sorted by SK, but we can sort in Python for simplicity
    items = response.get('Items', [])
    items.sort(key=lambda x: x.get('created_at', 0), reverse=True)
    
    return items

# core/db_utils.py

def get_all_videos():
    table = get_table()
    
    # SCAN: "Look at everything in the table"
    # Filter: Keep only items where SK starts with "VIDEO#" and Status is READY
    response = table.scan(
        FilterExpression=Attr('SK').begins_with('VIDEO#') & Attr('status').eq('READY')
    )
    
    items = response.get('Items', [])
    
    # Sort by creation time (Newest First)
    items.sort(key=lambda x: x.get('created_at', 0), reverse=True)
    
    return items

def toggle_subscription(subscriber_email, creator_email):
    table = get_table()
    
    # 1. Define the Relationship Key
    # PK = Subscriber, SK = Who they are subscribed to
    sub_key = {
        'PK': f"USER#{subscriber_email}",
        'SK': f"SUB#{creator_email}"
    }
    
    # 2. Check if subscription exists
    response = table.get_item(Key=sub_key)
    is_subscribed = 'Item' in response
    
    if is_subscribed:
        # ACTION: UNSUBSCRIBE
        # A. Remove the relationship
        table.delete_item(Key=sub_key)
        
        # B. Decrement Creator's Count (Atomic Update)
        table.update_item(
            Key={'PK': f"USER#{creator_email}", 'SK': 'PROFILE'},
            UpdateExpression="SET subscribers = subscribers - :val",
            ExpressionAttributeValues={':val': 1}
        )
        return False # Now unsubscribed
        
    else:
        # ACTION: SUBSCRIBE
        # A. Create the relationship
        table.put_item(Item={
            'PK': f"USER#{subscriber_email}",
            'SK': f"SUB#{creator_email}",
            'created_at': int(time.time())
        })
        
        # B. Increment Creator's Count
        # Note: We use 'SET subscribers = if_not_exists(subscribers, :zero) + :val'
        # This initializes the counter to 0 if it doesn't exist yet.
        table.update_item(
            Key={'PK': f"USER#{creator_email}", 'SK': 'PROFILE'},
            UpdateExpression="SET subscribers = if_not_exists(subscribers, :zero) + :val",
            ExpressionAttributeValues={':val': 1, ':zero': 0}
        )
        return True # Now subscribed

def get_subscriber_count(creator_email):
    table = get_table()
    response = table.get_item(Key={'PK': f"USER#{creator_email}", 'SK': 'PROFILE'})
    item = response.get('Item', {})
    return item.get('subscribers', 0)

def is_subscribed(subscriber_email, creator_email):
    table = get_table()
    response = table.get_item(Key={
        'PK': f"USER#{subscriber_email}",
        'SK': f"SUB#{creator_email}"
    })
    return 'Item' in response

def get_video_stats(video_pk, video_sk):
    table = get_table()
    response = table.get_item(Key={'PK': video_pk, 'SK': video_sk})
    item = response.get('Item', {})
    return {
        'likes': int(item.get('likes', 0)),
        'dislikes': int(item.get('dislikes', 0))
    }

def get_user_reaction(user_email, video_id):
    table = get_table()
    # Check if this user has reacted to this specific video ID
    response = table.get_item(Key={
        'PK': f"USER#{user_email}",
        'SK': f"REACTION#{video_id}"
    })
    # Returns "LIKE", "DISLIKE", or None
    return response.get('Item', {}).get('type')

def update_reaction(user_email, video_pk, video_sk, video_id, new_action):
    """
    new_action can be: 'LIKE', 'DISLIKE', or 'NONE' (removing vote)
    """
    table = get_table()
    reaction_key = {'PK': f"USER#{user_email}", 'SK': f"REACTION#{video_id}"}
    
    # 1. Get current state (Did I already like it?)
    current_reaction = get_user_reaction(user_email, video_id)
    
    if current_reaction == new_action:
        return # No change needed
    
    # 2. Update the User's "Memory" (The Reaction Item)
    if new_action == 'NONE':
        table.delete_item(Key=reaction_key)
    else:
        table.put_item(Item={
            'PK': f"USER#{user_email}", 
            'SK': f"REACTION#{video_id}",
            'type': new_action
        })

    # 3. Update the Video Counters (The Math)
    # We construct an update expression based on the change
    # e.g. If switching Like -> Dislike: likes -1, dislikes +1
    
    update_exp = "SET "
    exp_values = {}
    exp_names = {}
    
    # Helper to build the math
    # changes = {'likes': 1, 'dislikes': -1}
    changes = {}
    
    # Remove old effect
    if current_reaction == 'LIKE': changes['likes'] = -1
    if current_reaction == 'DISLIKE': changes['dislikes'] = -1
    
    # Add new effect
    if new_action == 'LIKE': changes['likes'] = changes.get('likes', 0) + 1
    if new_action == 'DISLIKE': changes['dislikes'] = changes.get('dislikes', 0) + 1
    
    # If no changes (rare), exit
    if not changes: return

    # Build DynamoDB Expression
    parts = []
    for k, v in changes.items():
        if v == 0: continue
        sign = "+" if v > 0 else "-"
        # "likes = if_not_exists(likes, 0) + 1"
        parts.append(f"#{k} = if_not_exists(#{k}, :zero) {sign} :val_{k}")
        exp_names[f"#{k}"] = k
        exp_values[f":val_{k}"] = abs(v)
    
    exp_values[':zero'] = 0
    
    table.update_item(
        Key={'PK': video_pk, 'SK': video_sk},
        UpdateExpression="SET " + ", ".join(parts),
        ExpressionAttributeNames=exp_names,
        ExpressionAttributeValues=exp_values
    )