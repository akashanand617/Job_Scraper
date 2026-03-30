"""
Company Tier Configuration
Defines tier levels, curated company lists, scoring weights, and target profiles
for the multi-signal company ranking system.
"""

# =============================================================================
# TIER DEFINITIONS
# =============================================================================
# Score ranges map to tiers. Scores are 0-100 composite.
TIER_THRESHOLDS = {
    "T1_ELITE": 80,      # 80-100: Top AI labs, FAANG, dominant market leaders
    "T2_PREMIUM": 60,    # 60-79:  CB Insights AI 100, Forbes AI 50, well-funded unicorns
    "T3_STRONG": 40,     # 40-59:  YC companies, Series B+, established tech
    "T4_STANDARD": 20,   # 20-39:  Recognized companies with some signal
    "T5_UNRANKED": 0,    # 0-19:   No signal data / unknown
}

TIER_LABELS = {
    "T1_ELITE": "Elite",
    "T2_PREMIUM": "Premium",
    "T3_STRONG": "Strong",
    "T4_STANDARD": "Standard",
    "T5_UNRANKED": "Unranked",
}

# =============================================================================
# SCORING WEIGHTS (must sum to 1.0)
# =============================================================================
SCORING_WEIGHTS = {
    "curated_list": 0.30,      # Presence on prestigious lists
    "funding_scale": 0.20,     # Funding amount / company scale
    "nlp_relevance": 0.25,     # Transformer-based description relevance
    "job_quality": 0.15,       # Salary, benefits, growth signals from job data
    "industry_alignment": 0.10, # How aligned with AI/ML/tech sectors
}

# =============================================================================
# CURATED COMPANY LISTS — ordered by prestige
# Each list has a base score contribution (0-100 scale within the curated signal)
# =============================================================================

# Tier 1: Elite companies — 100 pts curated signal
ELITE_COMPANIES = {
    # FAANG / Magnificent 7
    "Google", "Alphabet", "Meta", "Apple", "Amazon", "Microsoft", "Netflix",
    "NVIDIA", "Tesla",
    # Top AI Research Labs
    "OpenAI", "Anthropic", "DeepMind", "Google DeepMind",
    "xAI", "Mistral AI", "Cohere",
    # AI Infrastructure Leaders
    "Databricks", "Snowflake", "Palantir", "Scale AI",
    "Hugging Face", "Weights & Biases",
    # Dominant Tech Platforms
    "Salesforce", "Adobe", "Oracle", "IBM",
    "Uber", "Airbnb", "Stripe", "SpaceX",
    "Bloomberg", "Two Sigma", "Citadel", "Jane Street",
    "D.E. Shaw", "Renaissance Technologies",
}

# Tier 2: Premium companies — 80 pts curated signal
# CB Insights AI 100 2025
CB_INSIGHTS_AI_100_2025 = {
    "1X", "Aaru", "Altera", "Ambience", "Antiverse", "Apptronik", "Arcee",
    "Archetype AI", "Arize", "Atropos Health", "Auquan", "Binarly", "Bioptimus",
    "Bland AI", "BrainSightAI", "Braintrust", "Bria", "Browserbase", "Cartesia",
    "Chainguard", "Chroma", "Credo AI", "DEFCON AI", "Delphina",
    "Dexory", "ElevenLabs", "Ellipsis Health", "Etched", "EvolutionaryScale",
    "Exokernel", "Ferrum Health", "Fiddler", "Fixie", "Fwd", "Ganymede",
    "Gauss Labs", "Genei", "Globus AI", "Greeneye", "Hazy", "Hebbia",
    "Inflection", "K Health", "KEF Robotics", "Kumo", "Lakera", "LangChain",
    "Lamini", "LassoMD", "LightOn", "LolliBots", "Meistrari",
    "Metaplane", "Moonhub", "Moonshot AI", "Moonvalley", "MotherDuck",
    "Motional", "Nabla", "Neko Health", "Nomic", "OctoAI", "OneSchema",
    "OpenPipe", "OpenPodcast", "Orby AI", "Pawn AI", "Perplexity", "Phind",
    "Pixis", "PolyAI", "Predibase", "Primer", "Raycast", "Runway", "Sana",
    "Seek AI", "Shaped", "Skyfire", "Skyflow", "Slingshot AI", "Snyk",
    "Spate", "Synthflow", "Tavus", "Twelve Labs",
    "Tera AI", "ThinkLabs", "Together AI", "Unstructured", "Upstage",
    "Vijil", "Waabi", "Wayve", "World Labs", "Xscape Photonics",
    "Zama", "aiXplain", "webAI",
}

