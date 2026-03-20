# JLCPCB API Client - Development Notes | 23MAR2026

## Overview

This document contains the development notes and discoveries from building a Python client for JLCPCB's component API.

---

## Initial Setup

### Exploring the JLCPCB API

**Website:** https://open.jlcpcb.com

The official JLCPCB API at `api.jlcpcb.com` requires:
- Application approval (not guaranteed)
- AccessKey and SecretKey credentials
- HMAC-SHA256 authentication

**Existing credentials:** Found in `SecretKey.csv`

```csv
Accesskey,89c3c93d031d42aab34bc70578a89bb4
SecretKey,ayYupTloQf3HIIgiCeLuk3whb53UvX1g
```

---

## API Discovery Process

### Research Sources

The official API documentation requires approved access. Instead, discovered the API structure through open-source projects:

1. **`@jlcpcb/core`** (TypeScript) - GitHub: l3wi/jlc-cli
   - URL: `https://raw.githubusercontent.com/l3wi/jlc-cli/main/packages/core/src/api/jlc.ts`

2. **`jlcpcb-search-mcp`** (Python) - GitHub: peterb154/jlcpcb-search-mcp
   - URL: `https://raw.githubusercontent.com/peterb154/jlcpcb-search-mcp/main/src/jlcpcb_mcp/server.py`

3. **JLCSearch API** (Community) - jlcsearch.tscircuit.com
   - Free, no auth required
   - Good for basic component lookups

### Discovered API Endpoints

#### Component Search (Public - No Auth Required)

```python
POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2
```

**Request Body:**
```python
{
    "keyword": "STM32",
    "currentPage": 1,
    "pageSize": 20,
    "searchType": 2,
}
```

**Optional Filters:**
```python
{
    "presaleType": "stock",              # In-stock only
    "componentLibTypes": ["base"],        # Basic parts only
    "preferredComponentFlag": True,
}
```

**Response Structure:**
```json
{
    "code": 200,
    "data": {
        "componentPageInfo": {
            "total": 42,
            "list": [
                {
                    "componentCode": "C8734",
                    "componentModelEn": "STM32F103C8T6",
                    "componentBrandEn": "STMicroelectronics",
                    "componentSpecificationEn": "LQFP-48(7x7)",
                    "stockCount": 186654,
                    "describe": "...",
                    "componentPrices": [...],
                    "componentLibraryType": "base" or "expand",
                    "dataManualUrl": "...",
                    "lcscGoodsUrl": "..."
                }
            ]
        }
    }
}
```

#### Live Pricing API (Public - No Auth Required)

```python
GET https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=C17976
```

**Response:**
```json
{
    "code": 200,
    "result": {
        "stockNumber": 215200,
        "productPriceList": [
            {"ladder": 100, "usdPrice": 0.0044},
            {"ladder": 1000, "usdPrice": 0.0035}
        ],
        "pdfUrl": "https://datasheet.lcsc.com/...",
        "paramVOList": [...]
    }
}
```

#### Authentication (For Official API)

HMAC-SHA256 signature required:

```python
import hmac
import hashlib
from datetime import datetime

class JLCAPIAuth:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _create_signature(self, method: str, path: str, body: str = "") -> str:
        message = f"{self.timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def get_headers(self, method: str, path: str, body: str = "") -> dict:
        return {
            "X-Access-Key": self.access_key,
            "X-Timestamp": self.timestamp,
            "X-Signature": self._create_signature(method, path, body),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
```

---

## Code Structure

### File: `jlcpcb_client.py`

**Key Classes:**

1. **`JLCAPIAuth`** - Handles HMAC-SHA256 authentication
2. **`JLCPCBClient`** - Main API client

**Key Methods:**

| Method | Auth Required | Description |
|--------|--------------|-------------|
| `search_components()` | No | Search JLCPCB catalog |
| `get_live_pricing()` | No | Real-time stock/pricing |
| `get_component_by_lcsc()` | No | Full component details |
| `get_categories()` | No | List all categories |

### Safe Navigation Pattern

```python
# Chain .get() calls to safely traverse nested dicts
data.get("data", {}).get("componentPageInfo", {}).get("list", [])

# Equivalent to:
# data["data"]["componentPageInfo"]["list"]
# But returns [] instead of raising KeyError if any key is missing
```

### Headers Setup

Standard JSON API headers:

```python
headers = {
    "User-Agent": "Mozilla/5.0 (compatible; JLCPCB-API-Client/1.0)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
```

