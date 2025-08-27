import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from bs4 import BeautifulSoup
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from openai import AzureOpenAI

# === Config & Client =========================================================
load_dotenv()

AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
EMB_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-ada-002")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
PHASE2_DATA_DIR = Path(os.getenv("PHASE2_DATA_DIR", "./phase2_data"))
INDEX_DIR = Path(os.getenv("INDEX_DIR", "./kb_index"))
INDEX_DIR.mkdir(parents=True, exist_ok=True)

client = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT,
    api_key=AOAI_KEY,
    api_version=AOAI_API_VERSION,
)




# === Canon Tier (pour boost de recherche) ====================================
TIER_CANON = {
    "זהב": "זהב", "gold": "זהב", "Gold": "זהב",
    "כסף": "כסף", "silver": "כסף", "Silver": "כסף",
    "ארד": "ארד", "bronze": "ארד", "Bronze": "ארד",
}
def canon_tier(x: Optional[str]) -> str:
    if not x:
        return ""
    return TIER_CANON.get(x, x)

# === Helpers =================================================================
def parse_html(path: Path) -> List[Dict[str, Any]]:
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
    

        entries: List[Dict[str, Any]] = []
        current_h2 = ""

        def prev_immediate_h3_text(node):
            sib = node.previous_sibling
            # sauter espaces/commentaires
            while sib is not None and (getattr(sib, "name", None) is None) and str(sib).strip() == "":
                sib = sib.previous_sibling
            return sib.get_text(strip=True) if getattr(sib, "name", None) == "h3" else None

        # Parcours en ordre des blocs pertinents
        for node in soup.find_all(["h2", "h3", "p", "ul", "table"], recursive=True):
            if node.name == "h2":
                current_h2 = node.get_text(strip=True)

            elif node.name == "p":
                entries.append({
                    "title": current_h2,
                    "type": "paragraph",
                    "content": node.get_text(" ", strip=True),
                    "context": "description",
                })

            elif node.name == "ul":
                items = [li.get_text(" ", strip=True) for li in node.find_all("li", recursive=False)]
                if items:
                    sub = prev_immediate_h3_text(node)  # seulement si <h3> juste avant la liste
                    entry = {
                        "title": current_h2,
                        "type": "list",
                        "content": " \n ".join(items),
                        "context": "list",
                    }
                    if sub:
                        entry["subtitle"] = sub
                    entries.append(entry)

            elif node.name == "table":
                thead = node.find("thead")
                if thead:
                    header_row = thead.find("tr")
                    headers = [th.get_text(strip=True) for th in header_row.find_all("th")] if header_row else []
                else:
                    first_tr = node.find("tr")
                    headers = [th.get_text(strip=True) for th in first_tr.find_all(["th", "td"])] if first_tr else []

                body_rows = node.find_all("tr")
                if thead is None and body_rows and body_rows[0].find_all("th"):
                    body_rows = body_rows[1:]

                for row_idx, row in enumerate(body_rows):
                    cells = row.find_all("td")
                    if not cells:
                        continue

                    service_name = cells[0].get_text(strip=True)
                    for col_idx, cell in enumerate(cells[1:], start=1):
                        hmo_name = headers[col_idx] if col_idx < len(headers) else f"Column {col_idx + 1}"
                        strongs = cell.find_all("strong")

                        if strongs:
                            for i, st in enumerate(strongs):
                                level_name = st.get_text(strip=True).replace(":", "")
                                content_parts: List[str] = []
                                for sib in st.next_siblings:
                                    if getattr(sib, "name", None) == "strong":
                                        break
                                    text_piece = sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib).strip()
                                    if text_piece:
                                        content_parts.append(text_piece)
                                level_content = " ".join(content_parts).strip() or cell.get_text(" ", strip=True)
                                entries.append({
                                    "title": current_h2,
                                    "type": "table_cell",
                                    "content": level_content,
                                    "context": {
                                        "service_name": service_name,
                                        "hmo_name": hmo_name,
                                        "level": level_name
                                    },
                                    
                                })
                     
        return entries
    except Exception as e:
        print(f"Error parsing HTML {path}: {e}")
        return []

def embed_texts(texts: List[str]) -> np.ndarray:
    """Create embeddings for a list of strings using Azure OpenAI embeddings."""
    if not texts:
        return np.zeros((0, 1536), dtype="float32")  # ada dims; safe default
    resp = client.embeddings.create(model=EMB_DEPLOYMENT, input=texts)
    vecs = [d.embedding for d in resp.data]
    return np.array(vecs, dtype="float32")


# === Build / Load Index ======================================================


def translate_file(file_path: Path, target_language: str = "en") -> str:
    """Translate the entire content of a file to the target language."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        response = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful translator."},
                {"role": "user", "content": f"Translate the following html to {target_language}: {content}"}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error translating file {file_path}: {e}")
        return content  # Fallback to original content on error

def build_index_with_translated_files() -> Dict[str, Any]:
    """
    Build an index by first translating each file, then parsing the translated content.
    """
    entries: List[Dict[str, Any]] = []
    files = list(PHASE2_DATA_DIR.rglob("*.html"))

    for f in files:
        translated_file_path = INDEX_DIR / f"translated_{f.name}"
        if translated_file_path.exists():
            translated_content = translated_file_path.read_text(encoding="utf-8")
        else:
            translated_content = translate_file(f, target_language="en")
            translated_file_path.write_text(translated_content, encoding="utf-8")
        
        # Parse the translated file
        structured_data = parse_html(translated_file_path)
        for item in structured_data:
            content = item["content"]
            if item["type"] == "table_cell":
                ctx = item["context"]
                content = (
                    f"{ctx.get('title','')}\n"
                    f"{ctx.get('service_name','')}\n"
                    f"{content}"
                )
            else:
                title = item.get("title")
                subtitle = item.get("subtitle") if "subtitle" in item else None
                enriched_content = content
                if subtitle:
                    enriched_content = f"{subtitle} | {enriched_content}"
                if title:
                    enriched_content = f"{title} | {enriched_content}"
                content = enriched_content

            # Add to original entries
            entries.append({
                "source": str(f),
                "type": item["type"],
                "title": item.get("title"),
                "subtitle": item.get("subtitle"),
                "content": content,
                "context": item.get("context"),
            })
    if not entries:
        raise RuntimeError(f"No HTML files found under {PHASE2_DATA_DIR.resolve()}")

    # Generate embeddings for all content
    vecs = embed_texts([e["content"] for e in entries])
    np.save(INDEX_DIR / "vectors_translated.npy", vecs)
    with open(INDEX_DIR / "meta_translated.json", "w", encoding="utf-8") as w:
        json.dump(entries, w, ensure_ascii=False, indent=2)

    return {"count": len(entries), "files": len(files)}

def build_index() -> Dict[str, Any]:
    """
    Build two indices:
      - One with original content only.
      - One with translations to English.
      - Save separate vectors.npy and meta.json for each.
    """
    entries_original: List[Dict[str, Any]] = []
    files = list(PHASE2_DATA_DIR.rglob("*.html"))

    for f in files:
        structured_data = parse_html(f)
        for item in structured_data:
            content = item["content"]
            if item["type"] == "table_cell":
                ctx = item["context"]
                content = (
                    f"{ctx.get('title','')}\n"
                    f"{ctx.get('service_name','')}\n"
                    f"{content}"
                )
            else:
                title = item.get("title")
                subtitle = item.get("subtitle") if "subtitle" in item else None
                enriched_content = content
                if subtitle:
                    enriched_content = f"{subtitle} | {enriched_content}"
                if title:
                    enriched_content = f"{title} | {enriched_content}"
                content = enriched_content

            # Add to original entries
            entries_original.append({
                "source": str(f),
                "type": item["type"],
                "title": item.get("title"),
                "subtitle": item.get("subtitle"),
                "content": content,
                "context": item.get("context"),
            })


    if not entries_original:
        raise RuntimeError(f"No HTML files found under {PHASE2_DATA_DIR.resolve()}")

    # Generate embeddings for original content
    vecs_original = embed_texts([e["content"] for e in entries_original])
    np.save(INDEX_DIR / "vectors_original.npy", vecs_original)
    with open(INDEX_DIR / "meta_original.json", "w", encoding="utf-8") as w:
        json.dump(entries_original, w, ensure_ascii=False, indent=2)

    translation = build_index_with_translated_files()

    return {
        "original_count": len(entries_original),
        "translated_count": translation["count"],
        "files": len(files),
    }

def load_index() -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    vec_path = INDEX_DIR / "vectors.npy"
    meta_path = INDEX_DIR / "meta.json"
    if not vec_path.exists() or not meta_path.exists():
        raise FileNotFoundError("Index not built yet (run /build_index).")
    vecs = np.load(vec_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return vecs, meta


# === Search ==================================================================
def _canon_hmo(x: str | None) -> str:
    m = {"מכבי":"מכבי","maccabi":"מכבי","מאוחדת":"מאוחדת","meuhedet":"מאוחדת","כללית":"כללית","clalit":"כללית"}
    if not x: return ""
    x = x.strip()
    return m.get(x, m.get(x.lower(), x))

def _canon_tier(x: str | None) -> str:
    m = {"זהב":"זהב","gold":"זהב","כסף":"כסף","silver":"כסף","ארד":"ארד","bronze":"ארד"}
    if not x: return ""
    x = x.strip()
    return m.get(x, m.get(x.lower(), x))

def _strict_indices(meta, hmo: str, tier: str):
    want_hmo, want_tier = _canon_hmo(hmo), _canon_tier(tier)
    idxs = []
    for i, m in enumerate(meta):
        if m.get("type") != "table_cell":
            continue
        ctx = m.get("context") or {}
        hit_hmo = _canon_hmo(ctx.get("hmo_name"))
        hit_tier = _canon_tier(ctx.get("level"))
        if hit_hmo and hit_tier and hit_hmo == want_hmo and hit_tier == want_tier:
            idxs.append(i)
    return idxs

def load_index_by_language(language: str = "he") -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    if language == "en":
        vec_path = INDEX_DIR / "vectors_translated.npy"
        meta_path = INDEX_DIR / "meta_translated.json"
    else:
        vec_path = INDEX_DIR / "vectors_original.npy"
        meta_path = INDEX_DIR / "meta_original.json"
    if not vec_path.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Index for language '{language}' not built yet.")
    vecs = np.load(vec_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return vecs, meta

def search_basic(query: str, k: int = 6, language: str = "he"):
    vecs, meta = load_index_by_language(language)
    qv = embed_texts([query])[0].reshape(1, -1)
    sims = cosine_similarity(qv, vecs)[0]
    idxs = np.argsort(-sims)[:k]
    out = []
    for i in idxs:
        item = dict(meta[i])
        item["score"] = float(sims[i])
        out.append(item)
    return out

def search_filtered_strict(query: str, hmo: str, tier: str, k: int = 3, language: str = "he"):
    vecs, meta = load_index_by_language(language)
    idxs = _strict_indices(meta, hmo=hmo, tier=tier)
    if not idxs:
        return []  # aucun match strict -> rien
    sub_vecs = vecs[idxs]
    enriched_query = f"{query}"
    qv = embed_texts([enriched_query])[0].reshape(1, -1)
    sims = cosine_similarity(qv, sub_vecs)[0]
    order = np.argsort(-sims)[:k]
    out = []
    for j in order:
        i = idxs[int(j)]
        item = dict(meta[i])
        item["score"] = float(sims[int(j)])
        out.append(item)
    return out

def search_dual(query: str, hmo: str, tier: str, k_basic: int = 6, k_filtered: int = 3, language: str = "he"):
    basic = search_basic(query, k=k_basic, language=language)
    prof = search_filtered_strict(query, hmo=hmo, tier=tier, k=k_filtered, language=language)
    return {"basic": basic, "filtered": prof}





