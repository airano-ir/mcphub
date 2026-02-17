"""Events Handler - OpenPanel event tracking operations (10 tools)"""

import json
from typing import Any

from plugins.openpanel.client import OpenPanelClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (10 tools)"""
    return [
        {
            "name": "track_event",
            "method_name": "track_event",
            "description": "Track a custom event with properties. Events can have any custom properties for analytics.",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Event name (e.g., 'button_clicked', 'purchase_completed', 'page_viewed')",
                    },
                    "properties": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Custom properties for the event (e.g., {"product_id": "123", "price": 99.99})',
                    },
                    "profile_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User/profile ID to associate with the event",
                    },
                    "timestamp": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Event timestamp (ISO 8601 format, defaults to now)",
                    },
                    "client_ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client IP for geolocation tracking",
                    },
                    "user_agent": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User agent for device detection",
                    },
                },
                "required": ["name"],
            },
            "scope": "write",
        },
        {
            "name": "track_page_view",
            "method_name": "track_page_view",
            "description": "Track a page view event with URL and referrer information.",
            "schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Page path (e.g., '/products/123', '/blog/post-title')",
                    },
                    "title": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Page title",
                    },
                    "referrer": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Referrer URL",
                    },
                    "profile_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User/profile ID",
                    },
                    "properties": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Additional properties",
                    },
                    "client_ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client IP for geolocation",
                    },
                    "user_agent": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User agent for device detection",
                    },
                },
                "required": ["path"],
            },
            "scope": "write",
        },
        {
            "name": "track_screen_view",
            "method_name": "track_screen_view",
            "description": "Track a screen view event for mobile applications.",
            "schema": {
                "type": "object",
                "properties": {
                    "screen_name": {
                        "type": "string",
                        "description": "Screen name (e.g., 'HomeScreen', 'ProductDetail')",
                    },
                    "screen_class": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Screen class/component name",
                    },
                    "profile_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User/profile ID",
                    },
                    "properties": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Additional properties",
                    },
                    "client_ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client IP",
                    },
                    "user_agent": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User agent",
                    },
                },
                "required": ["screen_name"],
            },
            "scope": "write",
        },
        {
            "name": "identify_user",
            "method_name": "identify_user",
            "description": "Identify a user and set their profile properties. Use this to associate events with users.",
            "schema": {
                "type": "object",
                "properties": {
                    "profile_id": {
                        "type": "string",
                        "description": "Unique identifier for the user",
                    },
                    "email": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User's email address",
                    },
                    "first_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User's first name",
                    },
                    "last_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User's last name",
                    },
                    "properties": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": 'Additional profile properties (e.g., {"plan": "premium", "company": "Acme"})',
                    },
                    "client_ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client IP",
                    },
                    "user_agent": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User agent",
                    },
                },
                "required": ["profile_id"],
            },
            "scope": "write",
        },
        {
            "name": "set_user_properties",
            "method_name": "set_user_properties",
            "description": "Update properties for an existing user profile.",
            "schema": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string", "description": "User's profile ID"},
                    "properties": {
                        "type": "object",
                        "description": "Properties to set/update on the profile",
                    },
                },
                "required": ["profile_id", "properties"],
            },
            "scope": "write",
        },
        {
            "name": "increment_property",
            "method_name": "increment_property",
            "description": "Increment a numeric property on a user profile. IMPORTANT: Profile must exist first (use identify_user). Property must be numeric.",
            "schema": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string", "description": "User's profile ID"},
                    "property_name": {
                        "type": "string",
                        "description": "Name of the property to increment",
                    },
                    "value": {
                        "type": "integer",
                        "description": "Amount to increment by",
                        "default": 1,
                    },
                },
                "required": ["profile_id", "property_name"],
            },
            "scope": "write",
        },
        {
            "name": "decrement_property",
            "method_name": "decrement_property",
            "description": "Decrement a numeric property on a user profile. IMPORTANT: Profile must exist first (use identify_user). Property must be numeric.",
            "schema": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string", "description": "User's profile ID"},
                    "property_name": {
                        "type": "string",
                        "description": "Name of the property to decrement",
                    },
                    "value": {
                        "type": "integer",
                        "description": "Amount to decrement by",
                        "default": 1,
                    },
                },
                "required": ["profile_id", "property_name"],
            },
            "scope": "write",
        },
        # NOTE: alias_user removed - not supported on most self-hosted OpenPanel instances
        {
            "name": "track_revenue",
            "method_name": "track_revenue",
            "description": "Track a revenue/purchase event with amount and currency.",
            "schema": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Revenue amount"},
                    "currency": {
                        "type": "string",
                        "description": "Currency code (e.g., 'USD', 'EUR', 'IRR')",
                        "default": "USD",
                    },
                    "product_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product ID",
                    },
                    "product_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Product name",
                    },
                    "order_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Order/transaction ID",
                    },
                    "profile_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User's profile ID",
                    },
                    "properties": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Additional properties",
                    },
                    "client_ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client IP",
                    },
                },
                "required": ["amount"],
            },
            "scope": "write",
        },
        {
            "name": "track_batch",
            "method_name": "track_batch",
            "description": "Track multiple events in a single request for efficiency.",
            "schema": {
                "type": "object",
                "properties": {
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "properties": {"type": "object"},
                                "profile_id": {"type": "string"},
                                "timestamp": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                        "description": "Array of events to track",
                        "minItems": 1,
                        "maxItems": 100,
                    },
                    "client_ip": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Client IP for all events",
                    },
                    "user_agent": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "User agent for all events",
                    },
                },
                "required": ["events"],
            },
            "scope": "write",
        },
    ]


# =====================
# Event Tracking Functions (10)
# =====================


async def track_event(
    client: OpenPanelClient,
    name: str,
    properties: dict[str, Any] | None = None,
    profile_id: str | None = None,
    timestamp: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Track a custom event"""
    try:
        result = await client.track_event(
            name=name,
            properties=properties,
            profile_id=profile_id,
            timestamp=timestamp,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return json.dumps(
            {
                "success": True,
                "event": name,
                "profile_id": profile_id,
                "message": f"Event '{name}' tracked successfully",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def track_page_view(
    client: OpenPanelClient,
    path: str,
    title: str | None = None,
    referrer: str | None = None,
    profile_id: str | None = None,
    properties: dict[str, Any] | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Track a page view event"""
    try:
        event_properties = {
            "path": path,
        }
        if title:
            event_properties["title"] = title
        if referrer:
            event_properties["referrer"] = referrer
        if properties:
            event_properties.update(properties)

        result = await client.track_event(
            name="page_view",
            properties=event_properties,
            profile_id=profile_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return json.dumps(
            {
                "success": True,
                "event": "page_view",
                "path": path,
                "message": f"Page view tracked for '{path}'",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def track_screen_view(
    client: OpenPanelClient,
    screen_name: str,
    screen_class: str | None = None,
    profile_id: str | None = None,
    properties: dict[str, Any] | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Track a screen view event for mobile"""
    try:
        event_properties = {
            "screen_name": screen_name,
        }
        if screen_class:
            event_properties["screen_class"] = screen_class
        if properties:
            event_properties.update(properties)

        result = await client.track_event(
            name="screen_view",
            properties=event_properties,
            profile_id=profile_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return json.dumps(
            {
                "success": True,
                "event": "screen_view",
                "screen_name": screen_name,
                "message": f"Screen view tracked for '{screen_name}'",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def identify_user(
    client: OpenPanelClient,
    profile_id: str,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    properties: dict[str, Any] | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Identify a user with profile data"""
    try:
        result = await client.identify_user(
            profile_id=profile_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            properties=properties,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        return json.dumps(
            {
                "success": True,
                "profile_id": profile_id,
                "email": email,
                "message": f"User '{profile_id}' identified successfully",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def set_user_properties(
    client: OpenPanelClient, profile_id: str, properties: dict[str, Any]
) -> str:
    """Update properties for a user profile"""
    try:
        result = await client.identify_user(profile_id=profile_id, properties=properties)

        return json.dumps(
            {
                "success": True,
                "profile_id": profile_id,
                "properties_set": list(properties.keys()),
                "message": f"Properties updated for user '{profile_id}'",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def increment_property(
    client: OpenPanelClient, profile_id: str, property_name: str, value: int = 1
) -> str:
    """Increment a numeric property on a profile"""
    try:
        result = await client.increment_property(
            profile_id=profile_id, property_name=property_name, value=value
        )

        return json.dumps(
            {
                "success": True,
                "profile_id": profile_id,
                "property": property_name,
                "increment_by": value,
                "message": f"Property '{property_name}' incremented by {value}",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        error_str = str(e)
        hint = ""
        if "500" in error_str:
            hint = " (Hint: Profile must exist and property must be numeric. Try identifying the user first with identify_user.)"
        return json.dumps(
            {
                "success": False,
                "error": error_str + hint,
                "profile_id": profile_id,
                "property": property_name,
            },
            indent=2,
            ensure_ascii=False,
        )


async def decrement_property(
    client: OpenPanelClient, profile_id: str, property_name: str, value: int = 1
) -> str:
    """Decrement a numeric property on a profile"""
    try:
        result = await client.decrement_property(
            profile_id=profile_id, property_name=property_name, value=value
        )

        return json.dumps(
            {
                "success": True,
                "profile_id": profile_id,
                "property": property_name,
                "decrement_by": value,
                "message": f"Property '{property_name}' decremented by {value}",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        error_str = str(e)
        hint = ""
        if "500" in error_str:
            hint = " (Hint: Profile must exist and property must be numeric. Try identifying the user first with identify_user.)"
        return json.dumps(
            {
                "success": False,
                "error": error_str + hint,
                "profile_id": profile_id,
                "property": property_name,
            },
            indent=2,
            ensure_ascii=False,
        )


async def alias_user(client: OpenPanelClient, profile_id: str, alias: str) -> str:
    """Create an alias to link two profile IDs"""
    try:
        result = await client.alias_user(profile_id=profile_id, alias=alias)

        return json.dumps(
            {
                "success": True,
                "profile_id": profile_id,
                "alias": alias,
                "message": f"Alias '{alias}' linked to profile '{profile_id}'",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        error_str = str(e)
        hint = ""
        if "not supported" in error_str.lower() or "400" in error_str:
            hint = " (Note: Alias feature may not be available in all OpenPanel configurations. This is a server-side limitation.)"
        return json.dumps(
            {"success": False, "error": error_str + hint, "profile_id": profile_id, "alias": alias},
            indent=2,
            ensure_ascii=False,
        )


async def track_revenue(
    client: OpenPanelClient,
    amount: float,
    currency: str = "USD",
    product_id: str | None = None,
    product_name: str | None = None,
    order_id: str | None = None,
    profile_id: str | None = None,
    properties: dict[str, Any] | None = None,
    client_ip: str | None = None,
) -> str:
    """Track a revenue/purchase event"""
    try:
        event_properties = {
            "amount": amount,
            "currency": currency,
        }
        if product_id:
            event_properties["product_id"] = product_id
        if product_name:
            event_properties["product_name"] = product_name
        if order_id:
            event_properties["order_id"] = order_id
        if properties:
            event_properties.update(properties)

        result = await client.track_event(
            name="revenue", properties=event_properties, profile_id=profile_id, client_ip=client_ip
        )

        return json.dumps(
            {
                "success": True,
                "event": "revenue",
                "amount": amount,
                "currency": currency,
                "order_id": order_id,
                "message": f"Revenue of {amount} {currency} tracked",
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def track_batch(
    client: OpenPanelClient,
    events: list[dict[str, Any]],
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Track multiple events in batch"""
    try:
        results = []
        errors = []

        for event in events:
            try:
                await client.track_event(
                    name=event.get("name"),
                    properties=event.get("properties"),
                    profile_id=event.get("profile_id"),
                    timestamp=event.get("timestamp"),
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
                results.append({"name": event.get("name"), "success": True})
            except Exception as e:
                errors.append({"name": event.get("name"), "error": str(e)})

        return json.dumps(
            {
                "success": len(errors) == 0,
                "total": len(events),
                "tracked": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors if errors else None,
                "message": f"Batch tracked {len(results)}/{len(events)} events",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
