import time
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from trading.models import UserProfile, Trade
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Runs the automated trading system'

    def handle(self, *args, **options):
        channel_layer = get_channel_layer()
        
        while True:
            # Get all users with automated trading enabled
            active_traders = UserProfile.objects.filter(automated_trading_enabled=True)
            
            for profile in active_traders:
                try:
                    # Simulate market analysis
                    self.analyze_and_trade(profile, channel_layer)
                except Exception as e:
                    self.send_update(channel_layer, profile.user.id, {
                        'type': 'error',
                        'message': f'Error in automated trading: {str(e)}'
                    })
            
            # Wait for next iteration
            time.sleep(60)  # Check every minute

    def analyze_and_trade(self, profile, channel_layer):
        # Simulate market analysis
        self.send_update(channel_layer, profile.user.id, {
            'type': 'analysis',
            'message': 'Analyzing market conditions...'
        })
        
        # Random decision for demo purposes
        should_trade = random.random() < 0.3  # 30% chance to trade
        
        if should_trade:
            # Calculate trade amount within user's limits
            amount = random.uniform(
                float(profile.min_trade_amount),
                float(profile.max_trade_amount)
            )
            amount = Decimal(str(round(amount, 2)))
            
            # Random action (buy/sell)
            action = random.choice(['BUY', 'SELL'])
            
            # Random asset
            asset = random.choice(['BTC', 'ETH', 'DOGE'])
            
            # Simulate profit/loss (-5% to +5%)
            profit_loss = amount * Decimal(str(random.uniform(-0.05, 0.05)))
            
            # Create trade record
            trade = Trade.objects.create(
                user=profile.user,
                asset=asset,
                amount=amount,
                action=action,
                status='COMPLETED',
                automated=True,
                profit_loss=profit_loss
            )
            
            # Send trade notification
            self.send_update(channel_layer, profile.user.id, {
                'type': 'trade',
                'message': f'Executed {action} trade for {amount} {asset}',
                'stats': self.get_today_stats(profile.user)
            })

    def get_today_stats(self, user):
        today = timezone.now().date()
        today_trades = Trade.objects.filter(
            user=user,
            timestamp__date=today,
            automated=True
        )
        
        return {
            'trades_count': today_trades.count(),
            'profit_loss': float(today_trades.aggregate(total=models.Sum('profit_loss'))['total'] or 0)
        }

    def send_update(self, channel_layer, user_id, message):
        async_to_sync(channel_layer.group_send)(
            f'auto_trading_group_{user_id}',
            {
                'type': 'trading_update',
                **message
            }
        )
