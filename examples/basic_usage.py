"""
Basic Usage Examples for MCP Hub

This example demonstrates fundamental WordPress operations using MCP tools.
"""

import asyncio
import json
from datetime import datetime

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Example 1: List Posts
async def list_posts_example():
    """List published posts from a WordPress site."""
    print("\n" + "=" * 50)
    print("Example 1: List Posts")
    print("=" * 50)

    try:
        # Using unified tools (recommended)
        from src.main import app

        # List first 5 published posts
        result = await app.call_tool(
            "wordpress_list_posts",
            arguments={"site": "mainsite", "per_page": 5, "status": "publish"},  # Use site alias
        )

        posts = json.loads(result)
        print(f"\nFound {len(posts)} posts:")
        for post in posts:
            print(f"  - [{post['id']}] {post['title']['rendered']}")
            print(f"    Status: {post['status']}, Date: {post['date']}")

    except Exception as e:
        print(f"Error: {e}")

# Example 2: Create a Post
async def create_post_example():
    """Create a new WordPress post."""
    print("\n" + "=" * 50)
    print("Example 2: Create Post")
    print("=" * 50)

    try:
        from src.main import app

        # Create a new post
        result = await app.call_tool(
            "wordpress_create_post",
            arguments={
                "site": "mainsite",
                "title": f"Test Post - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "content": "<p>This is a test post created via MCP tools.</p>",
                "status": "draft",  # Start as draft
                "excerpt": "A test post demonstrating MCP tool usage",
                "categories": [1],  # Uncategorized
                "tags": [],
                "featured_media": None,
                "slug": None,
            },
        )

        post = json.loads(result)
        print("\nPost created successfully!")
        print(f"  ID: {post['id']}")
        print(f"  Title: {post['title']['rendered']}")
        print(f"  Status: {post['status']}")
        print(f"  Edit URL: {post['link']}")

        return post["id"]  # Return for next examples

    except Exception as e:
        print(f"Error: {e}")
        return None

# Example 3: Update a Post
async def update_post_example(post_id):
    """Update an existing WordPress post."""
    print("\n" + "=" * 50)
    print("Example 3: Update Post")
    print("=" * 50)

    if not post_id:
        print("No post ID provided. Skipping.")
        return

    try:
        from src.main import app

        # Update the post
        result = await app.call_tool(
            "wordpress_update_post",
            arguments={
                "site": "mainsite",
                "post_id": post_id,
                "title": f"Updated Test Post - {datetime.now().strftime('%H:%M')}",
                "content": "<p>This post has been updated!</p><p>Updated via MCP tools.</p>",
                "status": "publish",  # Publish the post
                "slug": None,
                "excerpt": None,
                "categories": None,
                "tags": None,
                "featured_media": None,
            },
        )

        post = json.loads(result)
        print("\nPost updated successfully!")
        print(f"  ID: {post['id']}")
        print(f"  New Title: {post['title']['rendered']}")
        print(f"  Status: {post['status']}")

    except Exception as e:
        print(f"Error: {e}")

# Example 4: List Categories
async def list_categories_example():
    """List WordPress categories."""
    print("\n" + "=" * 50)
    print("Example 4: List Categories")
    print("=" * 50)

    try:
        from src.main import app

        result = await app.call_tool(
            "wordpress_list_categories",
            arguments={"site": "mainsite", "per_page": 10, "page": 1, "hide_empty": False},
        )

        categories = json.loads(result)
        print(f"\nFound {len(categories)} categories:")
        for cat in categories:
            print(f"  - [{cat['id']}] {cat['name']} ({cat['count']} posts)")

    except Exception as e:
        print(f"Error: {e}")

