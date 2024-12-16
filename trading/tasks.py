from celery import shared_task
from .ai_trading import train_model, make_trade_prediction, get_market_data
from .models import UserProfile, Trade, AccountBalance
from decimal import Decimal
from core.celery import notify_trade_update
import logging

logger = logging.getLogger('trading')

@shared_task
def execute_trade_task():
    """Execute trades for users with automated trading enabled"""
    try:
        # Only get users with automated trading enabled
        users = UserProfile.objects.filter(automated_trading_enabled=True)
        logger.info(f"Found {users.count()} users with automated trading enabled")
        
        for user in users:
            try:
                # Check if user has sufficient balance
                balance = AccountBalance.objects.get(user=user.user)
                if balance.balance_usd < user.trade_amount:
                    logger.warning(f"Insufficient balance for user {user.user.username}")
                    continue

                # Fetch market data
                market_data = get_market_data('AAPL')
                current_price = Decimal(str(market_data['Close'].iloc[-1]))
                
                # Check if price is within user's parameters
                if current_price < user.min_price or current_price > user.max_price:
                    logger.info(f"Price {current_price} outside range [{user.min_price}-{user.max_price}] for user {user.user.username}")
                    continue

                # Train model and get prediction
                model = train_model(market_data)
                trade_action = make_trade_prediction(model, market_data)
                
                # Execute trade based on prediction
                if trade_action in ['buy', 'sell']:
                    # Create trade record
                    new_trade = Trade.objects.create(
                        user_profile=user,
                        trade_type=trade_action,
                        amount=user.trade_amount,
                        entry_price=current_price,
                        status='active'
                    )
                    
                    # Update balance
                    if trade_action == 'buy':
                        balance.balance_usd -= user.trade_amount
                    else:  # sell
                        balance.balance_usd += user.trade_amount
                    
                    balance.save()
                    
                    # Send notification using core function
                    notify_trade_update(
                        f'{user.user.username} executed a {trade_action} trade of ${user.trade_amount}!'
                    )
                    
                    logger.info(f"Executed {trade_action} trade for user {user.user.username} amount: ${user.trade_amount}")

            except Exception as e:
                logger.error(f"Error executing trade for user {user.user.username}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in execute_trade_task: {str(e)}")
        raise

    return "Trade execution completed"