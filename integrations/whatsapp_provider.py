import logging

logger = logging.getLogger('smart_property_ai.integrations.whatsapp')

class WhatsAppProvider:
    """Stub for a WhatsApp messaging provider.

    In a real implementation this could wrap Twilio's WhatsApp API or another service.
    The current method simply logs the message payload.
    """

    def send_message(self, phone_number: str, message: str) -> bool:
        """Send a WhatsApp message.

        Args:
            phone_number: Recipient's phone number in international format.
            message: The text to send.

        Returns:
            ``True`` if the operation is considered successful.
        """
        logger.info(f"Sending WhatsApp message to {phone_number}: {message}")
        raise NotImplementedError("WhatsApp sending not implemented in the stub provider")
