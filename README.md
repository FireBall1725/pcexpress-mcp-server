# PC Express MCP Server

> **Unofficial** Model Context Protocol (MCP) server for PC Express / Loblaws grocery shopping

Control your grocery cart with AI! This MCP server enables LLMs (like Claude) to search past orders, find products, and manage your shopping cart across all Loblaws-owned grocery banners.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **How the auth was cracked:** the login sits behind Akamai bot detection, so the OAuth flow was reverse-engineered out of Loblaw's Android app. If you want the emulator-and-mitmproxy story behind `pcid_config.py`, read the write-up: [Reverse-engineering PC Express](https://fireball1725.ca/articles/reverse-engineering-pc-express-oauth-secret).

## ⚠️ Important Disclaimers

- **Unofficial**: This project is NOT affiliated with, endorsed by, or supported by Loblaws Companies Limited, PC Express, or any related entities
- **Use at Your Own Risk**: This uses an undocumented API that may change without notice
- **No Warranty**: See [LICENSE](LICENSE) for details
- **Educational Purpose**: This project demonstrates API reverse engineering and MCP server development

## 🛒 Supported Grocery Banners

Works with all PC Express enabled stores:

- **Zehrs** - Ontario-based grocery chain
- **Loblaws** - Main flagship banner
- **No Frills** - Discount grocery banner
- **Real Canadian Superstore** - Western Canada supermarket
- **Your Independent Grocer** - Franchise stores
- **T&T Supermarket** - Asian specialty supermarket

## ✨ Features

### MCP Tools (6)

1. **search_past_orders** - Find items from your order history
2. **get_order_items** - Get detailed product list from specific orders
3. **search_products** - Search the product catalog
4. **add_to_cart** - Add products to your shopping cart
5. **remove_from_cart** - Remove items from cart
6. **view_cart** - See current cart contents

### Integration Ready

- ✅ **Home Assistant** - Voice-controlled grocery shopping
- ✅ **Claude Desktop** - Chat with your grocery list
- ✅ **Custom Clients** - Any MCP-compatible application

### Voice Assistant Examples

```
🎤 "Add ice cream to my grocery cart"
🎤 "What did I order last week?"
🎤 "Search for organic bananas"
🎤 "What's in my cart?"
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Active account with a PC Express enabled banner
- pip or pip3

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/pcexpress-mcp-server.git
   cd pcexpress-mcp-server
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials (see Configuration section)
   ```

4. **Test the connection**
   ```bash
   python test_api.py
   ```

5. **Run the server**
   ```bash
   python pcexpress_mcp_server.py
   ```

## ⚙️ Configuration

### Getting Your Credentials

Authentication uses the PC Express app's OAuth flow. You sign in once in a real browser to
get a refresh token; after that the server mints access tokens on its own and never needs
another manual login. See [AUTH_NOTES.md](AUTH_NOTES.md) for how it works, and
[DEPLOYMENT.md](DEPLOYMENT.md) for running it locally, in Docker, Home Assistant, or Kubernetes.

**Easiest:** run the setup wizard; it logs you in and writes the config for wherever you run it:

```bash
python setup.py
```

The manual steps below are the same thing, done by hand.

#### One-time login

```bash
python login_pcid.py
```

It opens your browser to the PC ID sign-in. After you log in, the page tries to open a
`com.loblaw.pcx://...` link and shows an error; that is expected. Copy that full address
from the address bar and paste it back into the script. It prints your `PCEXPRESS_REFRESH_TOKEN`.
The app client secret is baked into the code, so you don't supply it.

#### Automated login (optional, no paste)

If you'd rather not paste anything, `login_pcid_auto.py` drives a browser for you:

```bash
pip install -r requirements-auto.txt && python -m playwright install chromium
PCEXPRESS_CLIENT_SECRET=... PCEXPRESS_EMAIL=you@example.com PCEXPRESS_PASSWORD=... \
    python login_pcid_auto.py
```

It logs in and prints the same two values. It runs a **headed** browser (Akamai blocks
headless), so run it on a machine with a display, or under `xvfb-run` on a headless box.
Accounts with 2FA can't be automated; use the manual `login_pcid.py` for those. Either way,
the browser is used only for this one-time step; the server never runs a browser.

Your cart id and customer id are read from your profile at runtime, so you don't set them.

### Environment Variables

```bash
# Refresh token from the one-time login above (server rotates/persists it after first use)
PCEXPRESS_REFRESH_TOKEN=your_refresh_token_here

# Writable dir for the rotated token + cached access token; must persist across restarts
PCEXPRESS_STATE_DIR=~/.pcexpress-mcp

# Banner: zehrs, loblaws, nofrills, superstore, independent, tandt
PCEXPRESS_BANNER=zehrs

# Store ID (4-digit code)
PCEXPRESS_STORE_ID=your_store_id_here

# Optional: cart id is auto-discovered; set only to force a specific cart.
# PCEXPRESS_CART_ID=your_cart_id_here
# Optional: the app client secret is baked in; set only to override it.
# PCEXPRESS_CLIENT_SECRET=your_client_secret_here
```

## 🔌 Platform Integration

### Home Assistant

```yaml
# configuration.yaml
mcp:
  servers:
    - name: pcexpress
      command: python3
      args:
        - /path/to/pcexpress_mcp_server.py
      env:
        PCEXPRESS_REFRESH_TOKEN: "your_refresh_token"
        PCEXPRESS_STATE_DIR: "/config/pcexpress-mcp"
        PCEXPRESS_STORE_ID: "your_store"
        PCEXPRESS_BANNER: "zehrs"
```

