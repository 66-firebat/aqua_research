"""
JLCPCB Official API Client
=========================

Python client for JLCPCB's official API with authentication support.
Uses only standard library - no external dependencies required.

API Documentation: https://api.jlcpcb.com
Authentication: HMAC-SHA256 signature

Usage:
    # With credentials from SecretKey.csv
    from jlcpcb_client import JLCPCBClient, load_credentials
    
    creds = load_credentials("SecretKey.csv")
    client = JLCPCBClient(access_key=creds["access_key"], secret_key=creds["secret_key"])
    
    # Search components (public API, no auth required)
    results = client.search_components("STM32")
    
    # Get live pricing (public API)
    pricing = client.get_live_pricing("C17976")
"""

import csv
import hashlib
import hmac
import json
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from http.client import HTTPResponse
from typing import Any, Optional


class JLCAPIAuth:
    """
    HMAC-SHA256 authentication for JLCPCB API.
    
    The signature is computed as:
    HMAC-SHA256(secret_key, timestamp + method + path + body)
    """

    def __init__(self, access_key: str, secret_key: str, timestamp: Optional[str] = None):
        self.access_key = access_key
        self.secret_key = secret_key
        self.timestamp = timestamp or self._generate_timestamp()

    @staticmethod
    def _generate_timestamp() -> str:
        """Generate ISO8601 timestamp."""
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _create_signature(self, method: str, path: str, body: str = "") -> str:
        """
        Create HMAC-SHA256 signature.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., /v1/components/search)
            body: Request body as string (empty for GET requests)
            
        Returns:
            Hex-encoded signature
        """
        message = f"{self.timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def get_headers(self, method: str = "GET", path: str = "/", body: str = "") -> dict:
        """
        Generate authentication headers for API request.
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body
            
        Returns:
            Dictionary of headers including authentication
        """
        signature = self._create_signature(method, path, body)
        return {
            "X-Access-Key": self.access_key,
            "X-Timestamp": self.timestamp,
            "X-Signature": signature,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


def make_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    data: Optional[bytes] = None,
    params: Optional[dict] = None,
    timeout: int = 30
) -> tuple[int, dict, bytes]:
    """
    Make HTTP request using urllib.
    
    Returns:
        Tuple of (status_code, headers_dict, body_bytes)
    """
    headers = dict(headers) if headers else {}
    headers["User-Agent"] = "Mozilla/5.0 (compatible; JLCPCB-API-Client/1.0)"
    
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            resp_headers = dict(response.headers)
            body = response.read()
            return status, resp_headers, body
    except urllib.error.HTTPError as e:
        status = e.code
        resp_headers = dict(e.headers)
        body = e.read() if e.fp else b""
        return status, resp_headers, body
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request failed: {e.reason}")


