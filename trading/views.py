from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_http_methods

from .models import AccountBalance, Trade, TransactionHistory, UserProfile, Transaction
from .automated_trading import AutomatedTrading
from .ai_trading import train_model, make_trade_prediction, apply_combined_strategy
from .forms import UserRegistrationForm, UserProfileForm, UserForm
from paypal.standard.forms import PayPalPaymentsForm
import stripe

import pandas as pd
from alpha_vantage.timeseries import TimeSeries
from django.conf import settings

from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

import requests, logging
import asyncio
import json
from decimal import Decimal
from .payment_utils import process_stripe_payment, process_withdrawal
from datetime import datetime

logger = logging.getLogger('trading')

stripe.api_key = settings.STRIPE_SECRET_KEY


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
            return redirect('user_dashboard')
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
    return HttpResponseRedirect(reverse('user_dashboard'))


@login_required
def user_dashboard(request):
    user_profile = request.user.userprofile
    try:
        account_balance = AccountBalance.objects.get(user=user_profile)
    except AccountBalance.DoesNotExist:
        account_balance = AccountBalance.objects.create(user=user_profile)
    
    # Get trading metrics
    trades = Trade.objects.filter(user=user_profile)
    total_trades = trades.count()
    active_trades = trades.filter(status='active').count()
    
    # Calculate success rate
    successful_trades = trades.filter(profit__gt=0).count()
    success_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate total profit
    total_profit = trades.aggregate(Sum('profit'))['profit__sum'] or 0
    
    # Get recent trading activity
    recent_trades = trades.order_by('-trade_time')[:10]
    recent_transactions = TransactionHistory.objects.filter(user=user_profile).order_by('-timestamp')[:10]
    
    # Get market data
    market_data = get_market_data()
    
    context = {
        'user': request.user,
        'stripe_public_key': settings.STRIPE_PUBLISHABLE_KEY,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
        'account_balance': account_balance.balance_usd,
        'balance': account_balance,
        'total_trades': total_trades,
        'active_trades': active_trades,
        'success_rate': round(success_rate, 2),
        'total_profit': total_profit,
        'recent_trades': recent_trades,
        'recent_transactions': recent_transactions,
        'market_data': market_data,
    }
    
    return render(request, 'dashboard.html', context)


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
        user_profile.is_trading_active = True
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
        user_profile.is_trading_active = False
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
        account_balance = AccountBalance.objects.get(user=user_profile)
        
        # Get today's trades and performance
        today = datetime.now().date()
        today_trades = Trade.objects.filter(
            user=user_profile,
            trade_time__date=today
        )
        
        total_profit = today_trades.aggregate(
            total_profit=Sum('profit_or_loss')
        )['total_profit'] or 0

        return JsonResponse({
            'status': 'success',
            'is_trading_active': user_profile.is_trading_active,
            'current_balance': float(account_balance.balance_usd),
            'trades_today': today_trades.count(),
            'profit_today': float(total_profit),
            'last_trade_time': today_trades.last().trade_time.isoformat() if today_trades.exists() else None
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
    trades = Trade.objects.filter(user=user_profile)
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
            return redirect('profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user.userprofile)
    
    return render(request, 'profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


def get_market_data(asset='AAPL'):
    try:
        ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='pandas')
        data, meta_data = ts.get_intraday(symbol=asset, interval='60min', outputsize='compact')
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
            data = get_market_data(asset)
            
            if data is None:
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


def execute_trade(request, symbol, trade_type, amount):
    user_profile = request.user.userprofile

    # Fetch market data
    market_data = get_market_data('AAPL')

    # Train or load the AI model
    model = train_model(market_data)

    # Make a prediction (buy or sell)
    trade_action = make_trade_prediction(model, market_data)

    # Execute the trade (buy or sell)
    if trade_action == 'buy':
        amount = 100  # Example trade amount
        new_trade = Trade(user=user_profile, asset='AAPL', trade_type='buy', amount=amount, profit_or_loss=0.0)
        new_trade.save()

        # Deduct from balance
        balance = AccountBalance.objects.get(user=user_profile)
        balance.balance_usd -= amount
        balance.save()

        # Send real-time notification after trade execution
        send_trade_notification(request.user.username, trade_action, amount)

    elif trade_action == 'sell':
        # Assume we sold for a profit of 10 (just an example)
        new_trade = Trade(user=user_profile, asset='AAPL', trade_type='sell', amount=0, profit_or_loss=10.0)
        new_trade.save()

        # Add to balance
        balance = AccountBalance.objects.get(user=user_profile)
        balance.balance_usd += 10.0
        balance.save()

        # Send real-time notification after trade execution
        send_trade_notification(request.user.username, trade_action, new_trade.profit_or_loss)
        
    try:
        # Log the trade execution
        logger.info(f"Executed {trade_type} trade for {symbol} with amount {amount}")
    except Exception as e:
        logger.error(f"Failed to execute trade for {symbol}: {e}")

    return render(request, 'execution_result.html', {'trade_action': trade_action})


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
    # Assuming the amount and transaction details can be fetched from the request/session
    user_profile = request.user.userprofile
    amount_credited = 100.00  # This should be dynamic based on the transaction

    # Update the user's account balance
    balance = AccountBalance.objects.get(user=user_profile)
    balance.balance_usd += amount_credited
    balance.save()

    return render(request, 'trading/payment_success.html', {'amount_credited': amount_credited})


def payment_cancelled(request):
    return render(request, 'trading/payment_cancelled.html')


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
    # Assuming the amount and transaction details are fetched from the session
    user_profile = request.user.userprofile
    amount_credited = 100.00  # This should be dynamic

    # Update the user's account balance
    balance = AccountBalance.objects.get(user=user_profile)
    balance.balance_usd += amount_credited
    balance.save()

    return render(request, 'trading/payment_success.html', {'amount_credited': amount_credited})

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
def process_deposit(request):
    """Process a deposit via PayPal"""
    try:
        data = json.loads(request.body)
        amount = Decimal(data.get('amount'))
        payment_id = data.get('payment_id')
        status = data.get('status')

        if not all([amount, payment_id, status]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required payment information'
            }, status=400)

        if amount < Decimal('10.00'):
            return JsonResponse({
                'status': 'error',
                'message': 'Minimum deposit amount is $10'
            }, status=400)

        # Record the transaction
        transaction = Transaction.objects.create(
            user=request.user.userprofile,
            transaction_type='DEPOSIT',
            amount=amount,
            method='PAYPAL',
            status='COMPLETED',
            details=f'PayPal payment ID: {payment_id}'
        )

        # Update account balance
        account_balance = AccountBalance.objects.get(user=request.user.userprofile)
        account_balance.balance_usd += amount
        account_balance.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Successfully deposited ${amount}',
            'new_balance': str(account_balance.balance_usd)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error processing deposit: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to process deposit'
        }, status=500)

