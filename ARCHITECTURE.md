# Zehrs MCP Server - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface Layer                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                │
│  │ Home         │         │ Claude       │                │
│  │ Assistant    │         │ Desktop      │                │
│  │ Voice AI     │         │ App          │                │
│  └──────┬───────┘         └──────┬───────┘                │
│         │                        │                        │
│         └────────────┬───────────┘                        │
└──────────────────────┼────────────────────────────────────┘
                       │ MCP Protocol (stdio)
                       │
┌──────────────────────▼────────────────────────────────────┐
│              Zehrs MCP Server (Python)                    │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │            MCP Protocol Handler                  │    │
│  │  • list_tools() - Advertise 6 tools             │    │
│  │  • call_tool() - Execute tool requests          │    │
│  │  • stdio_server() - Stdin/stdout transport      │    │
│  └────────────────────┬─────────────────────────────┘    │
│                       │                                   │
│  ┌────────────────────▼─────────────────────────────┐    │
│  │             ZehrsAPI Client                      │    │
│  │  • get_historical_orders()                       │    │
│  │  • get_order_details(order_id)                   │    │
│  │  • search_products(query)                        │    │
│  │  • add_to_cart(product_code, qty)                │    │
│  │  • remove_from_cart(product_code)                │    │
│  │  • get_cart()                                    │    │
│  └────────────────────┬─────────────────────────────┘    │
│                       │                                   │
│  ┌────────────────────▼─────────────────────────────┐    │
│  │          Authentication & Headers                │    │
│  │  • Bearer Token (OAuth JWT)                      │    │
│  │  • Static API Key                                │    │
│  │  • Site Banner: zehrs                            │    │
│  │  • Tenant ID: ONLINE_GROCERIES                   │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
└──────────────────────┬────────────────────────────────────┘
                       │ HTTPS REST API
                       │
┌──────────────────────▼────────────────────────────────────┐
│              api.pcexpress.ca                             │
│              (PC Express Backend)                         │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  /pcx-bff/api/v1/                                        │
│    ├── ecommerce/v2/zehrs/customers/                     │
│    │   ├── historical-orders          [GET]             │
│    │   └── historical-orders/{id}     [GET]             │
│    │                                                     │
│    ├── products/                                         │
│    │   └── type-ahead                 [POST]            │
│    │                                                     │
│    └── carts/{cartId}                                    │
│        ├── (get cart)                 [GET]             │
│        └── ?inventory=true            [POST]            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Data Flow Examples

### Example 1: "Add ice cream to my cart"

```
1. User speaks to Home Assistant
   │
   ▼
2. Voice → Text conversion
   "Add ice cream to my cart"
   │
   ▼
3. LLM processes request → Decides to search products
   │
   ▼
4. MCP Tool Call: search_products
   {
     "query": "ice cream",
     "limit": 7
   }
   │
   ▼
5. ZehrsAPI.search_products("ice cream")
   │
   ▼
6. POST https://api.pcexpress.ca/.../products/type-ahead
   Headers: {
     Authorization: Bearer eyJ...,
     x-apikey: C1xujS...,
     Site-Banner: zehrs
   }
   Body: {
     "term": "ice cream",
     "storeId": "1234",
     "size": 7
   }
   │
   ▼
7. Response: [
     {"suggestion": "Ice Cream"},
     {"suggestion": "Ice Cream Bars"},
     ...
   ]
   │
   ▼
8. LLM also calls: search_past_orders
   to find what user bought before
   │
   ▼
9. LLM combines results and asks:
   "You've bought Chapman's Vanilla 2L before. Add it?"
   │
   ▼
10. User confirms "Yes"
   │
   ▼
11. MCP Tool Call: add_to_cart
   {
     "product_code": "21657456_EA",
     "quantity": 1
   }
   │
   ▼
12. POST https://api.pcexpress.ca/.../carts/{id}?inventory=true
   Body: {
     "entries": {
       "21657456_EA": {
         "quantity": 1,
         "fulfillmentMethod": "pickup",
         "sellerId": "1234"
       }
     }
   }
   │
   ▼
13. Response: {updated cart data}
   │
   ▼
14. LLM confirms: "Added Chapman's Vanilla Ice Cream to your cart!"
```

