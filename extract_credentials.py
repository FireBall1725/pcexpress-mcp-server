#!/usr/bin/env python3
"""
Extract credentials from HAR file for Zehrs MCP Server

This script parses a HAR file and extracts:
- Bearer token
- Customer ID
- Cart ID
- Store ID
"""

import json
import re
import sys
from pathlib import Path


def extract_credentials_from_har(har_file_path: str) -> dict:
    """
    Extract Zehrs API credentials from HAR file

    Args:
        har_file_path: Path to the HAR file

    Returns:
        dict: Extracted credentials
    """
    with open(har_file_path, 'r') as f:
        har = json.load(f)

    credentials = {
        'bearer_token': None,
        'customer_id': None,
        'cart_id': None,
        'store_id': None,
    }

    # Parse all entries
    for entry in har['log']['entries']:
        url = entry['request']['url']

        # Look for API requests to pcexpress
        if 'api.pcexpress.ca' not in url:
            continue

        # Extract bearer token from headers
        if credentials['bearer_token'] is None:
            for header in entry['request']['headers']:
                if header['name'].lower() == 'authorization' and 'Bearer' in header['value']:
                    credentials['bearer_token'] = header['value'].replace('Bearer ', '').strip()
                    break

        # Extract cart ID from URL
        cart_match = re.search(r'/carts/([a-f0-9\-]{36})', url)
        if cart_match and credentials['cart_id'] is None:
            credentials['cart_id'] = cart_match.group(1)

        # Extract customer ID from URL
        customer_match = re.search(r'/customers/([a-f0-9\-]{36})', url)
        if customer_match and credentials['customer_id'] is None:
            credentials['customer_id'] = customer_match.group(1)

        # Extract store ID from request body or query params
        if 'storeId' in url and credentials['store_id'] is None:
            store_match = re.search(r'storeId=(\d+)', url)
            if store_match:
                credentials['store_id'] = store_match.group(1)

        # Also check POST body for store ID
        if credentials['store_id'] is None and 'postData' in entry['request']:
            post_text = entry['request']['postData'].get('text', '')
            if 'storeId' in post_text:
                try:
                    post_data = json.loads(post_text)
                    if 'storeId' in post_data:
                        credentials['store_id'] = post_data['storeId']
                except:
                    pass

    # Set default store ID if not found
    if credentials['store_id'] is None:
        credentials['store_id'] = '0000'  # Placeholder - update with your store

    return credentials


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python extract_credentials.py <har_file_path>")
        print("\nExample:")
        print("  python extract_credentials.py ~/Downloads/www.zehrs.ca.har")
        sys.exit(1)

    har_file = sys.argv[1]

    if not Path(har_file).exists():
        print(f"Error: File not found: {har_file}")
        sys.exit(1)

    print("Extracting credentials from HAR file...")
    credentials = extract_credentials_from_har(har_file)

    # Check if we got all required credentials
    missing = [k for k, v in credentials.items() if v is None and k != 'store_id']

    if missing:
        print(f"\n⚠️  Warning: Could not extract: {', '.join(missing)}")
        print("\nMake sure your HAR file includes:")
        print("  - Authenticated API requests to api.pcexpress.ca")
        print("  - Cart operations (viewing or modifying cart)")
        print("  - Customer/account operations")
        print()

    # Print credentials
    print("\n" + "="*60)
    print("EXTRACTED CREDENTIALS")
    print("="*60)

    for key, value in credentials.items():
        if value:
            # Truncate long tokens for display
            display_value = value
            if len(str(value)) > 50:
                display_value = value[:30] + "..." + value[-20:]
            print(f"{key.upper()}: {display_value}")
        else:
            print(f"{key.upper()}: ❌ NOT FOUND")

    # Generate .env file
    print("\n" + "="*60)
    print("GENERATED .env FILE CONTENT")
    print("="*60)
    print()

    env_content = f"""# Zehrs MCP Server Configuration
# Generated from HAR file on {Path(har_file).name}

ZEHRS_BEARER_TOKEN={credentials['bearer_token'] or 'YOUR_TOKEN_HERE'}
ZEHRS_CUSTOMER_ID={credentials['customer_id'] or 'YOUR_CUSTOMER_ID_HERE'}
ZEHRS_CART_ID={credentials['cart_id'] or 'YOUR_CART_ID_HERE'}
ZEHRS_STORE_ID={credentials['store_id'] or '1234'}
"""

    print(env_content)

    # Offer to write .env file
    env_file = Path(__file__).parent / ".env"

    if env_file.exists():
        response = input(f"\n.env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Skipping .env file creation.")
            return

    with open(env_file, 'w') as f:
        f.write(env_content)

    print(f"\n✅ Credentials written to {env_file}")
    print("\n⚠️  Important Notes:")
    print("  - Bearer tokens expire (usually within hours)")
    print("  - You'll need to re-extract credentials when the token expires")
    print("  - Never commit .env file to version control")
    print("  - These credentials grant full access to your Zehrs account")


if __name__ == "__main__":
    main()
