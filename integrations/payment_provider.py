import logging

logger = logging.getLogger('smart_property_ai.integrations.payment')

class PaymentProvider:
    """Stub for a payment processing provider.

    In production this could wrap Stripe, PayPal, or another payment gateway. The stub
    simply logs the transaction details and raises ``NotImplementedError``.
    """

    def charge(self, amount_cents: int, currency: str, source_token: str, description: str = "") -> dict:
        """Create a charge.

        Args:
            amount_cents: Amount in the smallest currency unit (e.g., cents).
            currency: ISO currency code, e.g., ``"USD"``.
            source_token: Token representing the payment source (card, wallet, etc.).
            description: Optional description for the transaction.

        Returns:
            A dict with charge details. Stub returns an empty dict.
        """
        logger.info(
            f"Charging {amount_cents} {currency} (source: {source_token}) – {description}"
        )
        raise NotImplementedError("Payment processing not implemented in stub provider")

    def refund(self, charge_id: str, amount_cents: int | None = None) -> dict:
        """Refund a charge.

        Args:
            charge_id: Identifier of the original charge.
            amount_cents: Optional amount to refund; if ``None`` refunds full amount.

        Returns:
            A dict with refund details.
        """
        logger.info(f"Refunding charge {charge_id}, amount: {amount_cents or 'full'}")
        raise NotImplementedError("Refund not implemented in stub provider")
