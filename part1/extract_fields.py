from collections import Counter, defaultdict

import os, io, json
from typing import Tuple
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from openai import AzureOpenAI
from prompt import SYSTEM_PROMPT
from validators import ExtractedForm
from dotenv import load_dotenv

import re

load_dotenv()

DOCINT_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
DOCINT_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AOAI_MODEL = os.getenv("AZURE_OPENAI_GPT_MODEL", "gpt-4o")


SEP_CHARS = r"[\s\|\[\]\u200e\u200f\u202a-\u202e]+"  # espaces/|/[]/RLM/LRM/etc.

gender= ["נקבה/female", "זכר/male"]
accident_location= [
    "אחר",
    "תאונה בדרך ללא רכב",
    "ת. דרכים בדרך לעבודה/מהעבודה",
    "ת. דרכים בעבודה",
    "במפעל"]
hmo = ["כללית", "מאוחדת","מכבי","לאומית","הנפגע חבר בקופת חולים"]

not_hmo = ["הנפגע אינו חבר בקופת חולים"]
nature_of_accident=["מהות התאונה (אבחנות רפואיות)"]


# --- mapping utilitaires sur tes listes ---
def _he_label(option: str) -> str:
    # tes labels de gender sont "נקבה/female", "זכר/male" -> on garde la partie hébreu
    return option.split("/", 1)[0] if "/" in option else option

def _first_checked_index(boxes: str) -> int:
    """Retourne l'index de la première case cochée (☒) dans une chaîne de cases, sinon -1."""
    for i, ch in enumerate(boxes):
        if ch == "☒":
            return i
    return -1

def _extract_boxes_sequence(text: str) -> list[str]:
    """Retourne la liste brute des cases dans l'ordre (p.ex. ['☐','☒',...])."""
    return re.findall(r"[☒☐]", text)

def _split_groups(boxes_list: list[str]) -> list[str]:
    """Découpe en 2,5,5,1,1 et renvoie une liste de 5 chaînes."""
    sizes = [2, 5, 5, 1, 1]
    groups, s = [], 0
    for size in sizes:
        groups.append("".join(boxes_list[s:s+size]))
        s += size
    # si la source a moins de cases, on pad avec des '☐' pour éviter les IndexError
    for i, size in enumerate(sizes):
        if len(groups[i]) < size:
            groups[i] = groups[i] + "☐" * (size - len(groups[i]))
    return groups  # [gender2, accident5, hmo5, isMember1, notMember1]

def parse_checkbox_blocks(ocr_text: str):
    """
    Mappe les cases OCR aux listes:
      gender (2), accident_location (5), hmo (5), hmo_member (1), not_hmo (1)
    Renvoie un dict avec:
      - 'gender': label hébreu sélectionné ou ""
      - 'accidentLocation': label hébreu sélectionné ou "" (selon l'ordre imposé)
      - 'healthFundMember': label HMO sélectionné (כללית/מכבי/מאוחדת/לאומית) ou "אינו חבר בקופת חולים" ou ""
      - 'rawGroups': les 5 groupes de cases pour debug
    """
    boxes_list = _extract_boxes_sequence(ocr_text)
    g2, acc5, hmo5, isMember1, notMember1 = _split_groups(boxes_list)

    # 1) GENDER
    g_idx = _first_checked_index(g2)
    gender_selected = _he_label(gender[g_idx]) if g_idx != -1 else ""

    # 2) ACCIDENT LOCATION (ordre imposé dans ta liste)
    acc_idx = _first_checked_index(acc5)
    accident_selected = accident_location[acc_idx] if acc_idx != -1 else ""

    # 3) HMO SELECTIONS (כללית/מאוחדת/מכבי/לאומית/הנפגע חבר...)
    h_idx = _first_checked_index(hmo5)
    hmo_selected = hmo[h_idx] if h_idx != -1 else ""

    # 4) Membership flags
    mem_idx = _first_checked_index(isMember1)     # 0 si ☒, sinon -1
    notmem_idx = _first_checked_index(notMember1) # idem

    # Règle métier:
    # - Si "אינו חבר" coché => healthFundMember = "אינו חבר בקופת חולים"
    # - Sinon si "חבר בקופה" coché et une HMO cochée => healthFundMember = HMO choisi
    # - Sinon -> ""
    if notmem_idx == 0:
        health_fund_member = "אינו חבר בקופת חולים"
    elif mem_idx == 0 and hmo_selected and hmo_selected != "הנפגע חבר בקופת חולים":
        health_fund_member = hmo_selected
    else:
        health_fund_member = ""

    return {
        "gender": gender_selected,
        "accidentLocation": accident_selected,
        "healthFundMember": hmo_selected,
    
    }


def _ocr_to_text(file_bytes: bytes, language_hint: str = "auto") -> str:
    """
    Convert OCR output to text.
    """
    client = DocumentIntelligenceClient(DOCINT_ENDPOINT, AzureKeyCredential(DOCINT_KEY))
    poller = client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=file_bytes,
        output_content_format="markdown",
        string_index_type="textElements",
        locale=language_hint,
        pages="1",
        features=["OcrHighResolution"],

    )
    result = poller.result()
    text = result.get("content") or ""

    if not isinstance(text, str):
        text = str(text)
    return text

def _llm_extract(ocr_text: str, parsed_boxes: dict) -> dict:
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
                {"role": "user", "content": ocr_text+ "this is checked information you only have to take in account for gender,accident location, health fund member, : " + json.dumps(parsed_boxes)}
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


def norm(s: str) -> str:
     if not s: return ""
     s=s.replace("[","").replace("]","").replace("|","")
     return s.strip()

import re
import re
import json

def extract_and_split_boxes(text: str):
    """
    Extrait toutes les cases (☒/☐) et les découpe en groupes :
    2 premiers, puis 5, puis 5, puis 1, puis 1.
    """
    boxes = re.findall(r"[☒☐]", text)
    groups = []
    sizes = [2, 5, 5, 1, 1]
    start = 0
    for size in sizes:
        end = start + size
        groups.append("".join(boxes[start:end]))
        start = end
    return groups


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

    ocr_text = norm(ocr_text)
    
    parsed_boxes = parse_checkbox_blocks(ocr_text)
    

    extracted = _llm_extract(ocr_text,parsed_boxes)

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
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return final



