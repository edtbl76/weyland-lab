# MongoDB — query cookbook

**Connect:** `mongodb.data-mesh.svc:27017`, authSource `admin` (user `weyland` / dev password). IntelliJ →
MongoDB driver, port-forward the `mongodb` svc `27017`. In-pod:
`kubectl -n data-mesh exec -it deploy/mongodb -- mongosh -u weyland -p <pw> --authenticationDatabase admin`.

DB `datasets_health` (doc-per-row): `who_gho_*` collections, `open_food_facts` (~4.5M), and `aidlc_kb.entries`
(511 frontmatter docs — the methodology corpus, queryable by front-matter). DB `datasets_finance` (B113 Phase 2):
`company_financials` (20,741 XBRL-fact docs) + `company_meta` (49). Date columns are cast to BSON timestamps at
load (`mongo_encode.to_bson_encodable`; raw `datetime.date` is not BSON-encodable).

### Explore
```javascript
show dbs
use datasets_health
show collections
db.open_food_facts.findOne()                 // shape of one doc
db.open_food_facts.estimatedDocumentCount()  // fast count
```

### Open Food Facts
```javascript
// products per country (top 20)
db.open_food_facts.aggregate([
  { $group: { _id: "$countries_en", n: { $sum: 1 } } },
  { $sort: { n: -1 } }, { $limit: 20 }
])

// nutrition-grade breakdown
db.open_food_facts.aggregate([
  { $match: { nutrition_grade_fr: { $ne: null, $ne: "" } } },
  { $group: { _id: "$nutrition_grade_fr", n: { $sum: 1 } } }, { $sort: { _id: 1 } }
])

// high-sugar named products
db.open_food_facts.find(
  { product_name: { $ne: "" }, sugars_100g: { $ne: null } },
  { product_name: 1, sugars_100g: 1, _id: 0 }
).sort({ sugars_100g: -1 }).limit(20)
```

### WHO GHO (`who_gho_*` collections)
```javascript
// life-expectancy docs for a country
db.who_gho_life_expectancy.find({ SpatialDim: "USA" }, { TimeDim: 1, NumericValue: 1, _id: 0 })

// avg obesity by year
db.who_gho_adult_obesity.aggregate([
  { $group: { _id: "$TimeDim", avg: { $avg: "$NumericValue" } } }, { $sort: { _id: 1 } }
])
```

### AIDLC knowledge base (`aidlc_kb.entries`)
```javascript
use aidlc_kb   // (or datasets_health depending on load target — check `show dbs`)
// entries by front-matter type / vertical
db.entries.aggregate([{ $group: { _id: "$type", n: { $sum: 1 } } }, { $sort: { n: -1 } }])
// full-text-ish search on a field
db.entries.find({ title: /discovery/i }, { title: 1, type: 1, _id: 0 }).limit(20)
```

### Finance — EDGAR company facts (`datasets_finance`, B113 Phase 2)
```javascript
use datasets_finance
show collections                              // company_financials, company_meta
db.company_financials.findOne()              // {cik, ticker, company, concept, unit, period_end, fy, fp, form, filed, value}

// latest annual Revenue per company
db.company_financials.aggregate([
  { $match: { concept: { $in: ["Revenues","RevenueFromContractWithCustomerExcludingAssessedTax"] }, fp: "FY" } },
  { $sort: { period_end: -1 } },
  { $group: { _id: "$ticker", company: { $first: "$company" }, revenue: { $first: "$value" }, asOf: { $first: "$period_end" } } },
  { $sort: { revenue: -1 } }, { $limit: 20 }
])

// one company's fact history for a concept
db.company_financials.find({ ticker: "AAPL", concept: "Assets" }, { fy: 1, period_end: 1, value: 1, _id: 0 }).sort({ period_end: 1 })

// companies by industry (SIC)
db.company_meta.aggregate([{ $group: { _id: { sic: "$sic", desc: "$sic_description" }, n: { $sum: 1 } } }, { $sort: { n: -1 } }])
```

### Mongo-isms
- `aggregate([...])` is the workhorse (`$group`/`$match`/`$sort`/`$lookup`). `find()` for simple filters.
- `db.coll.createIndex({ field: 1 })` if a filter is slow (these are dumps — no indexes beyond `_id`).
- Fields mirror the parquet columns verbatim (case-sensitive — `SpatialDim`, not `spatialdim`).
