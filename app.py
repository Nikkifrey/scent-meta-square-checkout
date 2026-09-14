def resolve_product(identifier):
    key = identifier.strip().upper()

    # First try IDs from the exported Square catalog
    if key in PRODUCTS_BY_TOKEN:
        return PRODUCTS_BY_TOKEN[key]

    if key in PRODUCTS_BY_SKU:
        return PRODUCTS_BY_SKU[key]

    # If Instagram sends a live Square catalog object ID,
    # ask Square directly for that object.
    response = requests.get(
        f"{SQUARE_BASE_URL}/v2/catalog/object/{identifier.strip()}",
        headers=HEADERS,
        timeout=20
    )

    if response.status_code == 200:
        obj = response.json().get("object", {})

        if obj.get("type") == "ITEM_VARIATION":
            sku = str(
                obj.get("item_variation_data", {}).get("sku", "")
            ).strip()

            if sku:
                return {
                    "sku": sku,
                    "token": identifier
                }

        if obj.get("type") == "ITEM":
            variations = obj.get("item_data", {}).get("variations", [])

            usable = []

            for variation in variations:
                sku = str(
                    variation.get(
                        "item_variation_data", {}
                    ).get("sku", "")
                ).strip()

                if sku and not variation.get("is_deleted"):
                    usable.append(sku)

            if len(usable) == 1:
                return {
                    "sku": usable[0],
                    "token": identifier
                }

    raise LookupError(
        f"Product ID not found in Square catalog: {identifier}"
    )
