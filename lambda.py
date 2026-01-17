import json
import boto3
import urllib.parse
import os
from boto3.dynamodb.conditions import Key, Attr # <--- ADDED THIS IMPORT

# CONFIGURATION
DYNAMO_TABLE = "CloudStreamData"
PROCESSED_BUCKET = "vinayfinalvidscloudstream" 

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMO_TABLE)

def lambda_handler(event, context):
    # 1. Get the uploaded file details
    source_bucket = event['Records'][0]['s3']['bucket']['name']
    source_key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    print(f"New Upload Detected: {source_key} in {source_bucket}")

    try:
        # 2. Process (Move) the video
        destination_key = "processed_" + source_key 
        
        # Copy object (ACL removed, which is correct!)
        print(f"Copying to {PROCESSED_BUCKET}...")
        s3.copy_object(
            CopySource={'Bucket': source_bucket, 'Key': source_key},
            Bucket=PROCESSED_BUCKET,
            Key=destination_key
        )
        
        # 3. Update DynamoDB
        # CHANGED: Now uses 'Attr' directly from the import
        response = table.scan(
            FilterExpression=Attr('raw_s3_key').eq(source_key)
        )
        
        items = response.get('Items', [])
        if items:
            item = items[0]
            table.update_item(
                Key={'PK': item['PK'], 'SK': item['SK']},
                UpdateExpression="set #s = :s, #pk = :pk, #pb = :pb",
                ExpressionAttributeNames={
                    '#s': 'status',
                    '#pk': 'processed_s3_key',
                    '#pb': 'processed_bucket'
                },
                ExpressionAttributeValues={
                    ':s': 'READY',
                    ':pk': destination_key,
                    ':pb': PROCESSED_BUCKET
                }
            )
            print("Database Updated.")

            # 4. Cleanup (Delete Raw File)
            # This is enabled now. Your file will disappear from the Raw bucket after success.
            s3.delete_object(Bucket=source_bucket, Key=source_key)
            print(f"Original file deleted from {source_bucket}")
            
        else:
            print("WARNING: No matching DynamoDB item found for this file.")

    except Exception as e:
        print(f"Error: {e}")
        raise e

    return {'statusCode': 200, 'body': json.dumps('Processing Success')}