### Claude Desktop

Edit your Claude Desktop config:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "pcexpress": {
      "command": "python3",
      "args": ["/path/to/pcexpress_mcp_server.py"],
      "env": {
        "PCEXPRESS_REFRESH_TOKEN": "your_refresh_token",
        "PCEXPRESS_STATE_DIR": "~/.pcexpress-mcp",
        "PCEXPRESS_STORE_ID": "your_store",
        "PCEXPRESS_BANNER": "zehrs"
      }
    }
  }
}
```

Restart Claude Desktop and start chatting about groceries!

### Custom MCP Client

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python3",
    args=["pcexpress_mcp_server.py"],
    env={
        "PCEXPRESS_REFRESH_TOKEN": "your_refresh_token",
        # ... other env vars
    }
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # List available tools
        tools = await session.list_tools()

        # Call a tool
        result = await session.call_tool("search_products", {
            "query": "ice cream"
        })
```

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[SETUP.md](SETUP.md)** - Detailed configuration and login
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Local, Docker, Home Assistant, and Kubernetes
- **[AUTH_NOTES.md](AUTH_NOTES.md)** - How the PC id auth flow works
- **[API_REFERENCE.md](API_REFERENCE.md)** - The pcx-bff endpoints, params, and responses
- **[BANNERS.md](BANNERS.md)** - Multi-banner usage guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture details
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute
- **[Reverse-engineering PC Express](https://fireball1725.ca/articles/reverse-engineering-pc-express-oauth-secret)** - The write-up on getting the OAuth secret out of the app

## ⚠️ Known Limitations

Access-token expiry and cart-id changes used to be the big ones. Both are solved now:
the server refreshes its own tokens (rotating and persisting the single-use refresh
token), and it reads the cart id from your profile at runtime. What's left:

### 1. Product search reliability

**Problem**: Search goes through the banner website's Next.js route, which sits behind
Akamai, so it can be flakier than the authenticated pcx-bff calls.

**Impact**: A search can occasionally fail even when the rest of the API is fine.

**Workaround**: Retry, or use past orders to find product codes.

**Status**: 🔍 The app's token-authenticated `/products/search` route is a candidate replacement.

### 2. No official API

**Problem**: This is a reverse-engineered, undocumented API. Loblaw can change it, or
rotate the app client secret in a future release and break every copy at once.

**Impact**: Things can break without notice.

**Status**: ⚠️ Inherent to the approach.

### 3. Store-specific inventory

**Problem**: Product availability and pricing vary by store and banner.

**Workaround**: Set `PCEXPRESS_STORE_ID` to the store you want.

**Status**: ✅ Expected behaviour.

## 🐛 Troubleshooting

### Auth error / "re-run login_pcid.py"

**Cause**: The refresh token was consumed or revoked. Refresh tokens are single-use, so a
shared token chain (two instances on one token) or a long idle period can break it.

**Fix**: Run `python login_pcid.py` (or `setup.py`) and update `PCEXPRESS_REFRESH_TOKEN`.
A normal expired access token is refreshed automatically and needs nothing from you.

### "404 Not Found"

**Cause**: No orders or cart at that banner, or the wrong `PCEXPRESS_BANNER` code. Cart and
customer ids are read from your profile, so a stale id isn't the cause.

**Fix**: Check `PCEXPRESS_BANNER` is the banner you actually shop.

### "No products found"

**Cause**: Store doesn't carry product or wrong store ID

**Fix**: Verify `PCEXPRESS_STORE_ID` is correct

### Tests fail

**Cause**: Missing dependencies or invalid credentials

**Fix**:
```bash
pip install -r requirements.txt
# if the smoke test reports an auth error, your refresh token expired:
python login_pcid.py
```

See full troubleshooting guide in [SETUP.md](SETUP.md)

## 🗺️ Roadmap

### Done

- [x] Automatic token refresh (no manual token copying)
- [x] Cart id and customer id auto-discovery

### Open

- [ ] Token-authenticated product search (replace the website route)
- [ ] Store id auto-discovery from `homeStore`
- [ ] Better error messages

### Medium Priority

- [ ] Shopping list management
- [ ] PC Optimum points integration
- [ ] Checkout/order placement
- [ ] Product details (images, nutrition, etc.)
- [ ] Price tracking

### Low Priority

- [ ] Multiple banner support in single instance
- [ ] Recipe suggestions based on cart
- [ ] Price comparison across banners

See [Issues](https://github.com/YOUR_USERNAME/pcexpress-mcp-server/issues) for full list.

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Contribution Guide

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly (`python test_api.py`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📜 License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the MCP protocol team at Anthropic
- Inspired by the need for better grocery shopping automation
- Built with reverse-engineering and determination

## ⚖️ Legal

This project is provided for **educational and personal use only**.

- Not affiliated with Loblaws Companies Limited
- Uses undocumented API - use at your own risk
- May violate Terms of Service - check before using
- No warranty or guarantee of functionality
- Author not responsible for any consequences of use

By using this software, you agree to take full responsibility for your usage.

## 📧 Contact

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/pcexpress-mcp-server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/pcexpress-mcp-server/discussions)

---

**Made with ❤️ for better grocery shopping**

*If this project saved you time, consider starring ⭐ the repo!*
