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
