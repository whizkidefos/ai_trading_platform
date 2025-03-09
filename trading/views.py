from django.shortcuts import render, redirect, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Sum, Q, Count, Max, Min, Avg
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import login
from decimal import Decimal
import json
import logging
import requests
from django.contrib.admin.views.decorators import staff_member_required
from paypal.standard.forms import PayPalPaymentsForm
from paypal.standard.ipn.signals import valid_ipn_received
from paypal.standard.models import ST_PP_COMPLETED
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import (
    AccountBalance,
    Trade,
    TransactionHistory,
    UserProfile,
    Transaction,
    KYCVerification,
    WithdrawalRequest,
    Deposit,
    TradingAccount
)
from .forms import UserRegistrationForm, UserForm, UserProfileForm

logger = logging.getLogger(__name__)

def fetch_finance_news():
    url = 'https://newsapi.org/v2/top-headlines'
    params = {
        'category': 'business',
        'apiKey': settings.NEWS_API_KEY,
        'language': 'en',
    }
    response = requests.get(url, params=params)
    return response.json().get('articles', [])[:5]


def fetch_crypto_prices():
    url = 'https://api.coingecko.com/api/v3/simple/price'
    params = {
        'ids': 'bitcoin, ethereum, litecoin, dogecoin, cardano',
        'vs_currencies': 'usd',
    }
    response = requests.get(url, params=params)
    return response.json()


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to our trading platform.')
            return redirect('trading:user_dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


# Admin dashboard view
@staff_member_required
def admin_dashboard(request):
    user_profile = request.user.userprofile
    account_balance = AccountBalance.objects.get(user=user_profile).balance_usd
    total_trades = Trade.objects.filter(user=user_profile).count()
    total_transactions = TransactionHistory.objects.filter(user=user_profile).count()
    recent_trades = Trade.objects.filter(user=user_profile).order_by('-trade_time')[:10]
    
    news_articles = fetch_finance_news()
    
    stock_labels = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
    stock_data = [150, 200, 180, 220]  # Example data

    market_labels = ['Tech', 'Finance', 'Energy', 'Healthcare']
    market_data = [3000, 1500, 2000, 1200]  # Example data

    context = {
        'account_balance': account_balance,
        'total_trades': total_trades,
        'total_transactions': total_transactions,
        'recent_trades': recent_trades,
        
        'news_articles': news_articles,
        
        'stock_labels': stock_labels,
        'stock_data': stock_data,
        'market_labels': market_labels,
        'market_data': market_data,
    }
    
    return render(request, 'admin_dashboard.html', context)


# Admin transactions view
@staff_member_required
def admin_transactions(request):
    transactions = TransactionHistory.objects.all().order_by('-transaction_time')
    return render(request, 'admin_transactions.html', {'transactions': transactions})


# Redirect to the dashboard when accessing the root URL
def home(request):
    """Landing page view with market metrics."""
    try:
        # Get market data
        btc_price = get_market_data('BTC/USD')
        eth_price = get_market_data('ETH/USD')
        
        # Get platform statistics
        total_users = User.objects.count()
        total_trades = Trade.objects.count()
        success_trades = Trade.objects.filter(profit__gt=0).count()
        success_rate = (success_trades / total_trades * 100) if total_trades > 0 else 0
        
        context = {
            'market_data': {
                'btc_price': btc_price,
                'eth_price': eth_price,
            },
            'platform_stats': {
                'total_users': total_users,
                'total_trades': total_trades,
                'success_rate': round(success_rate, 1),
            }
        }
        
        return render(request, 'trading/home.html', context)
    except Exception as e:
        logger.error(f"Error in home view: {str(e)}")
        return render(request, 'trading/home.html')


@login_required
def user_dashboard(request):
    try:
        # Get or create user profile
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Get or create account balance (this maintains the original balance)
        account_balance, created = AccountBalance.objects.get_or_create(
            user=user_profile,
            defaults={'balance_usd': user_profile.balance}  # Use profile balance as default
        )
        
        # Get or create trading account
        trading_account, created = TradingAccount.objects.get_or_create(
            user=request.user,
            defaults={'balance': account_balance.balance_usd}  # Sync with account balance
        )
        
        # Ensure balances are synced
        if account_balance.balance_usd != trading_account.balance:
            trading_account.balance = account_balance.balance_usd
            trading_account.save()
        
        # Get all trades first
        trades_queryset = Trade.objects.filter(user_profile=user_profile)
        
        # Calculate trading statistics from full queryset
        total_trades = trades_queryset.count()
        successful_trades = trades_queryset.filter(profit__gt=0).count()
        win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
        total_profit = trades_queryset.aggregate(Sum('profit'))['profit__sum'] or 0
        
        # Get recent trades for display
        recent_trades = trades_queryset.order_by('-timestamp')[:10]
        
        # Get recent transactions
        transactions = TransactionHistory.objects.filter(user=user_profile).order_by('-timestamp')[:5]
        
        context = {
            'user': request.user,
            'user_profile': user_profile,
            'account_balance': account_balance.balance_usd,
            'trading_account': trading_account,
            'trades': recent_trades,
            'total_trades': total_trades,
            'win_rate': round(win_rate, 2),
            'total_profit': total_profit,
            'transactions': transactions,
            'paypal_client_id': settings.PAYPAL_CLIENT_ID,
            'paypal_receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
        }
        
        return render(request, 'trading/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return redirect('trading:home')


@login_required
def start_automated_trading(request):
    """Start automated trading for the user"""
    try:
        user_profile = request.user.userprofile
        
        # Check if user has sufficient balance
        account_balance = AccountBalance.objects.get(user=user_profile)
        if account_balance.balance_usd < 20:  # Minimum balance requirement
            return JsonResponse({
                'status': 'error',
                'message': 'Insufficient balance. Minimum $20 required to start automated trading.'
            }, status=400)

        # Set trading status to active
        user_profile.automated_trading_enabled = True
        user_profile.save()

        # Start the automated trading task
        automated_trading = AutomatedTrading(user_profile)
        automated_trading.start()

        return JsonResponse({
            'status': 'success',
            'message': 'Automated trading started successfully'
        })
    except Exception as e:
        logger.error(f"Error starting automated trading: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to start automated trading'
        }, status=500)


@login_required
def stop_automated_trading(request):
    """Stop automated trading for the user"""
    try:
        user_profile = request.user.userprofile
        
        # Set trading status to inactive
        user_profile.automated_trading_enabled = False
        user_profile.save()

        # Stop the automated trading task
        automated_trading = AutomatedTrading(user_profile)
        automated_trading.stop()

        return JsonResponse({
            'status': 'success',
            'message': 'Automated trading stopped successfully'
        })
    except Exception as e:
        logger.error(f"Error stopping automated trading: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to stop automated trading'
        }, status=500)


