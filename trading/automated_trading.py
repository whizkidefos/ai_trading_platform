from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import AccountBalance, Trade, TransactionHistory
from .ai_trading import get_market_data, apply_combined_strategy
import asyncio
import logging

logger = logging.getLogger('automated_trading')

class AutomatedTrading:
    def __init__(self, user_profile):
        self.user_profile = user_profile
        self.is_trading = False
        self.channel_layer = get_channel_layer()

    async def start_trading(self):
        self.is_trading = True
        while self.is_trading:
            try:
                # Check account balance
                balance = AccountBalance.objects.get(user=self.user_profile)
                if balance.balance_usd >= 10:  # Minimum trading amount
                    # Get market data and make trading decision
                    market_data = get_market_data()
                    for asset, data in market_data.items():
                        signals = apply_combined_strategy(data)
                        if signals['signal'][-1] == 1:  # Buy signal
                            await self.execute_trade(asset, 'buy', min(balance.balance_usd * 0.1, 100))
                        elif signals['signal'][-1] == -1:  # Sell signal
                            await self.execute_trade(asset, 'sell', min(balance.balance_usd * 0.1, 100))
                
                # Send update to websocket
                await self.send_update()
                
                # Wait for 5 minutes before next check
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in automated trading: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def stop_trading(self):
        self.is_trading = False

    async def execute_trade(self, asset, trade_type, amount):
        try:
            # Execute trade logic here
            trade = Trade.objects.create(
                user=self.user_profile,
                asset=asset,
                trade_type=trade_type,
                amount=amount
            )
            
            # Update account balance
            balance = AccountBalance.objects.get(user=self.user_profile)
            if trade_type == 'buy':
                balance.balance_usd -= amount
            else:
                balance.balance_usd += amount
            balance.save()

            # Record transaction
            TransactionHistory.objects.create(
                user=self.user_profile,
                transaction_type=f"AUTO_{trade_type.upper()}",
                amount=amount,
                status='completed'
            )

            # Send notification
            await self.send_notification(f"Automated {trade_type} trade executed for {asset}: ${amount}")

        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            await self.send_notification(f"Error executing trade: {str(e)}")

    async def send_notification(self, message):
        await self.channel_layer.group_send(
            f"user_{self.user_profile.user.id}",
            {
                "type": "trade_notification",
                "message": message
            }
        )

    async def send_update(self):
        balance = AccountBalance.objects.get(user=self.user_profile)
        await self.channel_layer.group_send(
            f"user_{self.user_profile.user.id}",
            {
                "type": "balance_update",
                "balance": float(balance.balance_usd)
            }
        )
