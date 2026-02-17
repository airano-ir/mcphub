"""
Documents Handler - manages Appwrite document CRUD operations

Phase I.1: 12 tools
- Documents CRUD: 5 (list, get, create, update, delete)
- Bulk Operations: 3 (bulk_create, bulk_update, bulk_delete)
- Query/Count: 4 (search, count, get_by_query, list_with_cursor)
"""

import json
from typing import Any

from plugins.appwrite.client import AppwriteClient

# =====================
# QUERY HELPERS (Appwrite 1.7.4 JSON format)
# =====================


def _query_limit(value: int) -> str:
    """Build limit query in JSON format."""
    return json.dumps({"method": "limit", "values": [value]})


def _query_offset(value: int) -> str:
    """Build offset query in JSON format."""
    return json.dumps({"method": "offset", "values": [value]})


def _query_order_asc(attribute: str) -> str:
    """Build orderAsc query in JSON format."""
    return json.dumps({"method": "orderAsc", "values": [attribute]})


def _query_order_desc(attribute: str) -> str:
    """Build orderDesc query in JSON format."""
    return json.dumps({"method": "orderDesc", "values": [attribute]})


def _query_cursor_after(document_id: str) -> str:
    """Build cursorAfter query in JSON format."""
    return json.dumps({"method": "cursorAfter", "values": [document_id]})


def _query_cursor_before(document_id: str) -> str:
    """Build cursorBefore query in JSON format."""
    return json.dumps({"method": "cursorBefore", "values": [document_id]})


def _query_search(attribute: str, value: str) -> str:
    """Build search query in JSON format."""
    return json.dumps({"method": "search", "attribute": attribute, "values": [value]})


def _query_equal(attribute: str, values: list[Any]) -> str:
    """Build equal query in JSON format."""
    return json.dumps({"method": "equal", "attribute": attribute, "values": values})


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator (12 tools)"""
    return [
        # =====================
        # DOCUMENT CRUD (5)
        # =====================
        {
            "name": "list_documents",
            "method_name": "list_documents",
            "description": """List documents in a collection with powerful query support.

Queries must be JSON objects (Appwrite 1.7.4 format):
- {"method": "equal", "attribute": "status", "values": ["active"]}
- {"method": "notEqual", "attribute": "type", "values": ["draft"]}
- {"method": "greaterThan", "attribute": "price", "values": [100]}
- {"method": "search", "attribute": "title", "values": ["keyword"]}
- {"method": "orderAsc", "values": ["createdAt"]}
- {"method": "orderDesc", "values": ["createdAt"]}
- {"method": "limit", "values": [25]}
- {"method": "offset", "values": [50]}
- {"method": "cursorAfter", "values": ["documentId"]}""",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Query JSON strings for filtering, sorting, and pagination",
                        "examples": [
                            [
                                '{"method":"equal","attribute":"status","values":["active"]}',
                                '{"method":"limit","values":[25]}',
                            ]
                        ],
                    },
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_document",
            "method_name": "get_document",
            "description": "Get a single document by ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "document_id": {"type": "string", "description": "Document ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Optional queries for selecting specific attributes",
                    },
                },
                "required": ["database_id", "collection_id", "document_id"],
            },
            "scope": "read",
        },
        {
            "name": "create_document",
            "method_name": "create_document",
            "description": "Create a new document. Use 'unique()' as document_id for auto-generated ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "document_id": {
                        "type": "string",
                        "description": "Unique document ID. Use 'unique()' for auto-generation",
                    },
                    "data": {
                        "type": "object",
                        "description": "Document data (key-value pairs matching collection attributes)",
                    },
                    "permissions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Document permissions (e.g., 'read(\"user:123\")', 'write(\"team:456\")')",
                    },
                },
                "required": ["database_id", "collection_id", "document_id", "data"],
            },
            "scope": "write",
        },
        {
            "name": "update_document",
            "method_name": "update_document",
            "description": "Update an existing document. Only provided fields will be updated.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "document_id": {"type": "string", "description": "Document ID"},
                    "data": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                        "description": "Fields to update",
                    },
                    "permissions": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "New permissions (replaces existing)",
                    },
                },
                "required": ["database_id", "collection_id", "document_id"],
            },
            "scope": "write",
        },
        {
            "name": "delete_document",
            "method_name": "delete_document",
            "description": "Delete a document by ID.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "document_id": {"type": "string", "description": "Document ID to delete"},
                },
                "required": ["database_id", "collection_id", "document_id"],
            },
            "scope": "write",
        },
        # =====================
        # BULK OPERATIONS (3)
        # =====================
        {
            "name": "bulk_create_documents",
            "method_name": "bulk_create_documents",
            "description": """Create multiple documents at once. More efficient than creating one by one.