@login_required
def get_trading_status(request):
    """Get current trading status and performance metrics"""
    try:
        user_profile = request.user.userprofile
        
        # Get today's trades
        today = timezone.now().date()
        today_trades = Trade.objects.filter(
            user_profile=user_profile,
            trade_time__date=today
        )
        
        # Calculate today's metrics
        trades_today = today_trades.count()
        profit_today = sum(trade.profit for trade in today_trades if trade.profit)
        total_traded = sum(trade.amount for trade in today_trades)
        profit_percentage = (profit_today / total_traded * 100) if total_traded > 0 else 0
        
        # Get active positions
        active_positions = Trade.objects.filter(
            user_profile=user_profile,
            status='active'
        ).count()
        
        return JsonResponse({
            'status': 'success',
            'is_trading_active': user_profile.automated_trading_enabled,
            'trades_today': trades_today,
            'profit_today': round(profit_percentage, 2),
            'active_positions': active_positions,
            'last_update': timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting trading status: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to get trading status'
        }, status=500)


@login_required
def manual_trade(request):
    if request.method == 'POST':
        user_profile = request.user.userprofile
        asset = request.POST.get('asset')
        trade_type = request.POST.get('trade_type')
        amount = float(request.POST.get('amount'))
        
        # Validate trade parameters
        if not all([asset, trade_type, amount]):
            return JsonResponse({'status': 'error', 'message': 'Missing trade parameters'})
        
        # Check sufficient balance
        balance = AccountBalance.objects.get(user=user_profile)
        if amount > balance.balance_usd:
            return JsonResponse({'status': 'error', 'message': 'Insufficient balance'})
        
        # Execute trade
        automated_trading = AutomatedTrading(user_profile)
        asyncio.create_task(automated_trading.execute_trade(asset, trade_type, amount))
        
        return JsonResponse({'status': 'success', 'message': f'{trade_type.capitalize()} trade executed for {asset}'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
def profile(request):
    user_profile = request.user.userprofile
    
    # Calculate trading statistics
    trades = Trade.objects.filter(user_profile=user_profile)
    total_trades = trades.count()
    successful_trades = trades.filter(profit__gt=0).count()
    total_profit = trades.aggregate(Sum('profit'))['profit__sum'] or 0
    win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
    
    context = {
        'user_profile': user_profile,
        'total_trades': total_trades,
        'successful_trades': successful_trades,
        'total_profit': total_profit,
        'win_rate': win_rate,
    }
    
    return render(request, 'profile.html', context)


@login_required
def edit_profile(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user.userprofile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('trading:profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user.userprofile)
    
    return render(request, 'profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


def get_alpha_vantage_data(symbol, function='TIME_SERIES_INTRADAY', interval='5min'):
    """Helper function to fetch data from Alpha Vantage API"""
    api_key = settings.ALPHA_VANTAGE_API_KEY
    base_url = 'https://www.alphavantage.co/query'
    
    params = {
        'function': function,
        'symbol': symbol,
        'interval': interval,
        'apikey': api_key
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Alpha Vantage: {e}")
        return None

def get_market_data(asset='AAPL'):
    try:
        data = get_alpha_vantage_data(asset)
        return data
    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}")
        return None


@login_required
def handle_selected_asset(request):
    if request.method == 'POST':
        # Retrieve the 'asset' value from the POST data
        asset = request.POST.get('asset', 'AAPL')  # Default to AAPL if no asset selected

        try:
            # Process the selected asset
            data = get_alpha_vantage_data(asset)
            
            if not data:
                # Return default/mock data if real data fetch fails
                return JsonResponse({
                    "asset": asset,
                    "last_price": 150.00,  # Default price
                    "volume": 1000000,     # Default volume
                    "signal": 0,           # Neutral signal
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "technical_indicators": {
                        "rsi": 50.0,       # Neutral RSI
                        "macd": 0.0,       # Neutral MACD
                        "sma5": 150.0,     # Default SMA
                        "sma20": 150.0     # Default SMA
                    }
                })
                
            # Apply trading strategy
            data = apply_combined_strategy(data)
            
            # Get the latest values
            latest_data = data.iloc[-1]
            
            # Prepare response data
            response_data = {
                "asset": asset,
                "last_price": float(latest_data['4. close']),
                "volume": float(latest_data['5. volume']),
                "signal": int(latest_data['signal']),
                "timestamp": data.index[-1].strftime("%Y-%m-%d %H:%M:%S"),
                "technical_indicators": {
                    "rsi": float(latest_data['RSI']),
                    "macd": float(latest_data['MACD']),
                    "sma5": float(latest_data['SMA_5']),
                    "sma20": float(latest_data['SMA_20'])
                }
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error processing asset data: {str(e)}")
            # Return the same default data structure on error
            return JsonResponse({
                "asset": asset,
                "last_price": 150.00,
                "volume": 1000000,
                "signal": 0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "technical_indicators": {
                    "rsi": 50.0,
                    "macd": 0.0,
                    "sma5": 150.0,
                    "sma20": 150.0
                }
            })
    
    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def execute_trade(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        asset = data.get('asset')
        amount = Decimal(str(data.get('amount', 0)))
        action = data.get('action')

        if not all([asset, amount, action]) or amount <= 0:
            return JsonResponse({'error': 'Invalid trade parameters'}, status=400)

        user_profile = request.user.userprofile
        balance = AccountBalance.objects.get(user=user_profile)

        # Validate sufficient balance for buy orders
        if action == 'buy' and balance.balance_usd < amount:
            return JsonResponse({'error': 'Insufficient balance'}, status=400)

        # Execute the trade
        new_trade = Trade.objects.create(
            user_profile=user_profile,
            asset=asset,
            trade_type=action,
            amount=amount,
            profit_or_loss=Decimal('0.0')  # This would be calculated based on actual execution price
        )

        # Update balance
        if action == 'buy':
            balance.balance_usd -= amount
        else:  # sell
            balance.balance_usd += amount
        balance.save()

        # Send real-time notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "trades",
            {
                "type": "trade_message",
                "message": {
                    "type": "trade_update",
                    "data": {
                        "trade_id": new_trade.id,
                        "asset": asset,
                        "action": action,
                        "amount": str(amount),
                        "timestamp": new_trade.timestamp.isoformat(),
                        "new_balance": str(balance.balance_usd)
                    }
                }
            }
        )

        return JsonResponse({
            'status': 'success',
            'trade_id': new_trade.id,
            'message': f'{action.capitalize()} trade executed successfully',
            'new_balance': str(balance.balance_usd)
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except AccountBalance.DoesNotExist:
        return JsonResponse({'error': 'User account balance not found'}, status=404)
    except Exception as e:
        logger.error(f"Trade execution error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


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


# PayPal deposit view   
def paypal_deposit(request):
    user_profile = request.user.userprofile
    paypal_dict = {
        'business': 'sb-910uy34436506@business.example.com',
        'amount': '10.00',  # Example amount
        'item_name': 'Deposit to Trading Account',
        'invoice': 'unique-invoice-id',  # Replace with a unique ID
        'currency_code': 'USD',
        'notify_url': 'http://127.0.0.1:8000/paypal-ipn/',
        'return_url': 'http://127.0.0.1:8000/trading/payment-success/',
        'cancel_return': 'http://127.0.0.1:8000/trading/payment-cancelled/',
    }

    form = PayPalPaymentsForm(initial=paypal_dict)
    context = {'form': form}
    return render(request, 'trading/paypal_deposit.html', context)


# Payment success and cancel views
@login_required
def payment_success(request):
    """Handle successful payment"""
    messages.success(request, 'Payment successful! Your account will be credited once the payment is confirmed.')
    return redirect('trading:user_dashboard')

@login_required
def payment_cancelled(request):
    """Handle cancelled payment"""
    messages.warning(request, 'Payment was cancelled. Your account has not been charged.')
    return redirect('trading:user_dashboard')


# Stripe checkout view
def stripe_checkout(request):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'Deposit to Trading Account',
                },
                'unit_amount': 10000,  # $100.00
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url='http://127.0.0.1:8000/trading/payment-success/',
        cancel_url='http://127.0.0.1:8000/trading/payment-cancelled/',
    )
    return render(request, 'trading/stripe_checkout.html', {'session_id': session.id})


# Payment success view for Stripe
@login_required
def payment_success_stripe(request):
    """Handle successful payment"""
    messages.success(request, 'Payment successful! Your account will be credited once the payment is confirmed.')
    return redirect('trading:user_dashboard')

def get_trading_news(request):
    """Fetch latest trading news from newsapi.org"""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": settings.NEWS_API_KEY,
            "q": "trading OR cryptocurrency OR stocks OR forex",
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 10
        }
        response = requests.get(url, params=params)
        news = response.json()
        return JsonResponse({"status": "success", "data": news["articles"]})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

@login_required
@require_http_methods(["POST", "GET"])
def process_deposit(request):
    """Process deposit request"""
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                data = json.loads(request.body)
                amount = Decimal(str(data.get('amount', '0')))
                payment_method = data.get('payment_method')

                if amount < 10:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Minimum deposit amount is $10'
                    }, status=400)

                if not payment_method:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Please select a payment method'
                    }, status=400)

                # Create deposit record
                deposit = Deposit.objects.create(
                    user=request.user,
                    amount=amount,
                    payment_method=payment_method,
                    status='pending'
                )

                # For PayPal payments
                if payment_method.lower() == 'paypal':
                    paypal_dict = {
                        "business": settings.PAYPAL_RECEIVER_EMAIL,
                        "amount": str(amount),
                        "item_name": "AI Trading Platform - Account Deposit",
                        "invoice": str(deposit.id),
                        "notify_url": request.build_absolute_uri(reverse('paypal-ipn')),
                        "return": request.build_absolute_uri(reverse('trading:deposit_success')),
                        "cancel_return": request.build_absolute_uri(reverse('trading:deposit_cancelled')),
                        "custom": str(request.user.id),
                        "currency_code": "USD",
                    }
                    form = PayPalPaymentsForm(initial=paypal_dict)
                    return JsonResponse({
                        'status': 'success',
                        'redirect_url': form.render().split('action="')[1].split('"')[0]
                    })

                # For bank transfer
                elif payment_method.lower() == 'bank_transfer':
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Bank transfer request received',
                        'details': {
                            'bank_name': 'Example Bank',
                            'account_number': 'XXXXXXXXXXXX',
                            'reference': f'DEP-{deposit.id}'
                        }
                    })

                # For crypto
                elif payment_method.lower() == 'crypto':
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Crypto deposit request received',
                        'details': {
                            'wallet_address': 'XXXXXXXXXXXXX',
                            'reference': f'DEP-{deposit.id}'
                        }
                    })

                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid payment method'
                }, status=400)

            except (json.JSONDecodeError, decimal.InvalidOperation) as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
            except Exception as e:
                logger.error(f"Deposit error: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'An error occurred processing your deposit'
                }, status=500)
        else:
            # Handle regular form submission
            return redirect('trading:deposit_success')
    
    # GET request - render deposit form
    return render(request, 'trading/deposit.html')

