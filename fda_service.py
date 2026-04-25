import httpx
import asyncio
from typing import Optional
from cache import cached

FDA_BASE = "https://api.fda.gov/drug/label.json"
TIMEOUT = 10.0


@cached(ttl=3600)
async def _fetch_label(drug_name: str) -> Optional[dict]:
    queries = [
        f'openfda.brand_name:"{drug_name}"',
        f'openfda.generic_name:"{drug_name}"',
        f'openfda.substance_name:"{drug_name}"',
    ]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for query in queries:
            try:
                resp = await client.get(FDA_BASE, params={"search": query, "limit": 1})
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if results:
                        return results[0]
            except Exception:
                continue
    return None


async def get_drug_fda_info(drug_name: str) -> dict:
    label = await _fetch_label(drug_name)
    if not label:
        return {"found": False, "drug": drug_name}

    openfda = label.get("openfda", {})
    return {
        "found": True,
        "drug": drug_name,
        "brand_names": openfda.get("brand_name", []),
        "generic_names": openfda.get("generic_name", []),
        "manufacturer": openfda.get("manufacturer_name", []),
        "route": openfda.get("route", []),
        "drug_interactions": label.get("drug_interactions", []),
        "contraindications": label.get("contraindications", []),
        "warnings": label.get("warnings_and_cautions", label.get("warnings", [])),
        "boxed_warning": label.get("boxed_warning", []),
        "adverse_reactions": label.get("adverse_reactions", []),
        "indications_and_usage": label.get("indications_and_usage", []),
    }


async def check_interaction(drug1: str, drug2: str) -> dict:
    data1, data2 = await asyncio.gather(
        get_drug_fda_info(drug1),
        get_drug_fda_info(drug2),
    )

    d2_lower = drug2.lower()
    d1_lower = drug1.lower()

    # Also check generic names for broader matching
    d2_names = [drug2.lower()] + [n.lower() for n in data2.get("generic_names", [])]
    d1_names = [drug1.lower()] + [n.lower() for n in data1.get("generic_names", [])]

    mentions_d2_in_d1 = []
    mentions_d1_in_d2 = []

    for entry in data1.get("drug_interactions", []):
        entry_lower = entry.lower()
        if any(n in entry_lower for n in d2_names):
            mentions_d2_in_d1.append(entry)

    for entry in data2.get("drug_interactions", []):
        entry_lower = entry.lower()
        if any(n in entry_lower for n in d1_names):
            mentions_d1_in_d2.append(entry)

    return {
        "drug1": drug1,
        "drug2": drug2,
        "drug1_fda": data1,
        "drug2_fda": data2,
        "interaction_found": bool(mentions_d2_in_d1 or mentions_d1_in_d2),
        "drug1_mentions_drug2": mentions_d2_in_d1,
        "drug2_mentions_drug1": mentions_d1_in_d2,
    }
