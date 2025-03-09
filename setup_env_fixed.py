import os
import secrets
import shutil

# Generate a secure Django secret key
def generate_secret_key():
    return secrets.token_urlsafe(50)

# Create .env file with required variables
def create_env_file():
    env_path = '.env'
    
    # Check if .env already exists
    if os.path.exists(env_path):
        print(f"Warning: {env_path} already exists. Backing it up to .env.bak")
        shutil.copy(env_path, f"{env_path}.bak")
    
    # Generate a secure secret key
    secret_key = generate_secret_key()
    
    # Create the .env file with required variables
    with open(env_path, 'w') as f:
        f.write(f"# Django Settings\n")
        f.write(f"SECRET_KEY={secret_key}\n")
        f.write(f"DEBUG=True\n\n")
        
        # Add NEWS_API_KEY which might be missing
        f.write(f"NEWS_API_KEY=demo\n\n")
        
        f.write(f"# API Keys\n")
        f.write(f"ALPHA_VANTAGE_API_KEY=demo\n")  # Using demo key for now
        f.write(f"ALPACA_API_KEY=PKZGZPKJT1WLZKXNV5PZ\n")  # Example key, replace with real one
        f.write(f"ALPACA_SECRET_KEY=example_secret_key\n")
        f.write(f"ALPACA_BASE_URL=https://paper-api.alpaca.markets\n\n")
        
        f.write(f"# Payment Settings\n")
        f.write(f"PAYPAL_RECEIVER_EMAIL=your-paypal-business-email@example.com\n")
        f.write(f"PAYPAL_CLIENT_ID=your_paypal_client_id\n\n")
        
        f.write(f"# Bank Transfer Settings\n")
        f.write(f"BANK_NAME=Example Bank\n")
        f.write(f"BANK_ACCOUNT_NUMBER=1234567890\n\n")
        
        f.write(f"# Cryptocurrency Settings\n")
        f.write(f"CRYPTO_WALLET_ADDRESS=your-crypto-wallet-address\n\n")
        
        f.write(f"# Redis Settings (for production)\n")
        f.write(f"REDIS_URL=redis://localhost:6379\n")
    
    print(f"Created {env_path} with a new SECRET_KEY and default values.")
    print("Note: For production use, replace the placeholder API keys with real ones.")

if __name__ == "__main__":
    create_env_file()
