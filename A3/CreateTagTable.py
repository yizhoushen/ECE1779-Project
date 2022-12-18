import boto3
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
def create_tag_table():
    table = dynamodb.create_table(
        TableName='Tags',
        KeySchema=[
            {
                'AttributeName': 'tag',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'user_img',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'tag',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'user_img',
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
    response = create_tag_table()
    print(response)


if __name__ == "__main__":
    main()