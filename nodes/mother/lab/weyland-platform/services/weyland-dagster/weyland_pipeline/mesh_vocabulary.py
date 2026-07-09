"""Hand-authored Data-Mesh business vocabulary for the DataHub glossary (Surface 1 of the field-semantics
build). Unlike aidlc_glossary.py (generated from the .methodaidlc source files), these are curated terms whose
definitions are CANONICAL — Spotify audio-feature docs, standard Big-Five psychology, standard lakehouse/medallion
terminology, MusicBrainz + WHO-GHO + Debezium schema semantics — transcribed, not invented.

Each term carries `attach`: leaf field-name patterns. emit_mesh_glossary() walks every cataloged dataset's schema
and attaches the term to any field whose leaf name equals a pattern OR starts with `<pattern>_` (so a single
"danceability" pattern covers danceability, danceability_mean, danceability_std across all ~15 store copies).
This is the "define once, attach everywhere" lever that collapses the 22k ambiguous-field duplication.

Root "Data Mesh" is a SEPARATE glossary root from aidlc_glossary's "AIDLC Knowledge".
"""

# ── nodes: (id, name, parent, definition) ───────────────────────────────────
NODES = [
    ("data-mesh", "Data Mesh", None,
     "Business vocabulary for the platform's actual data — the shared concepts, per-domain metrics, and source-"
     "schema semantics that recur across the lakehouse, Tier-2 stores, vector/graph stores, and streams."),
    ("data-platform", "Data Platform", "data-mesh",
     "Cross-cutting lakehouse and data-engineering concepts that apply to datasets in every domain."),
    ("music-concepts", "Music Concepts", "data-mesh",
     "Business concepts for the music domain — track audio features, genre, and artist popularity."),
    ("audio-feature", "Audio Feature", "music-concepts",
     "A quantitative attribute of a track's sound from Spotify's audio analysis. Most are normalized to [0.0, 1.0] "
     "unless the term notes another unit."),
    ("health-concepts", "Health Concepts", "data-mesh",
     "Business concepts for the health domain — population prevalence, indicators, and personality traits."),
    ("source-schemas", "Source Schemas", "data-mesh",
     "Coded columns from external source schemas we ingest but don't control — MusicBrainz, WHO GHO, and CDC "
     "change envelopes — whose field names are cryptic without a definition."),
]

