import logging
import time
import boto3
from botocore.exceptions import ClientError

# aws_sns_list_topics

logger = logging.getLogger(__name__)


def list_topics():
    """
    Lists topics for the current account.

    :return: An iterator that yields the topics.
    """
    sns_client = boto3.client('sns')

    try:
        topics_iter = sns_client.list_topics()
        logger.info("Got topics.")
    except ClientError:
        logger.exception("Couldn't get topics.")
        raise
    else:
        return topics_iter

if __name__ == '__main__':

    topics = list_topics()

    for arn in topics['Topics']:
        print(arn['TopicArn'])