# Example 5: Upload Media
async def upload_media_example():
    """Upload media from URL to WordPress."""
    print("\n" + "=" * 50)
    print("Example 5: Upload Media from URL")
    print("=" * 50)

    try:
        from src.main import app

        # Upload an image from URL
        image_url = "https://via.placeholder.com/800x600.png?text=MCP+Test+Image"

        result = await app.call_tool(
            "wordpress_upload_media_from_url",
            arguments={
                "site": "mainsite",
                "url": image_url,
                "title": "MCP Test Image",
                "alt_text": "Test image uploaded via MCP",
                "caption": "Uploaded using MCP Hub",
            },
        )

        media = json.loads(result)
        print("\nMedia uploaded successfully!")
        print(f"  ID: {media['id']}")
        print(f"  Title: {media['title']['rendered']}")
        print(f"  URL: {media['source_url']}")
        print(f"  Size: {media['media_details'].get('filesize', 'unknown')} bytes")

        return media["id"]

    except Exception as e:
        print(f"Error: {e}")
        return None

# Example 6: Get Site Health
async def site_health_example():
    """Check WordPress site health."""
    print("\n" + "=" * 50)
    print("Example 6: Site Health Check")
    print("=" * 50)

    try:
        from src.main import app

        result = await app.call_tool("wordpress_get_site_health", arguments={"site": "mainsite"})

        health = json.loads(result)
        print("\nSite Health:")
        print(f"  Status: {health.get('status', 'unknown')}")
        print(f"  WordPress: {health.get('wordpress_version', 'unknown')}")
        print(f"  PHP: {health.get('php_version', 'unknown')}")
        print(f"  Accessible: {health.get('accessible', 'unknown')}")

    except Exception as e:
        print(f"Error: {e}")

# Example 7: Get System Metrics
async def system_metrics_example():
    """Check MCP server health and metrics."""
    print("\n" + "=" * 50)
    print("Example 7: System Metrics")
    print("=" * 50)

    try:
        from src.main import app

        result = await app.call_tool("get_system_metrics", arguments={})

        metrics = json.loads(result)
        print("\nSystem Metrics:")
        print(f"  Uptime: {metrics['uptime_seconds']:.2f} seconds")
        print(f"  Total Requests: {metrics['total_requests']}")
        print(
            f"  Success Rate: {(metrics['successful_requests']/metrics['total_requests']*100):.1f}%"
        )
        print(f"  Avg Response Time: {metrics['average_response_time_ms']:.2f}ms")

    except Exception as e:
        print(f"Error: {e}")

# Example 8: Delete Post
async def delete_post_example(post_id):
    """Delete a WordPress post."""
    print("\n" + "=" * 50)
    print("Example 8: Delete Post")
    print("=" * 50)

    if not post_id:
        print("No post ID provided. Skipping.")
        return

    try:
        from src.main import app

        # Move to trash (not permanent delete)
        result = await app.call_tool(
            "wordpress_delete_post",
            arguments={
                "site": "mainsite",
                "post_id": post_id,
                "force": False,  # Move to trash, not permanent delete
            },
        )

        post = json.loads(result)
        print("\nPost moved to trash!")
        print(f"  ID: {post['id']}")
        print(f"  Title: {post['title']['rendered']}")
        print(f"  Status: {post['status']}")

    except Exception as e:
        print(f"Error: {e}")

# Main execution
async def main():
    """Run all examples in sequence."""
    print("\n" + "=" * 60)
    print("MCP Hub - Basic Usage Examples")
    print("=" * 60)

    # Run examples
    await list_posts_example()
    post_id = await create_post_example()
    await asyncio.sleep(1)  # Small delay between operations

    if post_id:
        await update_post_example(post_id)
        await asyncio.sleep(1)

    await list_categories_example()
    await upload_media_example()
    await site_health_example()
    await system_metrics_example()

    # Cleanup: Delete the test post
    if post_id:
        print("\n" + "=" * 50)
        print("Cleanup: Removing test post")
        print("=" * 50)
        await delete_post_example(post_id)

    print("\n" + "=" * 60)
    print("Examples completed successfully!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