@login_required
@require_http_methods(["POST"])
def process_withdrawal(request):
    """Process withdrawal request"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            amount = Decimal(str(data.get('amount', '0')))
            withdrawal_method = data.get('withdrawal_method')
            address = data.get('address')

            if amount <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid withdrawal amount'
                }, status=400)

            # Get user's trading account
            try:
                trading_account = TradingAccount.objects.get(user=request.user)
            except TradingAccount.DoesNotExist:
                trading_account = TradingAccount.objects.create(user=request.user)

            # Check if user has sufficient balance
            if trading_account.balance < amount:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Insufficient funds'
                }, status=400)

            # Create withdrawal request
            withdrawal = Withdrawal.objects.create(
                user=request.user,
                amount=amount,
                method=withdrawal_method,
                address=address,
                status='pending'
            )

            # Deduct amount from trading account
            trading_account.balance -= amount
            trading_account.save()

            # Create transaction record
            Transaction.objects.create(
                user=request.user,
                transaction_type='withdrawal',
                amount=amount,
                status='pending',
                reference=f'WD-{withdrawal.id}'
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Withdrawal request submitted successfully',
                'withdrawal_id': withdrawal.id
            })

        except (json.JSONDecodeError, decimal.InvalidOperation) as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        except Exception as e:
            logger.error(f"Withdrawal error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'An error occurred processing your withdrawal'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request'
    }, status=400)

def perform_aml_check(withdrawal):
    """
    Perform Anti-Money Laundering checks on withdrawal
    Returns: 'passed', 'pending', or 'flagged'
    """
    # Check for suspicious patterns
    user = withdrawal.user
    amount = withdrawal.amount
    
    # Get user's transaction history
    recent_withdrawals = Withdrawal.objects.filter(
        user=user,
        request_date__gte=timezone.now() - timezone.timedelta(days=30)
    ).aggregate(total=Sum('amount'))
    
    monthly_withdrawal_total = recent_withdrawals['total'] or 0
    
    # Flag for review if:
    # 1. Single withdrawal over $10,000
    # 2. Monthly withdrawals over $20,000
    # 3. Multiple withdrawals in short time period
    if amount > 10000:
        return 'flagged'
    
    if monthly_withdrawal_total > 20000:
        return 'flagged'
    
    recent_count = Withdrawal.objects.filter(
        user=user,
        request_date__gte=timezone.now() - timezone.timedelta(hours=24)
    ).count()
    
    if recent_count > 3:
        return 'flagged'
    
    return 'passed'

@login_required
def submit_kyc(request):
    """Submit KYC verification documents"""
    if request.method == 'POST':
        try:
            # Create or update KYC verification
            kyc, created = KYCVerification.objects.get_or_create(user=request.user)
            
            # Update fields from form data
            kyc.full_name = request.POST.get('full_name')
            kyc.date_of_birth = request.POST.get('date_of_birth')
            kyc.address = request.POST.get('address')
            kyc.country = request.POST.get('country')
            kyc.id_type = request.POST.get('id_type')
            kyc.id_number = request.POST.get('id_number')
            kyc.id_expiry_date = request.POST.get('id_expiry_date')
            
            # Handle file uploads
            if 'id_front' in request.FILES:
                kyc.id_front_image = request.FILES['id_front']
            if 'id_back' in request.FILES:
                kyc.id_back_image = request.FILES['id_back']
            if 'proof_of_address' in request.FILES:
                kyc.proof_of_address = request.FILES['proof_of_address']
            
            kyc.verification_status = 'pending'
            kyc.submission_date = timezone.now()
            kyc.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'KYC documents submitted successfully'
            })
            
        except Exception as e:
            logger.error(f"KYC submission error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': 'Error submitting KYC documents'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

@api_view(['POST'])
def start_trading(request):
    """Start automated trading for the user."""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        logger.info(f"Starting automated trading for user {request.user.username}")
        user_profile = UserProfile.objects.get(user=request.user)
        
        # Enable automated trading
        user_profile.automated_trading_enabled = True
        user_profile.save()
        
        logger.info(f"Automated trading enabled for user {request.user.username}")
        return JsonResponse({
            'status': 'success',
            'message': 'Automated trading started successfully'
        })
        
    except UserProfile.DoesNotExist:
        logger.error(f"User profile not found for {request.user.username}")
        return JsonResponse({
            'error': 'User profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error starting automated trading: {str(e)}")
        return JsonResponse({
            'error': 'Failed to start automated trading'
        }, status=500)

@api_view(['POST'])
def stop_trading(request):
    """Stop automated trading for the user."""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        logger.info(f"Stopping automated trading for user {request.user.username}")
        user_profile = UserProfile.objects.get(user=request.user)
        
        # Disable automated trading
        user_profile.automated_trading_enabled = False
        user_profile.save()
        
        logger.info(f"Automated trading disabled for user {request.user.username}")
        return JsonResponse({
            'status': 'success',
            'message': 'Automated trading stopped successfully'
        })
        
    except UserProfile.DoesNotExist:
        logger.error(f"User profile not found for {request.user.username}")
        return JsonResponse({
            'error': 'User profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error stopping automated trading: {str(e)}")
        return JsonResponse({
            'error': 'Failed to stop automated trading'
        }, status=500)

@api_view(['POST'])
def update_trading_parameters(request):
    """Update trading parameters for automated trading."""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        logger.info(f"Updating trading parameters for user {request.user.username}")
        user_profile = UserProfile.objects.get(user=request.user)
        
        # Get parameters from request
        data = json.loads(request.body) if isinstance(request.body, bytes) else request.data
        logger.info(f"Received parameters: {data}")
        
        # Validate parameters
        try:
            trade_amount = float(data.get('trade_amount', 0))
            min_price = float(data.get('min_price', 0))
            max_price = float(data.get('max_price', 0))
            
            if trade_amount <= 0:
                return JsonResponse({'error': 'Trade amount must be greater than 0'}, status=400)
            if min_price <= 0:
                return JsonResponse({'error': 'Minimum price must be greater than 0'}, status=400)
            if max_price <= min_price:
                return JsonResponse({'error': 'Maximum price must be greater than minimum price'}, status=400)
                
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid parameter values: {str(e)}")
            return JsonResponse({'error': 'Invalid parameter values'}, status=400)
        
        # Update trading parameters
        user_profile.trade_amount = trade_amount
        user_profile.min_price = min_price
        user_profile.max_price = max_price
        user_profile.automated_trading_enabled = True  # Enable trading when parameters are updated
        user_profile.save()
        
        logger.info(f"Trading parameters updated for user {request.user.username}")
        return JsonResponse({
            'status': 'success',
            'message': 'Trading parameters updated successfully'
        })
        
    except UserProfile.DoesNotExist:
        logger.error(f"User profile not found for {request.user.username}")
        return JsonResponse({
            'error': 'User profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating trading parameters: {str(e)}")
        return JsonResponse({
            'error': 'Failed to update trading parameters'
        }, status=500)

@api_view(['GET'])
def trading_status(request):
    """Get the current trading status and performance metrics."""
    try:
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
        logger.info(f"Getting trading status for user {request.user.username}")
        user_profile = UserProfile.objects.get(user=request.user)
        
        # Get trading statistics
        trades = Trade.objects.filter(user_profile=user_profile)
        active_trades = trades.filter(status='open').count()
        completed_trades = trades.filter(status='closed')
        total_trades = completed_trades.count()
        
        response_data = {
            'is_trading': user_profile.automated_trading_enabled,  # Match the field name expected by frontend
            'active_trades': active_trades,
            'total_profit': 0,
            'win_rate': 0,
            'last_trade_time': None
        }
        
        if total_trades > 0:
            profitable_trades = completed_trades.filter(profit__gt=0).count()
            response_data['win_rate'] = (profitable_trades / total_trades) * 100
            total_profit = completed_trades.aggregate(Sum('profit'))['profit__sum'] or 0
            response_data['total_profit'] = float(total_profit)
            
            last_trade = trades.order_by('-trade_time').first()
            if last_trade:
                response_data['last_trade_time'] = last_trade.trade_time.isoformat()
        
        logger.info(f"Trading status retrieved for user {request.user.username}")
        return JsonResponse(response_data)
        
    except UserProfile.DoesNotExist:
        logger.error(f"User profile not found for {request.user.username}")
        return JsonResponse({
            'error': 'User profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting trading status: {str(e)}")
        return JsonResponse({
            'error': 'Failed to get trading status'
        }, status=500)

@csrf_exempt
def paypal_ipn(request):
    """Process PayPal IPN (Instant Payment Notification)"""
    try:
        if request.method == "POST":
            # Verify the IPN
            form = PayPalIPNForm(request.POST)
            if form.is_valid():
                ipn_obj = form.save(commit=False)
                ipn_obj.save()
                
                # Verify that the payment status is Completed
                if ipn_obj.payment_status == "Completed":
                    # Get the user from the custom field
                    try:
                        user = User.objects.get(id=int(ipn_obj.custom))
                        amount = Decimal(ipn_obj.mc_gross)
                        
                        # Update user's account balance
                        account_balance, _ = AccountBalance.objects.get_or_create(user=user.userprofile)
                        account_balance.balance_usd += amount
                        account_balance.save()
                        
                        # Create transaction record
                        TransactionHistory.objects.create(
                            user=user.userprofile,
                            transaction_type='DEPOSIT',
                            amount=amount,
                            status='completed',
                            description=f'PayPal deposit - Transaction ID: {ipn_obj.txn_id}'
                        )
                        
                        # Log the successful payment
                        logger.info(f"Successful PayPal payment: {ipn_obj.txn_id} for user {user.username}")
                        
                    except User.DoesNotExist:
                        logger.error(f"PayPal IPN error: User not found for ID {ipn_obj.custom}")
                    except Exception as e:
                        logger.error(f"PayPal IPN processing error: {str(e)}")
                        
        return HttpResponse("OKAY")
    except Exception as e:
        logger.error(f"PayPal IPN error: {str(e)}")
        return HttpResponse("ERROR")

@login_required
def deposit_success(request):
    """Handle successful deposit"""
    try:
        return render(request, 'trading/deposit_success.html', {
            'message': 'Your deposit was successful!'
        })
    except Exception as e:
        logger.error(f"Error in deposit success view: {str(e)}")
        return JsonResponse({
            'error': 'An error occurred while processing your deposit success'
        }, status=500)

@login_required
def deposit_cancelled(request):
    """Handle cancelled deposit"""
    return render(request, 'trading/deposit_cancelled.html', {
        'message': 'Your deposit was cancelled. No funds were charged.'
    })

@login_required
def kyc_status(request):
    """Check the status of user's KYC verification."""
    try:
        kyc = KYCVerification.objects.get(user=request.user)
        return JsonResponse({
            'status': kyc.status,
            'submitted_at': kyc.submitted_at,
            'verified_at': kyc.verified_at,
            'rejection_reason': kyc.rejection_reason
        })
    except KYCVerification.DoesNotExist:
        return JsonResponse({
            'status': 'not_submitted',
            'message': 'KYC verification has not been submitted yet.'
        })

