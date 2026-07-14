from django.core.signing import TimestampSigner, BadSignature, SignatureExpired # <-- Use TimestampSigner
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.conf import settings
from authentication.email_backend import BrevoAPIBackend

# Active for 24 Hours (86400 seconds)
TOKEN_MAX_AGE = 86400 
signer = TimestampSigner() # <-- Instantiate TimestampSigner

def send_verification_email(user, request):
    # Encrypt user primary key (converted to string for reliable signing)
    token = signer.sign(str(user.pk))
    
    # Construct complete callback URI
    verify_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'token': token})
    )
    
    context = {
        'user': user,
        'verify_url': verify_url,
    }
    
    # Render rich HTML email template
    html_content = render_to_string('authentication/emails/verification_email.html', context)
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject="Action Required: Verify your Vertex Fit Account",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        connection=BrevoAPIBackend()
    )
    email.attach_alternative(html_content, "text/html")
    email.send()