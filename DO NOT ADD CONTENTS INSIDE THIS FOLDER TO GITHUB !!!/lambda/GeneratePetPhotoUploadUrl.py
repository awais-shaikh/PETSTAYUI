import boto3
import uuid
import json
import os
import traceback

s3 = boto3.client('s3')
BUCKET_NAME = os.environ.get("PET_PHOTO_BUCKET", "petstay-pet-photos-101481565")

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    print("RAW body field:", event.get("body"))

    try:
        # Safe parsing of the body regardless of source
        body = {}
        try:
            body_raw = event.get("body")
            if body_raw:
                if isinstance(body_raw, str):
                    body = json.loads(body_raw)
                elif isinstance(body_raw, dict):
                    body = body_raw
        except Exception as parse_err:
            print("Error parsing body:", str(parse_err))
            body = {}

        species = body.get("petSpecies", "").strip().lower()
        content_type = body.get("contentType", "").strip().lower()

        if species not in ["dog", "cat"]:
            return {
                'statusCode': 400,
                'headers': {"Access-Control-Allow-Origin": "*"},
                'body': json.dumps({'error': 'petSpecies must be "Dog" or "Cat"'})
            }

        if content_type not in ["image/jpeg", "image/png"]:
            return {
                'statusCode': 400,
                'headers': {"Access-Control-Allow-Origin": "*"},
                'body': json.dumps({'error': 'Only image/jpeg or image/png is supported'})
            }

        # Choose file extension based on content type
        extension = ".jpg" if content_type == "image/jpeg" else ".png"
        photo_id = str(uuid.uuid4()) + extension
        key = f"uploads/{species}/{photo_id}"
        print("S3 Key:", key)

        url = s3.generate_presigned_url(
            ClientMethod='put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': key,
                'ContentType': content_type
            },
            ExpiresIn=300
        )

        print("Generated URL:", url)

        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
                "Content-Type": "application/json"
            },
            'body': json.dumps({
                'uploadUrl': url,
                'key': key
            })
        }

    except Exception as e:
        traceback.print_exc()
        print("Error generating presigned URL:", str(e))
        return {
            'statusCode': 500,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps({'error': str(e)})
        }