@login_required
def verify_kyc(request):
    """Verify KYC documents (admin only)."""
    if not request.user.is_staff:
        return JsonResponse({
            'error': 'Unauthorized access'
        }, status=403)
    
    if request.method != 'POST':
        return JsonResponse({
            'error': 'Invalid request method'
        }, status=405)
    
    try:
        data = json.loads(request.body)
        kyc_id = data.get('kyc_id')
        action = data.get('action')  # 'approve' or 'reject'
        rejection_reason = data.get('rejection_reason')
        
        kyc = KYCVerification.objects.get(id=kyc_id)
        
        if action == 'approve':
            kyc.status = 'verified'
            kyc.verified_at = timezone.now()
        elif action == 'reject':
            kyc.status = 'rejected'
            kyc.rejection_reason = rejection_reason
        else:
            return JsonResponse({
                'error': 'Invalid action'
            }, status=400)
        
        kyc.save()
        return JsonResponse({
            'status': 'success',
            'kyc_status': kyc.status
        })
    except KYCVerification.DoesNotExist:
        return JsonResponse({
            'error': 'KYC verification not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)

@login_required
def upload_kyc_documents(request):
    """Handle KYC document uploads."""
    if request.method != 'POST':
        return JsonResponse({
            'error': 'Invalid request method'
        }, status=405)
    
    try:
        # Get or create KYC verification instance
        kyc, created = KYCVerification.objects.get_or_create(
            user=request.user,
            defaults={'status': 'pending'}
        )
        
        if not created and kyc.status == 'verified':
            return JsonResponse({
                'error': 'KYC already verified'
            }, status=400)
        
        # Handle file uploads
        id_document = request.FILES.get('id_document')
        proof_of_address = request.FILES.get('proof_of_address')
        selfie = request.FILES.get('selfie')
        
        if not all([id_document, proof_of_address, selfie]):
            return JsonResponse({
                'error': 'All required documents must be provided'
            }, status=400)
        
        # Update KYC documents
        kyc.id_document = id_document
        kyc.proof_of_address = proof_of_address
        kyc.selfie = selfie
        kyc.status = 'pending'
        kyc.submitted_at = timezone.now()
        kyc.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'KYC documents uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"Error uploading KYC documents: {str(e)}")
        return JsonResponse({
            'error': 'Error uploading documents'
        }, status=500)

@login_required
@require_http_methods(['POST'])
def start_trading(request):
    try:
        user_profile = request.user.userprofile
        user_profile.automated_trading_enabled = True
        user_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Automated trading started successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
@require_http_methods(['POST'])
def stop_trading(request):
    try:
        user_profile = request.user.userprofile
        user_profile.automated_trading_enabled = False
        user_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Automated trading stopped successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
@require_http_methods(['POST'])
def update_trading_parameters(request):
    try:
        data = json.loads(request.body)
        user_profile = request.user.userprofile
        
        # Update trading parameters
        user_profile.trade_amount = Decimal(data.get('trade_amount', 0))
        user_profile.min_price = Decimal(data.get('min_price', 0))
        user_profile.max_price = Decimal(data.get('max_price', 0))
        user_profile.automated_trading_enabled = True  # Enable trading when parameters are updated
        user_profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Trading parameters updated successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@login_required
def trading_status(request):
    try:
        user_profile = request.user.userprofile
        
        # Get active trades count
        active_trades = Trade.objects.filter(
            user_profile=user_profile,
            status='active'
        ).count()
        
        # Calculate total profit from completed trades
        total_profit = Trade.objects.filter(
            user_profile=user_profile,
            status='completed'
        ).aggregate(Sum('profit'))['profit__sum'] or 0
        
        # Calculate win rate
        completed_trades = Trade.objects.filter(
            user_profile=user_profile,
            status='completed'
        )
        winning_trades = completed_trades.filter(profit__gt=0).count()
        total_completed = completed_trades.count()
        win_rate = (winning_trades / total_completed * 100) if total_completed > 0 else 0
        
        # Get last trade
        last_trade = Trade.objects.filter(
            user_profile=user_profile
        ).order_by('-timestamp').first()
        
        status_data = {
            'is_trading': user_profile.automated_trading_enabled,  # Match the field name expected by frontend
            'active_trades': active_trades,
            'total_profit': float(total_profit),
            'win_rate': win_rate,
            'last_update': timezone.now().isoformat()
        }
        
        if last_trade:
            status_data['last_trade'] = {
                'type': last_trade.trade_type,
                'amount': str(last_trade.amount),
                'price': str(last_trade.entry_price),
                'time': last_trade.timestamp.isoformat()
            }
        
        return JsonResponse(status_data)
    except UserProfile.DoesNotExist:
        logger.error(f"User profile not found for user {request.user.username}")
        return JsonResponse({
            'status': 'error',
            'message': 'User profile not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in trading status for user {request.user.username}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)

@api_view(['POST'])
def get_asset_info(request):
    """Get asset information from Alpha Vantage API."""
    try:
        logger.info("Received asset info request")
        
        # Get the asset symbol from request data
        data = request.data
        logger.info(f"Request data: {data}")
        
        if not isinstance(data, dict):
            return JsonResponse({
                'error': 'Invalid request format - expected JSON object'
            }, status=400)
            
        symbol = data.get('asset', 'AAPL')
        logger.info(f"Getting info for symbol: {symbol}")
        
        # For testing, return mock data
        mock_data = {
            'symbol': symbol,
            'price': 150.25,
            'change': 2.50,
            'change_percent': 1.69,
            'volume': 1234567,
            'price_history': [
                {'time': '2024-01-09T14:30:00Z', 'price': 148.75},
                {'time': '2024-01-09T14:35:00Z', 'price': 149.25},
                {'time': '2024-01-09T14:40:00Z', 'price': 149.75},
                {'time': '2024-01-09T14:45:00Z', 'price': 150.25}
            ]
        }
        
        return JsonResponse(mock_data)

    except Exception as e:
        logger.error(f"Error in get_asset_info: {str(e)}")
        return JsonResponse({
            'error': 'An unexpected error occurred while fetching asset data'
        }, status=500)