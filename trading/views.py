from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Q
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
import logging
from decimal import Decimal

from .models import AccountBalance, Trade, TransactionHistory, UserProfile, Transaction
from .automated_trading import AutomatedTrading
from .ai_trading import train_model, make_trade_prediction, apply_combined_strategy
from .forms import UserRegistrationForm, UserProfileForm, UserForm
from paypal.standard.forms import PayPalPaymentsForm
import stripe

import pandas as pd
from alpha_vantage.timeseries import TimeSeries
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

import requests
import asyncio
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
        'paypal_receiver_email': settings.PAYPAL_RECEIVER_EMAIL,
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
            user=user_profile,
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
@require_http_methods(["POST"])
def process_deposit(request):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    try:
        logger.debug("Starting deposit process")
        logger.debug(f"Request body: {request.body.decode()}")
        
        # Parse request data
        data = json.loads(request.body)
        order_id = data.get('order_id')
        payment_id = data.get('payment_id')
        amount = Decimal(str(data.get('amount', '0')))
        status = data.get('status')
        details = data.get('details', {})

        logger.info(f"Processing deposit - Order ID: {order_id}, Payment ID: {payment_id}, Amount: {amount}, Status: {status}")
        
        # Validate required fields
        if not all([order_id, payment_id, amount, status]):
            logger.error("Missing required fields")
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required payment information'
            }, status=400)

        # Validate payment status
        if status != 'COMPLETED':
            logger.error(f"Invalid payment status: {status}")
            return JsonResponse({
                'status': 'error',
                'message': 'Payment not completed'
            }, status=400)

        # Check for duplicate payment
        if Transaction.objects.filter(Q(order_id=order_id) | Q(payment_id=payment_id)).exists():
            logger.warning(f"Duplicate payment detected - Order ID: {order_id}, Payment ID: {payment_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'This payment has already been processed'
            }, status=400)

        try:
            # Start transaction
            with transaction.atomic():
                user_profile = request.user.userprofile
                
                # Update account balance
                account_balance = AccountBalance.objects.select_for_update().get(user=user_profile)
                previous_balance = account_balance.balance_usd
                account_balance.balance_usd += amount
                account_balance.save()

                logger.info(f"Updated balance from ${previous_balance} to ${account_balance.balance_usd}")

                # Create transaction record
                transaction_record = Transaction.objects.create(
                    user=user_profile,
                    transaction_type='DEPOSIT',
                    amount=amount,
                    method='PAYPAL',
                    status='COMPLETED',
                    order_id=order_id,
                    payment_id=payment_id,
                    details=json.dumps(details)
                )

                logger.info(f"Created transaction record: {transaction_record.id}")

                # Create transaction history record
                TransactionHistory.objects.create(
                    user=user_profile,
                    transaction_type='DEPOSIT',
                    amount=amount,
                    status='completed',
                    description=f'PayPal deposit (Order ID: {order_id})'
                )

                # Send WebSocket notification
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        "trades",
                        {
                            "type": "trade_message",
                            "message": {
                                "type": "balance_update",
                                "data": {
                                    "new_balance": str(account_balance.balance_usd),
                                    "transaction_id": transaction_record.id
                                }
                            }
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"WebSocket notification error: {str(ws_error)}")
                    # Continue processing even if WebSocket fails

                return JsonResponse({
                    'status': 'success',
                    'message': f'Successfully deposited ${amount}',
                    'new_balance': str(account_balance.balance_usd)
                })

        except AccountBalance.DoesNotExist:
            logger.error(f"Account balance not found for user {request.user.id}")
            return JsonResponse({
                'status': 'error',
                'message': 'Account balance not found'
            }, status=404)
            
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Database error occurred while processing payment'
            }, status=500)

    except json.JSONDecodeError as json_error:
        logger.error(f"JSON decode error: {str(json_error)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid payment data format'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error in process_deposit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while processing your deposit'
        }, status=500)

@login_required
def get_balance(request):
    try:
        trading_account = AccountBalance.objects.get(user=request.user.userprofile)
        return JsonResponse({
            'status': 'success',
            'balance': float(trading_account.balance_usd)
        })
    except AccountBalance.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Trading account not found'
        })

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

from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

@method_decorator(login_required, name='dispatch')
class StartAutomatedTradingView(APIView):
    def post(self, request):
        try:
            # Print request data for debugging
            print("Request data:", request.data)
            
            # Get data from request.data instead of parsing JSON
            min_amount = request.data.get('min_trade_amount', 10)
            max_amount = request.data.get('max_trade_amount', 100)
            
            print(f"Min amount: {min_amount}, Max amount: {max_amount}")
            
            # Save automated trading settings to user profile
            profile = request.user.userprofile
            profile.automated_trading_enabled = True
            profile.min_trade_amount = Decimal(str(min_amount))
            profile.max_trade_amount = Decimal(str(max_amount))
            profile.save()
            
            return Response({'status': 'success', 'message': 'Automated trading enabled'})
        except Exception as e:
            print(f"Error in StartAutomatedTradingView: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=400)

@method_decorator(login_required, name='dispatch')
class StopAutomatedTradingView(APIView):
    def post(self, request):
        try:
            profile = request.user.userprofile
            profile.automated_trading_enabled = False
            profile.save()
            return Response({'status': 'success', 'message': 'Automated trading disabled'})
        except Exception as e:
            print(f"Error in StopAutomatedTradingView: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=400)

@method_decorator(login_required, name='dispatch')
class TradingStatusView(APIView):
    def get(self, request):
        try:
            profile = request.user.userprofile
            return Response({
                'auto_trading_enabled': profile.automated_trading_enabled,
                'min_trade_amount': float(profile.min_trade_amount),
                'max_trade_amount': float(profile.max_trade_amount)
            })
        except Exception as e:
            print(f"Error in TradingStatusView: {str(e)}")
            return Response({'status': 'error', 'message': str(e)}, status=400)