"""
JLCPCB API Integration - Python Examples
=========================================
Two sections:
  1. JLCSearch API  - free, no auth, queries JLCPCB's component library
  2. JLCPCB Ordering API - requires approved API credentials (template/skeleton)

Dependencies: pip install requests
"""

import requests
import json
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: JLCSearch API (free, no auth required)
# Base URL: https://jlcsearch.tscircuit.com
# Docs:     https://docs.tscircuit.com/web-apis/jlcsearch-api
# ─────────────────────────────────────────────────────────────────────────────

JLCSEARCH_BASE = "https://jlcsearch.tscircuit.com"


def search_components(query: str, package: Optional[str] = None, limit: int = 10) -> list[dict]:
    """
    Full-text search across all JLCPCB components.

    Args:
        query:   Search term (e.g. "STM32", "LM358", "555 timer")
        package: Optional footprint filter (e.g. "SOIC-8", "0402")
        limit:   Max results to return (default 10)

    Returns:
        List of component dicts with lcsc, mfr, package, description, stock, price
    """
    params = {"q": query, "limit": limit, "full": "true"}
    if package:
        params["package"] = package

    response = requests.get(f"{JLCSEARCH_BASE}/api/search", params=params)
    response.raise_for_status()
    return response.json().get("components", [])


def list_resistors(resistance: Optional[str] = None, package: Optional[str] = None) -> list[dict]:
    """
    List resistors with optional filters.

    Args:
        resistance: e.g. "10k", "100R", "4.7k"
        package:    e.g. "0402", "0603", "0805"
    """
    params = {}
    if resistance:
        params["resistance"] = resistance
    if package:
        params["package"] = package

    response = requests.get(f"{JLCSEARCH_BASE}/resistors/list.json", params=params)
    response.raise_for_status()
    return response.json().get("components", [])


def list_capacitors(capacitance: Optional[str] = None, package: Optional[str] = None) -> list[dict]:
    """List capacitors with optional filters (e.g. capacitance='100nF', package='0402')"""
    params = {}
    if capacitance:
        params["capacitance"] = capacitance
    if package:
        params["package"] = package

    response = requests.get(f"{JLCSEARCH_BASE}/capacitors/list.json", params=params)
    response.raise_for_status()
    return response.json().get("components", [])


def get_categories() -> list[dict]:
    """Return all top-level categories and subcategories in the JLCPCB library."""
    response = requests.get(f"{JLCSEARCH_BASE}/categories/list.json")
    response.raise_for_status()
    return response.json().get("categories", [])


