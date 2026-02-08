# 🎉 Project Renamed: Zehrs → PC Express

## What Changed?

The project has been renamed from "Zehrs MCP Server" to **"PC Express MCP Server"** to better reflect its capabilities!

### Why the Change?

The API we're using is `api.pcexpress.ca` - the backend for **ALL** Loblaws grocery banners, not just Zehrs!

This means the same code works for:
- ✅ Zehrs
- ✅ Loblaws
- ✅ No Frills
- ✅ Real Canadian Superstore
- ✅ Independent
- ✅ T&T Supermarket

### What's Different?

#### File Names
- `zehrs_mcp_server.py` → **`pcexpress_mcp_server.py`**
- Server name: `zehrs-mcp` → **`pcexpress-mcp`**
- Class: `ZehrsAPI` → **`PCExpressAPI`**

#### Environment Variables
OLD (❌):
```bash
ZEHRS_BEARER_TOKEN=...
ZEHRS_CUSTOMER_ID=...
ZEHRS_CART_ID=...
ZEHRS_STORE_ID=...
```

NEW (✅):
```bash
PCEXPRESS_BEARER_TOKEN=...
PCEXPRESS_CUSTOMER_ID=...
PCEXPRESS_CART_ID=...
PCEXPRESS_STORE_ID=...
PCEXPRESS_BANNER=zehrs  # NEW: Specify which banner!
```

### Migration Steps (If You Already Set Up)

If you already had the old version running, here's how to migrate:

1. **Rename environment variables** in `.env`:
   ```bash
   sed -i '' 's/ZEHRS_/PCEXPRESS_/g' .env
   # Add banner line
   echo "PCEXPRESS_BANNER=zehrs" >> .env
   ```

2. **Update imports** if you're using the API directly:
   ```python
   # Old
   from zehrs_mcp_server import ZehrsAPI

   # New
   from pcexpress_mcp_server import PCExpressAPI
   ```

3. **Update MCP config** (Claude Desktop, Home Assistant, etc.):
   ```json
   {
     "mcpServers": {
       "pcexpress": {
         "command": "python3",
         "args": ["/path/to/pcexpress_mcp_server.py"],
         "env": {
           "PCEXPRESS_BEARER_TOKEN": "...",
           "PCEXPRESS_BANNER": "zehrs"
         }
       }
     }
   }
   ```

4. **Run test** to verify:
   ```bash
   python test_api.py
   ```

### What Stayed the Same?

- ✅ API functionality
- ✅ MCP tools (search_past_orders, add_to_cart, etc.)
- ✅ Authentication method
- ✅ All features work exactly the same
- ✅ Your tokens and credentials are still valid

### New Features

With the rename, you now get:

1. **Multi-Banner Support**: Use with any Loblaws banner
2. **Banner Configuration**: `PCEXPRESS_BANNER` env variable
3. **Automatic Domain Mapping**: Server picks the right website for each banner
4. **Documentation**: See `BANNERS.md` for full banner list and usage

### For New Users

If this is your first time using the server, you don't need to do anything special!

Just follow the `QUICKSTART.md` guide and you're good to go.

### Questions?

- **"Will my Zehrs credentials still work?"** Yes! Just set `PCEXPRESS_BANNER=zehrs`
- **"Do I need new tokens?"** No, your existing tokens work fine
- **"Can I use multiple banners?"** Yes! See `BANNERS.md` for details
- **"Will this work with my Home Assistant setup?"** Yes, just update the env vars

### Benefits of the Rename

1. **More Accurate**: Reflects the actual API being used
2. **More Useful**: Anyone with a Loblaws banner can use it
3. **More Maintainable**: Single codebase for all banners
4. **More Discoverable**: People searching for "PC Express API" will find this

---

**Bottom Line**: Same great functionality, now works with 6 grocery chains instead of just 1! 🚀

## Quick Reference

| Old | New |
|-----|-----|
| `zehrs_mcp_server.py` | `pcexpress_mcp_server.py` |
| `ZehrsAPI` | `PCExpressAPI` |
| `ZEHRS_*` | `PCEXPRESS_*` |
| Zehrs only | All Loblaws banners |
| No banner config | `PCEXPRESS_BANNER` variable |
