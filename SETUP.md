# Zehrs MCP Server Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Your Bearer Token

You already have the bearer token from your curl command. Copy it from the `Authorization: bearer <TOKEN>` header.

**Important:** The token you provided earlier was:
```
eyJ4NXQjUzI1NiI6InFsakhobXpIS0prMm5uN2F2bHNqVGp4cHJVR0hFQ1h1MXdIUHEwVk94SW8iLCJ4...
```

This token is in your `.env` file as `YOUR_TOKEN_HERE` - you need to replace it with the actual token.

### 3. Update .env File

Edit the `.env` file and replace `YOUR_TOKEN_HERE` with your actual bearer token:

```bash
# The .env file already has these values from the HAR file:
ZEHRS_BEARER_TOKEN=<paste your token here>
ZEHRS_CUSTOMER_ID=your_customer_id_here
ZEHRS_CART_ID=your_cart_id_here
ZEHRS_STORE_ID=1234
```

### 4. Test the API

```bash
python test_api.py
```

This will verify:
- ✅ Your credentials work
- ✅ You can fetch past orders
- ✅ You can search for products
- ✅ You can view your cart

### 5. Run the MCP Server

```bash
python zehrs_mcp_server.py
```

The server will start and listen for MCP protocol messages on stdin/stdout.

## Token Expiration

**Important:** Bearer tokens expire after a few hours. When you see authentication errors:

1. Log in to https://www.zehrs.ca in your browser
2. Open DevTools (F12)
3. Go to Network tab
4. Navigate to your cart
5. Find a request to `api.pcexpress.ca`
6. Copy the new `Authorization: Bearer <TOKEN>` header
7. Update your `.env` file

Or re-export a HAR file and run:
```bash
python extract_credentials.py ~/Downloads/www.zehrs.ca.har
```

## Integration with Home Assistant

### Option 1: Direct MCP Integration

If Home Assistant supports MCP servers directly:

```yaml
# configuration.yaml
mcp:
  servers:
    - name: zehrs
      command: python3
      args:
        - /path/to/zehrs_mcp_server.py
      env:
        ZEHRS_BEARER_TOKEN: "your_token"
        ZEHRS_CUSTOMER_ID: "your_customer_id_here"
        ZEHRS_CART_ID: "your_cart_id_here"
        ZEHRS_STORE_ID: "1234"
```

### Option 2: REST API Wrapper

Create a Flask/FastAPI wrapper that exposes HTTP endpoints:

```python
from flask import Flask, request, jsonify
from zehrs_mcp_server import ZehrsAPI
import os

app = Flask(__name__)
api = ZehrsAPI(
    os.getenv("ZEHRS_BEARER_TOKEN"),
    os.getenv("ZEHRS_CUSTOMER_ID"),
    os.getenv("ZEHRS_CART_ID"),
    os.getenv("ZEHRS_STORE_ID")
)

@app.route('/api/orders/history')
def get_orders():
    return jsonify(api.get_historical_orders())

@app.route('/api/products/search')
def search_products():
    query = request.args.get('q')
    return jsonify(api.search_products(query))

# ... etc
```

Then use Home Assistant's REST integration.

## Voice Assistant Examples

Once integrated with Home Assistant's voice assistant:

**User:** "Add ice cream to the grocery cart"
**Flow:**
1. Voice assistant sends query to LLM
2. LLM uses `search_products` tool with query="ice cream"
3. LLM gets results and can also check `search_past_orders` to find previously purchased ice cream
4. LLM responds: "I found Chapman's Vanilla Ice Cream 2L that you bought last month. Should I add it?"
5. User confirms
6. LLM uses `add_to_cart` with the product code
7. Confirmation sent to user

**User:** "What did I order last week?"
**Flow:**
1. LLM uses `search_past_orders` tool
2. Filters orders from last week
3. Uses `get_order_items` for each order
4. Responds with summary of items

## Troubleshooting

### "Missing required credentials" error
- Make sure `.env` file exists
- Check all environment variables are set
- Token should not be `YOUR_TOKEN_HERE`

### "401 Unauthorized" error
- Your bearer token has expired
- Get a new token (see Token Expiration section)

### "404 Not Found" errors
- Cart ID or Customer ID might have changed
- Re-export HAR file to get latest IDs

### Cart ID keeps changing
- Each time you log out/in, you might get a new cart
- The API should handle cart merging
- Update `ZEHRS_CART_ID` in `.env` if needed

## API Reference

### Search Past Orders
```python
from zehrs_mcp_server import ZehrsAPI

api = ZehrsAPI(token, customer_id, cart_id, store_id)
orders = api.get_historical_orders()

# Returns:
# {
#   "orderHistory": [
#     {
#       "id": "531900018827200",
#       "total": 213.54,
#       "placed": "2026-02-01T15:12:17.000Z",
#       "store": "Zehrs YourStore",
#       ...
#     }
#   ],
#   "onlineOrdersCount": 18,
#   "offlineOrdersCount": 90
# }
```

### Get Order Details
```python
details = api.get_order_details("531900018513724")
# Returns full order with all items
```

### Search Products
```python
results = api.search_products("ice cream", size=7)
# Returns:
# [
#   {"suggestion": "Ice Cream"},
#   {"suggestion": "Ice Cream Bars"},
#   ...
# ]
```

### Add to Cart
```python
cart = api.add_to_cart("21657456_EA", quantity=2, fulfillment_method="pickup")
# Returns updated cart
```

### Remove from Cart
```python
cart = api.remove_from_cart("21657456_EA")
# Same as add_to_cart with quantity=0
```

### View Cart
```python
cart = api.get_cart()
# Returns:
# {
#   "code": "your_cart_id_here",
#   "entries": [
#     {
#       "product": {"name": "...", "code": "..."},
#       "quantity": 2,
#       ...
#     }
#   ]
# }
```

## Next Steps

1. ✅ Get your bearer token
2. ✅ Update `.env` file
3. ✅ Run `test_api.py` to verify
4. ✅ Run the MCP server
5. 🔄 Integrate with Home Assistant
6. 🎤 Test voice commands

## Security Notes

- **Never** commit `.env` file to git (it's in `.gitignore`)
- Tokens grant full access to your Zehrs account
- Keep tokens secure and rotate regularly
- Consider using a secrets manager for production

## Need Help?

- Check the logs: The MCP server logs to stderr
- Test with `test_api.py` first to isolate issues
- Make sure your token hasn't expired
- Verify network connectivity to api.pcexpress.ca

Happy grocery shopping! 🛒
