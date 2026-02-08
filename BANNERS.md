# Multi-Banner Support

The PC Express MCP Server works across all Loblaws-owned grocery banners that use the PC Express platform!

## Supported Banners

| Banner | Code | Website | Notes |
|--------|------|---------|-------|
| **Zehrs** | `zehrs` | www.zehrs.ca | Ontario-based |
| **Loblaws** | `loblaws` | www.loblaws.ca | Main banner |
| **No Frills** | `nofrills` | www.nofrills.ca | Discount banner |
| **Real Canadian Superstore** | `superstore` | www.realcanadiansuperstore.ca | Western Canada |
| **Your Independent Grocer** | `independent` | www.yourindependentgrocer.ca | Franchise stores |
| **T&T Supermarket** | `tandt` | www.tntsupermarket.com | Asian supermarket |

## How It Works

All these banners use the same backend API (`api.pcexpress.ca`) with just a few differences:

1. **Banner Header**: `Site-Banner: {banner}`
2. **Origin/Referer**: Points to the banner's website
3. **API Paths**: Include banner name in URLs (e.g., `/ecommerce/v2/zehrs/...`)

The server automatically handles these differences based on the `PCEXPRESS_BANNER` environment variable!

## Using a Different Banner

### Step 1: Get Credentials for Your Banner

1. Visit your banner's website (e.g., www.nofrills.ca)
2. Log in to your account
3. Open DevTools (F12) → Network tab
4. Navigate to your cart
5. Export HAR file or copy credentials

### Step 2: Update .env File

```bash
# Example for No Frills
PCEXPRESS_BEARER_TOKEN=your_token_here
PCEXPRESS_CUSTOMER_ID=your_customer_id
PCEXPRESS_CART_ID=your_cart_id
PCEXPRESS_STORE_ID=your_store_id
PCEXPRESS_BANNER=nofrills
```

### Step 3: Test

```bash
python test_api.py
```

You should see:
```
Testing PC Express API Client
Banner: nofrills
...
```

## Banner-Specific Notes

### Zehrs (Ontario)
- **Banner Code**: `zehrs`
- **Store ID Example**: your_store_id
- **Default in project**: Yes

### Loblaws
- **Banner Code**: `loblaws`
- **Store ID Example**: Various across Canada
- **Note**: Main flagship banner

### No Frills
- **Banner Code**: `nofrills`
- **Note**: Budget-focused banner, same API

### Real Canadian Superstore
- **Banner Code**: `superstore`
- **Region**: Primarily Western Canada
- **Note**: Larger format stores

### Independent
- **Banner Code**: `independent`
- **Note**: Franchise stores, may have different inventory

### T&T Supermarket
- **Banner Code**: `tandt`
- **Specialty**: Asian groceries
- **Note**: Different product selection

## Finding Your Store ID

Each store has a unique ID. To find yours:

1. Log in to your banner's website
2. Select your preferred store
3. Open DevTools → Network → Find API requests
4. Look for `storeId` parameter in request bodies
5. Common format: 4-digit number (e.g., 1234, 5678)

## Token Compatibility

**Important**: Tokens are banner-specific!

- A token from `www.zehrs.ca` only works with `PCEXPRESS_BANNER=zehrs`
- A token from `www.nofrills.ca` only works with `PCEXPRESS_BANNER=nofrills`

You cannot use a Zehrs token to access No Frills cart (and vice versa).

## Multiple Banners

Want to use multiple banners? Create separate MCP server instances:

### Option 1: Multiple .env Files

```bash
# .env.zehrs
PCEXPRESS_BANNER=zehrs
PCEXPRESS_BEARER_TOKEN=...
PCEXPRESS_CUSTOMER_ID=...
PCEXPRESS_CART_ID=...

# .env.nofrills
PCEXPRESS_BANNER=nofrills
PCEXPRESS_BEARER_TOKEN=...
PCEXPRESS_CUSTOMER_ID=...
PCEXPRESS_CART_ID=...
```

Load with: `python -c "from dotenv import load_dotenv; load_dotenv('.env.zehrs')"`

### Option 2: Multiple MCP Server Entries

In Claude Desktop config:

```json
{
  "mcpServers": {
    "zehrs": {
      "command": "python3",
      "args": ["/path/to/pcexpress_mcp_server.py"],
      "env": {
        "PCEXPRESS_BANNER": "zehrs",
        "PCEXPRESS_BEARER_TOKEN": "...",
        ...
      }
    },
    "nofrills": {
      "command": "python3",
      "args": ["/path/to/pcexpress_mcp_server.py"],
      "env": {
        "PCEXPRESS_BANNER": "nofrills",
        "PCEXPRESS_BEARER_TOKEN": "...",
        ...
      }
    }
  }
}
```

Then you can ask:
- "Add milk to my Zehrs cart"
- "What's in my No Frills cart?"

## Testing Different Banners

```bash
# Test Zehrs
PCEXPRESS_BANNER=zehrs python test_api.py

# Test No Frills
PCEXPRESS_BANNER=nofrills python test_api.py

# Test Superstore
PCEXPRESS_BANNER=superstore python test_api.py
```

## API Endpoint Structure

The banner name appears in API paths:

```
# Zehrs
GET /ecommerce/v2/zehrs/customers/historical-orders

# No Frills
GET /ecommerce/v2/nofrills/customers/historical-orders

# Loblaws
GET /ecommerce/v2/loblaws/customers/historical-orders
```

The server handles this automatically based on `PCEXPRESS_BANNER`.

## Cross-Banner Compatibility

**What works across banners:**
- ✅ Same API structure
- ✅ Same authentication method (Oracle IDCS)
- ✅ Same static API key
- ✅ Same cart operations
- ✅ Same product search format

**What's different per banner:**
- ❌ Bearer tokens (banner-specific)
- ❌ Customer accounts (separate per banner)
- ❌ Shopping carts (one per banner)
- ❌ Order history (separate per banner)
- ❌ Product availability (varies by store/banner)
- ❌ Pricing (may differ between banners)

## Why This Matters

**For Users:**
- Shop at multiple Loblaws banners with one MCP server
- Switch banners by changing one environment variable
- Use same voice commands across different stores

**For Developers:**
- Generic codebase works for all banners
- Easy to extend to new Loblaws acquisitions
- Single API client for entire Loblaws ecosystem

## Troubleshooting

### "404 Not Found" on order history
- Check that `PCEXPRESS_BANNER` matches where you got the token
- Verify you have orders at that banner

### "401 Unauthorized"
- Token might be from a different banner
- Token expired (get new one)

### Different products in search
- Each banner has different inventory
- Store selection affects product availability
- Some products are banner-exclusive

## Future Banners

If Loblaws launches new banners or acquires new chains, adding support is easy:

1. Add banner code to `BANNER_DOMAINS` dict in `pcexpress_mcp_server.py`
2. Get credentials from new banner's website
3. Set `PCEXPRESS_BANNER` to new code
4. Test!

---

**Pro Tip**: Price compare by running searches across multiple banners! No Frills often has lower prices than Loblaws for the same items.
