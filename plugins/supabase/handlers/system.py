"""System Handler - manages Supabase system operations (health, stats, info)"""

import json
from typing import Any

from plugins.supabase.client import SupabaseClient

def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (6 tools)"""
    return [
        {
            "name": "health_check",
            "method_name": "health_check",
            "description": "Check health of all Supabase services (PostgREST, GoTrue, Storage). Returns status for each service.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_service_status",
            "method_name": "get_service_status",
            "description": "Get detailed status of a specific Supabase service (postgrest, gotrue, storage, postgres-meta).",
            "schema": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "enum": ["postgrest", "gotrue", "storage", "postgres-meta"],
                        "description": "Service name to check",
                    }
                },
                "required": ["service"],
            },
            "scope": "read",
        },
        {
            "name": "get_database_stats",
            "method_name": "get_database_stats",
            "description": "Get database statistics including table count, total size, connection info, and PostgreSQL version.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_storage_stats",
            "method_name": "get_storage_stats",
            "description": "Get storage statistics including bucket count, total files, and usage information.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_auth_stats",
            "method_name": "get_auth_stats",
            "description": "Get authentication statistics including total users, confirmed users, and provider breakdown.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
        {
            "name": "get_instance_info",
            "method_name": "get_instance_info",
            "description": "Get Supabase instance information including base URL and available API endpoints.",
            "schema": {"type": "object", "properties": {}},
            "scope": "read",
        },
    ]

async def health_check(client: SupabaseClient) -> str:
    """Check health of all Supabase services"""
    try:
        result = await client.health_check()

        return json.dumps(
            {
                "success": True,
                "healthy": result.get("healthy", False),
                "instance_url": client.base_url,
                "services": result.get("services", {}),
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"success": False, "healthy": False, "error": str(e), "instance_url": client.base_url},
            indent=2,
            ensure_ascii=False,
        )

async def get_service_status(client: SupabaseClient, service: str) -> str:
    """Get status of a specific service"""
    try:
        status = {"service": service, "status": "unknown"}

        if service == "postgrest":
            # Check PostgREST by hitting root endpoint
            try:
                await client.request("GET", "/rest/v1/", use_service_role=True)
                status["status"] = "ok"
                status["endpoint"] = f"{client.base_url}/rest/v1/"
            except Exception as e:
                status["status"] = "error"
                status["error"] = str(e)

        elif service == "gotrue":
            # Check GoTrue health endpoint
            try:
                result = await client.request("GET", "/auth/v1/health", use_service_role=False)
                status["status"] = "ok"
                status["endpoint"] = f"{client.base_url}/auth/v1/"
                status["details"] = result
            except Exception as e:
                status["status"] = "error"
                status["error"] = str(e)

        elif service == "storage":
            # Check Storage by listing buckets
            try:
                buckets = await client.list_buckets()
                status["status"] = "ok"
                status["endpoint"] = f"{client.base_url}/storage/v1/"
                status["bucket_count"] = len(buckets) if isinstance(buckets, list) else 0
            except Exception as e:
                status["status"] = "error"
                status["error"] = str(e)

        elif service == "postgres-meta":
            # Check postgres-meta by listing schemas
            try:
                schemas = await client.list_schemas()
                status["status"] = "ok"
                status["endpoint"] = f"{client.base_url}/pg/"
                status["schema_count"] = len(schemas) if isinstance(schemas, list) else 0
            except Exception as e:
                status["status"] = "error"
                status["error"] = str(e)

        else:
            status["status"] = "unknown"
            status["error"] = f"Unknown service: {service}"

        return json.dumps(
            {"success": status["status"] == "ok", **status}, indent=2, ensure_ascii=False
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_database_stats(client: SupabaseClient) -> str:
    """Get database statistics"""
    try:
        stats = {
            "tables": 0,
            "schemas": 0,
            "extensions": 0,
            "size": "unknown",
            "version": "unknown",
        }

        # Get table count
        try:
            tables = await client.list_tables()
            stats["tables"] = len(tables) if isinstance(tables, list) else 0
        except:
            pass

        # Get schema count
        try:
            schemas = await client.list_schemas()
            stats["schemas"] = len(schemas) if isinstance(schemas, list) else 0
        except:
            pass

        # Get extension count
        try:
            extensions = await client.list_extensions()
            stats["extensions"] = len(extensions) if isinstance(extensions, list) else 0
        except:
            pass

        # Get database size and version
        try:
            size_result = await client.execute_sql(
                "SELECT pg_size_pretty(pg_database_size(current_database())) as size, version() as version"
            )
            if isinstance(size_result, list) and len(size_result) > 0:
                stats["size"] = size_result[0].get("size", "unknown")
                stats["version"] = size_result[0].get("version", "unknown")
        except:
            pass

        # Get connection info
        try:
            conn_result = await client.execute_sql(
                "SELECT count(*) as connections FROM pg_stat_activity WHERE state = 'active'"
            )
            if isinstance(conn_result, list) and len(conn_result) > 0:
                stats["active_connections"] = conn_result[0].get("connections", 0)
        except:
            pass

        return json.dumps({"success": True, "database_stats": stats}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_storage_stats(client: SupabaseClient) -> str:
    """Get storage statistics"""
    try:
        stats = {
            "buckets": 0,
            "public_buckets": 0,
            "private_buckets": 0,
            "total_files": 0,
            "bucket_details": [],
        }

        try:
            buckets = await client.list_buckets()

            if isinstance(buckets, list):
                stats["buckets"] = len(buckets)
                stats["public_buckets"] = sum(1 for b in buckets if b.get("public", False))
                stats["private_buckets"] = stats["buckets"] - stats["public_buckets"]

                # Get file counts per bucket
                for bucket in buckets:
                    bucket_id = bucket.get("id") or bucket.get("name")
                    bucket_info = {
                        "name": bucket_id,
                        "public": bucket.get("public", False),
                        "file_count": 0,
                    }

                    try:
                        files = await client.list_files(bucket_id, limit=1000)
                        if isinstance(files, list):
                            bucket_info["file_count"] = len(files)
                            stats["total_files"] += len(files)
                    except:
                        pass

                    stats["bucket_details"].append(bucket_info)
        except Exception as e:
            stats["error"] = str(e)

        return json.dumps({"success": True, "storage_stats": stats}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_auth_stats(client: SupabaseClient) -> str:
    """Get authentication statistics"""
    try:
        stats = {
            "total_users": 0,
            "confirmed_users": 0,
            "unconfirmed_users": 0,
            "users_with_mfa": 0,
            "providers": {},
        }

        try:
            # Get users (first page)
            users_response = await client.list_users(page=1, per_page=1000)

            if isinstance(users_response, dict):
                users = users_response.get("users", [])
            else:
                users = users_response if isinstance(users_response, list) else []

            stats["total_users"] = len(users)

            for user in users:
                # Count confirmed/unconfirmed
                if user.get("email_confirmed_at") or user.get("confirmed_at"):
                    stats["confirmed_users"] += 1
                else:
                    stats["unconfirmed_users"] += 1

                # Count MFA enabled
                factors = user.get("factors", [])
                if factors and len(factors) > 0:
                    stats["users_with_mfa"] += 1

                # Count by provider
                identities = user.get("identities", [])
                for identity in identities:
                    provider = identity.get("provider", "email")
                    stats["providers"][provider] = stats["providers"].get(provider, 0) + 1

            # If no identities, count as email
            if not stats["providers"]:
                stats["providers"]["email"] = stats["total_users"]

        except Exception as e:
            stats["error"] = str(e)

        return json.dumps({"success": True, "auth_stats": stats}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)

async def get_instance_info(client: SupabaseClient) -> str:
    """Get Supabase instance information"""
    try:
        info = {
            "base_url": client.base_url,
            "api_endpoints": {
                "rest": f"{client.base_url}/rest/v1",
                "auth": f"{client.base_url}/auth/v1",
                "storage": f"{client.base_url}/storage/v1",
                "functions": f"{client.base_url}/functions/v1",
                "realtime": f"{client.base_url}/realtime/v1",
                "postgres_meta": f"{client.base_url}/pg",
            },
            "deployment_type": "self-hosted",
            "services_available": [],
        }

        # Check which services are available
        services_to_check = ["postgrest", "gotrue", "storage", "postgres-meta"]

        for service in services_to_check:
            try:
                if service == "postgrest":
                    await client.request("GET", "/rest/v1/", use_service_role=True)
                elif service == "gotrue":
                    await client.request("GET", "/auth/v1/health", use_service_role=False)
                elif service == "storage":
                    await client.list_buckets()
                elif service == "postgres-meta":
                    await client.list_schemas()

                info["services_available"].append(service)
            except:
                pass

        # Try to get PostgreSQL version
        try:
            version_result = await client.execute_sql("SELECT version()")
            if isinstance(version_result, list) and len(version_result) > 0:
                info["postgres_version"] = version_result[0].get("version", "unknown")
        except:
            pass

        return json.dumps({"success": True, "instance_info": info}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, ensure_ascii=False)
