import json
import boto3
from datetime import datetime
from boto3.dynamodb.conditions import Attr
import uuid
import qrcode
from io import BytesIO
import os

# AWS clients
dynamodb = boto3.resource('dynamodb')
dynamodb_client = boto3.client('dynamodb')
ses = boto3.client('ses', region_name='us-east-1')
s3 = boto3.client('s3')
eventbridge = boto3.client('events')
iot = boto3.client('iot-data', region_name='us-east-1')

# Constants
QR_BUCKET = 'petstay-qr-images-101486688'
bookings_table = dynamodb.Table('Bookings')
rooms_table = dynamodb.Table('Rooms')
FRONTEND_URL = os.environ.get("FRONTEND_BASE_URL", "https://main.d3esln33qx1ws1.amplifyapp.com")
PHOTO_BUCKET = os.environ.get("PET_PHOTO_BUCKET", "petstay-pet-photos-101486688")
HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store'
}

allowed_staff = ["petstayteam@outlook.com", "petstayteam@gmail.com"]

def is_admin(event):
    email = extract_email_from_token(event)
    return email in allowed_staff

import json

def lambda_handler(event, context):
    print("Lambda triggered. Raw event:")
    print(json.dumps(event))

    # Handle EventBridge events
    if 'detail-type' in event:
        detail_type = event['detail-type']
        detail = event.get('detail', {})

        print(f"EventBridge Event Received: {detail_type}")
        print("Event Details:", json.dumps(detail))

        if detail_type == "BookingConfirmed":
            return handle_booking_confirmed(detail)
        elif detail_type == "BookingCancelled":
            return handle_booking_cancelled(detail)
        elif detail_type == "BookingCheckedIn":
            return handle_booking_checked_in(detail)
        elif detail_type == "BookingCheckedOut":
            return handle_booking_checked_out(detail)
        elif detail_type == "BookingRestored":
            return handle_booking_restored(detail)
        else:
            print("Unknown event type")

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f"Handled EventBridge: {detail_type}"}),
        }

    # Handle API Gateway requests
    method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
    path = event.get('rawPath') or event.get('path') or event.get('requestContext', {}).get('http', {}).get('path', '')
    print("API Gateway Request Path:", path, "Method:", method)

    try:
        segments = path.strip('/').split('/')
        body = json.loads(event.get("body", "{}"))
        booking_id = body.get("BookingID") or body.get("bookingId")  # Support both casings

        # Health check
        if method == 'GET' and path == '/health':
            return {'statusCode': 200, 'body': json.dumps({'status': 'ok'})}

        # Booking and room GET routes
        elif method == 'GET' and path == '/bookings':
            return get_all_bookings()

        elif method == 'GET' and path == '/rooms/availability':
            return get_room_availability()

        elif method == 'GET' and path == '/get-booking-trend':
            return get_booking_trend()


        elif method == 'GET' and segments[0] == 'booking' and len(segments) == 2:
            return get_single_booking(segments[1])

        # # Upload URL
        # elif method == 'POST' and path == '/upload-url':
        #     return generate_upload_url(event, context)

        # Room seeding
        elif method == 'POST' and path == '/rooms/seed':
            return seed_rooms()

        # Booking actions using body-based BookingID
        elif method == 'POST' and path == '/checkin':
            if not booking_id:
                return {'statusCode': 400, 'body': json.dumps({'message': 'Missing BookingID'})}
            return checkin_booking(event, booking_id)

        elif method == 'POST' and path == '/checkout':
            if not booking_id:
                return {'statusCode': 400, 'body': json.dumps({'message': 'Missing BookingID'})}
            return checkout_booking(event, booking_id)

        elif method == 'POST' and path == '/restore':
            if not booking_id:
                return {'statusCode': 400, 'body': json.dumps({'message': 'Missing BookingID'})}
            return restore_booking(event, booking_id)

        elif method == 'POST' and path == '/cancel':
            if not booking_id:
                return {'statusCode': 400, 'body': json.dumps({'message': 'Missing BookingID'})}
            return cancel_booking(event, booking_id)

        elif method == 'POST' and path == '/confirm':
            if not booking_id:
                return {'statusCode': 400, 'body': json.dumps({'message': 'Missing BookingID'})}
            return confirm_booking(event, booking_id)

        # Optional: fallback for /{action}/{id}
        elif method == 'POST' and len(segments) == 2:
            action, seg_id = segments
            if action in ['checkin', 'checkout', 'restore', 'cancel', 'confirm']:
                return route_action(event, action, seg_id)

        # Fallback route
        return {
            'statusCode': 404,
            'headers': HEADERS,
            'body': json.dumps({'message': 'Route not found'})
        }

    except Exception as e:
        print("Exception occurred:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }

def route_action(event, action, booking_id):
    if action == 'confirm':
        return confirm_booking(event, booking_id)
    elif action == 'cancel':
        return cancel_booking(event, booking_id)
    elif action == 'checkout':
        return checkout_booking(event, booking_id)
    elif action == 'checkin':
        return checkin_booking(event, booking_id)
    elif action == 'restore':
        return restore_booking(event, booking_id)
    else:
        return {
            'statusCode': 400,
            'headers': HEADERS,
            'body': json.dumps({'message': f'Unsupported action: {action}'})
        }

def publish_iot_stats():
    try:
        # Fetch room availability
        room_response = rooms_table.scan()
        rooms = room_response.get('Items', [])

        available_rooms = sum(1 for r in rooms if not r.get('isOccupied'))
        current_guests = sum(1 for r in rooms if r.get('isOccupied'))

        # Count pet species from bookings
        bookings = bookings_table.scan().get("Items", [])
        species_counter = {}
        for b in bookings:
            species = b.get("PetSpecies", "Unknown")
            species_counter[species] = species_counter.get(species, 0) + 1

        # Booking trend — just total today for now
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        today_bookings = sum(1 for b in bookings if b.get("CheckInDate", "").startswith(today_str))

        payload = {
            "metric": "bookingUpdate",
            "value": {
                "currentGuests": current_guests,
                "availableRooms": available_rooms,
                "petSpecies": species_counter,
                "bookingTrendPoint": today_bookings
            }
        }

        iot.publish(
            topic='petstay/admin/stats',
            qos=0,
            payload=json.dumps(payload)
        )
        print("IoT stats published to petstay/admin/stats")

    except Exception as e:
        print("Failed to publish IoT stats:", str(e))


def handle_booking_confirmed(detail):
    print(f"Booking Confirmed for: {detail.get('OwnerName')} (BookingID: {detail.get('BookingID')})")
    publish_iot_stats()
    return {'statusCode': 200, 'body': json.dumps({'message': 'BookingConfirmed processed'})}

def handle_booking_cancelled(detail):
    print(f"Booking Cancelled: {detail.get('BookingID')}")
    publish_iot_stats()
    return {'statusCode': 200, 'body': json.dumps({'message': 'BookingCancelled processed'})}

def handle_booking_checked_in(detail):
    print(f"Guest Checked In: {detail.get('BookingID')}")
    publish_iot_stats()
    return {'statusCode': 200, 'body': json.dumps({'message': 'BookingCheckedIn processed'})}

def handle_booking_checked_out(detail):
    print(f"Guest Checked Out: {detail.get('BookingID')}")
    publish_iot_stats()
    return {'statusCode': 200, 'body': json.dumps({'message': 'BookingCheckedOut processed'})}

def handle_booking_restored(detail):
    print(f"Booking Restored: {detail.get('BookingID')}")
    publish_iot_stats()
    return {'statusCode': 200, 'body': json.dumps({'message': 'BookingRestored processed'})}

def get_booking_trend():
    try:
        response = bookings_table.scan()
        bookings = response.get('Items', [])

        trend = {}
        for b in bookings:
            date = b.get("CheckInDate", "")[:10]  # Extract YYYY-MM-DD
            if date:
                trend[date] = trend.get(date, 0) + 1

        # Sort by date
        trend_list = [{"time": k, "count": v} for k, v in sorted(trend.items())]

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps(trend_list)
        }

    except Exception as e:
        print("Error in get_booking_trend:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }

def seed_rooms():
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Rooms')  

    rooms = []

    # First 10 rooms for Dogs: D101–D110
    for i in range(10):
        rooms.append({
            'roomId': str(uuid.uuid4()),
            'roomNumber': f'D{101 + i}',
            'isAvailable': True,
            'isOccupied': False,
            'petType': 'Dog',
            'lastUpdated': datetime.utcnow().isoformat()
        })

    # Next 10 rooms for Cats: C201–C210
    for i in range(10):
        rooms.append({
            'roomId': str(uuid.uuid4()),
            'roomNumber': f'C{201 + i}',
            'isAvailable': True,
            'isOccupied': False,
            'petType': 'Cat',
            'lastUpdated': datetime.utcnow().isoformat()
        })

    with table.batch_writer() as batch:
        for room in rooms:
            batch.put_item(Item=room)

    return {
        'statusCode': 200,
        'headers': HEADERS,
        'body': json.dumps({'message': f'Successfully seeded {len(rooms)} rooms'})
    }

def get_room_availability():
    try:
        response = rooms_table.scan()
        rooms = response.get('Items', [])

        # Auto-seed if no rooms found
        if not rooms:
            print("No rooms found. Seeding 20 default rooms...")
            seed_rooms()
            response = rooms_table.scan()
            rooms = response.get('Items', [])

        # Group by pet type
        dog_rooms = [r for r in rooms if r.get('petType') == 'Dog']
        cat_rooms = [r for r in rooms if r.get('petType') == 'Cat']

        dog_total = len(dog_rooms)
        dog_available = sum(1 for r in dog_rooms if not r.get('isOccupied'))
        cat_total = len(cat_rooms)
        cat_available = sum(1 for r in cat_rooms if not r.get('isOccupied'))

        print("Returning availability and room list")

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps({
                'dog': {'available': dog_available, 'total': dog_total},
                'cat': {'available': cat_available, 'total': cat_total},
                'stats': {
                    'rooms': rooms
                }
            })
        }

    except Exception as e:
        print("Error in get_room_availability:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }


def extract_email_from_token(event):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        email = claims.get("email")
        print("Extracted email (HTTP API):", email)
        return email
    except KeyError:
        try:
            # Fallback for REST API style
            email = event["requestContext"]["authorizer"]["claims"]["email"]
            print("Extracted email (REST API fallback):", email)
            return email
        except Exception as e:
            print("JWT extraction failed:", str(e))
            print("Full requestContext:", json.dumps(event.get("requestContext", {})))
            return None

def upload_qr_to_s3(qr_data):
    key = f"qr-codes/{uuid.uuid4()}.png"
    s3.put_object(
        Bucket=QR_BUCKET,
        Key=key,
        Body=qr_data,
        ContentType='image/png',
        CacheControl='max-age=31536000', 
    )
    return key

def generate_presigned_url(key, expiration=3600):
    if not key:
        return ""
    try:
        return s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': QR_BUCKET, 'Key': key},
            ExpiresIn=expiration
        )
    except Exception as e:
        print(f"[ERROR] Failed to generate presigned URL for '{key}': {str(e)}")
        return ""

