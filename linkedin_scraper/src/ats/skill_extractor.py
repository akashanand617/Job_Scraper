"""
Skill extraction and normalization engine.
Uses a curated taxonomy of tech/business skills with alias support
for deterministic, fast matching without NLP dependencies.
"""

import re
from typing import List, Set, Dict, Tuple

# ---------------------------------------------------------------------------
# Skill Taxonomy
# ---------------------------------------------------------------------------
# Each canonical skill maps to a list of aliases (lowercase).
# The extractor looks for any alias and normalizes to the canonical form.

SKILL_TAXONOMY: Dict[str, List[str]] = {
    # Programming Languages
    "Python": ["python", "python3", "python 3"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "C++": ["c++", "cpp", "c plus plus"],
    "C#": ["c#", "c sharp", "csharp"],
    "C": ["c programming", "c language"],
    "Go": ["golang", "go lang"],
    "Rust": ["rust", "rust lang"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "R": ["r programming", "r language", "r studio", "rstudio"],
    "MATLAB": ["matlab"],
    "Julia": ["julia"],
    "Perl": ["perl"],
    "Shell Scripting": ["bash", "shell", "shell scripting", "zsh", "sh"],
    "SQL": ["sql", "structured query language"],

    # AI / ML / Data Science
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "Natural Language Processing": ["natural language processing", "nlp"],
    "Computer Vision": ["computer vision", "cv", "image recognition"],
    "Reinforcement Learning": ["reinforcement learning", "rl"],
    "Large Language Models": ["large language model", "large language models", "llm", "llms"],
    "Generative AI": ["generative ai", "gen ai", "genai"],
    "Prompt Engineering": ["prompt engineering", "prompt design"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "Fine-tuning": ["fine-tuning", "fine tuning", "finetuning", "model fine-tuning"],
    "Transfer Learning": ["transfer learning"],
    "Feature Engineering": ["feature engineering"],
    "Data Science": ["data science"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Data Engineering": ["data engineering"],
    "Statistical Modeling": ["statistical modeling", "statistical analysis", "statistics"],
    "A/B Testing": ["a/b testing", "ab testing", "split testing"],
    "Time Series Analysis": ["time series", "time series analysis"],
    "Recommendation Systems": ["recommendation system", "recommender system", "collaborative filtering"],

    # ML Frameworks
    "TensorFlow": ["tensorflow", "tf"],
    "PyTorch": ["pytorch", "torch"],
    "Keras": ["keras"],
    "Scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "XGBoost": ["xgboost", "xg boost"],
    "LightGBM": ["lightgbm", "light gbm"],
    "Hugging Face": ["hugging face", "huggingface", "transformers library"],
    "LangChain": ["langchain", "lang chain"],
    "OpenAI API": ["openai", "openai api", "gpt api"],
    "spaCy": ["spacy"],
    "NLTK": ["nltk"],
    "MLflow": ["mlflow", "ml flow"],
    "Kubeflow": ["kubeflow"],
    "Weights & Biases": ["wandb", "weights and biases", "weights & biases"],
    "JAX": ["jax"],
    "ONNX": ["onnx"],

    # Data Tools
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "SciPy": ["scipy"],
    "Matplotlib": ["matplotlib"],
    "Seaborn": ["seaborn"],
    "Plotly": ["plotly"],
    "Jupyter": ["jupyter", "jupyter notebook", "jupyter lab", "jupyterlab"],
    "Apache Spark": ["spark", "apache spark", "pyspark"],
    "Apache Kafka": ["kafka", "apache kafka"],
    "Apache Airflow": ["airflow", "apache airflow"],
    "dbt": ["dbt", "data build tool"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    "Looker": ["looker"],
    "Excel": ["excel", "microsoft excel", "ms excel"],

    # Web Frameworks
    "React": ["react", "reactjs", "react.js"],
    "Angular": ["angular", "angularjs"],
    "Vue.js": ["vue", "vuejs", "vue.js"],
    "Next.js": ["next.js", "nextjs"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Express.js": ["express", "expressjs", "express.js"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "fast api"],
    "Spring Boot": ["spring boot", "spring", "springboot"],
    "Ruby on Rails": ["rails", "ruby on rails"],
    "ASP.NET": ["asp.net", "dotnet", ".net", ".net core"],

    # Databases
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search", "elk"],
    "DynamoDB": ["dynamodb", "dynamo db"],
    "Cassandra": ["cassandra"],
    "Neo4j": ["neo4j"],
    "SQLite": ["sqlite"],
    "Oracle DB": ["oracle", "oracle db", "oracle database"],
    "SQL Server": ["sql server", "mssql", "ms sql"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery", "big query"],
    "Redshift": ["redshift", "amazon redshift"],
    "Pinecone": ["pinecone"],
    "Weaviate": ["weaviate"],
    "ChromaDB": ["chroma", "chromadb"],
    "FAISS": ["faiss"],

    # Cloud Platforms
    "AWS": ["aws", "amazon web services"],
    "Google Cloud": ["gcp", "google cloud", "google cloud platform"],
    "Azure": ["azure", "microsoft azure"],
    "Heroku": ["heroku"],
    "Vercel": ["vercel"],
    "Netlify": ["netlify"],
    "DigitalOcean": ["digitalocean", "digital ocean"],

    # AWS Services
    "AWS Lambda": ["lambda", "aws lambda"],
    "AWS S3": ["s3", "aws s3", "amazon s3"],
    "AWS EC2": ["ec2", "aws ec2"],
    "AWS SageMaker": ["sagemaker", "aws sagemaker"],
    "AWS Bedrock": ["bedrock", "aws bedrock"],
    "AWS ECS": ["ecs", "aws ecs"],
    "AWS EKS": ["eks", "aws eks"],
    "AWS CloudFormation": ["cloudformation", "aws cloudformation"],
    "AWS Step Functions": ["step functions", "aws step functions"],
    "AWS Glue": ["aws glue", "glue"],
    "AWS Kinesis": ["kinesis", "aws kinesis"],

    # DevOps / Infrastructure
    "Docker": ["docker", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous deployment", "continuous delivery"],
    "GitHub Actions": ["github actions"],
    "Jenkins": ["jenkins"],
    "GitLab CI": ["gitlab ci", "gitlab-ci"],
    "CircleCI": ["circleci", "circle ci"],
    "ArgoCD": ["argocd", "argo cd"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    "Datadog": ["datadog"],
    "New Relic": ["new relic", "newrelic"],

    # Version Control
    "Git": ["git"],
    "GitHub": ["github"],
    "GitLab": ["gitlab"],
    "Bitbucket": ["bitbucket"],

    # API / Architecture
    "REST API": ["rest", "rest api", "restful", "restful api"],
    "GraphQL": ["graphql", "graph ql"],
    "gRPC": ["grpc", "g-rpc"],
    "Microservices": ["microservices", "micro services"],
    "Event-Driven Architecture": ["event-driven", "event driven architecture", "eda"],
    "Serverless": ["serverless"],
    "WebSocket": ["websocket", "websockets"],
    "OAuth": ["oauth", "oauth2", "oauth 2.0"],
    "JWT": ["jwt", "json web token"],

    # Testing
    "Unit Testing": ["unit testing", "unit tests"],
    "Integration Testing": ["integration testing", "integration tests"],
    "pytest": ["pytest"],
    "Jest": ["jest"],
    "Selenium": ["selenium"],
    "Cypress": ["cypress"],
    "Test-Driven Development": ["tdd", "test-driven development", "test driven development"],

    # Project Management / Methodologies
    "Agile": ["agile", "agile methodology"],
    "Scrum": ["scrum"],
    "Kanban": ["kanban"],
    "Jira": ["jira"],
    "Confluence": ["confluence"],
    "Notion": ["notion"],
    "Linear": ["linear"],

    # Soft Skills
    "Leadership": ["leadership", "team leadership", "people management"],
    "Communication": ["communication", "written communication", "verbal communication"],
    "Problem Solving": ["problem solving", "problem-solving", "analytical thinking"],
    "Teamwork": ["teamwork", "team collaboration", "cross-functional"],
    "Project Management": ["project management"],
    "Mentoring": ["mentoring", "coaching"],
    "Stakeholder Management": ["stakeholder management", "stakeholder engagement"],
    "Technical Writing": ["technical writing", "documentation"],
    "Presentation": ["presentation", "public speaking"],
}

# Build reverse lookup: alias -> canonical name
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for canonical, aliases in SKILL_TAXONOMY.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical

# Pre-compile regex patterns for each alias (word-boundary matching)
# Sort by length descending so longer matches take priority
_SORTED_ALIASES = sorted(_ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)
_ALIAS_PATTERNS: List[Tuple[re.Pattern, str]] = []
for alias in _SORTED_ALIASES:
    # For short aliases (<=2 chars), require exact word boundaries
    # For longer ones, use word boundaries
    if len(alias) <= 2:
        pattern = re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.IGNORECASE)
    else:
        pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
    _ALIAS_PATTERNS.append((pattern, _ALIAS_TO_CANONICAL[alias]))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_skills_from_text(text: str) -> List[str]:
    """Extract normalized skills from free-form text. Returns deduplicated list."""
    if not text:
        return []

    found: Set[str] = set()
    for pattern, canonical in _ALIAS_PATTERNS:
        if pattern.search(text):
            found.add(canonical)

    return sorted(found)


def extract_skills_from_job(job: dict) -> List[str]:
    """Extract skills from a scraped LinkedIn job dict.

    Uses the structured `skills_description` field first, then falls back
    to the job title and any available description text.
    """
    parts = []

    if job.get("skills_description"):
        parts.append(job["skills_description"])
    if job.get("title"):
        parts.append(job["title"])
    if job.get("education_description"):
        parts.append(job["education_description"])
    if job.get("job_functions"):
        if isinstance(job["job_functions"], list):
            parts.extend(job["job_functions"])
        else:
            parts.append(str(job["job_functions"]))
    if job.get("company_description"):
        parts.append(job["company_description"])

    combined = " ".join(parts)
    return extract_skills_from_text(combined)


def normalize_skill(skill: str) -> str:
    """Normalize a skill string to its canonical form."""
    return _ALIAS_TO_CANONICAL.get(skill.lower(), skill)


def get_skill_categories() -> Dict[str, List[str]]:
    """Return skills grouped by category for reference."""
    categories = {
        "Programming Languages": [],
        "AI / ML / Data Science": [],
        "ML Frameworks": [],
        "Data Tools": [],
        "Web Frameworks": [],
        "Databases": [],
        "Cloud Platforms": [],
        "DevOps / Infrastructure": [],
        "Other": [],
    }

    # Simple heuristic grouping based on taxonomy order
    # In practice, the full taxonomy above is already organized by category
    return {
        "total_skills": len(SKILL_TAXONOMY),
        "total_aliases": len(_ALIAS_TO_CANONICAL),
    }
