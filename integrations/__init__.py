'''integrations package

Provides a set of provider abstractions for external services used by the Smart Property AI
application. Each provider implements a minimal interface that can be extended with real
integrations (e.g., SMTP for email, Twilio for WhatsApp, Stripe for payments, etc.).
The implementations here are deliberately lightweight – they log actions and raise
`NotImplementedError` for the actual external calls. This keeps the project runnable
without requiring credentials or third‑party SDKs while still giving a clear contract
for future development.
'''
