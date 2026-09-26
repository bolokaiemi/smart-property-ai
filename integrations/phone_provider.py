import logging

logger = logging.getLogger('smart_property_ai.integrations.phone')

class PhoneProvider:
    """Stub for phone/SMS provider.

    A real implementation could use Twilio, Vonage, or another telephony service.
    The stub simply logs the request.
    """

    def send_sms(self, phone_number: str, message: str) -> bool:
        """Send an SMS.

        Args:
            phone_number: Recipient phone number in international format.
            message: Text message content.

        Returns:
            ``True`` if the operation is considered successful.
        """
        logger.info(f"Sending SMS to {phone_number}: {message}")
        raise NotImplementedError("SMS sending not implemented in the stub provider")

    def make_call(self, phone_number: str, voice_message: str) -> bool:
        """Initiate a voice call that plays a message.

        Args:
            phone_number: Destination phone number.
            voice_message: Text to be spoken during the call.

        Returns:
            ``True`` if the call was successfully initiated.
        """
        logger.info(f"Initiating call to {phone_number} with message: {voice_message}")
        raise NotImplementedError("Voice call not implemented in the stub provider")
