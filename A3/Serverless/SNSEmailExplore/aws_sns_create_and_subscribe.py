
import logging
import time
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

sns_client = boto3.client('sns')

def subscribe(topic, protocol, endpoint):
    """
    :param topic: The topic to subscribe to.
    :param protocol: The protocol of the endpoint, such as 'sms' or 'email'.
    :param endpoint: The endpoint that receives messages, such as a phone number
                     (in E.164 format) for SMS messages, or an email address for
                     email messages.
    :return: The newly added subscription.
    """
    try:
        subscription = sns_client.subscribe(
            TopicArn=topic, Protocol=protocol, Endpoint=endpoint, ReturnSubscriptionArn=True)
        logger.info("Subscribed %s %s to topic %s.", protocol, endpoint, topic)
    except ClientError:
        logger.exception(
            "Couldn't subscribe %s %s to topic %s.", protocol, endpoint, topic)
        raise
    else:
        return subscription

def create_topic(name):
    """
    Creates a notification topic.

    :param name: The name of the topic to create.
    :return: The newly created topic.
    """

    try:
        topic = sns_client.create_topic(Name=name)
        logger.info("Created topic %s with ARN %s.", name, topic['TopicArn'])

    except ClientError:
        logger.exception("Couldn't create topic %s.", name)
        raise
    else:
        return topic['TopicArn']

if __name__ == '__main__':

    topic_name = f'demo-101-topic-{time.time_ns()}'

    print(f"Creating topic {topic_name}.")
    # Create topic
    topicArn = create_topic(topic_name)

    # Create email subscription
    response = subscribe(topicArn, "email", "myemail@host")