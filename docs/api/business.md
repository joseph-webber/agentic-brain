# Business Models API

E-commerce and retail entity models with Neo4j graph database integration. Build scalable B2B and B2C applications with built-in data persistence.

## Table of Contents
- [BusinessEntity](#businessentity) - Base class
- [Repository](#repository) - Data persistence
- [Product](#product) - Product model
- [Category](#category) - Product categories
- [Order](#order) - Order management
- [OrderItem](#orderitem) - Line items
- [Customer](#customer) - Customer model
- [Examples](#examples)

---

## BusinessEntity

Abstract base class for all business models.

### Signature

```python
@dataclass
class BusinessEntity(ABC):
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

### Properties

All entities automatically track:
- `id` - Unique UUID
- `created_at` - Creation timestamp
- `updated_at` - Last modification timestamp

### Methods

#### `to_dict()`

Serialize entity to dictionary.

```python
def to_dict(self) -> Dict[str, Any]:
```

**Returns:**
- Dictionary with all fields (datetimes as ISO strings)

**Example:**
```python
product = Product(sku="PROD-001", name="Widget", price=19.99)
data = product.to_dict()

import json
json.dump(data, open("product.json", "w"))
```

---

#### `from_dict()`

Deserialize from dictionary.

```python
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> T:
```

**Parameters:**
- `data` (dict): Dictionary with entity fields

**Returns:**
- Entity instance

**Example:**
```python
import json

data = json.load(open("product.json"))
product = Product.from_dict(data)
```

---

#### `to_neo4j()`

Convert to Neo4j node properties.

```python
def to_neo4j(self) -> Dict[str, Any]:
```

**Returns:**
- Neo4j-compatible properties dictionary

**Example:**
```python
product = Product(sku="PROD-001", name="Widget", price=19.99)
neo4j_props = product.to_neo4j()

# Use with Neo4j driver
session.run("""
    CREATE (p:Product $props)
""", props=neo4j_props)
```

---

#### `entity_label`

Get Neo4j label for this entity.

```python
@property
def entity_label(self) -> str:
```

**Returns:**
- Class name to use as Neo4j label

**Example:**
```python
product = Product(sku="PROD-001", name="Widget")
print(product.entity_label)  # -> "Product"
```

---

#### `update_timestamp()`

Update modification time.

```python
def update_timestamp(self) -> None:
```

**Called automatically on modifications.**

---

## Repository

Abstract repository for CRUD operations.

### Signature

```python
class Repository(ABC, Generic[T]):
    def __init__(self, neo4j_driver: Optional[Any] = None):
        """Initialize repository with optional Neo4j driver."""
```

### Methods

#### `save()`

Save entity to database.

```python
@abstractmethod
def save(self, entity: T) -> T:
```

**Returns:**
- Saved entity with potentially updated fields

---

#### `load()`

Load entity by ID.

```python
@abstractmethod
def load(self, entity_id: str) -> Optional[T]:
```

**Returns:**
- Entity if found, None otherwise

---

#### `delete()`

Delete entity from database.

```python
@abstractmethod
def delete(self, entity_id: str) -> bool:
```

**Returns:**
- True if deleted, False if not found

---

#### `search()`

Search for entities.

```python
@abstractmethod
def search(self, **criteria: Any) -> List[T]:
```

**Parameters:**
- `**criteria`: Field-value pairs to match

**Returns:**
- List of matching entities

---

#### `save_batch()`

Save multiple entities.

```python
def save_batch(self, entities: List[T]) -> List[T]:
```

---

#### `load_batch()`

Load multiple entities.

```python
def load_batch(self, entity_ids: List[str]) -> List[T]:
```

---

## Product

Product entity for retail inventory.

### Signature

```python
@dataclass
class Product(BusinessEntity):
    sku: str = ""
    name: str = ""
    description: str = ""
    category_id: str = ""
    price: float = 0.0
    stock_quantity: int = 0
    reorder_level: int = 10
    is_active: bool = True
    attributes: dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sku` | `str` | required | Stock keeping unit |
| `name` | `str` | required | Product name |
| `description` | `str` | `""` | Product description |
| `category_id` | `str` | `""` | Category ID |
| `price` | `float` | `0.0` | Price in cents/units |
| `stock_quantity` | `int` | `0` | Available quantity |
| `reorder_level` | `int` | `10` | Reorder alert threshold |
| `is_active` | `bool` | `True` | Active in catalog |
| `attributes` | `dict` | `{}` | Custom attributes (color, size, etc.) |
| `tags` | `List[str]` | `[]` | Search tags |

### Methods

#### `is_in_stock()`

Check if product has stock.

```python
def is_in_stock(self) -> bool:
```

**Example:**
```python
product = Product(sku="PROD-001", name="Widget", stock_quantity=5)
if product.is_in_stock():
    print("Available")
```

---

#### `needs_reorder()`

Check if stock below reorder level.

```python
def needs_reorder(self) -> bool:
```

**Example:**
```python
product = Product(
    sku="PROD-001",
    name="Widget",
    stock_quantity=5,
    reorder_level=10
)
if product.needs_reorder():
    print("Order more inventory")
```

---

#### `reduce_stock()`

Reduce stock by quantity.

```python
def reduce_stock(self, quantity: int) -> bool:
```

**Returns:**
- True if successful, False if insufficient stock

**Example:**
```python
product = Product(sku="PROD-001", stock_quantity=10)
if product.reduce_stock(3):
    print("Stock reduced to 7")
else:
    print("Not enough stock")
```

---

#### `increase_stock()`

Increase stock.

```python
def increase_stock(self, quantity: int) -> None:
```

**Example:**
```python
product = Product(sku="PROD-001", stock_quantity=10)
product.increase_stock(5)  # Now 15
```

---

## Category

Product category entity.

### Signature

```python
@dataclass
class Category(BusinessEntity):
    name: str = ""
    description: str = ""
    parent_id: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Category name |
| `description` | `str` | `""` | Description |
| `parent_id` | `str` | `None` | Parent category (for hierarchy) |
| `display_order` | `int` | `0` | Sort order |
| `is_active` | `bool` | `True` | Active in catalog |

### Example

```python
# Create categories
electronics = Category(name="Electronics", display_order=1)
laptops = Category(name="Laptops", parent_id=electronics.id, display_order=1)
```

---

## Order

Order entity for order management.

### Signature

```python
@dataclass
class Order(BusinessEntity):
    customer_id: str = ""
    items: List[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    total_amount: float = 0.0
    shipping_address: str = ""
    notes: str = ""
    placed_at: datetime = field(default_factory=datetime.utcnow)
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `customer_id` | `str` | required | Associated customer |
| `items` | `List[OrderItem]` | `[]` | Line items |
| `status` | `OrderStatus` | `PENDING` | Current status |
| `total_amount` | `float` | `0.0` | Total price |
| `shipping_address` | `str` | `""` | Delivery address |
| `notes` | `str` | `""` | Order notes |
| `placed_at` | `datetime` | `now` | Creation time |
| `shipped_at` | `datetime` | `None` | Shipment time |
| `delivered_at` | `datetime` | `None` | Delivery time |

### OrderStatus Enum

```python
OrderStatus.PENDING     # Awaiting confirmation
OrderStatus.CONFIRMED   # Confirmed by customer
OrderStatus.PROCESSING  # Being prepared
OrderStatus.SHIPPED     # On its way
OrderStatus.DELIVERED   # Received
OrderStatus.CANCELLED   # Cancelled
OrderStatus.REFUNDED    # Refunded
```

### Methods

#### `add_item()`

Add item to order.

```python
def add_item(self, product_id: str, quantity: int, unit_price: float) -> OrderItem:
```

---

#### `remove_item()`

Remove item from order.

```python
def remove_item(self, item_id: str) -> bool:
```

---

#### `calculate_total()`

Recalculate order total.

```python
def calculate_total(self) -> float:
```

---

#### `can_ship()`

Check if order can be shipped.

```python
def can_ship(self) -> bool:
```

---

#### `mark_shipped()`

Mark order as shipped.

```python
def mark_shipped(self) -> None:
```

---

#### `mark_delivered()`

Mark order as delivered.

```python
def mark_delivered(self) -> None:
```

---

## OrderItem

Individual item in an order.

### Signature

```python
@dataclass
class OrderItem(BusinessEntity):
    order_id: str = ""
    product_sku: str = ""
    product_name: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    line_total: float = 0.0
```

### Example

```python
item = OrderItem(
    order_id="order_123",
    product_sku="PROD-001",
    product_name="Widget",
    quantity=3,
    unit_price=19.99,
    line_total=59.97
)
```

---

## Customer

Customer entity.

### Signature

```python
@dataclass
class Customer(BusinessEntity):
    email: str = ""
    name: str = ""
    phone: Optional[str] = None
    billing_address: str = ""
    shipping_address: str = ""
    is_active: bool = True
    metadata: dict = field(default_factory=dict)
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `email` | `str` | required | Email address |
| `name` | `str` | required | Full name |
| `phone` | `str` | `None` | Phone number |
| `billing_address` | `str` | `""` | Billing address |
| `shipping_address` | `str` | `""` | Default shipping address |
| `is_active` | `bool` | `True` | Active account |
| `metadata` | `dict` | `{}` | Custom data |

---

## Examples

### Example 1: Product Management

```python
from agentic_brain import Product

# Create product
product = Product(
    sku="LAPTOP-001",
    name="MacBook Pro",
    description="15-inch laptop",
    price=1299.99,
    stock_quantity=50,
    reorder_level=10,
    tags=["laptop", "apple", "professional"]
)

# Check stock
if product.is_in_stock():
    print(f"In stock: {product.stock_quantity}")

# Process sale
if product.reduce_stock(1):
    print("Sold one unit")

# Check reorder
if product.needs_reorder():
    print("Time to reorder")

# Receive shipment
product.increase_stock(100)
```

---

### Example 2: Order Processing

```python
from agentic_brain import Order, OrderItem, OrderStatus

# Create order
order = Order(
    customer_id="customer_123",
    shipping_address="123 Main St, City"
)

# Add items
order.add_item(
    product_id="PROD-001",
    quantity=2,
    unit_price=19.99
)

# Calculate total
total = order.calculate_total()
print(f"Total: ${total:.2f}")

# Process order
order.status = OrderStatus.CONFIRMED
# ... after packing ...
order.mark_shipped()
# ... after delivery ...
order.mark_delivered()
```

---

### Example 3: Category Hierarchy

```python
from agentic_brain import Category

# Create category tree
electronics = Category(name="Electronics", display_order=1)
computers = Category(name="Computers", parent_id=electronics.id, display_order=1)
laptops = Category(name="Laptops", parent_id=computers.id, display_order=1)
desktops = Category(name="Desktops", parent_id=computers.id, display_order=2)
```

---

### Example 4: Customer Management

```python
from agentic_brain import Customer

# Create customer
customer = Customer(
    email="alice@example.com",
    name="Alice Smith",
    phone="555-1234",
    billing_address="123 Elm St",
    shipping_address="456 Oak Ave",
    metadata={
        "source": "web",
        "vip": True,
        "registration_date": "2026-01-01"
    }
)

# Serialize
data = customer.to_dict()

# Deserialize
restored = Customer.from_dict(data)
```

---

### Example 5: Neo4j Integration

```python
from neo4j import GraphDatabase
from agentic_brain import Product

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

# Create product
product = Product(
    sku="PROD-001",
    name="Widget",
    price=19.99,
    stock_quantity=100
)

# Save to Neo4j
with driver.session() as session:
    props = product.to_neo4j()
    session.run("""
        CREATE (p:Product {
            id: $id,
            sku: $sku,
            name: $name,
            price: $price,
            stock_quantity: $stock_quantity
        })
    """, props)
```

---

### Example 6: Complete E-Commerce Flow

```python
from agentic_brain import (
    Product, Category, Customer, Order, OrderItem, OrderStatus
)

# 1. Create catalog
electronics = Category(name="Electronics")
product = Product(
    sku="PHONE-001",
    name="Smartphone",
    category_id=electronics.id,
    price=799.99,
    stock_quantity=50
)

# 2. Create customer
customer = Customer(
    email="buyer@example.com",
    name="John Buyer",
    shipping_address="123 Main St"
)

# 3. Create order
order = Order(
    customer_id=customer.id,
    shipping_address=customer.shipping_address
)

# 4. Add items
order.add_item(
    product_id=product.id,
    quantity=2,
    unit_price=product.price
)

# 5. Reduce stock
product.reduce_stock(2)

# 6. Update order status
order.status = OrderStatus.CONFIRMED
order.calculate_total()

# 7. Ship order
order.mark_shipped()

# 8. Deliver order
order.mark_delivered()

print(f"Order {order.id}: {order.status}")
print(f"Items: {len(order.items)}")
print(f"Total: ${order.total_amount:.2f}")
print(f"Product stock remaining: {product.stock_quantity}")
```

---

## Validation

All entities validate on initialization:

```python
from agentic_brain import Product

# Valid
product = Product(sku="SKU", name="Name", price=10)

# Invalid - missing required fields
try:
    product = Product(name="Name")  # Missing sku
except ValueError as e:
    print(f"Error: {e}")
```

---

## See Also

- [Chat Module](./chat.md) - Chatbot
- [Memory Module](./memory.md) - Storage
- [Index](./index.md) - All modules

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