## Authentication Flow

```
┌──────────────┐
│   Browser    │
│  (User)      │
└──────┬───────┘
       │ 1. Navigate to zehrs.ca
       │
       ▼
┌──────────────┐
│  Zehrs Web   │
│  Frontend    │
└──────┬───────┘
       │ 2. Redirect to login
       │
       ▼
┌─────────────────────────┐
│  Oracle Identity Cloud  │
│  (accounts.pcid.ca)     │
└──────┬──────────────────┘
       │ 3. OAuth 2.0 flow
       │    - Authorization code
       │    - PKCE challenge
       │
       ▼
┌──────────────┐
│   Browser    │
│  (receives)  │
│  JWT token   │
└──────┬───────┘
       │ 4. Extract from DevTools
       │    Authorization: Bearer eyJ...
       │
       ▼
┌──────────────┐
│   .env       │
│   file       │
│  BEARER_     │
│  TOKEN=...   │
└──────┬───────┘
       │ 5. Used by MCP server
       │
       ▼
┌──────────────┐
│  All API     │
│  requests    │
│  include     │
│  this token  │
└──────────────┘
```

## MCP Tools Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP Tools (6)                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ search_past_orders                       │     │
│  │  Input: { limit?: number }               │     │
│  │  Output: List of past orders             │     │
│  │  API: GET /historical-orders             │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ get_order_items                          │     │
│  │  Input: { order_id: string }             │     │
│  │  Output: Order details with items        │     │
│  │  API: GET /historical-orders/{id}        │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ search_products                          │     │
│  │  Input: { query: string, limit?: num }   │     │
│  │  Output: Product suggestions             │     │
│  │  API: POST /products/type-ahead          │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ add_to_cart                              │     │
│  │  Input: { product_code, quantity, ... }  │     │
│  │  Output: Updated cart                    │     │
│  │  API: POST /carts/{id}?inventory=true    │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ remove_from_cart                         │     │
│  │  Input: { product_code: string }         │     │
│  │  Output: Updated cart                    │     │
│  │  API: POST /carts/{id} (qty=0)           │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────┐     │
│  │ view_cart                                │     │
│  │  Input: {}                               │     │
│  │  Output: Current cart contents           │     │
│  │  API: GET /carts/{id}                    │     │
│  └──────────────────────────────────────────┘     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Component Responsibilities

### zehrs_mcp_server.py (Main Server)
**Responsibilities:**
- MCP protocol implementation
- Tool registration and discovery
- Tool invocation routing
- Error handling and logging
- Environment variable loading

**Key Classes:**
- `Server` - MCP server instance
- `ZehrsAPI` - API client wrapper

**Key Functions:**
- `list_tools()` - Returns available tools
- `call_tool()` - Routes tool calls to API methods
- `main()` - Server lifecycle management

### ZehrsAPI Class (API Client)
**Responsibilities:**
- HTTP request construction
- Authentication header injection
- API endpoint abstraction
- Response parsing
- Error propagation

**State:**
- `bearer_token` - User session token
- `customer_id` - User identifier
- `cart_id` - Active shopping cart
- `store_id` - Selected store location
- `banner` - Store banner (zehrs)

### extract_credentials.py (Utility)
**Responsibilities:**
- HAR file parsing
- Credential extraction
- .env file generation
- User guidance

**Extracted Data:**
- Bearer token from Authorization headers
- Customer ID from URL patterns
- Cart ID from URL patterns
- Store ID from request bodies

### test_api.py (Testing)
**Responsibilities:**
- Credential validation
- API endpoint testing
- Integration verification
- User feedback

## Configuration Management

