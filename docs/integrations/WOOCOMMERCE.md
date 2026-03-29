# WooCommerce Integration

> Production-ready WooCommerce connectivity for products, orders, inventory, and signed webhooks.

The `agentic_brain.commerce.WooCommerceAgent` talks directly to the WooCommerce REST API and pairs with `agentic_brain.commerce.webhooks` for secure event ingestion.

---

## What this integration covers

- Product catalogue reads and writes
- Order creation and lifecycle updates
- Inventory adjustments with stock-state safety
- Customer retrieval and creation
- Webhook signature verification with FastAPI routing
- Typed sync helpers for validating WooCommerce payloads

Relevant code:

- `src/agentic_brain/commerce/woocommerce.py`
- `src/agentic_brain/commerce/webhooks.py`
- `tests/integration/test_woocommerce_e2e.py`
- `examples/woocommerce_quickstart.py`

---

## Setup guide

### 1. Install dependencies

```bash
pip install "agentic-brain[test,api]"
```

If you are developing from the repository:

```bash
cd agentic-brain
python3 -m pip install -e ".[test,api]"
```

### 2. Enable the WooCommerce REST API

In WordPress Admin:

1. Open **WooCommerce → Settings → Advanced → REST API**
2. Click **Add key**
3. Give the key a descriptive label such as `agentic-brain-production`
4. Choose a user with the minimum required permissions
5. Set permissions:
   - **Read** for analytics or catalogue sync jobs
   - **Read/Write** for order automation, inventory, or product management
6. Save the generated **Consumer Key** and **Consumer Secret**

### 3. Configure environment variables

```bash
export WOOCOMMERCE_URL="https://store.example.com"
export WOOCOMMERCE_CONSUMER_KEY="ck_xxxxxxxxxxxxxxxxxxxxxxxxx"
export WOOCOMMERCE_CONSUMER_SECRET="cs_xxxxxxxxxxxxxxxxxxxxxxxxx"
export WOOCOMMERCE_WEBHOOK_SECRET="replace-with-strong-random-secret"
```

### 4. Verify connectivity

```python
import asyncio
from agentic_brain.commerce import WooCommerceAgent

async def main() -> None:
    agent = WooCommerceAgent()
    products = await agent.get_products({"per_page": 5})
    print(f"Connected. Retrieved {len(products)} products.")

asyncio.run(main())
```

---

## API credentials configuration

The agent can be configured with constructor arguments or environment variables.

### Constructor-based configuration

```python
from agentic_brain.commerce import WooCommerceAgent

agent = WooCommerceAgent(
    url="https://store.example.com",
    consumer_key="ck_xxxxxxxxxxxxxxxxxxxxxxxxx",
    consumer_secret="cs_xxxxxxxxxxxxxxxxxxxxxxxxx",
    verify_ssl=True,
    timeout=30,
)
```

### Environment-based configuration

```python
from agentic_brain.commerce import WooCommerceAgent

agent = WooCommerceAgent()
```

The environment-backed constructor reads:

- `WOOCOMMERCE_URL`
- `WOOCOMMERCE_CONSUMER_KEY`
- `WOOCOMMERCE_CONSUMER_SECRET`
- `WOOCOMMERCE_WEBHOOK_SECRET` (used by webhook handling)

### Security recommendations

- Use **HTTPS only** for production stores
- Create **separate API keys per environment**
- Restrict keys to the **least privilege** required
- Rotate credentials regularly and after incidents
- Store secrets in a secret manager or deployment environment, never in source control
- Keep `verify_ssl=True` in production

---

## Code examples for common tasks

### List and validate products

```python
import asyncio
from agentic_brain.commerce import WooCommerceAgent

async def main() -> None:
    agent = WooCommerceAgent()
    products = await agent.sync_products({"per_page": 20})

    for product in products:
        print(product.id, product.name, product.price, product.in_stock)

asyncio.run(main())
```

### Search products for sync or support workflows

```python
import asyncio
from agentic_brain.commerce import WooCommerceAgent

async def main() -> None:
    agent = WooCommerceAgent()
    results = await agent.search_products("braille")
    for product in results:
        print(product["sku"], product["name"])

asyncio.run(main())
```

### Create a product

```python
import asyncio
from agentic_brain.commerce import WooCommerceAgent

async def main() -> None:
    agent = WooCommerceAgent()
    created = await agent.create_product(
        {
            "name": "Accessible Keyboard",
            "type": "simple",
            "regular_price": "199.95",
            "price": "199.95",
            "description": "High-contrast keyboard with tactile markers",
            "sku": "AK-100",
            "stock": 12,
            "in_stock": True,
        }
    )
    print(created)

asyncio.run(main())
```

### Update inventory safely

```python
import asyncio
from agentic_brain.commerce import WooCommerceAgent

async def main() -> None:
    agent = WooCommerceAgent()
    updated = await agent.update_inventory(product_id=101, stock=3)
    print(updated["stock"], updated["in_stock"])

asyncio.run(main())
```

### Create and advance an order through its lifecycle

