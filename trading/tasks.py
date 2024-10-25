from celery import shared_task
from .ai_trading import train_model, make_trade_prediction, get_market_data
from .models import UserProfile, Trade, AccountBalance

@shared_task
def execute_trade_task():
    # Example: Execute trades for all users (you can adjust based on your needs)
    users = UserProfile.objects.all()
    
    for user in users:
        # Fetch market data for a specific asset
        market_data = get_market_data('AAPL')

        # Train the AI model and make a trade prediction
        model = train_model(market_data)
        trade_action = make_trade_prediction(model, market_data)

        # Execute the trade based on the AI prediction
        if trade_action == 'buy':
            amount = 100  # Example trade amount
            new_trade = Trade(user=user, asset='AAPL', trade_type='buy', amount=amount, profit_or_loss=0.0)
            new_trade.save()

            # Deduct from balance
            balance = AccountBalance.objects.get(user=user)
            balance.balance_usd -= amount
            balance.save()

        elif trade_action == 'sell':
            new_trade = Trade(user=user, asset='AAPL', trade_type='sell', amount=0, profit_or_loss=10.0)
            new_trade.save()

            # Add to balance
            balance = AccountBalance.objects.get(user=user)
            balance.balance_usd += 10.0
            balance.save()

    return "Trade execution completed"


# Helper function to send WebSocket notifications
def send_trade_notification(username, trade_action, amount):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        'trade_notifications',  # Group name
        {
            'type': 'trade_update',  # Custom event name
            'message': f'{username} executed a {trade_action} trade of ${amount}!'
        }
    )