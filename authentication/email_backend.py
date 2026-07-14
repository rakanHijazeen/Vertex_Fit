import logging
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)

logger = logging.getLogger(__name__)

class BrevoAPIBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.client = Brevo(api_key=settings.BREVO_API_KEY)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                # Setup recipients
                recipients = [
                    SendTransacEmailRequestToItem(email=to_email)
                    for to_email in message.to
                ]
                
                # Setup sender
                sender = SendTransacEmailRequestSender(
                    name=settings.BREVO_SENDER_NAME,
                    email=settings.DEFAULT_FROM_EMAIL
                )

                # Determine body content
                html_content = ""
                text_content = ""
                
                if isinstance(message.body, str):
                    text_content = message.body
                    # Simple plaintext fallback to HTML conversion if no explicit HTML version
                    html_content = f"<html><body><p>{message.body.replace(chr(10), '<br>')}</p></body></html>"

                # Safely check if the message is an EmailMultiAlternatives instance
                if isinstance(message, EmailMultiAlternatives) and message.alternatives:
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            html_content = content

                # API Call to Brevo
                self.client.transactional_emails.send_transac_email(
                    subject=message.subject,
                    html_content=html_content,
                    text_content=text_content if text_content else None,
                    sender=sender,
                    to=recipients
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send email via Brevo API: {e}")
                if not self.fail_silently:
                    raise e
        return sent_count