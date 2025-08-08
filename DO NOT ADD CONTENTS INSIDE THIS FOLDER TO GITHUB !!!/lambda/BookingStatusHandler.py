import json
import boto3

client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    # Get the executionArn from path parameters
    executionArn = event.get('pathParameters', {}).get('executionArn')

    if not executionArn:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({ 'error': 'Missing executionArn' })
        }

    try:
        # Describe the execution status
        response = client.describe_execution(executionArn=executionArn)
    except Exception as e:
        print("Error describing execution:", str(e))
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({ 'error': 'Failed to describe execution', 'details': str(e) })
        }

    parsed_output = {}

    if response['status'] == 'SUCCEEDED':
        try:
            # Decode the output from the Step Function
            raw_output = json.loads(response.get('output', '{}'))

            # Some outputs are double-encoded in Step Functions
            body = raw_output.get('body')
            if isinstance(body, str):
                parsed_output = json.loads(body)
            elif isinstance(body, dict):
                parsed_output = body
            else:
                parsed_output = raw_output  # fallback
        except Exception as e:
            print("Error parsing Step Function output:", e)

        result = {
            'status': 'SUCCEEDED',
            'output': parsed_output
        }
    else:
        # For RUNNING, FAILED, TIMED_OUT, etc.
        result = {
            'status': response['status']
        }

    print("Final Lambda Output to frontend:", result)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',  
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(result)
    }
