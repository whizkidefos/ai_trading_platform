import stripe
from django.conf import settings
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY

def process_stripe_payment(amount, currency='usd', payment_method_id=None):
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            payment_method=payment_method_id,
            confirm=True,
            return_url="http://localhost:8000/payment/success"
        )
        return {'status': 'success', 'client_secret': intent.client_secret}
    except stripe.error.StripeError as e:
        return {'status': 'error', 'message': str(e)}

def process_withdrawal(user_profile, amount):
    if user_profile.balance < Decimal(amount):
        return {'status': 'error', 'message': 'Insufficient funds'}
    
    try:
        # Here you would implement the actual withdrawal logic
        # This could involve Stripe Connect, bank transfers, etc.
        user_profile.balance -= Decimal(amount)
        user_profile.save()
        
        # Record the withdrawal transaction
        from .models import Transaction
        Transaction.objects.create(
            user=user_profile.user,
            transaction_type='withdrawal',
            amount=amount,
            status='completed'
        )
        
        return {'status': 'success', 'message': 'Withdrawal processed successfully'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
