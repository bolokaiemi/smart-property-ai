import logging

logger = logging.getLogger('smart_property_ai.integrations.email')

class EmailProvider:
    """Simple email provider interface.

    The concrete implementation would integrate with an SMTP server or a transactional
    email service (e.g., SendGrid, Mailgun). For now we only log the payload.
    """

    def send_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send an email.

        Args:
            recipient: Destination email address.
            subject: Subject line of the email.
            body: Plain‑text or HTML body.

        Returns:
            ``True`` if the send operation appears successful.
        """
        logger.info(f"Sending email to {recipient} – subject: {subject}")
        # Placeholder – replace with real email service call.
        raise NotImplementedError("Email sending not implemented in the stub provider")
