"""
Production-Ready Email Service
Real email sending implementation with multiple providers and templates
"""

import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any
from pathlib import Path
import jinja2
from datetime import datetime

# Third-party email services
try:
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

from config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Production-ready email service with multiple provider support"""

    def __init__(self):
        # Use string templates instead of file-based templates to avoid dependency issues
        self.template_env = jinja2.Environment(
            loader=jinja2.DictLoader(self._get_built_in_templates()),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )

        # Initialize providers based on availability and configuration
        self.providers = self._initialize_providers()
        self.primary_provider = self._get_primary_provider()

    def _get_built_in_templates(self) -> Dict[str, str]:
        """Get built-in email templates to avoid file dependency issues"""
        return {
            # Basic notification template
            'notification.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>{{ title }}</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #333;">{{ title }}</h2>
                <p>Hi {{ user_name }},</p>
                <p>{{ message }}</p>
                {% if action_url %}
                <p><a href="{{ action_url }}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">{{ action_text or 'Take Action' }}</a></p>
                {% endif %}
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            ''',

            'notification.txt': '''
            {{ title }}

            Hi {{ user_name }},

            {{ message }}

            {% if action_url %}{{ action_text or 'Take Action' }}: {{ action_url }}{% endif %}

            Best regards,
            MyTypist Team
            ''',

            # Welcome email template
            'welcome.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Welcome to MyTypist!</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #007bff;">Welcome to MyTypist!</h2>
                <p>Hi {{ user_name }},</p>
                <p>Welcome to MyTypist! We're excited to have you on board.</p>
                <p>You can now create professional documents with ease using our platform.</p>
                <p><a href="{{ dashboard_url }}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Dashboard</a></p>
                <p>If you have any questions, feel free to reach out to our support team.</p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            ''',

            # Password reset template
            'password_reset.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Reset Your Password</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #dc3545;">Reset Your Password</h2>
                <p>Hi {{ user_name }},</p>
                <p>We received a request to reset your password. Click the button below to reset it:</p>
                <p><a href="{{ reset_url }}" style="background: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                <p>This link will expire in {{ expires_in }}.</p>
                <p>If you didn't request this, please ignore this email.</p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            ''',

            # Document ready template
            'document_ready.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Your Document is Ready!</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #28a745;">Your Document is Ready!</h2>
                <p>Hi {{ user_name }},</p>
                <p>Great news! Your document "{{ document_title }}" has been processed and is ready for download.</p>
                <p><a href="{{ download_url }}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Download Document</a></p>
                <p>You can also access it from your <a href="{{ dashboard_url }}">dashboard</a>.</p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            ''',

            # Payment confirmation template
            'payment_confirmation.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Payment Confirmation</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #28a745;">Payment Confirmed!</h2>
                <p>Hi {{ user_name }},</p>
                <p>Thank you for your payment! Here are the details:</p>
                <ul>
                    <li><strong>Amount:</strong> {{ amount }} {{ currency }}</li>
                    <li><strong>Transaction ID:</strong> {{ transaction_id }}</li>
                    <li><strong>Tokens Purchased:</strong> {{ tokens_purchased }}</li>
                </ul>
                <p>Your tokens have been added to your account and you can start creating documents immediately.</p>
                <p><a href="{{ dashboard_url }}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Dashboard</a></p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            ''',

            # Subscription renewal template
            'subscription_renewal.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Subscription Renewed</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #007bff;">Subscription Renewed</h2>
                <p>Hi {{ user_name }},</p>
                <p>Your {{ plan_name }} subscription has been successfully renewed!</p>
                <ul>
                    <li><strong>Renewal Date:</strong> {{ renewal_date }}</li>
                    <li><strong>Amount:</strong> {{ amount }} NGN</li>
                </ul>
                <p>Your subscription benefits will continue uninterrupted.</p>
                <p><a href="{{ manage_subscription_url }}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Manage Subscription</a></p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            ''',

            # Signature request template
            'signature_request.html': '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Document Signature Request</title>
            </head>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ffc107;">Signature Request</h2>
                <p>Hi {{ signer_name }},</p>
                <p>You have been requested to sign the document: <strong>{{ document_title }}</strong></p>
                <p>Please click the button below to review and sign the document:</p>
                <p><a href="{{ signature_url }}" style="background: #ffc107; color: black; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Sign Document</a></p>
                <p>This request expires on {{ expires_at }}.</p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            '''
        }

    def _initialize_providers(self) -> Dict[str, Any]:
        """Initialize available email providers"""
        providers = {}

        # SendGrid
        if SENDGRID_AVAILABLE and hasattr(settings, 'SENDGRID_API_KEY'):
            providers['sendgrid'] = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            logger.info("SendGrid email provider initialized")

        # Resend
        if RESEND_AVAILABLE and hasattr(settings, 'RESEND_API_KEY'):
            resend.api_key = settings.RESEND_API_KEY
            providers['resend'] = resend
            logger.info("Resend email provider initialized")

        # SMTP Fallback
        if hasattr(settings, 'SMTP_HOST'):
            providers['smtp'] = {
                'host': settings.SMTP_HOST,
                'port': getattr(settings, 'SMTP_PORT', 587),
                'username': getattr(settings, 'SMTP_USERNAME', ''),
                'password': getattr(settings, 'SMTP_PASSWORD', ''),
                'use_tls': getattr(settings, 'SMTP_USE_TLS', True)
            }
            logger.info("SMTP email provider initialized")

        return providers

    def _get_primary_provider(self) -> str:
        """Get primary email provider based on priority"""
        priority = ['sendgrid', 'resend', 'smtp']

        for provider in priority:
            if provider in self.providers:
                logger.info(f"Using {provider} as primary email provider")
                return provider

        logger.warning("No email providers available")
        return None

    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        template_data: Dict[str, Any],
        from_email: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        priority: str = 'normal'
    ) -> Dict[str, Any]:
        """Send email using the best available provider"""

        try:
            # Prepare email content
            email_content = await self._prepare_email_content(
                template_name, template_data
            )

            # Set from email
            from_email = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mytypist.com')

            # Try primary provider first
            if self.primary_provider:
                result = await self._send_via_provider(
                    provider=self.primary_provider,
                    to_email=to_email,
                    from_email=from_email,
                    subject=subject,
                    html_content=email_content['html'],
                    text_content=email_content['text'],
                    attachments=attachments,
                    priority=priority
                )

                if result['success']:
                    return result

                logger.warning(f"Primary provider {self.primary_provider} failed, trying fallbacks")

            # Try fallback providers
            for provider_name in self.providers:
                if provider_name != self.primary_provider:
                    result = await self._send_via_provider(
                        provider=provider_name,
                        to_email=to_email,
                        from_email=from_email,
                        subject=subject,
                        html_content=email_content['html'],
                        text_content=email_content['text'],
                        attachments=attachments,
                        priority=priority
                    )

                    if result['success']:
                        logger.info(f"Email sent successfully via fallback provider: {provider_name}")
                        return result

            # If all providers failed, log the email instead of failing completely
            logger.warning(f"All email providers failed. Email details: To: {to_email}, Subject: {subject}")

            return {
                'success': False,
                'error': 'All email providers failed - email logged for manual processing',
                'provider_used': None,
                'fallback_logged': True
            }

        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'provider_used': None
            }

    async def _prepare_email_content(
        self,
        template_name: str,
        template_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Prepare email content from templates"""

        try:
            # Load HTML template
            html_template = self.template_env.get_template(f"{template_name}.html")
            html_content = html_template.render(**template_data)

            # Load text template (fallback to HTML if not available)
            try:
                text_template = self.template_env.get_template(f"{template_name}.txt")
                text_content = text_template.render(**template_data)
            except jinja2.TemplateNotFound:
                # Convert HTML to basic text
                import re
                text_content = re.sub(r'<[^>]+>', '', html_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()

            return {
                'html': html_content,
                'text': text_content
            }

        except jinja2.TemplateNotFound:
            # Fallback to basic template using provided data
            message = template_data.get('message', template_data.get('title', 'No content'))
            user_name = template_data.get('user_name', 'User')

            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2>MyTypist Notification</h2>
                <p>Hi {user_name},</p>
                <p>{message}</p>
                <p>Best regards,<br>MyTypist Team</p>
            </body>
            </html>
            """

            text_content = f"""
            MyTypist Notification

            Hi {user_name},

            {message}

            Best regards,
            MyTypist Team
            """

            return {
                'html': html_content,
                'text': text_content
            }

    async def _send_via_provider(
        self,
        provider: str,
        to_email: str,
        from_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        priority: str = 'normal'
    ) -> Dict[str, Any]:
        """Send email via specific provider"""

        try:
            if provider == 'sendgrid':
                return await self._send_via_sendgrid(
                    to_email, from_email, subject, html_content, text_content, attachments
                )
            elif provider == 'resend':
                return await self._send_via_resend(
                    to_email, from_email, subject, html_content, attachments
                )
            elif provider == 'smtp':
                return await self._send_via_smtp(
                    to_email, from_email, subject, html_content, text_content, attachments
                )
            else:
                return {'success': False, 'error': f'Unknown provider: {provider}'}

        except Exception as e:
            logger.error(f"Provider {provider} failed: {e}")
            return {'success': False, 'error': str(e)}

    async def _send_via_sendgrid(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send email via SendGrid"""

        try:
            message = Mail(
                from_email=Email(from_email),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content),
                plain_text_content=Content("text/plain", text_content)
            )

            # Add attachments
            if attachments:
                for attachment in attachments:
                    file_attachment = Attachment(
                        FileContent(attachment['content']),
                        FileName(attachment['filename']),
                        FileType(attachment.get('type', 'application/octet-stream')),
                        Disposition('attachment')
                    )
                    message.attachment = file_attachment

            sg = self.providers['sendgrid']
            response = sg.send(message)

            return {
                'success': response.status_code in [200, 202],
                'provider_used': 'sendgrid',
                'response_code': response.status_code,
                'message_id': response.headers.get('X-Message-Id')
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _send_via_resend(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        html_content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send email via Resend"""

        try:
            email_data = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }

            # Add attachments
            if attachments:
                email_data["attachments"] = [
                    {
                        "filename": att['filename'],
                        "content": att['content']
                    }
                    for att in attachments
                ]

            response = resend.Emails.send(email_data)

            return {
                'success': True,
                'provider_used': 'resend',
                'message_id': response.get('id')
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _send_via_smtp(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send email via SMTP"""

        try:
            smtp_config = self.providers['smtp']

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email

            # Add text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')

            msg.attach(text_part)
            msg.attach(html_part)

            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)

            # Send email
            with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
                if smtp_config['use_tls']:
                    server.starttls()

                if smtp_config['username']:
                    server.login(smtp_config['username'], smtp_config['password'])

                server.send_message(msg)

            return {
                'success': True,
                'provider_used': 'smtp'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def send_welcome_email(self, user_email: str, user_name: str) -> Dict[str, Any]:
        """Send welcome email to new user"""
        return await self.send_email(
            to_email=user_email,
            subject="Welcome to MyTypist!",
            template_name="welcome",
            template_data={
                'user_name': user_name,
                'login_url': f"{settings.FRONTEND_URL}/login",
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard"
            }
        )

    async def send_password_reset_email(
        self,
        user_email: str,
        user_name: str,
        reset_token: str
    ) -> Dict[str, Any]:
        """Send password reset email"""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        return await self.send_email(
            to_email=user_email,
            subject="Reset Your MyTypist Password",
            template_name="password_reset",
            template_data={
                'user_name': user_name,
                'reset_url': reset_url,
                'expires_in': "24 hours"
            }
        )

    async def send_document_ready_email(
        self,
        user_email: str,
        user_name: str,
        document_title: str,
        download_url: str
    ) -> Dict[str, Any]:
        """Send document ready notification"""
        return await self.send_email(
            to_email=user_email,
            subject=f"Your document '{document_title}' is ready!",
            template_name="document_ready",
            template_data={
                'user_name': user_name,
                'document_title': document_title,
                'download_url': download_url,
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard"
            }
        )

    async def send_payment_confirmation_email(
        self,
        user_email: str,
        user_name: str,
        amount: float,
        currency: str,
        transaction_id: str,
        tokens_purchased: int
    ) -> Dict[str, Any]:
        """Send payment confirmation email"""
        return await self.send_email(
            to_email=user_email,
            subject="Payment Confirmation - MyTypist",
            template_name="payment_confirmation",
            template_data={
                'user_name': user_name,
                'amount': amount,
                'currency': currency,
                'transaction_id': transaction_id,
                'tokens_purchased': tokens_purchased,
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard"
            }
        )

    async def send_subscription_renewal_email(
        self,
        user_email: str,
        user_name: str,
        plan_name: str,
        renewal_date: datetime,
        amount: float
    ) -> Dict[str, Any]:
        """Send subscription renewal notification"""
        return await self.send_email(
            to_email=user_email,
            subject="Subscription Renewed - MyTypist",
            template_name="subscription_renewal",
            template_data={
                'user_name': user_name,
                'plan_name': plan_name,
                'renewal_date': renewal_date.strftime('%B %d, %Y'),
                'amount': amount,
                'manage_subscription_url': f"{settings.FRONTEND_URL}/subscription"
            }
        )


# Global email service instance
email_service = EmailService()