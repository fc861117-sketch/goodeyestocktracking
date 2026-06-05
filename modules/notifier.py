import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

def send_email_notification(config, subject, body):
    """
    Sends an email notification using SMTP.
    Requires email_config in config.json:
    "email_config": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "your_email@gmail.com",
        "sender_password": "your_app_password",
        "recipient_email": "recipient@gmail.com"
    }
    """
    email_cfg = config.get('email_config')
    if not email_cfg:
        logger.warning("Email configuration missing. Skipping email notification.")
        return False
        
    sender = email_cfg.get('sender_email')
    password = email_cfg.get('sender_password')
    recipient = email_cfg.get('recipient_email')
    smtp_server = email_cfg.get('smtp_server', 'smtp.gmail.com')
    smtp_port = email_cfg.get('smtp_port', 587)
    
    if not sender or not password or not recipient or sender == "your_email@gmail.com":
        logger.warning("Email configuration incomplete. Skipping email notification.")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html', 'utf-8'))

    try:
        logger.info("Sending email notification to %s...", recipient)
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        logger.info("✅ Email notification sent successfully.")
        return True
    except Exception as e:
        logger.error("❌ Failed to send email: %s", e)
        return False
