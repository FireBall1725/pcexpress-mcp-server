# Multi-banner support

The server works across every PC Express banner. They share one backend
(`api.pcexpress.ca`) and one identity provider (PC id), so a single login covers all of them.

## Supported banners

| Banner | Code | Website |
| --- | --- | --- |
| Zehrs | `zehrs` | www.zehrs.ca |
| Loblaws | `loblaws` | www.loblaws.ca |
| No Frills | `nofrills` | www.nofrills.ca |
| Real Canadian Superstore | `superstore` | www.realcanadiansuperstore.ca |
| Your Independent Grocer | `independent` | www.yourindependentgrocer.ca |
| T&T Supermarket | `tandt` | www.tntsupermarket.com |

## How it works

The banner changes three things, and the server handles all of them from `PCEXPRESS_BANNER`:
the `Site-Banner` and `baseSiteId` headers, the `Origin` and `Referer`, and the banner segment
in paths like `/ecommerce/v2/{banner}/customers/historical-orders`. Your cart id and customer
id are read from the profile per banner, so you don't set them.

## Switching banners

PC id is one account across every banner, so the refresh token you already have works for all
of them. To point the server at a different banner, change one variable:

```bash
PCEXPRESS_BANNER=nofrills python test_api.py
```

Each banner has its own cart and its own order history under the same account, so switching the
banner switches which cart and orders you see. Set `PCEXPRESS_STORE_ID` to a store that carries
what you want, since availability and pricing vary by store and banner.

## Running two banners at once

Refresh tokens are single-use, so two server instances can't share one token chain. To run,
say, Zehrs and No Frills at the same time, do the login twice to get two independent refresh
tokens, and give each instance its own `PCEXPRESS_STATE_DIR`:

```json
{
  "mcpServers": {
    "zehrs": {
      "command": "python3",
      "args": ["/path/to/pcexpress_mcp_server.py"],
      "env": {
        "PCEXPRESS_BANNER": "zehrs",
        "PCEXPRESS_REFRESH_TOKEN": "first_refresh_token",
        "PCEXPRESS_STATE_DIR": "~/.pcexpress-mcp/zehrs"
      }
    },
    "nofrills": {
      "command": "python3",
      "args": ["/path/to/pcexpress_mcp_server.py"],
      "env": {
        "PCEXPRESS_BANNER": "nofrills",
        "PCEXPRESS_REFRESH_TOKEN": "second_refresh_token",
        "PCEXPRESS_STATE_DIR": "~/.pcexpress-mcp/nofrills"
      }
    }
  }
}
```

Then ask "add milk to my Zehrs cart" or "what's in my No Frills cart?" and the client picks the
matching server.

## Adding a new banner

If Loblaw adds a banner, add its code and website to `BANNER_DOMAINS` in
`pcexpress_mcp_server.py`, set `PCEXPRESS_BANNER` to the new code, and test. The rest of the
code is banner-agnostic.

## Troubleshooting

- **HTTP 404 on order history**: the account has no orders at that banner, or the banner code is
  wrong. The token itself is fine across banners.
- **Different products in search**: inventory and pricing are per store and per banner.
