"""Functions Handler - manages Supabase Edge Functions"""

import json
from typing import Any

from plugins.supabase.client import SupabaseClient


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (8 tools)"""
    return [
        {
            "name": "invoke_function",
            "method_name": "invoke_function",
            "description": "Invoke a Supabase Edge Function with POST method. Pass data in the body parameter.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the Edge Function to invoke",
                    },
                    "body": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "JSON body to send to the function",
                    },
                    "headers": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Additional headers to send",
                    },
                },
                "required": ["function_name"],
            },
            "scope": "write",
        },
        {
            "name": "invoke_function_get",
            "method_name": "invoke_function_get",
            "description": "Invoke a Supabase Edge Function with GET method. Use for read-only operations.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the Edge Function to invoke",
                    },
                    "params": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Query parameters to send",
                    },
                },
                "required": ["function_name"],
            },
            "scope": "read",
        },
        {
            "name": "list_edge_functions",
            "method_name": "list_edge_functions",
            "description": "List all deployed Edge Functions. Note: This reads from the functions volume in Self-Hosted.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_function_info",
            "method_name": "get_function_info",
            "description": "Get information about a specific Edge Function including its configuration.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Name of the function"}
                },
                "required": ["function_name"],
            },
            "scope": "read",
        },
        {
            "name": "test_function",
            "method_name": "test_function",
            "description": "Test an Edge Function with sample data and return the response.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function to test",
                    },
                    "test_data": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Test data to send",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP method",
                        "default": "POST",
                    },
                },
                "required": ["function_name"],
            },
            "scope": "write",
        },
        {
            "name": "get_function_url",
            "method_name": "get_function_url",
            "description": "Get the full URL for invoking an Edge Function.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Name of the function"}
                },
                "required": ["function_name"],
            },
            "scope": "read",
        },
        {
            "name": "check_function_health",
            "method_name": "check_function_health",
            "description": "Check if an Edge Function is responding correctly.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Name of the function"}
                },
                "required": ["function_name"],
            },
            "scope": "read",
        },
        {
            "name": "invoke_function_batch",
            "method_name": "invoke_function_batch",
            "description": "Invoke an Edge Function multiple times with different payloads. Useful for batch processing.",
            "schema": {
                "type": "object",
                "properties": {
                    "function_name": {"type": "string", "description": "Name of the function"},
                    "payloads": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Array of payloads to send",
                    },
                },
                "required": ["function_name", "payloads"],
            },
            "scope": "write",
        },
    ]


# =====================
# Functions Operations (8 tools)
# =====================


async def invoke_function(
    client: SupabaseClient,
    function_name: str,
    body: dict | None = None,
    headers: dict | None = None,
) -> str:
    """Invoke an Edge Function with POST"""
    try:
        result = await client.invoke_function(function_name=function_name, body=body, method="POST")

        return json.dumps(
            {"success": True, "function": function_name, "method": "POST", "response": result},
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def invoke_function_get(
    client: SupabaseClient, function_name: str, params: dict | None = None
) -> str:
    """Invoke an Edge Function with GET"""
    try:
        # Build query string
        endpoint = f"/functions/v1/{function_name}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            endpoint = f"{endpoint}?{query}"

        result = await client.request("GET", endpoint, use_service_role=False)

        return json.dumps(
            {
                "success": True,
                "function": function_name,
                "method": "GET",
                "params": params,
                "response": result,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def list_edge_functions(client: SupabaseClient) -> str:
    """List deployed Edge Functions"""
    try:
        # In self-hosted, we can try to list functions via the API
        # or check the functions volume. We'll try a health-check approach.
        functions_info = {
            "note": "In Self-Hosted Supabase, Edge Functions are deployed in volumes/functions/",
            "endpoint": f"{client.base_url}/functions/v1/",
            "available": True,
        }

        # Try to verify the functions endpoint is available
        try:
            await client.request("GET", "/functions/v1/", use_service_role=False)
            functions_info["status"] = "Functions endpoint available"
        except Exception as e:
            functions_info["status"] = f"Functions endpoint check: {str(e)}"

        return json.dumps(
            {
                "success": True,
                "functions_info": functions_info,
                "tip": "Deploy functions by adding them to volumes/functions/ directory",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def get_function_info(client: SupabaseClient, function_name: str) -> str:
    """Get function information"""
    try:
        info = {
            "name": function_name,
            "url": f"{client.base_url}/functions/v1/{function_name}",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "auth_required": True,
            "cors_enabled": True,
        }

        # Try to check if function exists by making a request
        try:
            await client.request(
                "OPTIONS", f"/functions/v1/{function_name}", use_service_role=False
            )
            info["status"] = "available"
        except Exception as e:
            if "404" in str(e):
                info["status"] = "not_found"
            else:
                info["status"] = "unknown"
                info["check_error"] = str(e)

        return json.dumps({"success": True, "function_info": info}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def test_function(
    client: SupabaseClient, function_name: str, test_data: dict | None = None, method: str = "POST"
) -> str:
    """Test an Edge Function"""
    try:
        if method.upper() == "GET":
            result = await client.request(
                "GET", f"/functions/v1/{function_name}", params=test_data, use_service_role=False
            )
        else:
            result = await client.invoke_function(
                function_name=function_name, body=test_data, method="POST"
            )

        return json.dumps(
            {
                "success": True,
                "function": function_name,
                "method": method.upper(),
                "test_data": test_data,
                "response": result,
                "status": "Function responded successfully",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "function": function_name,
                "method": method.upper(),
                "test_data": test_data,
                "error": str(e),
                "status": "Function test failed",
            },
            indent=2,
            ensure_ascii=False,
        )


async def get_function_url(client: SupabaseClient, function_name: str) -> str:
    """Get the full URL for a function"""
    try:
        url = f"{client.base_url}/functions/v1/{function_name}"

        return json.dumps(
            {
                "success": True,
                "function": function_name,
                "url": url,
                "curl_example": f"curl -X POST '{url}' -H 'Authorization: Bearer <anon_key>' -H 'Content-Type: application/json' -d '{{}}'",
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def check_function_health(client: SupabaseClient, function_name: str) -> str:
    """Check if a function is healthy"""
    try:
        healthy = False
        response_time = None
        error = None

        import time

        start = time.time()

        try:
            # Try to invoke with empty body
            await client.invoke_function(function_name=function_name, body={}, method="POST")
            healthy = True
        except Exception as e:
            error = str(e)
            # 400 errors might mean the function is running but needs valid input
            if "400" in str(e) or "422" in str(e):
                healthy = True
                error = "Function running (returned validation error)"

        response_time = round((time.time() - start) * 1000, 2)

        return json.dumps(
            {
                "success": True,
                "function": function_name,
                "healthy": healthy,
                "response_time_ms": response_time,
                "error": error,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)


async def invoke_function_batch(
    client: SupabaseClient, function_name: str, payloads: list[dict]
) -> str:
    """Invoke a function with multiple payloads"""
    try:
        results = []
        success_count = 0
        error_count = 0

        for i, payload in enumerate(payloads):
            try:
                result = await client.invoke_function(
                    function_name=function_name, body=payload, method="POST"
                )
                results.append({"index": i, "success": True, "response": result})
                success_count += 1
            except Exception as e:
                results.append({"index": i, "success": False, "error": str(e)})
                error_count += 1

        return json.dumps(
            {
                "success": True,
                "function": function_name,
                "total": len(payloads),
                "succeeded": success_count,
                "failed": error_count,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
