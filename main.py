import uuid
import asyncio
import subprocess
import sys
import os
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from mcp_client import search_drug, get_drug_info, get_alternatives, suggest_names
from ai_service import explain_drug, extract_drug_names, chat_with_context
from fda_service import get_drug_fda_info, check_interaction
from israeli_drugs import resolve_to_ingredients

app = FastAPI(title="AI Pharmacist API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve index.html at root ───────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

@app.get("/app", include_in_schema=False)
async def serve_app():
    return FileResponse(BASE_DIR / "index.html")

# ── Auto-start MCP server ──────────────────────────────────────────────────────
_mcp_process = None

@app.on_event("startup")
async def start_mcp():
    global _mcp_process
    mcp_dir = BASE_DIR / "israel-drugs-mcp-server"
    try:
        import shutil
        node_bin = shutil.which("node")
        if not node_bin:
            print("Warning: node not found, MCP server will not start")
            return
        _mcp_process = subprocess.Popen(
            f"{node_bin} dist/server.js --http",
            cwd=str(mcp_dir),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await asyncio.sleep(2)
        print(f"MCP server started using {node_bin}")
    except Exception as e:
        print(f"Warning: Could not start MCP server: {e}")

@app.on_event("shutdown")
async def stop_mcp():
    if _mcp_process:
        _mcp_process.terminate()

# ── Session store ──────────────────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
SESSION_MAX_TURNS = 50


def _get_session(session_id: Optional[str]) -> tuple[str, list[dict]]:
    if session_id and session_id in _sessions:
        _sessions[session_id]["last_active"] = datetime.now()
        return session_id, _sessions[session_id]["history"]
    new_id = str(uuid.uuid4())
    _sessions[new_id] = {"history": [], "last_active": datetime.now()}
    return new_id, []


def _save_to_session(session_id: str, user_msg: str, ai_reply: str) -> None:
    history = _sessions[session_id]["history"]
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": ai_reply})
    if len(history) > SESSION_MAX_TURNS * 2:
        _sessions[session_id]["history"] = history[-(SESSION_MAX_TURNS * 2):]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "message": "AI Pharmacist API is running"}


@app.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    scope: str = Query("similar_names"),
):
    try:
        data = await search_drug(q, scope)
        return {"query": q, "total": data.get("totalResults", 0), "drugs": data.get("drugs", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/drug/{registration_number}")
async def drug_info(registration_number: str, depth: str = Query("detailed")):
    try:
        return await get_drug_info(registration_number, depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alternatives")
async def alternatives(ingredient: str = Query(None), drug: str = Query(None)):
    if not ingredient and not drug:
        raise HTTPException(status_code=400, detail="Provide 'ingredient' or 'drug'")
    try:
        return await get_alternatives(active_ingredient=ingredient, drug_name=drug)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/suggest")
async def suggest(q: str = Query(..., min_length=1)):
    try:
        return await suggest_names(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/explain")
async def explain(reg: str = Query(...)):
    try:
        drug_data = await get_drug_info(reg, depth="comprehensive")
        explanation = await explain_drug(drug_data)
        return {"explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        session_id, history = _get_session(req.session_id)
        drug_names = await extract_drug_names(req.message)

        drug_contexts = []
        fda_contexts = []

        for name in drug_names[:2]:
            israeli_info = None
            try:
                result = await search_drug(name, "similar_names")
                drugs = result.get("drugs", [])
                if drugs:
                    israeli_info = await get_drug_info(drugs[0]["registrationNumber"], "comprehensive")
                    drug_contexts.append(israeli_info)
            except Exception:
                pass

            fda_terms = resolve_to_ingredients(name)
            if israeli_info:
                fda_terms = [i.lower() for i in israeli_info.get("activeIngredients", fda_terms)]

            for term in fda_terms[:2]:
                try:
                    fda_data = await get_drug_fda_info(term)
                    if fda_data.get("found"):
                        fda_contexts.append(fda_data)
                        break
                except Exception:
                    pass

        answer = await chat_with_context(req.message, drug_contexts, fda_contexts, history)
        _save_to_session(session_id, req.message, answer)

        return {
            "answer": answer,
            "session_id": session_id,
            "sources": len(drug_contexts),
            "fda_sources": len(fda_contexts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"cleared": True}


# ── FDA endpoints ──────────────────────────────────────────────────────────────

@app.get("/fda/drug")
async def fda_drug_info(name: str = Query(...)):
    try:
        terms = resolve_to_ingredients(name)
        for term in terms:
            data = await get_drug_fda_info(term)
            if data.get("found"):
                return data
        raise HTTPException(status_code=404, detail=f"'{name}' not found in OpenFDA")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fda/interactions")
async def fda_interactions(drug1: str = Query(...), drug2: str = Query(...)):
    try:
        async def resolve(name: str) -> str:
            terms = resolve_to_ingredients(name)
            if terms[0] != name.lower():
                return terms[0]
            try:
                result = await search_drug(name, "similar_names")
                drugs = result.get("drugs", [])
                if drugs:
                    info = await get_drug_info(drugs[0]["registrationNumber"], "basic")
                    ingredients = info.get("activeIngredients", [])
                    if ingredients:
                        return ingredients[0].lower()
            except Exception:
                pass
            return name

        r1, r2 = await resolve(drug1), await resolve(drug2)
        result = await check_interaction(r1, r2)
        result["resolved_drug1"] = r1
        result["resolved_drug2"] = r2
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