**Why these headers?**
- `Content-Type`: Tells server we're sending JSON
- `Accept`: We want JSON back
- `User-Agent`: Identifies our client, prevents blocking

### Request Body Encoding

```python
# Dict to JSON to bytes
body = json.dumps(request_body).encode()

# Example:
# {"keyword": "5007"} → '{"keyword": "5007"}' → b'{"keyword": "5007"}'
```

---

## Usage Examples

### Basic Usage (No Auth Required)

```python
from jlcpcb_client import JLCPCBClient

client = JLCPCBClient()

# Search components
results = client.search_components("STM32", basic_only=True)

# Get live pricing
pricing = client.get_live_pricing("C17976")

# Print results
for comp in results:
    client.print_component(comp)
```

### With Credentials

```python
from jlcpcb_client import JLCPCBClient, load_credentials

creds = load_credentials("SecretKey.csv")
client = JLCPCBClient(**creds)

# Now authenticated endpoints are available
```

### CLI Usage

```bash
# Demo
python3 jlcpcb_client.py demo

# Search
python3 jlcpcb_client.py search -q "5007"

# Get pricing
python3 jlcpcb_client.py price -l C17976
```

---

## Static Methods

### What is `@staticmethod`?

A method that doesn't receive `self` as an argument:

```python
class JLCAPIAuth:
    @staticmethod
    def _generate_timestamp() -> str:
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# Can be called directly:
ts = JLCAPIAuth._generate_timestamp()

# Or from instance:
self._generate_timestamp()
```

**Why use it?**
- Utility function that doesn't need class/instance state
- Grouped logically within class namespace
- Equivalent to module-level function

---

## Session Persistence

### Option 1: Environment Variables

```bash
export JLPCB_ACCESS_KEY="your_key"
export JLPCB_SECRET_KEY="your_secret"
```

```python
import os
access_key = os.environ.get("JLPCB_ACCESS_KEY")
secret_key = os.environ.get("JLPCB_SECRET_KEY")
```

### Option 2: JSON Config File

Create `~/.jlcpcb_config.json`:
```json
{
    "access_key": "89c3c93d...",
    "secret_key": "ayYupTlo..."
}
```

```python
import json
from pathlib import Path

config = json.loads(Path.home() / ".jlcpcb_config.json")
client = JLCPCBClient(**config)
```

### Option 3: CSV (Existing)

Uses existing `SecretKey.csv`:
```python
from jlcpcb_client import load_credentials
creds = load_credentials("SecretKey.csv")
```

---

## Flow: `python3 jlcpcb_client.py search -q "5007"`

1. **`if __name__ == "__main__"`** - Entry point
2. **`argparse`** - Parse args: `command="search"`, `query="5007"`
3. **`elif command == "search"`** - Route to search handler
4. **`JLCPCBClient()`** - Create client (no credentials)
5. **`client.search_components("5007")`** - Call search method
6. **Build `request_body`** - Create JSON payload
7. **`_make_public_request("POST", url, json_data=request_body)`** - Make HTTP request
8. **`json.dumps().encode()`** - Convert dict to bytes
9. **`urllib.request.Request()`** - Create request object
10. **`urllib.request.urlopen()`** - Send request, get response
11. **`json.loads(response_body)`** - Parse JSON response
12. **`_parse_component()`** - Transform each component
13. **`print_component()`** - Output formatted results

---

## Key Takeaways

1. **Public APIs exist** - Component search and pricing don't require auth
2. **Open-source is valuable** - Found API structure from community projects
3. **Safe navigation** - Use `.get()` for nested dict access
4. **Standard headers** - `Content-Type`, `Accept`, `User-Agent`
5. **HMAC auth** - For future official API access with credentials

---

## Files Created

| File | Description |
|------|-------------|
| `jlcpcb_client.py` | Main API client (uses only stdlib) |
| `jlcpcb_lookup.py` | Original community-based lookup |
| `jlcpcb_lookup_mod.py` | Modified version of original |
| `jlcpcb_csv_lookup.py` | Batch CSV lookup tool |
| `SecretKey.csv` | API credentials (do not commit) |

---

## Useful Links

- JLCPCB API Portal: https://api.jlcpcb.com
- Community Search: https://jlcsearch.tscircuit.com
- TypeScript Client: https://github.com/l3wi/jlc-cli
- Python MCP Server: https://github.com/peterb154/jlcpcb-search-mcp
- KiCad Plugin: https://github.com/bouni/kicad-jlcpcb-tools