Example documents array:
[
  {"document_id": "unique()", "data": {"title": "Doc 1", "status": "active"}},
  {"document_id": "doc-2", "data": {"title": "Doc 2", "status": "draft"}, "permissions": ["read(\\"any\\")"]}
]

Each document must have:
- document_id: Use 'unique()' for auto-generated ID or provide your own
- data: Object with field values matching collection attributes""",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "documents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "document_id": {
                                    "type": "string",
                                    "description": "Document ID. Use 'unique()' for auto-generation",
                                },
                                "data": {
                                    "type": "object",
                                    "description": "Document data (key-value pairs matching collection attributes)",
                                },
                                "permissions": {
                                    "anyOf": [
                                        {"type": "array", "items": {"type": "string"}},
                                        {"type": "null"},
                                    ],
                                    "description": "Optional permissions for this document",
                                },
                            },
                            "required": ["document_id", "data"],
                        },
                        "description": "Array of documents to create. Each must have document_id and data.",
                    },
                },
                "required": ["database_id", "collection_id", "documents"],
            },
            "scope": "write",
        },
        {
            "name": "bulk_update_documents",
            "method_name": "bulk_update_documents",
            "description": "Update multiple documents at once.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "document_id": {"type": "string"},
                                "data": {"type": "object"},
                                "permissions": {
                                    "anyOf": [
                                        {"type": "array", "items": {"type": "string"}},
                                        {"type": "null"},
                                    ]
                                },
                            },
                            "required": ["document_id", "data"],
                        },
                        "description": "Array of document updates",
                    },
                },
                "required": ["database_id", "collection_id", "updates"],
            },
            "scope": "write",
        },
        {
            "name": "bulk_delete_documents",
            "method_name": "bulk_delete_documents",
            "description": "Delete multiple documents at once.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of document IDs to delete",
                    },
                },
                "required": ["database_id", "collection_id", "document_ids"],
            },
            "scope": "write",
        },
        # =====================
        # QUERY/SEARCH (4)
        # =====================
        {
            "name": "search_documents",
            "method_name": "search_documents",
            "description": "Full-text search in documents. Requires a fulltext index on the searched attribute.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "attribute": {
                        "type": "string",
                        "description": "Attribute name to search in (must have fulltext index)",
                    },
                    "query": {"type": "string", "description": "Search query string"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 25},
                },
                "required": ["database_id", "collection_id", "attribute", "query"],
            },
            "scope": "read",
        },
        {
            "name": "count_documents",
            "method_name": "count_documents",
            "description": "Count documents in a collection with optional filters.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "queries": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Optional filter queries",
                    },
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "read",
        },
        {
            "name": "get_documents_by_ids",
            "method_name": "get_documents_by_ids",
            "description": "Get multiple documents by their IDs.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of document IDs to fetch",
                    },
                },
                "required": ["database_id", "collection_id", "document_ids"],
            },
            "scope": "read",
        },
        {
            "name": "list_documents_paginated",
            "method_name": "list_documents_paginated",
            "description": "List documents with cursor-based pagination for efficient large dataset traversal.",
            "schema": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Database ID"},
                    "collection_id": {"type": "string", "description": "Collection ID"},
                    "limit": {
                        "type": "integer",
                        "description": "Results per page",
                        "default": 25,
                        "maximum": 100,
                    },
                    "cursor": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Cursor from previous response for next page",
                    },
                    "cursor_direction": {
                        "type": "string",
                        "enum": ["after", "before"],
                        "description": "Cursor direction",
                        "default": "after",
                    },
                    "order_attribute": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Attribute to order by (default: $id)",
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "Sort order",
                        "default": "DESC",
                    },
                    "filters": {
                        "anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}],
                        "description": "Additional filter queries",
                    },
                },
                "required": ["database_id", "collection_id"],
            },
            "scope": "read",
        },
    ]


# =====================
# HANDLER FUNCTIONS
# =====================


async def list_documents(
    client: AppwriteClient, database_id: str, collection_id: str, queries: list[str] | None = None
) -> str:
    """List documents with queries."""
    try:
        result = await client.list_documents(
            database_id=database_id, collection_id=collection_id, queries=queries
        )
        documents = result.get("documents", [])

        response = {
            "success": True,
            "database_id": database_id,
            "collection_id": collection_id,
            "total": result.get("total", len(documents)),
            "documents": documents,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_document(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    document_id: str,
    queries: list[str] | None = None,
) -> str:
    """Get document by ID."""
    try:
        result = await client.get_document(
            database_id=database_id,
            collection_id=collection_id,
            document_id=document_id,
            queries=queries,
        )
        return json.dumps({"success": True, "document": result}, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def create_document(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    document_id: str,
    data: dict[str, Any],
    permissions: list[str] | None = None,
) -> str:
    """Create a new document."""
    try:
        result = await client.create_document(
            database_id=database_id,
            collection_id=collection_id,
            document_id=document_id,
            data=data,
            permissions=permissions,
        )
        return json.dumps(
            {"success": True, "message": "Document created successfully", "document": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def update_document(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    document_id: str,
    data: dict[str, Any] | None = None,
    permissions: list[str] | None = None,
) -> str:
    """Update document."""
    try:
        result = await client.update_document(
            database_id=database_id,
            collection_id=collection_id,
            document_id=document_id,
            data=data,
            permissions=permissions,
        )
        return json.dumps(
            {"success": True, "message": "Document updated successfully", "document": result},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def delete_document(
    client: AppwriteClient, database_id: str, collection_id: str, document_id: str
) -> str:
    """Delete document."""
    try:
        await client.delete_document(database_id, collection_id, document_id)
        return json.dumps(
            {"success": True, "message": f"Document '{document_id}' deleted successfully"}, indent=2
        )

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def bulk_create_documents(
    client: AppwriteClient, database_id: str, collection_id: str, documents: list[dict[str, Any]]
) -> str:
    """Create multiple documents."""
    try:
        results = []
        errors = []

        for doc in documents:
            try:
                result = await client.create_document(
                    database_id=database_id,
                    collection_id=collection_id,
                    document_id=doc.get("document_id", "unique()"),
                    data=doc["data"],
                    permissions=doc.get("permissions"),
                )
                results.append({"id": result.get("$id"), "success": True})
            except Exception as e:
                errors.append({"document_id": doc.get("document_id"), "error": str(e)})

        response = {
            "success": len(errors) == 0,
            "created": len(results),
            "failed": len(errors),
            "results": results,
        }
        if errors:
            response["errors"] = errors

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def bulk_update_documents(
    client: AppwriteClient, database_id: str, collection_id: str, updates: list[dict[str, Any]]
) -> str:
    """Update multiple documents."""
    try:
        results = []
        errors = []

        for update in updates:
            try:
                result = await client.update_document(
                    database_id=database_id,
                    collection_id=collection_id,
                    document_id=update["document_id"],
                    data=update.get("data"),
                    permissions=update.get("permissions"),
                )
                results.append({"id": result.get("$id"), "success": True})
            except Exception as e:
                errors.append({"document_id": update["document_id"], "error": str(e)})

        response = {
            "success": len(errors) == 0,
            "updated": len(results),
            "failed": len(errors),
            "results": results,
        }
        if errors:
            response["errors"] = errors

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def bulk_delete_documents(
    client: AppwriteClient, database_id: str, collection_id: str, document_ids: list[str]
) -> str:
    """Delete multiple documents."""
    try:
        results = []
        errors = []

        for doc_id in document_ids:
            try:
                await client.delete_document(database_id, collection_id, doc_id)
                results.append({"id": doc_id, "success": True})
            except Exception as e:
                errors.append({"document_id": doc_id, "error": str(e)})

        response = {
            "success": len(errors) == 0,
            "deleted": len(results),
            "failed": len(errors),
            "results": results,
        }
        if errors:
            response["errors"] = errors

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def search_documents(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    attribute: str,
    query: str,
    limit: int = 25,
) -> str:
    """Full-text search in documents."""
    try:
        # Appwrite 1.7.4 JSON format for queries
        queries = [_query_search(attribute, query), _query_limit(limit)]
        result = await client.list_documents(
            database_id=database_id, collection_id=collection_id, queries=queries
        )
        documents = result.get("documents", [])

        response = {
            "success": True,
            "query": query,
            "attribute": attribute,
            "total": result.get("total", len(documents)),
            "documents": documents,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = str(e)
        if "fulltext" in error_msg.lower() or "index" in error_msg.lower():
            error_msg += " (Hint: Make sure you have a fulltext index on the searched attribute)"
        return json.dumps({"success": False, "error": error_msg}, indent=2)


async def count_documents(
    client: AppwriteClient, database_id: str, collection_id: str, queries: list[str] | None = None
) -> str:
    """Count documents in collection."""
    try:
        # Build query list: start with user filters, add limit(1) to minimize data
        count_queries = []

        # Add user-provided filter queries (make a copy to avoid mutating input)
        if queries and len(queries) > 0:
            count_queries.extend(queries)

        # Always add limit(1) to minimize data transfer - Appwrite 1.7.4 JSON format
        count_queries.append(_query_limit(1))

        result = await client.list_documents(
            database_id=database_id, collection_id=collection_id, queries=count_queries
        )

        response = {
            "success": True,
            "database_id": database_id,
            "collection_id": collection_id,
            "count": result.get("total", 0),
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def get_documents_by_ids(
    client: AppwriteClient, database_id: str, collection_id: str, document_ids: list[str]
) -> str:
    """Get multiple documents by IDs."""
    try:
        documents = []
        errors = []

        for doc_id in document_ids:
            try:
                doc = await client.get_document(
                    database_id=database_id, collection_id=collection_id, document_id=doc_id
                )
                documents.append(doc)
            except Exception as e:
                errors.append({"document_id": doc_id, "error": str(e)})

        response = {
            "success": len(errors) == 0,
            "found": len(documents),
            "not_found": len(errors),
            "documents": documents,
        }
        if errors:
            response["errors"] = errors

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


async def list_documents_paginated(
    client: AppwriteClient,
    database_id: str,
    collection_id: str,
    limit: int = 25,
    cursor: str | None = None,
    cursor_direction: str = "after",
    order_attribute: str | None = None,
    order_type: str = "DESC",
    filters: list[str] | None = None,
) -> str:
    """List documents with cursor pagination."""
    try:
        # Build query list (don't mutate input) - Appwrite 1.7.4 JSON format
        queries = []

        # Add user-provided filter queries
        if filters and len(filters) > 0:
            queries.extend(filters)

        # Add ordering only if explicitly specified
        if order_attribute:
            if order_type == "DESC":
                queries.append(_query_order_desc(order_attribute))
            else:
                queries.append(_query_order_asc(order_attribute))

        # Add cursor
        if cursor:
            if cursor_direction == "after":
                queries.append(_query_cursor_after(cursor))
            else:
                queries.append(_query_cursor_before(cursor))

        # Add limit only if queries exist or limit differs from default
        if queries or limit != 25:
            queries.append(_query_limit(min(limit, 100)))

        result = await client.list_documents(
            database_id=database_id,
            collection_id=collection_id,
            queries=queries if queries else None,
        )
        documents = result.get("documents", [])

        # Determine next cursor
        next_cursor = None
        if documents and len(documents) == limit:
            next_cursor = documents[-1].get("$id")

        response = {
            "success": True,
            "total": result.get("total", 0),
            "count": len(documents),
            "documents": documents,
            "pagination": {
                "limit": limit,
                "cursor": cursor,
                "next_cursor": next_cursor,
                "has_more": next_cursor is not None,
            },
        }
        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