def print_components(components: list[dict], max_show: int = 5) -> None:
    """Pretty-print a component list."""
    for i, c in enumerate(components[:max_show]):
        print(f"  [{i+1}] LCSC: C{c.get('lcsc')} | {c.get('mfr','N/A')} | "
              f"{c.get('package','?')} | Stock: {c.get('stock',0)} | "
              f"Price: ${c.get('price','?')} | {c.get('description','')[:60]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: JLCPCB Ordering API (requires approved credentials)
# Base URL: https://api.jlcpcb.com  (confirm in your approved docs)
# Auth:     Bearer token in Authorization header
# Apply at: https://api.jlcpcb.com
# ─────────────────────────────────────────────────────────────────────────────

JLCPCB_API_BASE = "https://api.jlcpcb.com"  # confirm exact base URL in your docs


class JLCPCBClient:
    """
    Client for the JLCPCB Ordering API.
    Requires approved API credentials from https://api.jlcpcb.com

    Usage:
        client = JLCPCBClient(api_key="your_key_here")
        quote  = client.get_pcb_quote(gerber_id="abc123", layers=2, quantity=10)
    """

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def upload_gerber(self, gerber_path: str) -> str:
        """
        Upload a Gerber zip file and return the file ID for quoting.

        Args:
            gerber_path: Local path to your .zip Gerber file

        Returns:
            file_id string to use in subsequent quote/order calls
        """
        with open(gerber_path, "rb") as f:
            response = self.session.post(
                f"{JLCPCB_API_BASE}/file/upload",
                files={"file": (gerber_path, f, "application/zip")},
                headers={"Content-Type": None},  # let requests set multipart header
            )
        response.raise_for_status()
        data = response.json()
        file_id = data["fileId"]
        print(f"Gerber uploaded. File ID: {file_id}")
        return file_id

    def get_pcb_quote(
        self,
        file_id: str,
        layers: int = 2,
        quantity: int = 5,
        thickness: float = 1.6,
        color: str = "green",
        surface_finish: str = "HASL",
    ) -> dict:
        """
        Request a PCB price quote.

        Args:
            file_id:        ID returned from upload_gerber()
            layers:         Number of copper layers (2, 4, 6...)
            quantity:       Number of PCBs
            thickness:      Board thickness in mm (e.g. 1.6)
            color:          Soldermask color (green, red, blue, black, white, yellow)
            surface_finish: HASL, HASL(lead-free), ENIG, OSP

        Returns:
            Quote dict including price, lead time, etc.
        """
        payload = {
            "fileId": file_id,
            "layers": layers,
            "quantity": quantity,
            "thickness": thickness,
            "soldermaskColor": color,
            "surfaceFinish": surface_finish,
        }
        response = self.session.post(f"{JLCPCB_API_BASE}/pcb/quote", json=payload)
        response.raise_for_status()
        return response.json()

    def place_order(self, quote_id: str, shipping_address: dict) -> dict:
        """
        Place an order using a confirmed quote.

        Args:
            quote_id:         ID from get_pcb_quote() response
            shipping_address: Dict with name, address, city, country, zip, phone

        Returns:
            Order confirmation dict including order_id
        """
        payload = {
            "quoteId": quote_id,
            "shippingAddress": shipping_address,
        }
        response = self.session.post(f"{JLCPCB_API_BASE}/order/create", json=payload)
        response.raise_for_status()
        return response.json()

    def get_order_status(self, order_id: str) -> dict:
        """
        Check the status of an existing order.

        Args:
            order_id: ID returned from place_order()

        Returns:
            Dict with status, tracking number (once shipped), timestamps, etc.
        """
        response = self.session.get(f"{JLCPCB_API_BASE}/order/status/{order_id}")
        response.raise_for_status()
        return response.json()


# ─────────────────────────────────────────────────────────────────────────────
# DEMO — runs immediately with no credentials
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 60)
    print("1. Searching for STM32 microcontrollers in SOIC-28 package")
    print("=" * 60)
    results = search_components("STM32", package="SOIC-28", limit=5)
    print_components(results)

    print("\n" + "=" * 60)
    print("2. Listing 10kΩ resistors in 0402 package")
    print("=" * 60)
    resistors = list_resistors(resistance="10k", package="0402")
    print_components(resistors)

    print("\n" + "=" * 60)
    print("3. Listing 100nF capacitors in 0402 package")
    print("=" * 60)
    caps = list_capacitors(capacitance="100nF", package="0402")
    print_components(caps)

    print("\n" + "=" * 60)
    print("4. Fetching component categories")
    print("=" * 60)
    cats = get_categories()
    for cat in cats[:8]:
        print(f"  - {cat}")

    print("\n" + "=" * 60)
    print("5. Ordering API (skeleton — requires approved credentials)")
    print("=" * 60)
    print("""
    # Uncomment and fill in your API key to use the ordering flow:

    # client = JLCPCBClient(api_key="YOUR_API_KEY")

    # Step 1 — Upload your Gerber zip
    # file_id = client.upload_gerber("my_board.zip")

    # Step 2 — Get a quote
    # quote = client.get_pcb_quote(
    #     file_id=file_id,
    #     layers=2,
    #     quantity=10,
    #     color="black",
    #     surface_finish="ENIG",
    # )
    # print(json.dumps(quote, indent=2))

    # Step 3 — Place the order
    # order = client.place_order(
    #     quote_id=quote["quoteId"],
    #     shipping_address={
    #         "name": "Jane Smith",
    #         "address": "123 Main St",
    #         "city": "Albuquerque",
    #         "state": "NM",
    #         "country": "US",
    #         "zip": "87101",
    #         "phone": "+15055550000",
    #     }
    # )
    # print("Order placed:", order["orderId"])

    # Step 4 — Track it
    # status = client.get_order_status(order["orderId"])
    # print("Status:", status)
    """)