@login_required
def process_withdrawal_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    
    data = json.loads(request.body)
    amount = data.get("amount")
    
    if not amount:
        return JsonResponse({"status": "error", "message": "Amount is required"})
    
    result = process_withdrawal(request.user.userprofile, amount)
    return JsonResponse(result)

@login_required
@require_http_methods(['POST'])
def process_withdrawal(request):
    """Process withdrawal request to bank or PayPal"""
    try:
        data = json.loads(request.body)
        amount = Decimal(data.get('amount'))
        method = data.get('method')
        bank_account = data.get('bank_account')
        paypal_email = data.get('paypal_email')

        user_profile = request.user.userprofile
        account_balance = AccountBalance.objects.get(user=user_profile)

        # Validate amount
        if amount < Decimal('10.00'):
            return JsonResponse({
                'status': 'error',
                'message': 'Minimum withdrawal amount is $10'
            }, status=400)

        if amount > account_balance.balance_usd:
            return JsonResponse({
                'status': 'error',
                'message': 'Insufficient balance for withdrawal'
            }, status=400)

        # Validate withdrawal method details
        if method == 'bank' and not bank_account:
            return JsonResponse({
                'status': 'error',
                'message': 'Bank account number is required'
            }, status=400)
        elif method == 'paypal' and not paypal_email:
            return JsonResponse({
                'status': 'error',
                'message': 'PayPal email is required'
            }, status=400)

        # Process withdrawal based on method
        if method == 'bank':
            # Implement bank transfer logic here
            # For now, just deduct the balance
            account_balance.balance_usd -= amount
            account_balance.save()

            # Create withdrawal transaction record
            Transaction.objects.create(
                user=user_profile,
                transaction_type='WITHDRAWAL',
                amount=amount,
                method='BANK',
                status='COMPLETED',
                details=f'Bank transfer to account {bank_account}'
            )
        else:  # PayPal
            # Implement PayPal transfer logic here
            # For now, just deduct the balance
            account_balance.balance_usd -= amount
            account_balance.save()

            # Create withdrawal transaction record
            Transaction.objects.create(
                user=user_profile,
                transaction_type='WITHDRAWAL',
                amount=amount,
                method='PAYPAL',
                status='COMPLETED',
                details=f'PayPal transfer to {paypal_email}'
            )

        return JsonResponse({
            'status': 'success',
            'message': f'Successfully processed withdrawal of ${amount}',
            'new_balance': str(account_balance.balance_usd)
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error processing withdrawal: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to process withdrawal'
        }, status=500)