# CB Insights Fintech 100 2024
CB_INSIGHTS_FINTECH_100_2024 = {
    "AccessFintech", "Airbase", "Alloy", "AlphaSense", "Altruist",
    "Arc Technologies", "BitGo", "Brex", "Brightside", "Clear Street",
    "Clerkie", "Column", "Dave", "Elavon", "Etana Custody", "Fattmerchant",
    "FinLync", "Fleetcor", "Highnote", "Hippo", "Imprint", "Ladder",
    "Lendio", "Marqeta", "Maverick Payments", "Next Insurance", "Oportun",
    "Payoneer", "Ramp", "Sardine", "Upgrade",
}

# Forbes AI 50 (approximate — scraped dynamically when possible)
FORBES_AI_50 = {
    "Adept AI", "Abridge", "Abnormal Security", "Anduril", "Anthropic",
    "Celonis", "Cerebras Systems", "Cohere", "CoreWeave", "Cresta",
    "Databricks", "DeepL", "ElevenLabs", "Figure AI", "Glean",
    "Groq", "Harvey", "Hugging Face", "Imbue", "Inflection AI",
    "Jasper", "LangChain", "Lightmatter", "Mistral AI", "Modal",
    "Moveworks", "Navan", "Notion AI", "Observe.AI", "OpenAI",
    "Oscilar", "Perplexity", "Pika", "Pinecone", "Poolside",
    "Replit", "Runway", "Scale AI", "Samsara", "Shield AI",
    "Stability AI", "Together AI", "Typeface", "Weights & Biases",
    "Writer", "xAI",
}

# Tier 3: Strong — 60 pts curated signal
# Well-known tech companies and growth-stage startups
STRONG_TECH_COMPANIES = {
    # Large established tech
    "Intel", "AMD", "Qualcomm", "Broadcom", "ServiceNow", "Workday",
    "Shopify", "Square", "Block", "Twilio", "Cloudflare", "Datadog",
    "MongoDB", "Elastic", "Confluent", "HashiCorp", "GitLab",
    "Atlassian", "Zoom", "DocuSign", "Okta", "CrowdStrike",
    "Palo Alto Networks", "Fortinet", "Zscaler", "SentinelOne",
    "Splunk", "New Relic", "Dynatrace", "Sumo Logic",
    # Notable AI/ML companies
    "H2O.ai", "DataRobot", "C3.ai", "SambaNova Systems",
    "Graphcore", "Cerebras", "Groq", "Lambda", "CoreWeave",
    "Anyscale", "Determined AI", "Paperspace", "Replicate",
    "Pinecone", "Weaviate", "Qdrant", "Milvus", "Zilliz",
    "Comet", "Neptune.ai", "Valohai", "ClearML",
    "Snorkel AI", "Labelbox", "Dataloop", "V7",
    # Finance / Quant
    "Goldman Sachs", "JP Morgan", "Morgan Stanley", "BlackRock",
    "Bridgewater Associates", "Point72", "Millennium Management",
    "Virtu Financial", "Tower Research Capital", "Hudson River Trading",
    # Robotics / Autonomous
    "Boston Dynamics", "Waymo", "Cruise", "Aurora", "Nuro",
    "Zoox", "Argo AI", "TuSimple", "Plus", "Gatik",
    "Agility Robotics", "Figure AI", "Covariant", "Locus Robotics",
    # Biotech / Health AI
    "Recursion Pharmaceuticals", "Insitro", "BenevolentAI",
    "Tempus", "PathAI", "Paige AI", "Viz.ai",
}

# Companies sourced from YC get a base score (populated dynamically)
YC_BASE_SCORE = 50  # Score for being a YC company

# =============================================================================
# NLP TARGET PROFILES
# Descriptions of "ideal" companies — transformer models compute similarity
# against these to produce a relevance score.
# =============================================================================
TARGET_PROFILES = {
    "ai_research": (
        "Cutting-edge artificial intelligence research lab developing foundation models, "
        "large language models, and advancing machine learning capabilities. "
        "Publishes research at top venues like NeurIPS, ICML, and ICLR. "
        "Works on alignment, safety, and responsible AI development."
    ),
    "ai_infrastructure": (
        "Building core AI infrastructure including GPU clusters, model serving platforms, "
        "vector databases, ML pipelines, and developer tools for training and deploying "
        "machine learning models at scale. Focus on performance and reliability."
    ),
    "ai_applications": (
        "Applying artificial intelligence and machine learning to solve real-world problems. "
        "Building products powered by LLMs, computer vision, NLP, and generative AI. "
        "Delivering measurable business value through intelligent automation and insights."
    ),
    "high_growth_tech": (
        "Fast-growing technology company with strong engineering culture, competitive compensation, "
        "significant venture funding or revenue growth. Offers equity, learning opportunities, "
        "and career advancement in a dynamic environment."
    ),
    "quant_finance": (
        "Quantitative finance and algorithmic trading firm using advanced mathematics, "
        "statistics, and machine learning for market prediction and risk management. "
        "Top compensation, intellectually rigorous work environment."
    ),
}

