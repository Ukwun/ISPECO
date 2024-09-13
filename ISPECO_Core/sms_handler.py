from http import client
import logging

from botocore.exceptions import HTTPClientError


logger = logging.getLogger(__name__)


class SnsWrapper:
    """Encapsulates Amazon SNS topic and subscription functions."""

    def __init__(self, client):
        """
        :param client: A Boto3 Amazon SNS resource.
        """
        self.client = client

    def publish_text_message(self, phone_number, message):
        """
        Publishes a text message directly to a phone number without need for a
        subscription.

        :param phone_number: The phone number that receives the message. This must be
                             in E.164 format. For example, a United States phone
                             number might be +12065550101.
        :param message: The message to send.
        :return: The ID of the message.
        """
        try:
            response = self.client.publish(PhoneNumber=phone_number, Message=message)
            message_id = response["MessageId"]
            logger.info("Published message to %s.", phone_number)
        except HTTPClientError:
            logger.exception("Couldn't publish message to %s.", phone_number)
            raise
        else:
            return message_id


if __name__ == "__main__":
    import os

    import boto3

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION", "af-south-1")

    client_obj = boto3.client(
        "sns",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    sns_wrapper = SnsWrapper(client_obj)

    response = sns_wrapper.publish_text_message(
        "+2348142549489", f"Testing the SMS service"
    )
    print(response)
