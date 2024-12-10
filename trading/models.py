from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db import models


# Model to extend the User model with additional trading-related fields
class UserProfile(models.Model):
    TRADING_EXPERIENCE_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert')
    ]
    
    RISK_TOLERANCE_CHOICES = [
        ('conservative', 'Conservative'),
        ('moderate', 'Moderate'),
        ('aggressive', 'Aggressive')
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('JPY', 'Japanese Yen'),
        ('AUD', 'Australian Dollar'),
        ('CAD', 'Canadian Dollar')
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    trading_experience = models.CharField(
        max_length=20,
        choices=TRADING_EXPERIENCE_CHOICES,
        default='beginner'
    )
    risk_tolerance = models.CharField(
        max_length=20,
        choices=RISK_TOLERANCE_CHOICES,
        default='moderate'
    )
    preferred_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD'
    )
    verified = models.BooleanField(default=False)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    automated_trading_enabled = models.BooleanField(default=False)
    min_trade_amount = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    max_trade_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)

    def __str__(self):
        return self.user.username

    def get_avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return '/static/trading/images/default_avatar.svg'


# Model to track account balances in multiple currencies
class AccountBalance(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE)
    balance_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance_gbp = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    auto_trading_enabled = models.BooleanField(default=False)
    min_trade_amount = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    max_trade_amount = models.DecimalField(max_digits=10, decimal_places=2, default=1000)

    def __str__(self):
        return f"Balance for {self.user.user.username}"


# Model to track individual trades made by the AI
class Trade(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    TRADE_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    asset = models.CharField(max_length=10, default='BTC')
    trade_type = models.CharField(max_length=4, choices=TRADE_TYPES, default='buy')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    entry_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exit_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user_profile.user.username} - {self.trade_type} {self.asset} at {self.entry_price}"

    def calculate_profit(self):
        if self.exit_price and self.status == 'completed':
            if self.trade_type == 'buy':
                self.profit = (self.exit_price - self.entry_price) * self.amount
            else:  # sell
                self.profit = (self.entry_price - self.exit_price) * self.amount
            self.save()
        return self.profit


# Model to track user transactions such as deposits, withdrawals, and trade activity
class TransactionHistory(models.Model):
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('AUTO_BUY', 'Automated Buy'),
        ('AUTO_SELL', 'Automated Sell'),
        ('MANUAL_BUY', 'Manual Buy'),
        ('MANUAL_SELL', 'Manual Sell'),
    ]

    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=TRANSACTION_STATUS, default='pending')
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} ({self.status})"


# Model to handle withdrawals and deposits
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('TRADE', 'Trade'),
    ]
    
    PAYMENT_METHODS = [
        ('BANK', 'Bank Transfer'),
        ('PAYPAL', 'PayPal'),
        ('CARD', 'Credit/Debit Card'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} USD - {self.status}"


class Deposit(models.Model):
    PAYMENT_METHODS = [
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('crypto', 'Cryptocurrency'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.payment_method})"

    class Meta:
        ordering = ['-created_at']


class KYCVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    address = models.TextField()
    country = models.CharField(max_length=100)
    id_type = models.CharField(max_length=50, choices=[
        ('passport', 'Passport'),
        ('drivers_license', "Driver's License"),
        ('national_id', 'National ID')
    ])
    id_number = models.CharField(max_length=100)
    id_expiry_date = models.DateField()
    id_front_image = models.ImageField(upload_to='kyc_documents/')
    id_back_image = models.ImageField(upload_to='kyc_documents/')
    proof_of_address = models.FileField(upload_to='kyc_documents/')
    verification_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='pending')
    submission_date = models.DateTimeField(auto_now_add=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'KYC Verification'
        verbose_name_plural = 'KYC Verifications'

class WithdrawalRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    withdrawal_method = models.CharField(max_length=50, choices=[
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('crypto', 'Cryptocurrency')
    ])
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed')
    ], default='pending')
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    account_number = models.CharField(max_length=50, null=True, blank=True)
    routing_number = models.CharField(max_length=50, null=True, blank=True)
    paypal_email = models.EmailField(null=True, blank=True)
    crypto_address = models.CharField(max_length=255, null=True, blank=True)
    crypto_network = models.CharField(max_length=50, null=True, blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    processed_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    aml_check_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('flagged', 'Flagged')
    ], default='pending')
    aml_check_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-request_date']


class TradingAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Trading settings
    automated_trading_enabled = models.BooleanField(default=False)
    trade_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    min_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Trading Account"

    def deposit(self, amount):
        """Add funds to the account"""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.balance += amount
        self.save()

    def withdraw(self, amount):
        """Withdraw funds from the account"""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        self.save()

    def update_trading_parameters(self, trade_amount=None, min_price=None, max_price=None):
        """Update automated trading parameters"""
        if trade_amount is not None:
            self.trade_amount = trade_amount
        if min_price is not None:
            self.min_price = min_price
        if max_price is not None:
            self.max_price = max_price
        self.save()

    class Meta:
        verbose_name = "Trading Account"
        verbose_name_plural = "Trading Accounts"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        AccountBalance.objects.create(user=instance.userprofile)
        TradingAccount.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()