```
┌─────────────────────────────────────────────┐
│          Configuration Sources              │
├─────────────────────────────────────────────┤
│                                             │
│  .env file (primary)                        │
│  ├── ZEHRS_BEARER_TOKEN                     │
│  ├── ZEHRS_CUSTOMER_ID                      │
│  ├── ZEHRS_CART_ID                          │
│  └── ZEHRS_STORE_ID                         │
│                                             │
│  Environment Variables (override)           │
│  └── Same keys as .env                      │
│                                             │
│  Hardcoded Defaults                         │
│  ├── API_KEY (static from HAR analysis)     │
│  ├── BASE_URL                               │
│  ├── BANNER = "zehrs"                       │
│  └── Default store = "1234"                 │
│                                             │
└─────────────────────────────────────────────┘
```

## Error Handling Strategy

```
┌─────────────────────────────────────────────┐
│              Error Types                    │
├─────────────────────────────────────────────┤
│                                             │
│  Authentication Errors (401)                │
│  → Token expired                            │
│  → Return: "Token expired, please refresh"  │
│                                             │
│  Not Found (404)                            │
│  → Cart/Order doesn't exist                 │
│  → Return: Specific error message           │
│                                             │
│  Validation Errors (400)                    │
│  → Invalid product code                     │
│  → Invalid quantity                         │
│  → Return: Validation details               │
│                                             │
│  Network Errors                             │
│  → Connection timeout                       │
│  → DNS failure                              │
│  → Return: Network error message            │
│                                             │
│  Server Errors (500)                        │
│  → Zehrs backend issues                     │
│  → Return: "Service unavailable"            │
│                                             │
└─────────────────────────────────────────────┘
```

## Security Architecture

```
┌─────────────────────────────────────────────┐
│           Security Layers                   │
├─────────────────────────────────────────────┤
│                                             │
│  1. Credential Storage                      │
│     • .env file (not in git)                │
│     • File permissions: 600                 │
│     • No credentials in code                │
│                                             │
│  2. Transport Security                      │
│     • HTTPS only                            │
│     • TLS 1.2+                              │
│     • Certificate validation                │
│                                             │
│  3. Authentication                          │
│     • OAuth 2.0 Bearer tokens               │
│     • Short-lived tokens (hours)            │
│     • No password storage                   │
│                                             │
│  4. API Keys                                │
│     • Static API key (extracted)            │
│     • Per-request injection                 │
│     • Not user-specific                     │
│                                             │
│  5. Input Validation                        │
│     • Type checking                         │
│     • Required field validation             │
│     • Format validation                     │
│                                             │
└─────────────────────────────────────────────┘
```

## Scalability Considerations

### Current Limitations
- **Single User:** One token = one user
- **Single Store:** Hardcoded store ID
- **No Caching:** Every request hits API
- **Synchronous:** Blocking I/O

### Future Enhancements
- **Multi-User:** Token per user
- **Store Selection:** Dynamic store picking
- **Caching:** Redis for order history
- **Async:** AsyncIO for concurrent requests
- **Rate Limiting:** Respect API limits
- **Connection Pooling:** Reuse HTTP connections

## Deployment Options

### Option 1: Local Process
```
Home Assistant → spawns → python zehrs_mcp_server.py
```

### Option 2: System Service
```
systemd service → runs continuously → accepts MCP connections
```

### Option 3: Docker Container
```
Docker container → isolated environment → managed lifecycle
```

### Option 4: Cloud Function
```
AWS Lambda / GCP Function → serverless → on-demand execution
```

## Monitoring & Observability

```
┌─────────────────────────────────────────────┐
│          Observability Strategy             │
├─────────────────────────────────────────────┤
│                                             │
│  Logging (Python logging module)            │
│  • INFO: Tool calls, API requests           │
│  • ERROR: API failures, auth issues         │
│  • DEBUG: Request/response details          │
│                                             │
│  Metrics (Future)                           │
│  • Request count per tool                   │
│  • API latency                              │
│  • Error rate                               │
│  • Token refresh frequency                  │
│                                             │
│  Health Checks (Future)                     │
│  • Token validity                           │
│  • API connectivity                         │
│  • Cart accessibility                       │
│                                             │
└─────────────────────────────────────────────┘
```

---

**Architecture Status:** ✅ Implemented and documented
**Last Updated:** February 8, 2026