```python
import asyncio
from agentic_brain.commerce import WooCommerceAgent

async def main() -> None:
    agent = WooCommerceAgent()

    order = await agent.create_order(
        {
            "payment_method": "stripe",
            "payment_method_title": "Stripe",
            "billing": {
                "first_name": "John",
                "last_name": "Webber",
                "email": "joseph@example.com",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
            "shipping": {
                "first_name": "John",
                "last_name": "Webber",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
            "line_items": [{"product_id": 101, "quantity": 1}],
        }
    )

    await agent.update_order(order["id"], {"status": "processing", "set_paid": True})
    # Note: "shipped" is not a default WooCommerce status. Use a shipping
    # plugin such as WooCommerce Shipment Tracking, or move straight to
    # "completed" for digital goods and simple fulfilment workflows.
    completed = await agent.update_order(order["id"], {"status": "completed"})
    print(completed["status"])

asyncio.run(main())
```

---

## Webhook setup instructions

`agentic-brain` includes a FastAPI webhook receiver with HMAC verification compatible with WooCommerce.

### 1. Register the webhook route in your FastAPI app

```python
from fastapi import FastAPI
from agentic_brain.commerce.webhooks import register_commerce_webhooks

app = FastAPI()
register_commerce_webhooks(app)
```

This exposes:

- `POST /webhooks/woocommerce`

### 2. Configure the webhook in WooCommerce

In **WooCommerce → Settings → Advanced → Webhooks**:

1. Click **Add webhook**
2. Name it clearly, for example `agentic-brain-order-updates`
3. Status: **Active**
4. Topic: choose one of:
   - `Order created`
   - `Order updated`
   - `Product created`
   - `Product updated`
   - `Customer created`
5. Delivery URL: `https://your-api.example.com/webhooks/woocommerce`
6. Secret: use the same value as `WOOCOMMERCE_WEBHOOK_SECRET`
7. Save the webhook and send a test delivery

### 3. Understand supported event mapping

| WooCommerce topic | Internal event type |
|---|---|
| `order.created` | `commerce.woocommerce.order.created` |
| `order.updated` | `commerce.woocommerce.order.updated` |
| `product.created` | `commerce.woocommerce.product.created` |
| `product.updated` | `commerce.woocommerce.product.updated` |
| `customer.created` | `commerce.woocommerce.customer.created` |

### 4. Signature verification details

WooCommerce sends a base64-encoded HMAC-SHA256 digest in `X-WC-Webhook-Signature`. The middleware validates the signature before the request reaches the route handler.

If verification fails, the endpoint returns `401 Unauthorized`.

---

## Running the integration tests

The integration suite uses a local mock WooCommerce server and does not require a real store.

```bash
cd agentic-brain
CI_RUN_INTEGRATION=1 python3 -m pytest tests/integration/test_woocommerce_e2e.py -q
```

What is covered:

- mock WooCommerce API server setup
- full order lifecycle (`create → pay → ship → complete`)
- product sync and search validation
- inventory updates and stock-state transitions
- webhook signature verification and dispatch

---

## Troubleshooting guide

### 401 Unauthorized from the WooCommerce API

**Cause**
- incorrect consumer key or secret
- wrong environment variables loaded
- credentials created for a different site

**Fix**
- regenerate the API key in WooCommerce
- verify `WOOCOMMERCE_URL`, `WOOCOMMERCE_CONSUMER_KEY`, and `WOOCOMMERCE_CONSUMER_SECRET`
- test with a simple `get_products()` call first

### SSL verification failures

**Cause**
- self-signed certificate in development
- incomplete certificate chain on the server

**Fix**
- keep `verify_ssl=True` in production
- for local development only, instantiate with `verify_ssl=False`
- correct the certificate chain before deploying to production

### Webhooks return 401 Invalid WooCommerce webhook signature

**Cause**
- WooCommerce webhook secret does not match the server configuration
- reverse proxy or middleware modifies the raw request body

**Fix**
- ensure WooCommerce and `WOOCOMMERCE_WEBHOOK_SECRET` use the exact same secret
- verify your stack forwards the raw body untouched
- test with the signed webhook flow from `tests/integration/test_woocommerce_e2e.py`

### Webhooks return 500 WooCommerce webhook secret not configured

**Cause**
- `WOOCOMMERCE_WEBHOOK_SECRET` is missing from the runtime environment

**Fix**
- add the secret to the deployment environment
- restart the application after updating configuration

### Products sync but validation fails

**Cause**
- WooCommerce payload contains malformed values, such as invalid URLs, email addresses, currency codes, or inconsistent stock fields

**Fix**
- run `sync_products()` or `sync_orders()` in a controlled environment to identify invalid records
- correct malformed data in WooCommerce or transform it before validation

### Order updates appear to succeed but status does not change

**Cause**
- downstream WooCommerce plugins may override status transitions
- custom business logic may require additional metadata

**Fix**
- inspect order notes and plugin hooks in WooCommerce
- update the order with any required metadata or payment fields
- confirm the store allows the target status transition

---

## Production checklist

- Use HTTPS and valid certificates
- Separate development and production API credentials
- Store secrets outside the repository
- Enable request/response logging with sensitive fields redacted
- Monitor webhook failures and retry behaviour
- Cover your store-specific customisations with dedicated tests alongside `test_woocommerce_e2e.py`

---

## See also

- [WordPress integration guide](./WORDPRESS.md)
- [Examples directory](../../examples/)
- [Integration overview](./README.md)