def send_confirmation_email(owner_name, booking_id, qr_url):
    qr_link = f"{FRONTEND_URL}/checkin.html?bookingId={booking_id}"

    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #2e6c80;">PetStay Booking Confirmed</h2>
        <p><strong>Owner:</strong> {owner_name}</p>
        <p><strong>Booking ID:</strong> {booking_id}</p>
        <p>Click this link to check-in: <a href="{qr_link}">{qr_link}</a></p>
        <p>Or scan the QR code below:</p>
        <p><img src="{qr_url}" width="200" height="200" alt="QR Code" /></p>
        <p style="color: #888;">— PetStay Team</p>
      </body>
    </html>
    """

    try:
        response = ses.send_email(
            Source='petstayteam@gmail.com',
            Destination={"ToAddresses": ["petstayteam@outlook.com"]},
            Message={
                "Subject": {"Data": f"PetStay Booking Confirmed - {owner_name}"},
                "Body": {
                    "Text": {"Data": f"Owner: {owner_name}\nBooking ID: {booking_id}\nCheck-in link: {qr_link}"},
                    "Html": {"Data": body_html}
                }
            }
        )

        bookings_table.update_item(
            Key={'BookingID': booking_id},
            UpdateExpression='SET EmailStatus = :status, EmailSentAt = :time',
            ExpressionAttributeValues={
                ':status': 'Success',
                ':time': datetime.utcnow().isoformat()
            }
        )

        return "Email sent to PetStay team"

    except Exception as e:
        bookings_table.update_item(
            Key={'BookingID': booking_id},
            UpdateExpression='SET EmailStatus = :status, EmailSentAt = :time',
            ExpressionAttributeValues={
                ':status': f'Failed: {str(e)}',
                ':time': datetime.utcnow().isoformat()
            }
        )
        return f"Email failed: {str(e)}"

def get_single_booking(booking_id):
    try:
        print(f"Looking for booking: {booking_id}")
        response = bookings_table.get_item(Key={'BookingID': booking_id})
        print(f"Raw DB response: {response}")
        booking = response.get('Item')

        if not booking:
            return {
                'statusCode': 404,
                'headers': HEADERS,
                'body': json.dumps({'message': 'Booking not found'})
            }

        if 'QRCodeKey' in booking:
            booking['QRCodeURL'] = generate_presigned_url(booking['QRCodeKey'])

        if 'PetPhotoKey' in booking and booking['PetPhotoKey']:
            try:
                booking['PetPhotoURL'] = generate_pet_photo_url(booking['PetPhotoKey'])
            except Exception as e:
                print(f"Failed to generate PetPhotoURL: {str(e)}")
                booking['PetPhotoURL'] = ""

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps(booking)
        }

    except Exception as e:
        print("Error fetching booking:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }


def get_all_bookings():
    try:
        print("Scanning Bookings table...")
        response = bookings_table.scan()
        bookings = response.get('Items', [])
        print(f"Retrieved {len(bookings)} bookings")

        for b in bookings:
            # Add QR Code URL if available
            if 'QRCodeKey' in b:
                try:
                    b['QRCodeURL'] = generate_presigned_url(b['QRCodeKey'])
                except Exception as qr_err:
                    print(f"Failed to generate QR URL for BookingID {b.get('BookingID')}: {str(qr_err)}")

            # Add Pet Photo URL if available
            if 'PetPhotoKey' in b and b['PetPhotoKey']:
                try:
                    b['PetPhotoURL'] = generate_pet_photo_url(b['PetPhotoKey'])
                except Exception as err:
                    print(f"Error generating pet photo URL for BookingID {b.get('BookingID')}: {str(err)}")
                    b['PetPhotoURL'] = ""

        # Sort by Check-In Date (newest first)
        try:
            bookings.sort(key=lambda x: x.get("CheckInDate", ""), reverse=True)
        except Exception as sort_err:
            print("Sorting error:", str(sort_err))

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps({'bookings': bookings})
        }

    except Exception as e:
        print("Exception in get_all_bookings:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }

# def generate_upload_url(event, context):
#     print("DEBUG: Entered generate_upload_url function")
#     try:
#         body = json.loads(event.get("body", "{}"))
#         pet_species = body.get("petSpecies", "cat").lower()
#         content_type = body.get("contentType", "image/jpeg")

#         if pet_species not in ["dog", "cat"]:
#             return {
#                 'statusCode': 400,
#                 'headers': HEADERS,
#                 'body': json.dumps({ "message": "Invalid petSpecies. Must be 'Dog' or 'Cat'." })
#             }

#         bucket = os.environ.get("PET_PHOTO_BUCKET", "petstay-pet-photos-101481565")
#         filename = f"{uuid.uuid4()}.jpg"
#         key = f"{pet_species}/{filename}"

#         url = s3.generate_presigned_url(
#             ClientMethod='put_object',
#             Params={
#                 'Bucket': bucket,
#                 'Key': key,
#                 'ContentType': content_type
#             },
#             ExpiresIn=300
#         )

#         return {
#             'statusCode': 200,
#             'headers': HEADERS,
#             'body': json.dumps({ 'uploadUrl': url, 'key': key })  # changed to 'key' to match frontend
#         }

#     except Exception as e:
#         print("Error in generate_upload_url:", str(e))
#         return {
#             'statusCode': 500,
#             'headers': HEADERS,
#             'body': json.dumps({ "message": "Internal Server Error" })
#         }

def generate_pet_photo_url(photo_key, expiration=3600):
    bucket = os.environ.get("PET_PHOTO_BUCKET", "petstay-pet-photos-101481565")
    if not photo_key:
        print("[WARN] photo_key is empty")
        return ""
    try:
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': photo_key},
            ExpiresIn=expiration
        )
        print(f"Generated photo URL for key: {photo_key}")
        return url
    except Exception as e:
        print(f"[ERROR] Failed to generate pet photo URL for key '{photo_key}': {str(e)}")
        return ""


def confirm_booking(event, booking_id):
    try:
        print("Checking admin access...")
        if not is_admin(event):
            print("Unauthorized access attempt.")
            return {
                'statusCode': 403,
                'headers': HEADERS,
                'body': json.dumps({'message': 'Unauthorized: Email not allowed or missing token'})
            }

        print(f"Fetching booking ID: {booking_id}")
        booking = bookings_table.get_item(Key={'BookingID': booking_id}).get('Item')
        if not booking or booking.get('Status') != 'Pending':
            print("Booking not found or status is not Pending")
            return {
                'statusCode': 400,
                'headers': HEADERS,
                'body': json.dumps({'message': 'Invalid booking status'})
            }

        print("Generating QR code...")
        qr_url_text = f"{FRONTEND_URL}/checkin.html?bookingId={booking_id}"
        img = qrcode.make(qr_url_text)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        qr_data = buffer.read()

        print("Uploading QR code to S3...")
        qr_key = upload_qr_to_s3(qr_data)

        print("Updating booking status in DynamoDB...")
        bookings_table.update_item(
            Key={'BookingID': booking_id},
            UpdateExpression='SET #s = :status, QRCodeKey = :qrkey',
            ExpressionAttributeNames={'#s': 'Status'},
            ExpressionAttributeValues={
                ':status': 'Confirmed',
                ':qrkey': qr_key
            }
        )

        print("Generating presigned URL...")
        qr_url = generate_presigned_url(qr_key)

        print("Sending confirmation email...")
        email_result = send_confirmation_email(booking['OwnerName'], booking_id, qr_url)

        print("Emitting EventBridge event...")
        eventbridge.put_events(
            Entries=[{
                'Source': 'PetStay.Booking',
                'DetailType': 'BookingConfirmed',
                'Detail': json.dumps({
                    'BookingID': booking_id,
                    'OwnerName': booking['OwnerName'],
                    'Status': 'Confirmed'
                }),
                'EventBusName': 'PetStayBus'
            }]
        )

        print("Booking confirmed successfully.")
        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps({'message': f'Booking confirmed and email sent. {email_result}'})
        }

    except Exception as e:
        print("Exception during confirmation:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': f'Booking confirmation failed: {str(e)}'})
        }

def cancel_booking(event, booking_id):
    try:
        if not is_admin(event):
            return {'statusCode': 403, 'headers': HEADERS, 'body': json.dumps({'message': 'Unauthorized: Only admin can cancel'})}

        booking = bookings_table.get_item(Key={'BookingID': booking_id}).get('Item')
        if not booking:
            return {'statusCode': 404, 'headers': HEADERS, 'body': json.dumps({'message': 'Booking not found'})}

        transact_items = [{
            'Update': {
                'TableName': 'Bookings',
                'Key': {'BookingID': {'S': booking_id}},
                'UpdateExpression': 'SET #s = :cancelled',
                'ExpressionAttributeNames': {'#s': 'Status'},
                'ExpressionAttributeValues': {':cancelled': {'S': 'Cancelled'}}
            }
        }]

        room_number = booking.get('RoomNumber')
        if room_number:
            room_lookup = rooms_table.scan(FilterExpression=Attr('roomNumber').eq(room_number))
            if room_lookup['Items']:
                room_id = room_lookup['Items'][0]['roomId']
                transact_items.append({
                    'Update': {
                        'TableName': 'Rooms',
                        'Key': {'roomId': {'S': room_id}},
                        'UpdateExpression': 'SET isOccupied = :false',
                        'ExpressionAttributeValues': {':false': {'BOOL': False}}
                    }
                })

        dynamodb_client.transact_write_items(TransactItems=transact_items)

        eventbridge.put_events(
            Entries=[{
                'Source': 'PetStay.Booking',
                'DetailType': 'BookingCancelled',
                'Detail': json.dumps({'BookingID': booking_id}),
                'EventBusName': 'PetStayBus'
            }]
        )

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps({'message': 'Booking cancelled'})
        }

    except Exception as e:
        return {'statusCode': 500, 'headers': HEADERS, 'body': json.dumps({'error': str(e)})}

def restore_booking(event, booking_id):
    try:
        if not is_admin(event):
            return {'statusCode': 403, 'headers': HEADERS, 'body': json.dumps({'message': 'Unauthorized: Only admin can restore'})}

        booking = bookings_table.get_item(Key={'BookingID': booking_id}).get('Item')
        if not booking:
            return {'statusCode': 404, 'headers': HEADERS, 'body': json.dumps({'message': 'Booking not found'})}
        if booking.get('Status') != 'Cancelled':
            return {'statusCode': 400, 'headers': HEADERS, 'body': json.dumps({'message': 'Only cancelled bookings can be restored'})}

        bookings_table.update_item(
            Key={'BookingID': booking_id},
            UpdateExpression='SET #s = :status',
            ExpressionAttributeNames={'#s': 'Status'},
            ExpressionAttributeValues={':status': 'Pending'}
        )

        # Emit event to EventBridge
        eventbridge.put_events(
            Entries=[
                {
                    'Source': 'PetStay.Booking',
                    'DetailType': 'BookingRestored',
                    'Detail': json.dumps({'BookingID': booking_id}),
                    'EventBusName': 'PetStayBus'
                }
            ]
        )

        return {'statusCode': 200, 'headers': HEADERS, 'body': json.dumps({'message': 'Booking restored'})}
    except Exception as e:
        return {'statusCode': 500, 'headers': HEADERS, 'body': json.dumps({'error': str(e)})}

def checkout_booking(event, booking_id):
    try:
        if not is_admin(event):
            return {'statusCode': 403, 'headers': HEADERS, 'body': json.dumps({'message': 'Unauthorized: Only admin can check out'})}

        booking = bookings_table.get_item(Key={'BookingID': booking_id}).get('Item')
        if not booking:
            return {'statusCode': 404, 'headers': HEADERS, 'body': json.dumps({'message': 'Booking not found'})}
        if booking.get('Status') != 'Checked-In':
            return {'statusCode': 400, 'headers': HEADERS, 'body': json.dumps({'message': 'Only checked-in bookings can be checked out'})}

        room_number = booking.get('RoomNumber')
        if room_number:
            room_lookup = rooms_table.scan(FilterExpression=Attr('roomNumber').eq(room_number))
            if room_lookup['Items']:
                room_id = room_lookup['Items'][0]['roomId']
                rooms_table.update_item(
                    Key={'roomId': room_id},
                    UpdateExpression='SET isOccupied = :false',
                    ExpressionAttributeValues={':false': False}
                )

        bookings_table.update_item(
            Key={'BookingID': booking_id},
            UpdateExpression='SET #s = :status, CheckOutTime = :time',
            ExpressionAttributeNames={'#s': 'Status'},
            ExpressionAttributeValues={
                ':status': 'Checked-Out',
                ':time': datetime.utcnow().isoformat()
            }
        )

        eventbridge.put_events(
            Entries=[{
                'Source': 'PetStay.Booking',
                'DetailType': 'BookingCheckedOut',
                'Detail': json.dumps({'BookingID': booking_id}),
                'EventBusName': 'PetStayBus'
            }]
        )

        return {'statusCode': 200, 'headers': HEADERS, 'body': json.dumps({'message': 'Guest checked out'})}
    except Exception as e:
        return {'statusCode': 500, 'headers': HEADERS, 'body': json.dumps({'error': str(e)})}

def checkin_booking(event, booking_id):
    try:
        email = extract_email_from_token(event)
        if not email:
            return {'statusCode': 401, 'headers': HEADERS, 'body': json.dumps({'message': 'Missing or invalid token'})}

        if email not in allowed_staff:
            return {'statusCode': 403, 'headers': HEADERS, 'body': json.dumps({'message': 'Unauthorized email'})}

        booking = bookings_table.get_item(Key={'BookingID': booking_id}).get('Item')
        if not booking:
            return {'statusCode': 404, 'headers': HEADERS, 'body': json.dumps({'message': 'Booking not found'})}

        if booking.get('Status') == 'Checked-In':
            return {'statusCode': 200, 'headers': HEADERS, 'body': json.dumps({'message': 'Already checked in', 'roomId': booking.get('RoomNumber')})}

        if booking.get('Status') == 'Checked-Out':
            return {'statusCode': 400, 'headers': HEADERS, 'body': json.dumps({'message': 'Guest has already checked out. Check-in not allowed.'})}

        if booking.get('Status') != 'Confirmed':
            return {'statusCode': 400, 'headers': HEADERS, 'body': json.dumps({'message': 'Booking must be confirmed before check-in'})}

        pet_type = booking.get('PetSpecies')
        if not pet_type or pet_type not in ['Dog', 'Cat']:
            return {'statusCode': 400, 'headers': HEADERS, 'body': json.dumps({'message': 'Unsupported or missing pet type'})}

        available_rooms = rooms_table.scan(
            FilterExpression=Attr('petType').eq(pet_type) & Attr('isOccupied').eq(False)
        )

        # Auto-seed if no rooms found
        if not available_rooms['Items']:
            print(f"No available rooms for {pet_type}. Checking if table is empty...")

            room_check = rooms_table.scan()
            if not room_check['Items']:
                print("Rooms table is empty. Seeding default 20 rooms...")
                seed_rooms()

                # Re-scan after seeding
                available_rooms = rooms_table.scan(
                    FilterExpression=Attr('petType').eq(pet_type) & Attr('isOccupied').eq(False)
                )

            if not available_rooms['Items']:
                return {
                    'statusCode': 409,
                    'headers': HEADERS,
                    'body': json.dumps({'message': f'No available room for {pet_type}', 'errorType': 'RoomFull', 'petType': pet_type})
                }

        room = available_rooms['Items'][0]
        room_id = room['roomId']
        room_name = room.get('roomNumber', room_id)

        print(f"Assigning room {room_name} (ID: {room_id}) to booking {booking_id} for {pet_type}")

        checkin_time = datetime.utcnow().isoformat()
        checkin_date = datetime.utcnow().date().isoformat()

        # Transactional update with reserved word fix
        dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    'Update': {
                        'TableName': 'Rooms',
                        'Key': {'roomId': {'S': room_id}},
                        'UpdateExpression': 'SET isOccupied = :occupied',
                        'ConditionExpression': 'isOccupied = :false',
                        'ExpressionAttributeValues': {
                            ':occupied': {'BOOL': True},
                            ':false': {'BOOL': False}
                        }
                    }
                },
                {
                    'Update': {
                        'TableName': 'Bookings',
                        'Key': {'BookingID': {'S': booking_id}},
                        'UpdateExpression': 'SET #s = :status, CheckInTime = :time, CheckInDate = :date, RoomNumber = :room',
                        'ConditionExpression': 'attribute_not_exists(#s) OR #s = :confirmed',
                        'ExpressionAttributeNames': {
                            '#s': 'Status'
                        },
                        'ExpressionAttributeValues': {
                            ':status': {'S': 'Checked-In'},
                            ':time': {'S': checkin_time},
                            ':date': {'S': checkin_date},
                            ':room': {'S': room_name},
                            ':confirmed': {'S': 'Confirmed'}
                        }
                    }
                }
            ]
        )

        # Emit EventBridge event
        eventbridge.put_events(
            Entries=[{
                'Source': 'PetStay.Booking',
                'DetailType': 'BookingCheckedIn',
                'Detail': json.dumps({'BookingID': booking_id}),
                'EventBusName': 'PetStayBus'
            }]
        )

        return {
            'statusCode': 200,
            'headers': HEADERS,
            'body': json.dumps({
                'message': f'Checked-in to room {room_name}',
                'roomId': room_name,
                'newStatus': 'Checked-In',
                'room': room
            })
        }

    except dynamodb_client.exceptions.TransactionCanceledException as e:
        print("Transaction conflict:", str(e))
        return {
            'statusCode': 409,
            'headers': HEADERS,
            'body': json.dumps({'error': 'Check-in failed. Room might already be occupied.', 'details': str(e)})
        }

    except Exception as e:
        print("Unexpected error:", str(e))
        return {
            'statusCode': 500,
            'headers': HEADERS,
            'body': json.dumps({'error': str(e)})
        }
