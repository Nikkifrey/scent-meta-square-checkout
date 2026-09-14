import os
import uuid
import json
import requests
from flask import Flask, request, redirect, jsonify

app = Flask(__name__)

SQUARE_ACCESS_TOKEN = os.environ["SQUARE_ACCESS_TOKEN"]
SQUARE_LOCATION_ID = os.environ["SQUARE_LOCATION_ID"]
SQUARE_VERSION = os.environ.get("SQUARE_VERSION", "2026-08-19")
SQUARE_BASE_URL = os.environ.get("SQUARE_BASE_URL", "https://connect.squareup.com")
SQUARE_BASE_URL = os.environ.get(
    "SQUARE_BASE_URL",
    "https://connect.squareup.com"
)

HEADERS = {
    "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}",
@@ -20,34 +23,74 @@
with open("product_map.json", "r", encoding="utf-8") as f:
    PRODUCTS = json.load(f)

PRODUCTS_BY_SKU = {str(p["sku"]).strip().upper(): p for p in PRODUCTS if p.get("sku")}
# Meta is sending the "token" from the Square catalog export as its Content ID.
# We also keep SKU support in case Meta sends a SKU for any product.
PRODUCTS_BY_TOKEN = {
    str(p["token"]).strip().upper(): p
    for p in PRODUCTS
    if p.get("token")
}

PRODUCTS_BY_SKU = {
    str(p["sku"]).strip().upper(): p
    for p in PRODUCTS
    if p.get("sku")
}


def resolve_product(identifier):
    key = identifier.strip().upper()

    if key in PRODUCTS_BY_TOKEN:
        return PRODUCTS_BY_TOKEN[key]

    if key in PRODUCTS_BY_SKU:
        return PRODUCTS_BY_SKU[key]

    raise LookupError(
        f"Product ID not found in exported Square catalog: {identifier}"
    )


def parse_products(raw):
    if not raw:
        raise ValueError("Missing products parameter.")

    parsed = []

    for entry in raw.split(","):
        entry = entry.strip()

        if not entry:
            continue

        parts = entry.rsplit(":", 1)

        if len(parts) != 2:
            raise ValueError(f"Invalid product entry: {entry}")

        sku = parts[0].strip()
        identifier = parts[0].strip()

        try:
            qty = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid quantity for SKU {sku}")
            raise ValueError(
                f"Invalid quantity for product {identifier}"
            )

        if qty < 1:
            raise ValueError(f"Quantity must be at least 1 for SKU {sku}")
            raise ValueError(
                f"Quantity must be at least 1 for product {identifier}"
            )

        if sku.upper() not in PRODUCTS_BY_SKU:
            raise LookupError(f"SKU not found in exported Square catalog: {sku}")
        product = resolve_product(identifier)

        sku = str(product.get("sku", "")).strip()

        if not sku:
            raise LookupError(
                f"Square SKU missing for product: {identifier}"
            )

        parsed.append((sku, qty))

@@ -69,24 +112,36 @@
        "limit": 10
    }

    r = requests.post(
    response = requests.post(
        f"{SQUARE_BASE_URL}/v2/catalog/search",
        headers=HEADERS,
        json=payload,
        timeout=20
    )
    r.raise_for_status()

    response.raise_for_status()

    matches = []
    for obj in r.json().get("objects", []):

    for obj in response.json().get("objects", []):
        variation_data = obj.get("item_variation_data", {})
        if str(variation_data.get("sku", "")).strip().upper() == sku.upper():

        found_sku = str(
            variation_data.get("sku", "")
        ).strip().upper()

        if found_sku == sku.upper():
            matches.append(obj)

    if not matches:
        raise LookupError(f"Square could not find SKU: {sku}")
        raise LookupError(
            f"Square could not find SKU: {sku}"
        )

    if len(matches) > 1:
        raise LookupError(f"More than one Square variation uses SKU: {sku}")
        raise LookupError(
            f"More than one Square variation uses SKU: {sku}"
        )

    return matches[0]

@@ -96,6 +151,7 @@

    for sku, qty in products:
        variation = find_square_variation_by_sku(sku)

        line_items.append({
            "quantity": str(qty),
            "catalog_object_id": variation["id"]
@@ -109,42 +165,63 @@
        }
    }

    r = requests.post(
    response = requests.post(
        f"{SQUARE_BASE_URL}/v2/online-checkout/payment-links",
        headers=HEADERS,
        json=body,
        timeout=20
    )
    r.raise_for_status()

    return r.json()["payment_link"]["long_url"]
    response.raise_for_status()

    return response.json()["payment_link"]["long_url"]


@app.get("/")
def home():
    return f"Meta → Square checkout bridge is running. Catalog contains {len(PRODUCTS_BY_SKU)} SKUs.", 200
    return (
        "Meta → Square checkout bridge is running. "
        f"Catalog contains {len(PRODUCTS_BY_TOKEN)} product IDs "
        f"and {len(PRODUCTS_BY_SKU)} SKUs."
    ), 200


@app.get("/checkout")
def checkout():
    try:
        products = parse_products(request.args.get("products", ""))
        products = parse_products(
            request.args.get("products", "")
        )

        checkout_url = create_checkout(products)

        return redirect(checkout_url, code=302)

    except requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = str(e)
        return jsonify({"error": "Square API error", "detail": detail}), 502

        return jsonify({
            "error": "Square API error",
            "detail": detail
        }), 502

    except (ValueError, LookupError) as e:
        return jsonify({"error": str(e)}), 400
        return jsonify({
            "error": str(e)
        }), 400

    except Exception as e:
        return jsonify({"error": "Unexpected error", "detail": str(e)}), 500
        return jsonify({
            "error": "Unexpected error",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080"))
    )