# Weight each profile's contribution to the final NLP score
PROFILE_WEIGHTS = {
    "ai_research": 0.30,
    "ai_infrastructure": 0.20,
    "ai_applications": 0.25,
    "high_growth_tech": 0.15,
    "quant_finance": 0.10,
}

# =============================================================================
# FUNDING SCALE SCORING
# Maps funding ranges to scores (0-100)
# =============================================================================
FUNDING_SCORE_BRACKETS = [
    (10_000_000_000, 100),  # $10B+   → 100
    (5_000_000_000, 95),    # $5B+    → 95
    (1_000_000_000, 90),    # $1B+    → 90 (unicorn)
    (500_000_000, 80),      # $500M+  → 80
    (200_000_000, 70),      # $200M+  → 70
    (100_000_000, 60),      # $100M+  → 60
    (50_000_000, 50),       # $50M+   → 50
    (20_000_000, 40),       # $20M+   → 40
    (10_000_000, 30),       # $10M+   → 30
    (5_000_000, 20),        # $5M+    → 20
    (1_000_000, 10),        # $1M+    → 10
    (0, 5),                 # Any known funding → 5
]

EMPLOYEE_SCORE_BRACKETS = [
    (100_000, 90),   # 100k+ employees
    (50_000, 80),
    (10_000, 70),
    (5_000, 60),
    (1_000, 50),
    (500, 40),
    (200, 30),
    (50, 20),
    (10, 10),
    (0, 5),
]

# =============================================================================
# JOB QUALITY SCORING SIGNALS
# =============================================================================
# Keywords in job descriptions that indicate high-quality positions
HIGH_VALUE_KEYWORDS = [
    "equity", "stock options", "RSU", "competitive salary",
    "401k match", "unlimited PTO", "remote-first",
    "research", "PhD", "publications", "patents",
    "series B", "series C", "series D", "IPO",
    "machine learning", "deep learning", "NLP", "computer vision",
    "foundation model", "LLM", "transformer", "reinforcement learning",
    "distributed systems", "large scale", "petabyte",
]

# Salary brackets to score (annual USD)
SALARY_SCORE_BRACKETS = [
    (400_000, 100),
    (300_000, 90),
    (250_000, 80),
    (200_000, 70),
    (175_000, 60),
    (150_000, 50),
    (125_000, 40),
    (100_000, 30),
    (75_000, 20),
    (50_000, 10),
]

# =============================================================================
# INDUSTRY ALIGNMENT
# Industries that score highest for AI/ML relevance
# =============================================================================
HIGH_RELEVANCE_INDUSTRIES = {
    "artificial intelligence", "machine learning", "deep learning",
    "computer software", "information technology", "internet",
    "cloud computing", "data analytics", "cybersecurity",
    "robotics", "autonomous vehicles", "biotechnology",
    "financial technology", "blockchain", "semiconductor",
    "research", "defense & space", "quantum computing",
}

MEDIUM_RELEVANCE_INDUSTRIES = {
    "telecommunications", "e-commerce", "gaming",
    "media & entertainment", "healthtech", "edtech",
    "marketing technology", "human resources technology",
    "real estate technology", "logistics technology",
    "insurance technology", "legal technology",
    "consulting", "management consulting",
}

# =============================================================================
# BLACKLIST — companies to always exclude (staffing, aggregators)
# =============================================================================
BLACKLISTED_COMPANIES = {
    "jobright", "jooble", "talent.com", "ziprecruiter", "lensa",
    "adzuna", "simplyhired", "neuvoo", "jora", "glassdoor",
    "jobs2careers", "myjobhelper", "careerbuilder", "monster", "snagajob",
    "insight global", "teksystems", "kforce", "aerotek", "randstad",
    "robert half", "apex systems", "experis", "actalent",
    "harnham", "crossover", "toptal freelance",
}

# =============================================================================
# HELPER: Build unified lookup for curated list scoring
# =============================================================================
def build_curated_lookup():
    """Build a name→score mapping from all curated lists.
    Higher score = more prestigious list membership.
    If a company appears in multiple lists, take the max.
    """
    lookup = {}

    for name in ELITE_COMPANIES:
        lookup[name.lower()] = max(lookup.get(name.lower(), 0), 100)

    for name in FORBES_AI_50:
        lookup[name.lower()] = max(lookup.get(name.lower(), 0), 85)

    for name in CB_INSIGHTS_AI_100_2025:
        lookup[name.lower()] = max(lookup.get(name.lower(), 0), 80)

    for name in CB_INSIGHTS_FINTECH_100_2024:
        lookup[name.lower()] = max(lookup.get(name.lower(), 0), 75)

    for name in STRONG_TECH_COMPANIES:
        lookup[name.lower()] = max(lookup.get(name.lower(), 0), 60)

    return lookup


# Pre-build for fast access
CURATED_LOOKUP = build_curated_lookup()
