import logging
import threading
import time
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Optional

from django.utils import timezone
from alpaca_trade_api.rest import TimeFrame

from .models import Trade, AccountBalance, UserProfile
from .alpaca_client import AlpacaClient
from .ai_trading import make_trade_prediction, train_model

logger = logging.getLogger(__name__)

class AutomatedTrading:
    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile
        self.is_running = False
        self.trading_thread = None
        self.alpaca = AlpacaClient()
        self.model = None  # Will store trained model
        self.max_position_size = Decimal('1000.00')  # Maximum position size in USD
        self.risk_per_trade = Decimal('0.01')  # 1% risk per trade
        self.stop_loss_percent = Decimal('0.02')  # 2% stop loss
        self.take_profit_percent = Decimal('0.04')  # 4% take profit

    def start(self):
        """Start automated trading"""
        if self.is_running:
            return False

        # Get initial data and train model
        try:
            # Get historical data for training
            training_data = self.alpaca.get_bars(
                'SPY',  # Use SPY (S&P 500 ETF) for training
                TimeFrame.Hour,
                limit=1000  # Get more historical data for training
            )
            
            # Train the model
            self.model = train_model(training_data)
            logger.info("Successfully trained trading model")
            
            self.is_running = True
            self.trading_thread = threading.Thread(target=self._trading_loop)
            self.trading_thread.daemon = True
            self.trading_thread.start()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start automated trading: {str(e)}")
            return False

    def stop(self):
        """Stop automated trading"""
        self.is_running = False
        try:
            # Cancel all pending orders
            self.alpaca.cancel_all_orders()
            # Close all positions
            self.alpaca.close_all_positions()
        except Exception as e:
            logger.error(f"Error stopping trading: {str(e)}")

    async def _check_account_status(self) -> bool:
        """Check if account is ready for trading"""
        try:
            account = await self.alpaca.get_account()
            
            # Check if account has sufficient balance
            if Decimal(account['cash']) < Decimal('20.00'):
                logger.warning(f"Insufficient balance for trading: ${account['cash']}")
                return False

            # Check if account is restricted
            if account['trading_blocked'] or account['trades_blocked']:
                logger.warning("Account is restricted from trading")
                return False

            # Check day trade count (Pattern Day Trading rule)
            if int(account['day_trade_count']) >= 3 and Decimal(account['portfolio_value']) < Decimal('25000.00'):
                logger.warning("Day trade limit reached for account under $25,000")
                return False

            return True
        except Exception as e:
            logger.error(f"Error checking account status: {str(e)}")
            return False

    async def _execute_trade(self, symbol: str, prediction: Dict) -> Optional[Dict]:
        """Execute a trade based on prediction"""
        try:
            # Get current position
            position = await self.alpaca.get_position(symbol)
            
            # Get account info for position sizing
            account = await self.alpaca.get_account()
            portfolio_value = Decimal(account['portfolio_value'])
            
            # Calculate position size (1% risk per trade)
            position_size = min(
                portfolio_value * self.risk_per_trade,
                self.max_position_size
            )
            
            # Get current price
            bars = await self.alpaca.get_bars(symbol, TimeFrame.Minute, limit=1)
            current_price = bars[-1]['close']
            
            # Calculate quantity
            qty = int(position_size / current_price)
            if qty < 1:
                logger.warning(f"Position size too small for {symbol}")
                return None
            
            # Calculate stop loss and take profit prices
            stop_loss = None
            take_profit = None
            
            if prediction['action'] == 'buy':
                stop_loss = current_price * (1 - self.stop_loss_percent)
                take_profit = current_price * (1 + self.take_profit_percent)
            else:  # sell
                stop_loss = current_price * (1 + self.stop_loss_percent)
                take_profit = current_price * (1 - self.take_profit_percent)
            
            # Place the order
            order = await self.alpaca.place_order(
                symbol=symbol,
                qty=qty,
                side=prediction['action'],
                type='limit',
                limit_price=float(current_price),
                stop_price=float(stop_loss)
            )
            
            # Record the trade
            trade = Trade.objects.create(
                user=self.user_profile,
                symbol=symbol,
                trade_type=prediction['action'].upper(),
                amount=position_size,
                price=current_price,
                quantity=qty,
                status='EXECUTED',
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            # Update account balance
            account_balance = AccountBalance.objects.get(user=self.user_profile)
            account_balance.balance_usd = Decimal(account['cash'])
            account_balance.save()
            
            return {
                'trade_id': trade.id,
                'order_id': order['id'],
                'symbol': symbol,
                'action': prediction['action'],
                'quantity': qty,
                'price': current_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            return None

    def _trading_loop(self):
        """Main trading loop"""
        while self.is_running:
            try:
                # Check if market is open
                clock = self.alpaca.api.get_clock()
                if not clock.is_open:
                    logger.info("Market is closed")
                    time.sleep(60)
                    continue

                # Check account status
                if not self._check_account_status():
                    logger.warning("Account not ready for trading")
                    time.sleep(60)
                    continue

                # Get tradeable assets
                assets = self.alpaca.api.list_assets(status='active', asset_class='us_equity')
                tradeable_symbols = [asset.symbol for asset in assets if asset.tradable]

                # Analyze each asset
                for symbol in tradeable_symbols[:10]:  # Limit to top 10 for now
                    # Get historical data
                    bars = self.alpaca.get_bars(
                        symbol,
                        TimeFrame.Hour,
                        limit=100
                    )
                    
                    # Make prediction using trained model
                    if self.model is not None:
                        prediction = make_trade_prediction(self.model, bars)
                        
                        if prediction['confidence'] >= 0.7:  # Only trade with high confidence
                            trade_result = self._execute_trade(symbol, prediction)
                            if trade_result:
                                logger.info(f"Executed trade: {trade_result}")
                    else:
                        logger.warning("No trained model available")

                # Sleep for a minute before next iteration
                time.sleep(60)

            except Exception as e:
                logger.error(f"Error in trading loop: {str(e)}")
                time.sleep(60)

    def get_status(self) -> Dict:
        """Get current trading status"""
        try:
            account = self.alpaca.api.get_account()
            positions = self.alpaca.api.list_positions()
            
            # Get today's trades
            today = timezone.now().date()
            trades_today = Trade.objects.filter(
                user=self.user_profile,
                created_at__date=today
            ).count()
            
            # Calculate today's profit/loss
            total_pl = sum(Decimal(pos.unrealized_pl) for pos in positions)
            
            return {
                'is_trading': self.is_running,
                'account_value': Decimal(account.portfolio_value),
                'buying_power': Decimal(account.buying_power),
                'cash': Decimal(account.cash),
                'trades_today': trades_today,
                'total_positions': len(positions),
                'unrealized_pl': total_pl,
                'last_updated': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting trading status: {str(e)}")
            return {
                'is_trading': self.is_running,
                'error': str(e)
            }