class JLCPCBClient:
    """
    Client for JLCPCB API.
    
    Supports:
    - Component search and information (public endpoints)
    - Real-time pricing and inventory (public endpoints)
    - Authenticated API operations (requires credentials)
    """

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize JLCPCB client.
        
        Args:
            access_key: API access key (from SecretKey.csv)
            secret_key: API secret key (from SecretKey.csv)
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        
        self.auth = None
        if access_key and secret_key:
            self.auth = JLCAPIAuth(access_key, secret_key)
        
        self._authenticated_base = "https://api.jlcpcb.com"
        self._public_base = "https://jlcpcb.com"
        self._live_api_base = "https://wmsc.lcsc.com"

    def _make_authenticated_request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None
    ) -> dict[str, Any]:
        """
        Make authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Query parameters
            json_data: JSON body
            
        Returns:
            API response as dict
            
        Raises:
            RuntimeError: If no authentication credentials provided
        """
        if not self.auth:
            raise RuntimeError("Authentication required for this operation. Provide access_key and secret_key.")
        
        body = json.dumps(json_data).encode() if json_data else b""
        headers = self.auth.get_headers(method, path, body.decode() if body else "")
        
        url = f"{self._authenticated_base}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        
        status, _, response_body = make_request(
            method, url, headers=headers, data=body, timeout=self.timeout
        )
        
        if status >= 400:
            raise RuntimeError(f"API error ({status}): {response_body.decode()}")
        
        return json.loads(response_body)

    def _make_public_request(
        self,
        method: str,
        url: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make public API request (no authentication)."""
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        
        if json_data:
            body = json.dumps(json_data).encode()
            status, _, response_body = make_request(
                method, url, headers=headers, data=body, timeout=self.timeout
            )
        else:
            if params:
                url = f"{url}?{urllib.parse.urlencode(params)}"
            status, _, response_body = make_request(
                method, url, headers=headers, timeout=self.timeout
            )
        
        if status >= 400:
            raise RuntimeError(f"API error ({status}): {response_body.decode()}")
        
        return json.loads(response_body)

    def search_components(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
        in_stock_only: bool = False,
        basic_only: bool = False
    ) -> list[dict[str, Any]]:
        """
        Search for components in JLCPCB catalog.
        
        Uses public API endpoint - no authentication required.
        
        Args:
            query: Search term (part number, description, etc.)
            page: Page number (1-indexed)
            page_size: Results per page (max 50)
            in_stock_only: Only show in-stock components
            basic_only: Only show basic parts (no assembly fee)
            
        Returns:
            List of component dictionaries
        """
        request_body = {
            "keyword": query,
            "currentPage": page,
            "pageSize": min(page_size, 50),
            "searchType": 2,
        }
        
        if in_stock_only:
            request_body["presaleType"] = "stock"
        
        if basic_only:
            request_body["componentLibTypes"] = ["base"]
            request_body["preferredComponentFlag"] = True
        
        url = f"{self._public_base}/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2"
        
        data = self._make_public_request("POST", url, json_data=request_body)
        
        if data.get("code") != 200:
            raise RuntimeError(f"API error: {data.get('message', 'Unknown error')}")
        
        components = data.get("data", {}).get("componentPageInfo", {}).get("list", [])
        
        return [self._parse_component(c) for c in components]

    def _parse_component(self, raw: dict) -> dict[str, Any]:
        """Parse raw component data into standardized format."""
        return {
            "lcsc": raw.get("componentCode", ""),
            "mfr_part": raw.get("componentModelEn", ""),
            "manufacturer": raw.get("componentBrandEn", ""),
            "package": raw.get("componentSpecificationEn", ""),
            "description": raw.get("describe", ""),
            "stock": raw.get("stockCount", 0),
            "prices": raw.get("componentPrices", []),
            "library_type": "basic" if raw.get("componentLibraryType") == "base" else "extended",
            "datasheet_url": raw.get("dataManualUrl"),
            "product_url": raw.get("lcscGoodsUrl"),
        }

    def get_live_pricing(self, lcsc: str) -> Optional[dict[str, Any]]:
        """
        Get live pricing and stock data for a component.
        
        Uses public API - no authentication required.
        
        Args:
            lcsc: JLCPCB part number (with or without 'C' prefix)
            
        Returns:
            Dictionary with live pricing data or None if not found
        """
        lcsc = lcsc.upper()
        if not lcsc.startswith("C"):
            lcsc = f"C{lcsc}"
        
        url = f"{self._live_api_base}/ftps/wm/product/detail"
        params = {"productCode": lcsc}
        
        try:
            status, _, response_body = make_request("GET", url, params=params, timeout=self.timeout)
        except Exception:
            return None
        
        if status == 404:
            return None
        
        if status >= 400:
            return None
        
        data = json.loads(response_body)
        
        if data.get("code") != 200:
            return None
        
        result = data.get("result", {})
        
        return {
            "lcsc": lcsc,
            "stock": result.get("stockNumber", 0),
            "pricing": [
                {"qty": p.get("ladder", 0), "price": p.get("usdPrice", 0)}
                for p in result.get("productPriceList", [])
            ],
            "datasheet": result.get("pdfUrl"),
            "specifications": result.get("paramVOList", []),
        }

    def get_component_by_lcsc(self, lcsc: str) -> Optional[dict[str, Any]]:
        """
        Get component details by LCSC number.
        
        Combines search API with live pricing data.
        
        Args:
            lcsc: JLCPCB part number
            
        Returns:
            Component details or None if not found
        """
        lcsc = lcsc.upper().lstrip("C")
        results = self.search_components(lcsc, page_size=1)
        
        if not results:
            return None
        
        component = results[0]
        
        live_data = self.get_live_pricing(component["lcsc"])
        if live_data:
            component["live_stock"] = live_data["stock"]
            component["live_pricing"] = live_data["pricing"]
        
        return component

    def get_categories(self) -> list[dict[str, str]]:
        """
        Get all component categories.
        
        Returns:
            List of category dictionaries with id and name
        """
        url = f"{self._public_base}/api/overseas-pcb-order/v1/shoppingCart/smtGood/getCategory"
        
        data = self._make_public_request("GET", url)
        return data.get("data", [])

    def get_packages(self, category: Optional[str] = None) -> list[str]:
        """
        Get available package types.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of package type strings
        """
        request_body = {}
        if category:
            request_body["categoryName"] = category
        
        url = f"{self._public_base}/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentPackage"
        
        data = self._make_public_request("POST", url, json_data=request_body)
        return data.get("data", [])

    def print_component(self, component: dict, show_price: bool = True) -> None:
        """Pretty print component information."""
        print(f"\n{'='*60}")
        print(f"LCSC: {component.get('lcsc', 'N/A')}")
        print(f"Part:  {component.get('mfr_part', 'N/A')}")
        print(f"Mfr:   {component.get('manufacturer', 'N/A')}")
        print(f"Pkg:   {component.get('package', 'N/A')}")
        print(f"Type:  {component.get('library_type', 'N/A').upper()}")
        print(f"Stock: {component.get('stock', 0):,}")
        
        if show_price and component.get("prices"):
            print("\nPricing:")
            for p in component["prices"][:5]:
                print(f"  {p.get('startNumber', 1)}+ : ${p.get('productPrice', 'N/A')}")
        
        if component.get("description"):
            print(f"\nDesc:  {component['description'][:100]}")

    def print_live_pricing(self, data: dict) -> None:
        """Pretty print live pricing data."""
        print(f"\n{'='*60}")
        print(f"LCSC: {data.get('lcsc', 'N/A')}")
        print(f"Stock: {data.get('stock', 0):,}")
        
        if data.get("pricing"):
            print("\nPricing Tiers:")
            for p in data["pricing"]:
                print(f"  {p['qty']:,}+ : ${p['price']:.4f}")
        
        if data.get("datasheet"):
            print(f"\nDatasheet: {data['datasheet']}")


def load_credentials(filepath: str) -> dict[str, str]:
    """
    Load API credentials from CSV file.
    
    Expected format (from SecretKey.csv):
        Accesskey,89c3c93d031d42aab34bc70578a89bb4
        SecretKey,ayYupTloQf3HIIgiCeLuk3whb53UvX1g
    
    Args:
        filepath: Path to credentials CSV file
        
    Returns:
        Dictionary with 'access_key' and 'secret_key'
    """
    credentials = {}
    
    with open(filepath, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row.get("Accesskey", row.get("AccessKey", row.get("accesskey", "")))
            value = row.get("SecretKey", row.get("secretkey", row.get("Secretkey", "")))
            
            if key and value:
                if "access" in key.lower():
                    credentials["access_key"] = value
                elif "secret" in key.lower():
                    credentials["secret_key"] = value
    
    if "access_key" not in credentials or "secret_key" not in credentials:
        raise ValueError("Could not find both AccessKey and SecretKey in file")
    
    return credentials


def demo():
    """Demo function showing basic usage."""
    print("JLCPCB API Client Demo")
    print("=" * 60)
    
    client = JLCPCBClient()
    
    print("\n1. Searching for 'STM32 microcontrollers'...")
    try:
        results = client.search_components("STM32", page_size=5, basic_only=True)
        print(f"Found {len(results)} components")
        for comp in results[:3]:
            client.print_component(comp)
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n2. Getting live pricing for C17976 (NE555)...")
    try:
        pricing = client.get_live_pricing("C17976")
        if pricing:
            client.print_live_pricing(pricing)
        else:
            print("No pricing data found")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n3. Getting component details for C12345...")
    try:
        comp = client.get_component_by_lcsc("C12345")
        if comp:
            client.print_component(comp)
        else:
            print("Component not found")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="JLCPCB API Client")
    parser.add_argument("command", choices=["demo", "search", "price"], 
                        help="Command to execute")
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--lcsc", "-l", help="LCSC part number")
    parser.add_argument("--creds", "-c", default="SecretKey.csv",
                        help="Path to credentials file")
    parser.add_argument("--basic", "-b", action="store_true",
                        help="Only show basic parts")
    
    args = parser.parse_args()
    
    if args.command == "demo":
        demo()
    elif args.command == "search":
        client = JLCPCBClient()
        results = client.search_components(
            args.query or "capacitor",
            basic_only=args.basic
        )
        print(f"Found {len(results)} components:")
        for comp in results:
            client.print_component(comp)
    elif args.command == "price":
        if not args.lcsc:
            print("Error: --lcsc required for price command")
        else:
            client = JLCPCBClient()
            pricing = client.get_live_pricing(args.lcsc)
            if pricing:
                client.print_live_pricing(pricing)
            else:
                print(f"Could not find pricing for {args.lcsc}")
