"""
WooCommerce Plugin - E-commerce Management

Split from WordPress Core in Phase D.1.
Provides 28 tools for WooCommerce store management.

Uses shared WordPress handlers for implementation.
"""

import logging
from typing import Any

from plugins.base import BasePlugin
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers import (
    AIMediaHandler,
    CouponsHandler,
    CustomersHandler,
    MediaAttachHandler,
    OrdersHandler,
    ProductsHandler,
    ReportsHandler,
    get_ai_media_specs,
    get_coupons_specs,
    get_customers_specs,
    get_media_attach_specs,
    get_orders_specs,
    get_products_specs,
    get_reports_specs,
)

logger = logging.getLogger(__name__)


class WooCommercePlugin(BasePlugin):
    """
    WooCommerce E-commerce Plugin.

    Provides comprehensive WooCommerce management capabilities:
    - Products (12 tools): CRUD, categories, tags, attributes, variations
    - Orders (5 tools): list, get, create, update_status, delete
    - Customers (4 tools): list, get, create, update
    - Coupons (4 tools): list, create, update, delete
    - Reports (3 tools): sales, top_sellers, customer_report

    Total: 28 tools
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "woocommerce"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize WooCommerce plugin with handlers.

        Args:
            config: Configuration dictionary containing:
                - url: WordPress/WooCommerce site URL
                - consumer_key/consumer_secret: WooCommerce REST API keys (preferred)
                - username/app_password: WordPress application password (fallback)
                - wp_username/wp_app_password: optional WP Application Password
                  for /wp/v2/media calls (used by media tools — F.X.fix-pass4).
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # WooCommerce supports two credential formats:
        # 1. consumer_key/consumer_secret (WooCommerce REST API keys — preferred)
        # 2. username/app_password (WordPress Application Passwords — legacy fallback)
        username = config.get("consumer_key") or config.get("username")
        password = config.get("consumer_secret") or config.get("app_password")

        if not username or not password:
            from plugins.wordpress.client import ConfigurationError

            raise ConfigurationError(
                "WooCommerce credentials not configured. "
                "Please set either CONSUMER_KEY/CONSUMER_SECRET or USERNAME/APP_PASSWORD."
            )

        # Create WordPress API client (used for /wc/v3/* WooCommerce REST).
        self.client = WordPressClient(
            site_url=config["url"], username=username, app_password=password
        )

        # F.X.fix-pass4 — derive a SECONDARY client for /wp/v2/* media
        # uploads. WC's Consumer Key + Secret pair does NOT authenticate
        # WP core REST endpoints; uploads to /wp/v2/media require an
        # Application Password from the WP admin user. Three resolution
        # paths, first that wins:
        #   1. explicit wp_username + wp_app_password fields (recommended)
        #   2. legacy username + app_password (single-credential mode)
        #   3. None — media tools will surface a clear error at call time
        wp_user = (config.get("wp_username") or "").strip()
        wp_pw = (config.get("wp_app_password") or "").strip()
        legacy_user = (config.get("username") or "").strip()
        legacy_pw = (config.get("app_password") or "").strip()
        # If consumer_key/consumer_secret are present, we're in WC-keys
        # mode and the primary client cannot hit /wp/v2/*. We need
        # explicit WP creds OR legacy app_password to enable media tools.
        if wp_user and wp_pw:
            self.wp_media_client: WordPressClient | None = WordPressClient(
                site_url=config["url"], username=wp_user, app_password=wp_pw
            )
        elif (
            legacy_user
            and legacy_pw
            and not (config.get("consumer_key") or config.get("consumer_secret"))
        ):
            # Legacy app_password mode (no ck/cs at all) — same client
            # works for both /wp/v2/* and /wc/v3/* because it uses an
            # Application Password.
            self.wp_media_client = self.client
        else:
            self.wp_media_client = None

        # Initialize WooCommerce handlers
        self.products = ProductsHandler(self.client)
        self.orders = OrdersHandler(self.client)
        self.customers = CustomersHandler(self.client)
        self.coupons = CouponsHandler(self.client)
        self.reports = ReportsHandler(self.client)
        self.media_attach = MediaAttachHandler(self.client, wp_media_client=self.wp_media_client)
        # F.X.fix-pass5 — expose generate_and_upload_image on WC sites
        # too (was WP-only). The handler reads the per-site provider
        # key resolver and uploads via wp_media_client (so WC sites
        # with consumer_key/consumer_secret as primary still work as
        # long as wp_username + wp_app_password are configured).
        # When wp_media_client is None we still register the tool so
        # the user sees a clear NO_PROVIDER_KEY / WP_CREDENTIALS_MISSING
        # error rather than a missing-tool 404.
        self.ai_media = AIMediaHandler(
            self.wp_media_client or self.client,
            user_id=config.get("user_id"),
            site_id=config.get("site_id"),
            # F.X.fix-pass6 — pass the primary WC client so
            # _apply_metadata_and_attach can detect "attach_to_post
            # is a WC product" and route featured-image set through
            # /wc/v3/products/{id} instead of the WP /posts endpoint
            # which 404s for products.
            wc_client=self.client,
        )

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries (28 tools)
        """
        specs = []

        # Products (12 tools)
        specs.extend(get_products_specs())

        # Orders (5 tools)
        specs.extend(get_orders_specs())

        # Customers (4 tools)
        specs.extend(get_customers_specs())

        # Coupons (4 tools)
        specs.extend(get_coupons_specs())

        # Reports (3 tools)
        specs.extend(get_reports_specs())

        # F.5a.3: Media attachment (3 tools — attach_media_to_product,
        # upload_and_attach_to_product, set_featured_image)
        specs.extend(get_media_attach_specs())

        # F.X.fix-pass5: AI image generation (1 tool — also surfaced on
        # the WP plugin; same handler, same per-site provider key
        # resolver). On a WC site this lets the operator chain
        # generate → attach without two endpoints.
        specs.extend(get_ai_media_specs())

        return specs

    async def health_check(self) -> dict[str, Any]:
        """
        Check WooCommerce availability and health.

        Returns:
            Dict with health status and WooCommerce version
        """
        try:
            wc_status = await self.client.check_woocommerce()
            if wc_status.get("available"):
                return {
                    "healthy": True,
                    "message": "WooCommerce is available",
                    "version": wc_status.get("version", "unknown"),
                    "plugin_type": "woocommerce",
                }
            else:
                return {
                    "healthy": False,
                    "message": "WooCommerce is not available on this site",
                    "plugin_type": "woocommerce",
                }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Health check failed: {str(e)}",
                "plugin_type": "woocommerce",
            }

    async def probe_credential_capabilities(self) -> dict[str, Any]:
        """F.7e — report what the WooCommerce consumer key grants.

        Uses ``GET /wp-json/wc/v3/system_status`` which is readable by any
        key with at least ``read`` permission and includes a
        ``security.rest_api_keys[]`` array where each entry carries a
        ``permissions`` field (``read`` / ``write`` / ``read_write``). We
        match the caller's consumer_key against the ``truncated_key`` the
        endpoint reports (last 7 chars) and derive the granted cap list.

        Falls back gracefully on any network / shape failure — callers
        still get the tools, they just don't get the early-warning badge.
        """
        try:
            status = await self.client.get("system_status", use_woocommerce=True)
        except Exception as exc:  # noqa: BLE001
            return {
                "probe_available": False,
                "granted": [],
                "source": "woocommerce_system_status",
                "reason": f"system_status_unreachable: {exc}",
            }

        if not isinstance(status, dict):
            return {
                "probe_available": False,
                "granted": [],
                "source": "woocommerce_system_status",
                "reason": "non_dict_response",
            }

        keys = ((status.get("security") or {}).get("rest_api_keys")) or []
        consumer_key = self.config.get("consumer_key") or self.config.get("username") or ""
        # WC's system_status truncates to last 7 chars by default.
        my_tail = consumer_key[-7:] if consumer_key else ""
        match = None
        for entry in keys:
            if not isinstance(entry, dict):
                continue
            tail = str(entry.get("truncated_key") or "")
            if my_tail and tail == my_tail:
                match = entry
                break

        if match is None:
            # Fallback: if there's exactly one key listed OR the endpoint
            # doesn't expose truncated_key on this WC version, fall back
            # to the top entry so we still show *something* useful.
            if len(keys) == 1 and isinstance(keys[0], dict):
                match = keys[0]

        # F.X.fix-pass5 — flag whether the site has WP App Password
        # credentials configured. Media tools (and AI image with
        # attach) need these on a WC site whose primary credential is
        # consumer_key + secret. The prerequisites resolver in
        # core/tool_access reads this to gate the WC media tool list.
        wp_credentials_present = bool(
            (self.config.get("wp_username") and self.config.get("wp_app_password"))
            or (
                self.config.get("username")
                and self.config.get("app_password")
                and not (self.config.get("consumer_key") or self.config.get("consumer_secret"))
            )
        )

        if match is not None:
            permission = str(match.get("permissions") or "").lower()
            granted: list[str] = []
            if permission in {"read", "read_write", "write"}:
                granted.append("read_products")
                granted.append("read_orders")
            if permission in {"write", "read_write"}:
                granted.append("write_products")
                granted.append("write_orders")

            return {
                "probe_available": True,
                "granted": sorted(granted),
                "source": "woocommerce_system_status",
                "permissions": permission,
                "wp_credentials_present": wp_credentials_present,
            }

        # F.X.fix-pass3 — match is None (consumer key not listed). This
        # happens when:
        #   * system_status omits truncated_key on the running WC build
        #   * the key was created via WP-CLI / a custom path
        #   * the key is shadowed by another key with the same tail
        # Don't surface a false-negative "probe unavailable" (which the
        # badge labelled with a misleading "install companion plugin"
        # hint, since WC has no companion).
        #
        # F.X.fix-pass5 — STAY CONSERVATIVE. The previous pass probed
        # ``GET /wc/v3/settings`` and upgraded to write+admin on 200,
        # but that signal mixes two unrelated facts (WP user has
        # ``manage_woocommerce`` capability AND key has any read perm)
        # and was over-granting on read-only keys whose backing user
        # was an admin. Result: tier-fit "Read + Write" stayed green
        # for read-only keys. Now we report read-only and let the
        # tier-fit warning fire correctly. Operators with read+write
        # keys still see their tools work; the badge just says
        # "Currently granted: read_products, read_orders" — a soft
        # signal, not a block.
        return {
            "probe_available": True,
            "granted": sorted({"read_products", "read_orders"}),
            "source": "woocommerce_system_status_inferred",
            "permissions": "inferred",
            "probe_inferred": True,
            "wp_credentials_present": wp_credentials_present,
        }

    # ========================================
    # Method Delegation to Handlers
    # ========================================

    # === Products ===
    async def list_products(self, **kwargs):
        return await self.products.list_products(**kwargs)

    async def get_product(self, **kwargs):
        return await self.products.get_product(**kwargs)

    async def create_product(self, **kwargs):
        return await self.products.create_product(**kwargs)

    async def update_product(self, **kwargs):
        return await self.products.update_product(**kwargs)

    async def delete_product(self, **kwargs):
        return await self.products.delete_product(**kwargs)

    async def list_product_categories(self, **kwargs):
        return await self.products.list_product_categories(**kwargs)

    async def create_product_category(self, **kwargs):
        return await self.products.create_product_category(**kwargs)

    async def list_product_tags(self, **kwargs):
        return await self.products.list_product_tags(**kwargs)

    async def list_product_attributes(self, **kwargs):
        return await self.products.list_product_attributes(**kwargs)

    async def create_product_attribute(self, **kwargs):
        return await self.products.create_product_attribute(**kwargs)

    async def list_product_variations(self, **kwargs):
        return await self.products.list_product_variations(**kwargs)

    async def create_product_variation(self, **kwargs):
        return await self.products.create_product_variation(**kwargs)

    # === Orders ===
    async def list_orders(self, **kwargs):
        return await self.orders.list_orders(**kwargs)

    async def get_order(self, **kwargs):
        return await self.orders.get_order(**kwargs)

    async def create_order(self, **kwargs):
        return await self.orders.create_order(**kwargs)

    async def update_order_status(self, **kwargs):
        return await self.orders.update_order_status(**kwargs)

    async def delete_order(self, **kwargs):
        return await self.orders.delete_order(**kwargs)

    # === Customers ===
    async def list_customers(self, **kwargs):
        return await self.customers.list_customers(**kwargs)

    async def get_customer(self, **kwargs):
        return await self.customers.get_customer(**kwargs)

    async def create_customer(self, **kwargs):
        return await self.customers.create_customer(**kwargs)

    async def update_customer(self, **kwargs):
        return await self.customers.update_customer(**kwargs)

    # === Coupons ===
    async def list_coupons(self, **kwargs):
        return await self.coupons.list_coupons(**kwargs)

    async def create_coupon(self, **kwargs):
        return await self.coupons.create_coupon(**kwargs)

    async def update_coupon(self, **kwargs):
        return await self.coupons.update_coupon(**kwargs)

    async def delete_coupon(self, **kwargs):
        return await self.coupons.delete_coupon(**kwargs)

    # === Reports ===
    async def get_sales_report(self, **kwargs):
        return await self.reports.get_sales_report(**kwargs)

    async def get_top_sellers(self, **kwargs):
        return await self.reports.get_top_sellers(**kwargs)

    async def get_customer_report(self, **kwargs):
        return await self.reports.get_customer_report(**kwargs)

    # === F.5a.3: Media attach ===
    async def attach_media_to_product(self, **kwargs):
        return await self.media_attach.attach_media_to_product(**kwargs)

    async def upload_and_attach_to_product(self, **kwargs):
        return await self.media_attach.upload_and_attach_to_product(**kwargs)

    async def set_featured_image(self, **kwargs):
        return await self.media_attach.set_featured_image(**kwargs)

    # === F.X.fix-pass5: AI image (re-exported from WP handler) ===
    async def generate_and_upload_image(self, **kwargs):
        return await self.ai_media.generate_and_upload_image(**kwargs)
