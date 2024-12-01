from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate

from .models import AccountBalance, Trade, TransactionHistory, UserProfile
from .ai_trading import train_model, make_trade_prediction, get_market_data
from .forms import UserForm, UserProfileForm
from paypal.standard.forms import PayPalPaymentsForm
import stripe

import pandas as pd
from alpha_vantage.timeseries import TimeSeries
from django.conf import settings

from django.http import HttpResponseRedirect
from django.urls import reverse

stripe.api_key = settings.STRIPE_SECRET_KEY


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create a UserProfile instance if it exists
            user_profile = UserProfile.objects.create(user=user)  # Creates the associated profile
            login(request, user)
            return redirect('user_dashboard')  # Redirect to dashboard or another page
    else:
        form = UserCreationForm()
    return render(request, 'registration/login.html', {'form': form})


# Admin dashboard view
@staff_member_required
def admin_dashboard(request):
    total_balance = AccountBalance.objects.aggregate(total_usd=Sum('balance_usd'))['total_usd']
    recent_trades = Trade.objects.all().order_by('-trade_time')[:10]

    context = {
        'total_balance': total_balance,
        'recent_trades': recent_trades,
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
    # Check if the AccountBalance exists, if not, create one
    balance, created = AccountBalance.objects.get_or_create(user=user_profile)
    recent_trades = Trade.objects.filter(user=user_profile).order_by('-trade_time')[:5]
    transaction_history = TransactionHistory.objects.filter(user=user_profile).order_by('-transaction_time')[:5]

    context = {
        'balance': balance,
        'recent_trades': recent_trades,
        'transaction_history': transaction_history,
    }
    return render(request, 'dashboard.html', context)


@login_required
def profile(request):
    user_profile = request.user.userprofile
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'profile.html', context)


@login_required
def edit_profile(request):
    user_profile = request.user.userprofile

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, instance=user_profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('profile')  # Redirect to the profile page after saving

    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=user_profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }

    return render(request, 'edit_profile.html', context)


def get_market_data(request):
    ts = TimeSeries(key=settings.ALPHA_VANTAGE_API_KEY, output_format='pandas')
    data, meta_data = ts.get_intraday(symbol=asset, interval='60min', outputsize='full')
    return data.to_json()


def execute_trade(request):
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
        'amount': '50.00',  # Example amount
        'item_name': 'Deposit to Trading Account',
        'invoice': 'unique-invoice-id',  # Replace with a unique ID
        'currency_code': 'USD',
        'notify_url': 'http://127.0.0.1:8000/paypal-ipn/',
        'return_url': 'http://127.0.0.1:8000/payment-success/',
        'cancel_return': 'http://127.0.0.1:8000/payment-cancelled/',
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