# ── terms: (id, name, parent, definition, [attach patterns]) ─────────────────
TERMS = [
    # Data Platform ----------------------------------------------------------
    ("medallion-architecture", "Medallion Architecture", "data-platform",
     "A design pattern that refines data through progressive layers — Bronze (raw), Silver (cleaned/conformed), "
     "Gold (business aggregates) — raising quality and reusability downstream.", []),
    ("bronze-layer", "Bronze / Raw Layer", "data-platform",
     "The landing layer: source data ingested as-is, unmodified, for replayability and audit.", ["raw"]),
    ("silver-layer", "Silver Layer", "data-platform",
     "The cleaned, deduplicated, type-conformed layer — the trustworthy base for analytics and further modeling.",
     []),
    ("gold-layer", "Gold Layer", "data-platform",
     "Business-level aggregates and features built on Silver, shaped for consumption (BI, ML, serving).", []),
    ("mart", "Mart", "data-platform",
     "A curated, tested Gold-layer table modeling one business subject (dbt-materialized Iceberg here).", []),
    ("feature-view", "Feature View", "data-platform",
     "A named group of ML features over an entity, served online (low-latency) and offline (training) from the "
     "feature store (Feast).", []),
    ("embedding", "Embedding / Vector", "data-platform",
     "A dense numeric vector encoding an item's semantics for similarity search in a vector store.",
     ["embedding", "vector"]),
    ("chunk", "Chunk", "data-platform",
     "A passage-sized slice of a source document, the unit of retrieval in the RAG corpus.", ["chunk"]),
    # Music: audio features (canonical Spotify definitions) -------------------
    ("danceability", "Danceability", "audio-feature",
     "How suitable a track is for dancing (0–1) from tempo, rhythm stability, beat strength, and regularity.",
     ["danceability"]),
    ("energy", "Energy", "audio-feature",
     "Perceptual intensity/activity (0–1) — fast, loud, noisy tracks score high.", ["energy"]),
    ("valence", "Valence", "audio-feature",
     "Musical positiveness (0–1) — high = happy/cheerful, low = sad/angry.", ["valence"]),
    ("acousticness", "Acousticness", "audio-feature",
     "Confidence (0–1) the track is acoustic.", ["acousticness"]),
    ("instrumentalness", "Instrumentalness", "audio-feature",
     "Likelihood (0–1) the track has no vocals; above ~0.5 suggests instrumental.", ["instrumentalness"]),
    ("liveness", "Liveness", "audio-feature",
     "Probability (0–1) the track was performed live (audience presence).", ["liveness"]),
    ("speechiness", "Speechiness", "audio-feature",
     "Presence of spoken words (0–1); above ~0.66 is likely all-spoken.", ["speechiness"]),
    ("loudness", "Loudness", "audio-feature",
     "Overall loudness averaged across the track, in decibels (dB), typically −60 to 0.", ["loudness"]),
    ("tempo", "Tempo", "audio-feature",
     "Estimated pace in beats per minute (BPM).", ["tempo"]),
    ("audio-key", "Key", "audio-feature",
     "Estimated key as a pitch class integer (0=C, 1=C♯/D♭, … 11=B); −1 if undetected.", ["key"]),
    ("audio-mode", "Mode", "audio-feature",
     "Modality: 1 = major, 0 = minor.", ["mode"]),
    # Music: other -----------------------------------------------------------
    ("genre", "Genre", "music-concepts",
     "A category of musical style. In this platform sourced from Spotify track_genre and the FMA genre taxonomy.",
     ["genre", "track_genre"]),
    ("genre-hierarchy", "Genre Hierarchy", "music-concepts",
     "The FMA parent/child genre tree; parent_id links a genre to its broader parent, is_top_level flags roots.",
     ["parent_id", "parent_title", "is_top_level"]),
    ("mbid", "MBID (MusicBrainz Identifier)", "music-concepts",
     "A stable UUID assigned by MusicBrainz to an entity (artist, release, recording…).", ["mbid"]),
    ("play-count", "Play Count", "music-concepts",
     "Total scrobbles/plays for an artist or track (Last.fm).", ["total_plays", "playcount", "plays"]),
    ("listener-count", "Listener Count", "music-concepts",
     "Distinct listeners for an artist or track (Last.fm).", ["n_listeners", "listeners"]),
    # Health -----------------------------------------------------------------
    ("prevalence", "Prevalence", "health-concepts",
     "The share of a population with a condition/behavior at a point in time (BRFSS: % of respondents).",
     ["prevalence"]),
    ("chronic-condition", "Chronic Condition", "health-concepts",
     "A long-lasting health condition (e.g. diabetes, mental-health disorders) tracked by BRFSS.",
     ["mental_health_disorders", "tobacco_smoking"]),
    ("health-indicator", "Health Indicator", "health-concepts",
     "A measured population-health metric reported by country/year (WHO GHO).", []),
    ("life-expectancy", "Life Expectancy", "health-concepts",
     "Average years a person is expected to live given current mortality (WHO GHO).", ["life_expectancy"]),
    ("respondent", "Respondent", "health-concepts",
     "An individual surveyed; n_respondents is the sample size behind an aggregate.", ["n_respondents"]),
    ("ocean", "Big Five / OCEAN", "health-concepts",
     "The five-factor personality model: Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism, "
     "each a normalized trait score.", []),
    ("openness", "Openness", "health-concepts", "OCEAN trait: curiosity, imagination, openness to experience.",
     ["openness"]),
    ("conscientiousness", "Conscientiousness", "health-concepts",
     "OCEAN trait: organization, dependability, self-discipline.", ["conscientiousness"]),
    ("extraversion", "Extraversion", "health-concepts", "OCEAN trait: sociability, assertiveness, energy.",
     ["extraversion"]),
    ("agreeableness", "Agreeableness", "health-concepts", "OCEAN trait: compassion, cooperativeness, trust.",
     ["agreeableness"]),
    ("neuroticism", "Neuroticism", "health-concepts", "OCEAN trait: emotional instability, anxiety, moodiness.",
     ["neuroticism"]),
    # Statistical conventions (cross-domain) ---------------------------------
    ("stat-mean", "Mean (_mean)", "data-platform",
     "Arithmetic mean of the base measure across the group (suffix _mean).", []),
    ("stat-std", "Std Dev (_std)", "data-platform",
     "Standard deviation of the base measure across the group (suffix _std).", []),
    # Source schemas: MusicBrainz -------------------------------------------
    ("mb-gid", "GID (Global ID)", "source-schemas",
     "MusicBrainz row-level UUID (the stable public identifier / MBID) for an entity.", ["gid"]),
    ("mb-entity", "Relationship Endpoint (entity0 / entity1)", "source-schemas",
     "The two entities a MusicBrainz relationship (l_* tables) links; entity0 and entity1 are FKs to the "
     "endpoint rows.", ["entity0", "entity1"]),
    ("mb-entity-credit", "Relationship Credit (entity0_credit / entity1_credit)", "source-schemas",
     "The credited name for a relationship endpoint when it differs from the entity's canonical name.",
     ["entity0_credit", "entity1_credit"]),
    ("mb-edits-pending", "Edits Pending", "source-schemas",
     "Count of open community edits awaiting application to a MusicBrainz row.", ["edits_pending"]),
    # Source schemas: WHO GHO ------------------------------------------------
    ("gho-dim", "GHO Disaggregation Dimension (dim1/dim2/dim3)", "source-schemas",
     "WHO GHO breakdown dimensions for an indicator value (e.g. sex, age group); dimNtype names the dimension, "
     "dimN gives the code.", ["dim1", "dim2", "dim3", "dim1type", "dim2type", "dim3type"]),
    ("gho-bounds", "Confidence Bounds (low / high)", "source-schemas",
     "Lower/upper bound of the uncertainty interval around a GHO numeric value.", ["low", "high"]),
    # Source schemas: CDC ----------------------------------------------------
    ("cdc-op", "CDC Operation (op)", "source-schemas",
     "Debezium change-event operation: c=create, u=update, d=delete, r=snapshot read.", ["op"]),
]
