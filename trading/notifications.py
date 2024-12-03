from django.core.mail import send_mail

def send_trade_notification(user_email, trade_details):
    subject = "Trade Execution Notification"
    message = f"Your trade has been executed successfully:\n\n{trade_details}"
    send_mail(
        subject,
        message,
        'no-reply@tradingplatform.com',  # Replace with your email address
        [user_email],
        fail_silently=False,
    )
