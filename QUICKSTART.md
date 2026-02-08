# Quick Start Guide - 5 Minutes to Grocery Shopping AI

## Step 1: Install Dependencies (30 seconds)

```bash
cd /Users/areed/temp/zehrs
pip install -r requirements.txt
```

## Step 2: Add Your Bearer Token (1 minute)

From your earlier curl command, you have this token:
```
eyJ4NXQjUzI1NiI6InFsakhobXpIS0prMm5uN2F2bHNqVGp4cHJVR0hFQ1h1MXdIUHEwVk94SW8i...
```

Edit `.env` file and replace `YOUR_TOKEN_HERE` with your actual token:

```bash
# Option 1: Use a text editor
nano .env

# Option 2: Use sed (be careful with special chars in token!)
# sed -i '' 's/YOUR_TOKEN_HERE/your_actual_token_here/' .env
```

Your `.env` should look like:
```env
ZEHRS_BEARER_TOKEN=eyJ4NXQjUzI1NiI6InFsakhobXpIS0prMm5uN2F2bHNqVGp4cHJVR0hFQ1h1MXdIUHEwVk94SW8i...
ZEHRS_CUSTOMER_ID=your_customer_id_here
ZEHRS_CART_ID=your_cart_id_here
ZEHRS_STORE_ID=1234
```

## Step 3: Test It Works (30 seconds)

```bash
python test_api.py
```

You should see:
```
✅ Success! Found 18 online orders
✅ Success! Found 7 suggestions
✅ Success! Cart ID: your_cart_id_here
✅ All tests passed!
```

If you get errors, see the [Troubleshooting](#troubleshooting) section below.

## Step 4: Start the MCP Server (10 seconds)

```bash
python zehrs_mcp_server.py
```

The server is now running and waiting for MCP client connections!

## Step 5: Connect from Claude Desktop (Optional)

If you want to test with Claude Desktop:

1. Edit your Claude Desktop config:
   - **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%/Claude/claude_desktop_config.json`

2. Add this configuration:
```json
{
  "mcpServers": {
    "zehrs": {
      "command": "python3",
      "args": ["/Users/areed/temp/zehrs/zehrs_mcp_server.py"],
      "env": {
        "ZEHRS_BEARER_TOKEN": "your_token_here",
        "ZEHRS_CUSTOMER_ID": "your_customer_id_here",
        "ZEHRS_CART_ID": "your_cart_id_here",
        "ZEHRS_STORE_ID": "1234"
      }
    }
  }
}
```

3. Restart Claude Desktop

4. Test with: "Can you search my past Zehrs orders for ice cream?"

## Example Queries to Try

Once connected to an MCP client (Claude Desktop, Home Assistant, etc.):

### Past Orders
- "What did I order from Zehrs last week?"
- "Show me my recent grocery orders"
- "What was in order 531900018513724?"

### Product Search
- "Search for ice cream at Zehrs"
- "Find organic bananas"
- "Look for coffee"

### Cart Operations
- "Add ice cream to my cart"
- "What's in my Zehrs cart?"
- "Remove product 21657456_EA from cart"
- "Add 3 units of product 20143653_EA"

### Smart Shopping
- "I want to buy milk - what did I buy last time?"
- "Add the same items from my last order"
- "Search for greek yogurt and add it to cart"

## Troubleshooting

### ❌ "Missing required credentials"
- Make sure `.env` file exists in the project directory
- Check that you replaced `YOUR_TOKEN_HERE` with your actual token
- Verify no extra spaces or quotes around the token

### ❌ "401 Unauthorized"
- Your bearer token has expired (they last a few hours)
- Get a new token:
  1. Log in to https://www.zehrs.ca
  2. Open DevTools (F12) → Network tab
  3. Navigate to your cart
  4. Find request to `api.pcexpress.ca/pcx-bff/api/v1/carts/`
  5. Copy `Authorization: Bearer <TOKEN>` header
  6. Update `.env` file

### ❌ "404 Not Found"
- Your cart ID might have changed
- Export a new HAR file:
  1. Clear browser cache/cookies
  2. Log in fresh
  3. Navigate cart and orders
  4. Export HAR
  5. Run: `python extract_credentials.py ~/Downloads/www.zehrs.ca.har`

### ❌ Import errors
```bash
# Make sure you're in the right directory
cd /Users/areed/temp/zehrs

# Reinstall dependencies
pip install -r requirements.txt
```

### ❌ "No module named 'mcp'"
```bash
# The MCP package might not be available via pip yet
# Install from source or use the version in requirements.txt
pip install --upgrade mcp
```

## Token Refresh Needed?

Your token will expire! When it does:

**Option 1: Quick Manual Update**
1. Open https://www.zehrs.ca and log in
2. DevTools → Network → Find API request
3. Copy new Bearer token
4. Update `.env` file

**Option 2: Re-export HAR**
1. Export new HAR file with fresh session
2. Run: `python extract_credentials.py new_file.har`
3. Automatically updates `.env`

## Next Steps

- ✅ Server running? Great!
- 📱 Integrate with Home Assistant for voice control
- 🤖 Build custom automation workflows
- 🛒 Never forget items again!

## Files You Created

```
/Users/areed/temp/zehrs/
├── .env                      # Your credentials (NEVER commit!)
├── .env.example              # Template
├── .gitignore                # Git safety
├── extract_credentials.py    # HAR → credentials
├── mcp_config_example.json   # Claude Desktop config
├── PROJECT_SUMMARY.md        # What we built
├── QUICKSTART.md            # This file
├── README.md                # Full documentation
├── requirements.txt         # Python packages
├── SETUP.md                 # Detailed setup
├── test_api.py              # Test your credentials
└── zehrs_mcp_server.py      # The MCP server ⭐
```

## Support

Need help?
1. Check `SETUP.md` for detailed instructions
2. Read `PROJECT_SUMMARY.md` for architecture
3. Review logs from `test_api.py`
4. Make sure token hasn't expired

---

**You're ready to go!** 🚀

Your AI can now:
- ✅ Search your past orders
- ✅ Find products
- ✅ Manage your cart
- ✅ Help you shop smarter

Just remember to refresh the token when it expires!
