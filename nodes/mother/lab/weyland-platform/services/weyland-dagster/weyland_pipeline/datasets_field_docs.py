"""Per-dataset field descriptions transcribed from each SOURCE's PUBLISHED field dictionary — real documentation,
not generated. Keyed by a dataset-name substring (matches the dataset/table name in the DataHub URN) → {column:
description}. A parallel *_SUFFIX map matches any column ENDING with the pattern (e.g. every Open Food Facts
`*_100g` nutriment), so a few rules cover the long tail; an exact column doc always wins over a suffix rule.

emit_field_docs() (datahub_emit.py) attaches these to EVERY store copy of the dataset (define-once per dataset).
Add datasets one at a time, prioritized by field count. Sources:
  - open_food_facts: https://static.openfoodfacts.org/data/data-fields.txt
"""

# ── Open Food Facts (OFF CSV export field docs) ──────────────────────────────
OPEN_FOOD_FACTS = {
    "code": "Barcode of the product (EAN-13 or an internal code; barcode-less products get a 200-prefixed number).",
    "url": "URL of the product page on Open Food Facts.",
    "creator": "Contributor who first added the product.",
    "product_name": "Name of the product.",
    "abbreviated_product_name": "Shortened form of the product name.",
    "generic_name": "Generic (category) name of the product.",
    "quantity": "Net quantity and unit of the product.",
    "serving_size": "Serving size (with unit).",
    "packaging": "Shape and material of the product packaging.",
    "brands": "Brand name(s).",
    "categories": "Product categories.",
    "categories_fr": "Product categories, in French.",
    "origins": "Origins of the ingredients.",
    "manufacturing_places": "Places where the product was manufactured or transformed.",
    "labels": "Product labels and certifications (organic, fair-trade, …).",
    "labels_fr": "Product labels, in French.",
    "emb_codes": "Packaging / establishment codes (EMB).",
    "first_packaging_code_geo": "Coordinates of the first packaging code.",
    "cities": "Cities associated with the product.",
    "purchase_places": "Places where the product can be purchased.",
    "stores": "Retail stores selling the product.",
    "countries": "Countries where the product is sold.",
    "countries_fr": "Countries where the product is sold, in French.",
    "ingredients_text": "Free-text list of the product's ingredients.",
    "traces": "Allergen traces that may be present.",
    "additives": "List of food additives detected in the ingredients.",
    "additives_n": "Number of food additives detected.",
    "no_nutriments": "Flag: the product has no nutrition facts on its label.",
    "nutrition_grade_fr": "Nutri-Score grade ('a'–'e') for nutritional quality (French/EU system).",
    "nutriscore_grade": "Nutri-Score grade ('a'–'e') summarising nutritional quality.",
    "nutriscore_score": "Numeric Nutri-Score (lower is better).",
    "nova_group": "NOVA food-processing classification (1 = unprocessed … 4 = ultra-processed).",
    "ecoscore_grade": "Eco-Score grade ('a'–'e') for environmental impact.",
    "ecoscore_score": "Numeric Eco-Score for environmental impact.",
    "pnns_groups_1": "PNNS food group, level 1 (French public-health nutrition grouping).",
    "pnns_groups_2": "PNNS food group, level 2.",
    "main_category": "Primary product category.",
    "main_category_fr": "Primary product category, in French.",
    "image_url": "URL of the product image.",
    "image_small_url": "URL of the small product image.",
    "states": "Open Food Facts completeness / workflow states of the product record.",
    "brand_owner": "Company that owns the brand.",
    "ph": "pH value of the product (unitless).",
}
OPEN_FOOD_FACTS_SUFFIX = {
    "_100g": "Nutrient / component content per 100 g or 100 ml of the product.",
    "_serving": "Nutrient / component content per serving.",
    "_tags": "Normalized (lowercased, language-prefixed) tag list for the corresponding field.",
    "_fr": "French-language value of the corresponding field.",
    "_n": "Count for the corresponding field.",
    "_datetime": "ISO-8601 timestamp of the corresponding event.",
    "_t": "UNIX timestamp of the corresponding event.",
    "_url": "URL of the corresponding image / resource.",
    "_by": "Contributor who performed the corresponding action.",
}


FIELD_DOCS = {
    "open_food_facts": OPEN_FOOD_FACTS,
}
FIELD_DOCS_SUFFIX = {
    "open_food_facts": OPEN_FOOD_FACTS_SUFFIX,
}
