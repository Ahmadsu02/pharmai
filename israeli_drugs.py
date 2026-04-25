# Maps common Israeli/regional brand names to their active ingredients
# Used to improve OpenFDA lookup accuracy for drugs not found by brand name

BRAND_TO_INGREDIENT: dict[str, list[str]] = {
    # ── Pain / Fever ──
    "optalgin":     ["metamizole", "dipyrone"],
    "acamol":       ["paracetamol", "acetaminophen"],
    "panadol":      ["paracetamol", "acetaminophen"],
    "tylenol":      ["paracetamol", "acetaminophen"],
    "advil":        ["ibuprofen"],
    "nurofen":      ["ibuprofen"],
    "voltaren":     ["diclofenac"],
    "dexxon":       ["diclofenac"],
    "diclac":       ["diclofenac"],
    "aspirin":      ["aspirin", "acetylsalicylic acid"],
    "tramadex":     ["tramadol"],

    # ── Antibiotics ──
    "augmentin":    ["amoxicillin", "clavulanate"],
    "amoxil":       ["amoxicillin"],
    "penicilin":    ["amoxicillin"],
    "cipro":        ["ciprofloxacin"],
    "zithromax":    ["azithromycin"],
    "azithromycin": ["azithromycin"],
    "flagyl":       ["metronidazole"],
    "tavanic":      ["levofloxacin"],
    "clindamycin":  ["clindamycin"],
    "doxycycline":  ["doxycycline"],
    "cephalexin":   ["cephalexin"],

    # ── Cardiovascular ──
    "normoten":     ["amlodipine"],
    "norvasc":      ["amlodipine"],
    "lipitor":      ["atorvastatin"],
    "zocor":        ["simvastatin"],
    "crestor":      ["rosuvastatin"],
    "plavix":       ["clopidogrel"],
    "coumadin":     ["warfarin"],
    "concor":       ["bisoprolol"],
    "tritace":      ["ramipril"],
    "ramipril":     ["ramipril"],
    "enalapril":    ["enalapril"],
    "lasix":        ["furosemide"],
    "aldactone":    ["spironolactone"],
    "clexane":      ["enoxaparin"],
    "digoxin":      ["digoxin"],

    # ── GI ──
    "nexium":       ["esomeprazole"],
    "losec":        ["omeprazole"],
    "controloc":    ["pantoprazole"],
    "zantac":       ["ranitidine"],
    "imodium":      ["loperamide"],
    "dulcolax":     ["bisacodyl"],
    "motilium":     ["domperidone"],

    # ── Respiratory ──
    "ventolin":     ["salbutamol", "albuterol"],
    "flixotide":    ["fluticasone"],
    "singulair":    ["montelukast"],
    "singular":     ["montelukast"],
    "telfast":      ["fexofenadine"],
    "claritine":    ["loratadine"],
    "claritin":     ["loratadine"],
    "zyrtec":       ["cetirizine"],
    "atrovent":     ["ipratropium"],

    # ── CNS / Psychiatry ──
    "dipan":        ["diazepam"],
    "valium":       ["diazepam"],
    "prozac":       ["fluoxetine"],
    "cipralex":     ["escitalopram"],
    "zoloft":       ["sertraline"],
    "risperdal":    ["risperidone"],
    "xanax":        ["alprazolam"],
    "stilnox":      ["zolpidem"],
    "lamictal":     ["lamotrigine"],
    "tegretol":     ["carbamazepine"],
    "depakine":     ["valproate", "valproic acid"],

    # ── Diabetes ──
    "glucophage":   ["metformin"],
    "amaryl":       ["glimepiride"],
    "lantus":       ["insulin glargine"],
    "humalog":      ["insulin lispro"],
    "januvia":      ["sitagliptin"],

    # ── Thyroid ──
    "eltroxin":     ["levothyroxine"],
    "synthroid":    ["levothyroxine"],

    # ── Other ──
    "zofran":       ["ondansetron"],
    "diflucan":     ["fluconazole"],
    "zovirax":      ["acyclovir"],
    "tamiflu":      ["oseltamivir"],
    "prednisolone": ["prednisolone"],
    "prednisone":   ["prednisone"],
    "dexamethasone":["dexamethasone"],
}


def resolve_to_ingredients(name: str) -> list[str]:
    """Return active ingredient(s) for a drug name, or [name] if not in dictionary."""
    return BRAND_TO_INGREDIENT.get(name.lower(), [name.lower()])
