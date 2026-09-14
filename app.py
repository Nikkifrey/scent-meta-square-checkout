import os
import uuid
import requests
from flask import Flask, request, redirect, jsonify

app = Flask(__name__)

SQUARE_ACCESS_TOKEN = os.environ["SQUARE_ACCESS_TOKEN"]
SQUARE_LOCATION_ID = os.environ["SQUARE_LOCATION_ID"]

SQUARE_VERSION = os.environ.get(
    "SQUARE_VERSION",
    "2026-08-19"
)

SQUARE_BASE_URL = os.environ.get(
    "SQUARE_BASE_URL",
    "https://connect.squareup.com"
)

HEADERS = {
    "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Square-Version": SQUARE_VERSION,
}


def parse_products(raw):
    """
    Instagram sends products like:

    PRODUCT_ID:1,PRODUCT_ID:2

    Returns a list of:
    (product_id, quantity)
    """

    if not raw:
        raise ValueError("Missing products parameter.")

    products = []

    for part in raw.split(","):
        part = part.strip()

        if not part:
            continue

        pieces = part.rsplit(":", 1)

        if len(pieces) != 2:
            raise ValueError(
                f"Invalid product entry: {part}"
            )

        product_id = pieces[0].strip()

        try:
            quantity = int(pieces[1])
        except ValueError:
            raise ValueError(
                f"Invalid quantity for product: {product_id}"
            )

        if not product_id:
            raise ValueError(
                "Product ID cannot be empty."
            )

        if quantity < 1:
            raise ValueError(
                f"Quantity must be at least 1 for {product_id}"
            )

        products.append(
            (product_id, quantity)
        )

    if not products:
        raise ValueError(
            "No valid products supplied."
        )

    return products


def get_square_catalog_object(object_id):
    """
    Ask Square directly for the catalog object.
    """

    response = requests.get(
        f"{SQUARE_BASE_URL}/v2/catalog/object/{object_id}",
        headers=HEADERS,
        timeout=20
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.json().get("object")


def find_variation_for_item(item):
    """
    Find a usable variation belonging to a Square item.
    """

    item_data = item.get("item_data", {})

    variations = item_data.get(
        "variations",
        []
    )

    usable = []

    for variation in variations:
        if variation.get("is_deleted"):
            continue

        if variation.get("type") != "ITEM_VARIATION":
            continue

        variation_data = variation.get(
            "item_variation_data",
            {}
        )

        if variation_data.get("sellable") is False:
            continue

        if variation_data.get("location_overrides"):
            usable.append(variation)
        else:
            usable.append(variation)

    if len(usable) == 1:
        return usable[0]

    if len(usable) > 1:
        # If there are multiple variations, prefer
        # the first sellable variation with a price.
        priced = []

        for variation in usable:
            variation_data = variation.get(
                "item_variation_data",
                {}
            )

            price_money = variation_data.get(
                "price_money"
            )

            if price_money:
                priced.append(variation)

        if len(priced) == 1:
            return priced[0]

        raise LookupError(
            "Square item has multiple variations. "
            "Instagram sent the item ID instead of "
            "a specific variation ID."
        )

    raise LookupError(
        "Square item has no usable variation."
    )


def resolve_catalog_variation(product_id):
    """
    Convert the ID Instagram sends into the
    Square catalog variation ID needed for checkout.
    """

    obj = get_square_catalog_object(product_id)

    if not obj:
        return None

    object_type = obj.get("type")

    # Instagram sent a Square variation ID.
    if object_type == "ITEM_VARIATION":
        return obj

    # Instagram sent a Square item ID.
    if object_type == "ITEM":
        return find_variation_for_item(obj)

    return None


def create_square_checkout(products):
    """
    Build a Square payment link from Instagram's cart.
    """

    line_items = []

    for product_id, quantity in products:

        variation = resolve_catalog_variation(
            product_id
        )

        if not variation:
            raise LookupError(
                f"Instagram product ID "
                f"{product_id} could not be matched "
                f"to a Square catalog item."
            )

        line_items.append({
            "quantity": str(quantity),
            "catalog_object_id": variation["id"]
        })

    body = {
        "idempotency_key": str(uuid.uuid4()),
        "order": {
            "location_id": SQUARE_LOCATION_ID,
            "line_items": line_items
        }
    }

    response = requests.post(
        f"{SQUARE_BASE_URL}/v2/online-checkout/payment-links",
        headers=HEADERS,
        json=body,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    payment_link = data.get(
        "payment_link",
        {}
    )

    checkout_url = payment_link.get(
        "long_url"
    )

    if not checkout_url:
        raise LookupError(
            "Square did not return a checkout URL."
        )

    return checkout_url


@app.get("/")
def home():
    return (
        "The SCENT & Market Co. "
        "Meta → Square checkout bridge is running."
    ), 200


@app.get("/checkout")
def checkout():

    try:

        raw_products = request.args.get(
            "products",
            ""
        )

        products = parse_products(
            raw_products
        )

        checkout_url = create_square_checkout(
            products
        )

        return redirect(
            checkout_url,
            code=302
        )

    except requests.HTTPError as error:

        try:
            detail = error.response.json()
        except Exception:
            detail = str(error)

        return jsonify({
            "error": "Square API error",
            "detail": detail
        }), 502

    except (ValueError, LookupError) as error:

        return jsonify({
            "error": str(error)
        }), 400

    except Exception as error:

        return jsonify({
            "error": "Unexpected error",
            "detail": str(error)
        }), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                "8080"
            )
        )
    )
