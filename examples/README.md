# 📚 Examples

This directory contains practical examples demonstrating how to use MCP Hub tools.

## 📂 Files

- **[basic_usage.py](basic_usage.py)** - Basic WordPress operations
- **[bulk_operations.py](bulk_operations.py)** - Batch processing and bulk updates
- **[woocommerce_shop.py](woocommerce_shop.py)** - E-commerce management examples
- **[content_migration.py](content_migration.py)** - Migrating content between sites
- **[.env.example](.env.example)** - Configuration template for examples

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp examples/.env.example examples/.env

# Edit with your WordPress credentials
nano examples/.env
```

### 2. Run Examples

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows

# Run an example
python examples/basic_usage.py
```

## 📖 Example Descriptions

### Basic Usage

Demonstrates fundamental operations:
- Listing posts
- Creating posts
- Updating posts
- Deleting posts
- Working with media
- Managing categories

**Use Case**: Learning the basics, quick operations

### Bulk Operations

Shows how to handle large-scale tasks:
- Bulk post creation
- Batch updates
- Mass deletion
- Progress tracking
- Error handling

**Use Case**: Content migrations, mass updates, cleanup

### WooCommerce Shop

E-commerce management examples:
- Product CRUD operations
- Inventory management
- Order processing
- Customer management
- Sales reports

**Use Case**: Online store management, inventory sync

### Content Migration

Cross-site content transfer:
- Migrating posts between sites
- Copying pages
- Media migration
- Taxonomy mapping
- URL rewriting

**Use Case**: Site consolidation, content backup, multi-site sync

## 🔧 Prerequisites

1. **Configured WordPress sites** in `.env`
2. **Valid credentials** (Application Passwords)
3. **WooCommerce** installed (for e-commerce examples)
4. **Sufficient permissions** on WordPress sites

## 💡 Tips

### Error Handling

All examples include comprehensive error handling:

```python
try:
    result = wordpress_create_post(...)
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")
    # Log error, retry, or handle appropriately
```

### Rate Limiting

Examples respect rate limits:

```python
import time

for item in items:
    process(item)
    time.sleep(0.1)  # Avoid hitting rate limits
```

### Progress Tracking

For long-running operations:

```python
from tqdm import tqdm

for post in tqdm(posts, desc="Processing posts"):
    update_post(post)
```

## 🧪 Testing Examples

Before running on production:

1. **Test on staging site first**
2. **Backup your WordPress site**
3. **Start with small batches**
4. **Verify results manually**

## 📞 Support

If you encounter issues with examples:

- Check [Troubleshooting Guide](../docs/troubleshooting.md)
- Review [Getting Started](../docs/getting-started.md)
- Contact: hello@mcphub.dev

---
