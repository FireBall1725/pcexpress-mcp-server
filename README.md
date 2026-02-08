# PC Express MCP Server

> **Unofficial** Model Context Protocol (MCP) server for PC Express / Loblaws grocery shopping

Control your grocery cart with AI! This MCP server enables LLMs (like Claude) to search past orders, find products, and manage your shopping cart across all Loblaws-owned grocery banners.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

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

Since there's no public API, you need to extract credentials from your browser session:

#### Method 1: HAR File Export (Recommended)

1. Visit your banner's website (e.g., www.zehrs.ca)
2. Log in to your account
3. Open DevTools (F12) → **Network** tab
4. ✅ Check "Preserve log"
5. Clear network log
6. Navigate to your cart and past orders
7. Right-click in Network tab → **"Save all as HAR with content"**
8. Run the credential extractor:
   ```bash
   python extract_credentials.py path/to/file.har
   ```

This automatically creates your `.env` file!

#### Method 2: Manual Extraction

See [SETUP.md](SETUP.md) for detailed manual extraction instructions.

### Environment Variables

```bash
# OAuth Bearer Token (expires after a few hours)
PCEXPRESS_BEARER_TOKEN=your_bearer_token_here

# Your customer/user ID
PCEXPRESS_CUSTOMER_ID=your_customer_id_here

# Your active cart ID
PCEXPRESS_CART_ID=your_cart_id_here

# Store ID (4-digit code)
PCEXPRESS_STORE_ID=your_store_id_here

# Banner: zehrs, loblaws, nofrills, superstore, independent, tandt
PCEXPRESS_BANNER=zehrs
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
        PCEXPRESS_BEARER_TOKEN: "your_token"
        PCEXPRESS_CUSTOMER_ID: "your_id"
        PCEXPRESS_CART_ID: "your_cart"
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
        "PCEXPRESS_BEARER_TOKEN": "your_token",
        "PCEXPRESS_CUSTOMER_ID": "your_id",
        "PCEXPRESS_CART_ID": "your_cart",
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
        "PCEXPRESS_BEARER_TOKEN": "your_token",
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
- **[SETUP.md](SETUP.md)** - Detailed configuration instructions
- **[BANNERS.md](BANNERS.md)** - Multi-banner usage guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture details
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute

## ⚠️ Known Limitations

### 1. Token Expiration

**Problem**: Bearer tokens expire after a few hours

**Impact**: Server stops working when token expires

**Workaround**: Re-extract credentials from browser session

**Status**: ❌ Not solved - Long-term authentication not yet implemented

See [#1 - Implement automatic token refresh](https://github.com/YOUR_USERNAME/pcexpress-mcp-server/issues/1)

### 2. Product Search Limitations

**Problem**: Type-ahead search only returns category suggestions, not actual products

**Impact**: Can't directly get product codes for adding to cart

**Workaround**: Use past orders to find product codes

**Status**: 🔍 Investigating alternative endpoints

### 3. Cart ID Changes

**Problem**: Cart ID may change on logout/login

**Impact**: Server needs cart ID updated

**Workaround**: Re-extract credentials

**Status**: ⚠️ Needs cart merging implementation

### 4. No Official API

**Problem**: Using reverse-engineered, undocumented API

**Impact**: May break if Loblaws changes their API

**Workaround**: Monitor for changes, update accordingly

**Status**: ⚠️ Inherent limitation

### 5. Store-Specific Inventory

**Problem**: Product availability varies by store location

**Impact**: Search results depend on selected store

**Workaround**: Ensure correct `PCEXPRESS_STORE_ID` is set

**Status**: ✅ Expected behavior

## 🐛 Troubleshooting

### "401 Unauthorized"

**Cause**: Token expired or invalid

**Fix**: Re-extract credentials from browser

### "404 Not Found"

**Cause**: Cart/Customer ID changed or wrong banner

**Fix**: Verify `PCEXPRESS_BANNER` matches token source, re-extract IDs

### "No products found"

**Cause**: Store doesn't carry product or wrong store ID

**Fix**: Verify `PCEXPRESS_STORE_ID` is correct

### Tests fail

**Cause**: Missing dependencies or invalid credentials

**Fix**:
```bash
pip install -r requirements.txt
python extract_credentials.py your_file.har
```

See full troubleshooting guide in [SETUP.md](SETUP.md)

## 🗺️ Roadmap

### High Priority

- [ ] Automatic token refresh (#1)
- [ ] Full product search (not just type-ahead) (#2)
- [ ] Cart ID change detection (#3)
- [ ] Better error messages (#4)

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
