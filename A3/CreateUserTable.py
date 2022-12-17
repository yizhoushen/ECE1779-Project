import boto3
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
def create_user_table():

    table = dynamodb.create_table(
        TableName='UserTable',
        KeySchema=[
            {
                'AttributeName': 'email',
                'KeyType': 'HASH'  # Partition key
            },
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'email',
                'AttributeType': 'S'
            },
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        }
    )
    return 'Success'

def main():
    response = create_user_table()
    print(response)


if __name__ == "__main__":
    main()