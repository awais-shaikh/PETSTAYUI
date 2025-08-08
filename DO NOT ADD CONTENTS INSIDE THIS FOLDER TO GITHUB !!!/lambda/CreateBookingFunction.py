import json
import boto3
import uuid
import datetime

dynamodb = boto3.resource('dynamodb')
bookings_table = dynamodb.Table('Bookings')

HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
}

def lambda_handler(event, context):
    print("Full Event:", json.dumps(event))

    http_method = event.get('httpMethod')
    path = event.get('path') or ''
    path_params = event.get('pathParameters') or {}
    booking_id = path_params.get('bookingId') if path_params else None

    print("HTTP Method:", http_method)
    print("Path:", path)

    try:
        # === Handle API Gateway POST for new booking ===
        if http_method:
            if http_method == 'POST' and path.lower().endswith('/newbooking'):
                body = json.loads(event['body'])
            elif http_method == 'GET' and booking_id:
                # Get booking status
                response = bookings_table.get_item(Key={'BookingID': booking_id})
                item = response.get('Item')
                if not item:
                    return {
                        'statusCode': 404,
                        'headers': HEADERS,
                        'body': json.dumps({'message': 'Booking not found'})
                    }
                return {
                    'statusCode': 200,
                    'headers': HEADERS,
                    'body': json.dumps(item)
                }
            else:
                return {
                    'statusCode': 404,
                    'headers': HEADERS,
                    'body': json.dumps({'message': 'Route not found'})
                }

        else:
            # If triggered directly by Step Function — payload is raw
            body = event

        # === Validate required fields ===
        required_fields = ['OwnerName', 'Email', 'PhoneNumber', 'PetName', 'CheckInDate', 'CheckOutDate']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'headers': HEADERS,
                    'body': json.dumps({'message': f'Missing field: {field}'})
                }

        try:
            datetime.datetime.strptime(body["CheckInDate"], "%Y-%m-%d")
            datetime.datetime.strptime(body["CheckOutDate"], "%Y-%m-%d")
        except ValueError:
            return {
                'statusCode': 400,
                'headers': HEADERS,
                'body': json.dumps({'message': 'Invalid date format. Use YYYY-MM-DD.'})
            }

        # === Generate BookingID ===
        booking_id = str(uuid.uuid4())
        created_at = datetime.datetime.utcnow().isoformat()

        item = {
            "BookingID": booking_id,
            "OwnerName": body["OwnerName"],
            "Email": body["Email"],
            "PhoneNumber": body["PhoneNumber"],
            "PetName": body["PetName"],
            "PetSpecies": body.get("PetSpecies", ""),
            "PetBreed": body.get("PetBreed", ""),
            "PetAge": str(body["PetAge"]) if "PetAge" in body else "",
            "CheckInDate": body["CheckInDate"],
            "CheckOutDate": body["CheckOutDate"],
            "ArrivalTime": body.get("ArrivalTime", ""),
            "Status": "Pending",
            "RoomNumber": "",
            "CreatedAt": created_at,
            "QRBase64": ""  ,
            "PetPhotoKey": body.get("PetPhotoKey", "")
        }

        bookings_table.put_item(Item=item)

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps({
                'message': 'Booking created successfully!',
                'BookingID': booking_id,
                'OwnerName': body["OwnerName"]
            })
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }
