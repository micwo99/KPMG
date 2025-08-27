from collections import Counter, defaultdict

import os, io, json
from typing import Tuple
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from openai import AzureOpenAI
from prompt import SYSTEM_PROMPT
from validators import ExtractedForm
from dotenv import load_dotenv

load_dotenv()

DOCINT_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOCINT_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AOAI_MODEL = os.getenv("AZURE_OPENAI_GPT_MODEL", "gpt-4o")

def _ocr_to_text(file_bytes: bytes, language_hint: str = "auto") -> str:
    """
    Convert OCR output to text.
    """
    client = DocumentIntelligenceClient(DOCINT_ENDPOINT, AzureKeyCredential(DOCINT_KEY))
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=file_bytes,
        output_content_format="text",
        string_index_type="textElements",
        locale=None if language_hint == "auto" else language_hint,
    )
    result = poller.result()
    text = result.get("content") or ""

    if not isinstance(text, str):
        text = str(text)
    return text

def _llm_extract(ocr_text: str) -> dict:
    """
    Extract structured information from OCR text using LLM.
    
    """
    client = AzureOpenAI(
        api_key=AOAI_KEY,
        api_version=AOAI_API_VERSION,
        azure_endpoint=AOAI_ENDPOINT,
    )

    try:
        completion = client.chat.completions.create(
            model=AOAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ocr_text}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content
        data = json.loads(raw)
    except Exception as e:
        print(f"Error in LLM extraction: {e}")
        data = {}
    return data
import re
def norm(s: str) -> str:
    if not s:
        return ""
    s=s.replace("[","").replace("]","").replace("|","")
    return s.strip()


def extract_fields(file_bytes: bytes, language_hint: str = "auto") -> Tuple[str, dict, dict]:
    """
    Reçoit le chemin d'un PDF, lit le fichier, puis extrait les champs.
    Args:
        pdf_path (str): Chemin vers le fichier PDF.
        language_hint (str): Langue pour l'OCR.
    Returns:
        Tuple[str, dict, dict]: Texte OCR, extraction brute, extraction normalisée.
    """

    ocr_text = _ocr_to_text(file_bytes, language_hint=language_hint)
    print(ocr_text)

    ocr_text = norm(ocr_text)
    print("ocr after norm:")
    print(ocr_text  )

    extracted = _llm_extract(ocr_text)

    # Validate and fill defaults
    try:
        model = ExtractedForm.model_validate(extracted)
        normalized = json.loads(model.model_dump_json())

        errors = {}
    except Exception as e:
        print(f"Validation error: {e}")
        normalized = extracted or {}
        errors = {"validation": str(e)}
    return ocr_text, extracted, normalized

def extract_fields_majority_vote(file_bytes: bytes, language_hint: str = "auto", runs: int = 3):
    results = []
    for _ in range(runs):
        ocr_text, extracted, normalized = extract_fields(file_bytes, language_hint)
        results.append(normalized)

    if not results:
        return {}

    final = {}
    keys = results[0].keys()
    for key in keys:
        values = [r.get(key, "") for r in results]
        non_empty = [tuple(v.items()) if isinstance(v, dict) else v for v in values if v]
        if non_empty:
            try:
                most_common = Counter(non_empty).most_common(1)[0][0]
                final[key] = dict(most_common) if isinstance(most_common, tuple) else most_common
            except IndexError:
                print(f"Error processing key '{key}': non_empty={non_empty}")
                final[key] = ""
        else:
            final[key] = ""
    return final



### plusieur probleme si landind telephone la barre est prise pour un | et le taz dasn ex3 est lu a l envers et taz dans ex2 n est aps bien reconnu comment faire 