import os
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from openai import AzureOpenAI

from models import (
    CollectRequest,
    CollectResponse,
    ChatRequest,
    ChatResponse,
)
from prompts import COLLECT_PROMPT, QA_PROMPT
from kb_index import build_index, search_dual
from logger import log

# === Config & client =========================================================
load_dotenv()

AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

client = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT,
    api_key=AOAI_KEY,
    api_version=AOAI_API_VERSION,
)

# === App ====================================================================
app = FastAPI(title="Stateless HMO Chatbot (Part 2)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Routes =================================================================


@app.post("/build_index")
def api_build_index():
    try:
        res = build_index()
        log("index_built", **res)
        return {"status": "ok", **res}
    except Exception as e:
        log("index_build_error", error=str(e))
        raise HTTPException(500, str(e))


def _normalize_history_for_llm(raw_msgs, limit=12):
    role_map = {"user": "user", "assistant": "assistant", "bot": "assistant", "ai": "assistant"}
    out = []
    for m in raw_msgs[-limit:]:
        role = m.get("role", "").lower()
        r = role_map.get(role, None)
        if r in ("user", "assistant"):
            out.append({"role": r, "content": m.get("content", "")})
    return out


@app.post("/collect", response_model=CollectResponse)
def api_collect(req: CollectRequest):
    """
    LLM-led intake (stateless): the client sends history + current user_info.
    The LLM returns a JSON control object: phase, message, missing, userinfo, lang.
    """

    messages = [
        {"role": "system", "content": COLLECT_PROMPT},
        {
            "role": "system",
            "content": f"Here is the current collected user info (may be partial or invalid):\n{req.user_info.model_dump()} and the language preference is '{req.lang}'.",
        },
        *req.history
    ]
    try:
        log("collect_request", lang=req.lang)
        rsp = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = rsp.choices[0].message.content
        data = json.loads(content)
        out = CollectResponse(**data)
        log("collect_response", phase=out.phase)
        return out
    except Exception as e:
        log("collect_error", error=str(e))
        raise HTTPException(500, f"Collect failed: {e}")


@app.post("/chat", response_model=ChatResponse)
def api_chat(req: ChatRequest):
    """
    Q&A over KB (stateless): client provides history + user_info + question.
    We retrieve KB chunks, then ask the model to answer strictly from them.
    """
    # 1) Retrieve top-k KB chunks
    try:
        res = search_dual(req.question, hmo=req.user_info.hmo, tier=req.user_info.tier, k_basic=6, k_filtered=6, language=req.lang)
        hits= res["basic"]+res["filtered"]

    except FileNotFoundError:
        raise HTTPException(400, "KB index not built. Call /build_index first.")
    except Exception as e:
        log("search_error", error=str(e))
        raise HTTPException(500, f"Search failed: {e}")

    # Add context to each snippet if available
    snippets = []
    for h in hits:
        snippet = h["content"]
        context = h.get("context")
        if context:
            snippet = f"{context}\n{snippet}"
        snippets.append(snippet)

    # 2) Build system payload for the Q&A prompt
    system_payload = {
        "lang": req.lang,
        "user_info": req.user_info.model_dump(),
        "question": req.question,
        "kb_snippets": snippets,
    }
    messages = [
        {"role": "system", "content": QA_PROMPT},
        *req.history,
        {"role": "user", "content": json.dumps(system_payload, ensure_ascii=False)}
    ]
    

    # 3) Ask the model for a strict-JSON answer
    try:
        log("chat_request", hmo=req.user_info.hmo, tier=req.user_info.tier)
        rsp = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = rsp.choices[0].message.content
        data = json.loads(content)
        out = ChatResponse(**data)
        log("chat_response")
        return out
    except Exception as e:
        log("chat_error", error=str(e))
        raise HTTPException(500, f"Chat failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)