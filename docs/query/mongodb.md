# MongoDB — query cookbook

**Connect:** `mongodb.data-mesh.svc:27017`, authSource `admin` (user `weyland` / dev password). IntelliJ →
MongoDB driver, port-forward the `mongodb` svc `27017`. In-pod:
`kubectl -n data-mesh exec -it deploy/mongodb -- mongosh -u weyland -p <pw> --authenticationDatabase admin`.

DB `datasets_health` (doc-per-row): `who_gho_*` collections, `open_food_facts` (~4.5M), and `aidlc_kb.entries`
(511 frontmatter docs — the methodology corpus, queryable by front-matter).

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

### Mongo-isms
- `aggregate([...])` is the workhorse (`$group`/`$match`/`$sort`/`$lookup`). `find()` for simple filters.
- `db.coll.createIndex({ field: 1 })` if a filter is slow (these are dumps — no indexes beyond `_id`).
- Fields mirror the parquet columns verbatim (case-sensitive — `SpatialDim`, not `spatialdim`).
