import os
import json
from groq import AsyncGroq

_client = None

def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", ""))
    return _client

CHAT_SYSTEM = """أنت مساعد صيدلاني ذكي متخصص. مهمتك الوحيدة مساعدة الصيادلة في الأسئلة الصيدلانية والطبية فقط.

قواعد صارمة:
- أجب دائماً بالعربية بلغة واضحة ومهنية
- إذا كان السؤال غير متعلق بالصيدلة أو الأدوية أو الصحة، ارفض الإجابة بأدب: "أنا متخصص في الصيدلة فقط، لا أستطيع مساعدتك في هذا الموضوع."
- إذا كان السؤال عن دواء محدد، استخدم البيانات المتوفرة أولاً
- إذا لم تتوفر بيانات، أجب من معرفتك الطبية العامة مع التنبيه: "⚠️ من المعرفة العامة — استشر مرجعاً طبياً للتأكد"
- كن موجزاً ومفيداً — الصيدلي أمامه مريض ينتظر
- استخدم **bold** للمعلومات المهمة
- عند ذكر تفاعلات الأدوية، صنّف درجة الخطورة دائماً:
  ⛔ خطر شديد — يمنع الجمع كلياً
  ⚠️ يحتاج مراقبة — تعديل الجرعة أو متابعة مستمرة
  ℹ️ تفاعل بسيط — للعلم فقط، لا يستوجب تغييراً
- لا تنصح بتغيير الجرعة أو إيقاف الدواء بدون طبيب
- مصادر البيانات الموثوقة: قاعدة بيانات الأدوية الإسرائيلية + OpenFDA الأمريكية الرسمية"""

EXTRACT_SYSTEM = """Extract drug names from the user's question. Return ONLY a JSON array of drug names in English.
Examples:
- "ما هو أدفيل؟" → ["ibuprofen"]
- "الفرق بين بندول وأدفيل" → ["panadol", "ibuprofen"]
- "كيف يعمل الأموكسيسيلين" → ["amoxicillin"]
- "ما هي أعراض نقص الحديد" → []
Return [] if no specific drug is mentioned. Return ONLY the JSON array, nothing else."""


async def extract_drug_names(message: str) -> list[str]:
    response = await get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0,
        max_tokens=100,
    )
    try:
        text = response.choices[0].message.content.strip()
        return json.loads(text)
    except Exception:
        return []


def _build_israeli_context(drug_contexts: list[dict]) -> str:
    if not drug_contexts:
        return ""
    lines = ["\n\n=== قاعدة بيانات الأدوية الإسرائيلية ==="]
    for drug in drug_contexts:
        clinical = drug.get("clinicalInfo", {})
        warnings = clinical.get("warnings", [])
        lines.append(
            f"دواء: {drug.get('englishName', '')} ({drug.get('hebrewName', '')})\n"
            f"المادة الفعالة: {', '.join(drug.get('activeIngredients', []))}\n"
            f"الشكل: {drug.get('dosageForm', '')} - {drug.get('administrationRoute', '')}\n"
            f"الحالة: {'يحتاج وصفة' if drug.get('requiresPrescription') else 'OTC'} | "
            f"{'سلة الصحة ✓' if drug.get('inHealthBasket') else 'خارج السلة'}\n"
            f"الاستخدامات: {clinical.get('indications', 'غير متوفر')}\n"
            f"التحذيرات: {'; '.join(warnings) if warnings else 'لا توجد'}\n---"
        )
    return "\n".join(lines)


def _build_fda_context(fda_contexts: list[dict]) -> str:
    if not fda_contexts:
        return ""
    lines = ["\n\n=== بيانات OpenFDA الأمريكية (موثقة رسمياً) ==="]
    for fda in fda_contexts:
        if not fda.get("found"):
            continue
        interactions = fda.get("drug_interactions", [])
        contraindications = fda.get("contraindications", [])
        boxed = fda.get("boxed_warning", [])
        warnings = fda.get("warnings", [])
        adverse = fda.get("adverse_reactions", [])

        lines.append(f"دواء: {fda['drug']}")
        if fda.get("brand_names"):
            lines.append(f"الأسماء التجارية: {', '.join(fda['brand_names'][:3])}")
        if boxed:
            lines.append(f"⛔ تحذير مربع (Boxed Warning): {boxed[0][:500]}")
        if contraindications:
            lines.append(f"موانع الاستخدام: {contraindications[0][:400]}")
        if interactions:
            lines.append(f"تفاعلات الأدوية: {interactions[0][:600]}")
        if warnings:
            lines.append(f"تحذيرات: {warnings[0][:400]}")
        if adverse:
            lines.append(f"الأعراض الجانبية: {adverse[0][:300]}")
        lines.append("---")
    return "\n".join(lines)


async def chat_with_context(
    message: str,
    drug_contexts: list[dict],
    fda_contexts: list[dict] | None = None,
    history: list[dict] | None = None,
) -> str:
    context = _build_israeli_context(drug_contexts)
    context += _build_fda_context(fda_contexts or [])

    messages = [{"role": "system", "content": CHAT_SYSTEM + context}]
    if history:
        messages.extend(history[-10:])  # last 10 turns to stay within token limits
    messages.append({"role": "user", "content": message})

    response = await get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
    )
    return response.choices[0].message.content


async def explain_drug(drug_data: dict) -> str:
    return await chat_with_context(
        f"اشرح دواء {drug_data.get('englishName', '')} بشكل كامل",
        [drug_data]
    )
