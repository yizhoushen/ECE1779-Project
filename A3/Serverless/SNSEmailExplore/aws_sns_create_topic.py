import logging
import time
import boto3
from botocore.exceptions import ClientError

# aws_sns_create_topic

logger = logging.getLogger(__name__)

def create_topic(name):
    """
    Creates a notification topic.

    :param name: The name of the topic to create.
    :return: The newly created topic.
    """
    sns_client = boto3.client('sns', verify=False)

    try:
        topic = sns_client.create_topic(Name=name)
        logger.info("Created topic %s with ARN %s.", name, topic['TopicArn'])

    except ClientError:
        logger.exception("Couldn't create topic %s.", name)
        raise
    else:
        return topic

if __name__ == '__main__':

    topic_name = f'demo-101-topic-{time.time_ns()}'

    print(f"Creating topic {topic_name}.")
    topic = create_topic(topic_name)