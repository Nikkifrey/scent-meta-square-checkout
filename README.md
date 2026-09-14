# The SCENT & Market Co. — Meta → Square Checkout Bridge

Built from the Square catalog export supplied by the user.

Catalog mapping included: 200 SKUs.

Meta can call:

`https://YOUR-HOST/checkout?products=SKU1:1,SKU2:2`

The bridge:
1. Checks that each incoming SKU exists in the exported Square catalog.
2. Looks up the live Square catalog variation by SKU.
3. Creates a Square-hosted checkout.
4. Redirects the shopper to Square.

## Private environment variables required on the host

- `SQUARE_ACCESS_TOKEN`
- `SQUARE_LOCATION_ID`

Optional:
- `SQUARE_VERSION=2026-08-19`
- `SQUARE_BASE_URL=https://connect.squareup.com`

Do not put the Square access token into the code or send it in screenshots.

## Start command

`gunicorn -b 0.0.0.0:$PORT app:app`

## Meta Step 3

After this is deployed, enter only:

`https://YOUR-HOST/checkout`

Meta will append the `products=` values automatically.
