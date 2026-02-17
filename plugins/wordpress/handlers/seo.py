"""SEO Handler - manages WordPress SEO plugin operations (Yoast/RankMath)"""

import json
from typing import Any

from plugins.wordpress.client import WordPressClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator"""
    return [
        # === SEO (Rank Math / Yoast) ===
        {
            "name": "get_post_seo",
            "method_name": "get_post_seo",
            "description": "Get SEO metadata for a WordPress post or page. Returns Rank Math or Yoast SEO fields including focus keyword, meta title, description, and social media settings. Requires SEO API Bridge plugin.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "description": "Post or Page ID", "minimum": 1}
                },
                "required": ["post_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_product_seo",
            "method_name": "get_product_seo",
            "description": "Get SEO metadata for a WooCommerce product. Returns Rank Math or Yoast SEO fields including focus keyword, meta title, description, and social media settings. Requires SEO API Bridge plugin.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "Product ID", "minimum": 1}
                },
                "required": ["product_id"],
            },
            "scope": "read",
        },
        {
            "name": "update_post_seo",
            "method_name": "update_post_seo",
            "description": "Update SEO metadata for a WordPress post or page. Supports both Rank Math and Yoast SEO fields. Automatically detects which plugin is active. Requires SEO API Bridge plugin.",
            "schema": {
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "integer",
                        "description": "Post or Page ID to update",
                        "minimum": 1,
                    },
                    "focus_keyword": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Primary focus keyword for SEO",
                    },
                    "seo_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "SEO meta title (appears in search results)",
                    },
                    "meta_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "SEO meta description (appears in search results)",
                    },
                    "additional_keywords": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Additional keywords (comma-separated)",
                    },
                    "canonical_url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Canonical URL for this content",
                    },
                    "robots": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Robots meta directives (e.g., ['noindex', 'nofollow'])",
                    },
                    "og_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Open Graph title for Facebook",
                    },
                    "og_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Open Graph description for Facebook",
                    },
                    "og_image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Open Graph image URL for Facebook",
                    },
                    "twitter_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Twitter Card title",
                    },
                    "twitter_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Twitter Card description",
                    },
                    "twitter_image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Twitter Card image URL",
                    },
                },
                "required": ["post_id"],
            },
            "scope": "write",
        },
        {
            "name": "update_product_seo",
            "method_name": "update_product_seo",
            "description": "Update SEO metadata for a WooCommerce product. Same as update_post_seo but specifically for products. Requires SEO API Bridge plugin.",
            "schema": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "Product ID to update",
                        "minimum": 1,
                    },
                    "focus_keyword": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Primary focus keyword for SEO",
                    },
                    "seo_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "SEO meta title (appears in search results)",
                    },
                    "meta_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "SEO meta description (appears in search results)",
                    },
                    "additional_keywords": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Additional keywords (comma-separated)",
                    },
                    "canonical_url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Canonical URL for this product",
                    },
                    "og_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Open Graph title for Facebook",
                    },
                    "og_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Open Graph description for Facebook",
                    },
                    "og_image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Open Graph image URL for Facebook",
                    },
                    "twitter_title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Twitter Card title",
                    },
                    "twitter_description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Twitter Card description",
                    },
                    "twitter_image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Twitter Card image URL",
                    },
                },
                "required": ["product_id"],
            },
            "scope": "write",
        },
    ]

class SEOHandler:
    """Handle SEO-related operations for WordPress (Yoast SEO and RankMath)"""

    def __init__(self, client: WordPressClient):
        """
        Initialize SEO handler.

        Args:
            client: WordPress API client instance
        """
        self.client = client

    async def _check_seo_plugins(self) -> dict[str, Any]:
        """
        Check if Rank Math or Yoast SEO is installed and SEO API Bridge is active.

        Returns:
            Dict with plugin status information
        """
        try:
            # First, try to use the new health check endpoint (v1.1.0+)
            try:
                status_result = await self.client.get(
                    "seo-api-bridge/v1/status", use_custom_namespace=True
                )

                if status_result and isinstance(status_result, dict):
                    # Successfully got status from dedicated endpoint
                    rank_math_info = status_result.get("seo_plugins", {}).get("rank_math", {})
                    yoast_info = status_result.get("seo_plugins", {}).get("yoast", {})

                    return {
                        "rank_math": {
                            "active": rank_math_info.get("active", False),
                            "version": rank_math_info.get("version"),
                        },
                        "yoast": {
                            "active": yoast_info.get("active", False),
                            "version": yoast_info.get("version"),
                        },
                        "api_bridge_active": True,
                        "api_bridge_version": status_result.get("version"),
                        "message": status_result.get("message", "SEO API Bridge is active"),
                    }
            except Exception:
                # Health check endpoint not available, fall back to old method
                pass

            # Fallback: Try to check posts for SEO meta fields
            result = await self.client.get("posts", params={"per_page": 1})

            # If no posts, try products
            if not result or (isinstance(result, list) and len(result) == 0):
                result = await self.client.get(
                    "products", params={"per_page": 1}, use_woocommerce=True
                )

                if not result or (isinstance(result, list) and len(result) == 0):
                    return {
                        "rank_math": {"active": False},
                        "yoast": {"active": False},
                        "api_bridge_active": False,
                        "message": "No posts or products available to check SEO plugin status. Please install SEO API Bridge v1.1.0+ or create content with SEO metadata.",
                    }

            # Check if meta fields are present (indicates SEO API Bridge is active)
            first_item = result[0] if isinstance(result, list) and len(result) > 0 else {}
            meta = first_item.get("meta", {})

            # Check for Rank Math fields
            rank_math_active = any(
                key in meta
                for key in [
                    "rank_math_focus_keyword",
                    "rank_math_seo_title",
                    "rank_math_description",
                ]
            )

            # Check for Yoast SEO fields
            yoast_active = any(
                key in meta
                for key in ["_yoast_wpseo_focuskw", "_yoast_wpseo_title", "_yoast_wpseo_metadesc"]
            )

            api_bridge_active = rank_math_active or yoast_active

            return {
                "rank_math": {"active": rank_math_active},
                "yoast": {"active": yoast_active},
                "api_bridge_active": api_bridge_active,
                "message": (
                    "SEO API Bridge required. Please install and activate the plugin, then upgrade to v1.1.0+ for better detection."
                    if not api_bridge_active
                    else "SEO fields accessible via meta (legacy detection)"
                ),
            }
        except Exception as e:
            return {
                "rank_math": {"active": False},
                "yoast": {"active": False},
                "api_bridge_active": False,
                "message": f"SEO plugin check failed: {str(e)}",
            }

    # === SEO METHODS ===

    async def get_post_seo(self, post_id: int) -> str:
        """
        Get SEO metadata for a post or page.

        Args:
            post_id: Post or Page ID

        Returns:
            JSON string with SEO metadata
        """
        try:
            result = await self.client.get(f"posts/{post_id}")

            # Extract SEO meta fields
            meta = result.get("meta", {})

            # Check which SEO plugin is active
            has_rank_math = "rank_math_focus_keyword" in meta
            has_yoast = "_yoast_wpseo_focuskw" in meta

            if not has_rank_math and not has_yoast:
                return json.dumps(
                    {
                        "error": "SEO API Bridge plugin not detected",
                        "message": "Please install and activate the SEO API Bridge WordPress plugin.",
                    },
                    indent=2,
                )

            # Format SEO data
            seo_data = {
                "post_id": post_id,
                "post_title": result.get("title", {}).get("rendered", ""),
                "plugin_detected": "rank_math" if has_rank_math else "yoast",
            }

            if has_rank_math:
                seo_data.update(
                    {
                        "focus_keyword": meta.get("rank_math_focus_keyword", ""),
                        "seo_title": meta.get("rank_math_seo_title", ""),
                        "meta_description": meta.get("rank_math_description", ""),
                        "additional_keywords": meta.get("rank_math_additional_keywords", ""),
                        "canonical_url": meta.get("rank_math_canonical_url", ""),
                        "robots": meta.get("rank_math_robots", []),
                        "breadcrumb_title": meta.get("rank_math_breadcrumb_title", ""),
                        "open_graph": {
                            "title": meta.get("rank_math_facebook_title", ""),
                            "description": meta.get("rank_math_facebook_description", ""),
                            "image": meta.get("rank_math_facebook_image", ""),
                            "image_id": meta.get("rank_math_facebook_image_id", ""),
                        },
                        "twitter": {
                            "title": meta.get("rank_math_twitter_title", ""),
                            "description": meta.get("rank_math_twitter_description", ""),
                            "image": meta.get("rank_math_twitter_image", ""),
                            "image_id": meta.get("rank_math_twitter_image_id", ""),
                            "card_type": meta.get("rank_math_twitter_card_type", ""),
                        },
                    }
                )
            elif has_yoast:
                seo_data.update(
                    {
                        "focus_keyword": meta.get("_yoast_wpseo_focuskw", ""),
                        "seo_title": meta.get("_yoast_wpseo_title", ""),
                        "meta_description": meta.get("_yoast_wpseo_metadesc", ""),
                        "canonical_url": meta.get("_yoast_wpseo_canonical", ""),
                        "noindex": meta.get("_yoast_wpseo_meta-robots-noindex", ""),
                        "nofollow": meta.get("_yoast_wpseo_meta-robots-nofollow", ""),
                        "breadcrumb_title": meta.get("_yoast_wpseo_bctitle", ""),
                        "open_graph": {
                            "title": meta.get("_yoast_wpseo_opengraph-title", ""),
                            "description": meta.get("_yoast_wpseo_opengraph-description", ""),
                            "image": meta.get("_yoast_wpseo_opengraph-image", ""),
                            "image_id": meta.get("_yoast_wpseo_opengraph-image-id", ""),
                        },
                        "twitter": {
                            "title": meta.get("_yoast_wpseo_twitter-title", ""),
                            "description": meta.get("_yoast_wpseo_twitter-description", ""),
                            "image": meta.get("_yoast_wpseo_twitter-image", ""),
                            "image_id": meta.get("_yoast_wpseo_twitter-image-id", ""),
                        },
                    }
                )

            return json.dumps(seo_data, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to get SEO data for post {post_id}: {str(e)}",
                },
                indent=2,
            )

    async def get_product_seo(self, product_id: int) -> str:
        """
        Get SEO metadata for a WooCommerce product.

        Uses SEO API Bridge endpoint for products.

        Args:
            product_id: Product ID

        Returns:
            JSON string with SEO metadata
        """
        try:
            # Use SEO API Bridge endpoint for products (same as update_product_seo)
            result = await self.client.get(
                f"seo-api-bridge/v1/products/{product_id}/seo", use_custom_namespace=True
            )

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to get SEO data for product {product_id}: {str(e)}",
                },
                indent=2,
            )

    async def update_post_seo(
        self,
        post_id: int,
        focus_keyword: str | None = None,
        seo_title: str | None = None,
        meta_description: str | None = None,
        additional_keywords: str | None = None,
        canonical_url: str | None = None,
        robots: list[str] | None = None,
        og_title: str | None = None,
        og_description: str | None = None,
        og_image: str | None = None,
        twitter_title: str | None = None,
        twitter_description: str | None = None,
        twitter_image: str | None = None,
    ) -> str:
        """
        Update SEO metadata for a post or page.

        Automatically detects whether Rank Math or Yoast is active and uses appropriate field names.

        Args:
            post_id: Post or Page ID
            focus_keyword: Primary focus keyword
            seo_title: Meta title
            meta_description: Meta description
            additional_keywords: Additional keywords
            canonical_url: Canonical URL
            robots: Robots meta directives
            og_title: Open Graph title
            og_description: Open Graph description
            og_image: Open Graph image URL
            twitter_title: Twitter Card title
            twitter_description: Twitter Card description
            twitter_image: Twitter Card image URL

        Returns:
            JSON string with update result
        """
        try:
            # First check which SEO plugin is active
            seo_check = await self._check_seo_plugins()

            if not seo_check.get("api_bridge_active"):
                return json.dumps(
                    {
                        "error": "SEO API Bridge plugin not detected",
                        "message": "Please install and activate the SEO API Bridge WordPress plugin.",
                    },
                    indent=2,
                )

            # Build meta object based on active plugin
            meta = {}

            if seo_check.get("rank_math", {}).get("active"):
                # Use Rank Math field names
                if focus_keyword is not None:
                    meta["rank_math_focus_keyword"] = focus_keyword
                if seo_title is not None:
                    meta["rank_math_seo_title"] = seo_title
                if meta_description is not None:
                    meta["rank_math_description"] = meta_description
                if additional_keywords is not None:
                    meta["rank_math_additional_keywords"] = additional_keywords
                if canonical_url is not None:
                    meta["rank_math_canonical_url"] = canonical_url
                if robots is not None:
                    meta["rank_math_robots"] = robots
                if og_title is not None:
                    meta["rank_math_facebook_title"] = og_title
                if og_description is not None:
                    meta["rank_math_facebook_description"] = og_description
                if og_image is not None:
                    meta["rank_math_facebook_image"] = og_image
                if twitter_title is not None:
                    meta["rank_math_twitter_title"] = twitter_title
                if twitter_description is not None:
                    meta["rank_math_twitter_description"] = twitter_description
                if twitter_image is not None:
                    meta["rank_math_twitter_image"] = twitter_image

            elif seo_check.get("yoast", {}).get("active"):
                # Use Yoast field names
                if focus_keyword is not None:
                    meta["_yoast_wpseo_focuskw"] = focus_keyword
                if seo_title is not None:
                    meta["_yoast_wpseo_title"] = seo_title
                if meta_description is not None:
                    meta["_yoast_wpseo_metadesc"] = meta_description
                if canonical_url is not None:
                    meta["_yoast_wpseo_canonical"] = canonical_url
                if og_title is not None:
                    meta["_yoast_wpseo_opengraph-title"] = og_title
                if og_description is not None:
                    meta["_yoast_wpseo_opengraph-description"] = og_description
                if og_image is not None:
                    meta["_yoast_wpseo_opengraph-image"] = og_image
                if twitter_title is not None:
                    meta["_yoast_wpseo_twitter-title"] = twitter_title
                if twitter_description is not None:
                    meta["_yoast_wpseo_twitter-description"] = twitter_description
                if twitter_image is not None:
                    meta["_yoast_wpseo_twitter-image"] = twitter_image

            # Update post with meta fields
            data = {"meta": meta}
            await self.client.post(f"posts/{post_id}", json_data=data)

            # Read back saved values for confirmation
            saved_seo_json = await self.get_post_seo(post_id)
            saved_seo = json.loads(saved_seo_json)

            response = {
                "post_id": post_id,
                "updated_fields": list(meta.keys()),
                "message": f"SEO metadata updated successfully for post {post_id}",
                "current_values": saved_seo,
            }

            return json.dumps(response, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to update SEO data for post {post_id}: {str(e)}",
                },
                indent=2,
            )

    async def update_product_seo(
        self,
        product_id: int,
        focus_keyword: str | None = None,
        seo_title: str | None = None,
        meta_description: str | None = None,
        additional_keywords: str | None = None,
        canonical_url: str | None = None,
        og_title: str | None = None,
        og_description: str | None = None,
        og_image: str | None = None,
        twitter_title: str | None = None,
        twitter_description: str | None = None,
        twitter_image: str | None = None,
    ) -> str:
        """
        Update SEO metadata for a WooCommerce product.

        Uses SEO API Bridge endpoint for products.

        Args:
            product_id: Product ID
            focus_keyword: Primary focus keyword
            seo_title: Meta title
            meta_description: Meta description
            additional_keywords: Additional keywords
            canonical_url: Canonical URL
            og_title: Open Graph title
            og_description: Open Graph description
            og_image: Open Graph image URL
            twitter_title: Twitter Card title
            twitter_description: Twitter Card description
            twitter_image: Twitter Card image URL

        Returns:
            JSON string with update result
        """
        try:
            # Build request data with only provided fields
            data = {}

            if focus_keyword is not None:
                data["focus_keyword"] = focus_keyword
            if seo_title is not None:
                data["seo_title"] = seo_title
            if meta_description is not None:
                data["meta_description"] = meta_description
            if additional_keywords is not None:
                data["additional_keywords"] = additional_keywords
            if canonical_url is not None:
                data["canonical_url"] = canonical_url
            if og_title is not None:
                data["og_title"] = og_title
            if og_description is not None:
                data["og_description"] = og_description
            if og_image is not None:
                data["og_image"] = og_image
            if twitter_title is not None:
                data["twitter_title"] = twitter_title
            if twitter_description is not None:
                data["twitter_description"] = twitter_description
            if twitter_image is not None:
                data["twitter_image"] = twitter_image

            # Use SEO API Bridge endpoint for products
            await self.client.post(
                f"seo-api-bridge/v1/products/{product_id}/seo",
                json_data=data,
                use_custom_namespace=True,
            )

            # Read back saved values for confirmation
            saved_seo_json = await self.get_product_seo(product_id)
            saved_seo = json.loads(saved_seo_json)

            response = {
                "product_id": product_id,
                "updated_fields": list(data.keys()),
                "message": f"SEO metadata updated successfully for product {product_id}",
                "current_values": saved_seo,
            }

            return json.dumps(response, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "error": str(e),
                    "message": f"Failed to update SEO data for product {product_id}: {str(e)}",
                },
                indent=2,
            )
