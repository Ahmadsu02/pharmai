import httpx
import uuid

MCP_URL = "http://localhost:3000/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


async def _get_session() -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MCP_URL,
            headers=HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ai-pharmacist", "version": "1.0"},
                },
            },
        )
        return resp.headers.get("mcp-session-id", "")


async def _call_tool(session_id: str, tool: str, args: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            MCP_URL,
            headers={**HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
        )
        text = resp.text
        # SSE format: "data: {...}"
        for line in text.splitlines():
            if line.startswith("data:"):
                import json
                payload = json.loads(line[5:].strip())
                result = payload.get("result", {})
                if result.get("isError"):
                    raise ValueError(result["content"][0]["text"])
                content = result.get("content", [{}])
                raw = content[0].get("text", "{}")
                return json.loads(raw) if isinstance(raw, str) else raw
    return {}


async def search_drug(query: str, scope: str = "similar_names") -> dict:
    session_id = await _get_session()
    return await _call_tool(session_id, "discover_drug_by_name", {
        "medication_query": query,
        "search_scope": scope,
    })


async def get_drug_info(registration_number: str, depth: str = "detailed") -> dict:
    session_id = await _get_session()
    return await _call_tool(session_id, "get_comprehensive_drug_info", {
        "drug_registration_number": registration_number,
        "info_depth": depth,
        "language_preference": "both",
    })


async def get_alternatives(active_ingredient: str = None, drug_name: str = None) -> dict:
    session_id = await _get_session()
    criteria = {}
    if active_ingredient:
        criteria["active_ingredient"] = active_ingredient
    if drug_name:
        criteria["reference_drug_name"] = drug_name
    return await _call_tool(session_id, "explore_generic_alternatives", {
        "search_criteria": criteria,
        "comparison_criteria": {"include_price_comparison": True, "health_basket_priority": True},
    })


async def suggest_names(partial: str) -> dict:
    session_id = await _get_session()
    return await _call_tool(session_id, "suggest_drug_names", {
        "partial_name": partial,
        "search_type": "both",
        "max_suggestions": 10,
    })