"""Single source for projects, nav and search entries. Imported by build.py.

Facts here come from each repo's README or the résumé; evidence labels say which.
"""

GH = 'https://github.com/saravanaprabhu1398-afk/'

# cats: lakehouse | streaming | ai | warehouse | governance
PROJECTS = [
    dict(
        slug='guardrail', featured=True, title='Guardrail', status='Snowflake · experimentation',
        desc='A Snowflake experimentation platform that decides whether a feature is safe to ship: assigning variants, '
             'ingesting telemetry through Redpanda and Snowpipe Streaming, running statistical tests, and blocking the '
             'rollout when the telemetry itself can\'t be trusted.',
        tags=['Snowflake', 'dbt', 'Redpanda', 'FastAPI', 'Terraform', 'Kubernetes'],
        cats=['warehouse', 'streaming', 'governance'],
        img=('/assets/guardrail-decision-loop.svg',
             'Guardrail decision loop: assignment and exposure feed integrity checks, which gate the statistical result'),
        metric=('4.8%', 'Apparent conversion lift in the demo scenario, caught and blocked: mobile clients were '
                        'switching variants mid-session.',
                ('Simulated', GH + 'Guardrail-Safe-Feature-Rollout-Platform#interview-narrative', 'Demo narrative')),
        links=[('View source', GH + 'Guardrail-Safe-Feature-Rollout-Platform')],
    ),
    dict(
        slug='flightpulse', featured=True, title='FlightPulse', status='Streaming lakehouse',
        desc='A local-first flight-delay lakehouse: live positions streamed through Redpanda into Apache Iceberg, '
             'batch sources modelled with dbt into a bronze, silver, gold star schema, and a delay-probability model '
             'tracked in MLflow. Blocking Great Expectations checks gate the batch gold tables.',
        tags=['Apache Iceberg', 'dbt', 'Dagster', 'Great Expectations', 'MLflow'],
        cats=['lakehouse', 'streaming', 'ai'],
        img=('/assets/02_delay_by_airport.png', 'FlightPulse dashboard: delay rate by origin airport, shown as a bubble map'),
        metric=('611K+', 'Historical flights in the dashboard. Live aircraft positions are served separately from Iceberg.',
                ('Measured', GH + 'FlightPulse#opening-the-dashboard', 'README')),
        links=[('View source', GH + 'FlightPulse')],
    ),
    dict(
        slug='dataplatform', featured=True, title='Dataplatform', status='Orchestration platform',
        desc='A self-hosted alternative to Airflow: YAML-defined pipelines, a plain-English pipeline generator, a '
             'governed deployment hub with rollback, and full observability across metrics, alerting, cost and lineage.',
        tags=['FastAPI', 'dbt', 'RBAC', 'NetworkX'],
        cats=['governance'],
        img=None,
        metric=('12', 'Plugin executors, with RBAC and a NetworkX-backed DAG engine.',
                ('In the code', GH + 'dataplatform-modern-dbt#readme', 'README')),
        links=[('View source', GH + 'dataplatform-modern-dbt')],
    ),
    dict(
        slug='clinical-document-intelligence', featured=True, title='Clinical Document Intelligence',
        status='Databricks · GenAI',
        desc='A Databricks Lakehouse converting thousands of unstructured FDA drug labels into a queryable knowledge '
             'base. A cited RAG agent routes questions to SQL or Vector Search, governed under the same Unity Catalog '
             'contracts as the underlying data.',
        tags=['Databricks', 'Unity Catalog', 'Mosaic AI', 'Vector Search'],
        cats=['lakehouse', 'ai', 'governance'],
        img=None,
        metric=('<1s', 'Source-attributed answers, governed by Unity Catalog contracts.',
                ('From résumé', '/assets/Prabhu_Saravanan_Resume_UAE.pdf', 'Résumé')),
        links=[('View source', GH + 'data-document-intelligence-platform')],
    ),
    dict(
        slug='subscription-warehouse', featured=False, title='Subscription Analytics Warehouse',
        status='Personal project · synthetic data',
        desc='A Kimball star schema with an SCD2 customer dimension, cohort, churn and LTV marts, and GDPR masking. '
             'Runs locally on DuckDB and deploys to Snowflake with Terraform.',
        tags=['Snowflake', 'dbt', 'Terraform', 'DuckDB'], cats=['warehouse', 'governance'], img=None, metric=None,
        links=[('View on GitHub', GH + 'snowflake-dbt-subscription-warehouse')],
    ),
    dict(
        slug='freshness-control-plane', featured=False, title='Freshness Control Plane', status='Open source',
        desc='Detects stale aviation data with CDC, re-embeds only what changed, enforces freshness SLAs as data '
             'contracts, and makes a RAG agent flag outdated answers.',
        tags=['Debezium', 'Kafka', 'Postgres', 'RAG'], cats=['streaming', 'ai'], img=None, metric=None,
        links=[('View on GitHub', GH + 'freshness-control-plane')],
    ),
    dict(
        slug='nexus', featured=False, title='NEXUS', status='Design + early build',
        desc='A governed, read-only AI agent that investigates data-platform incidents and recommends the next '
             'engineering action. Solution design, Phase 0 package and Phase 1 agent service.',
        tags=['AI agents', 'Governance', 'Python'], cats=['ai', 'governance'], img=None, metric=None,
        links=[('View on GitHub', GH + 'Project_Nexus')],
    ),
    dict(
        slug='stellenradar', featured=False, title='Stellenradar', status='In development',
        desc='A serverless AWS pipeline that analyses Germany\'s data-engineering job market: Iceberg on S3, Bedrock '
             'enrichment, DMS CDC and pgvector matching, all in Terraform.',
        tags=['AWS', 'Iceberg', 'Bedrock', 'Terraform'], cats=['lakehouse', 'ai'], img=None, metric=None,
        links=[('View on GitHub', GH + 'stellenradar')],
    ),
    dict(
        slug='clinical-docs-agent', featured=False, title='Clinical Docs Agent', status='Early stage',
        desc='Answers pharmacist and clinician questions from public FDA drug labels, cites the exact section behind '
             'each answer, and says so when the labels don\'t cover the question.',
        tags=['openFDA', 'Pydantic', 'Ollama / Claude'], cats=['ai'], img=None, metric=None,
        links=[('View on GitHub', GH + 'clinical-docs-agent')],
    ),
    dict(
        slug='ai-agent-company', featured=False, title='AI Agent Company Kit', status='Starter kit',
        desc='A virtual software company of Claude Code agents with approval gates, safety guardrails and GitHub '
             'workflows, for building products as a product owner.',
        tags=['Claude Code', 'GitHub Actions'], cats=['ai'], img=None, metric=None,
        links=[('View on GitHub', GH + 'ai-agent-company')],
    ),
]

SPOTLIGHT = dict(
    slug='flightpulse',
    summary='A local-first lakehouse with separate batch analytics and live-position paths.',
    source=GH + 'FlightPulse#architecture',
    flows=[
        ('Historical flights', [
            ('Ingest', 'BTS + reference / weather', 'dlt → MinIO'),
            ('Model', 'dbt / DuckDB', 'Bronze → silver → gold'),
            ('Serve', 'Streamlit', 'Delay analytics'),
        ]),
        ('Live positions', [
            ('Ingest', 'OpenSky', 'Redpanda'),
            ('Stream', 'Spark', 'Iceberg on MinIO'),
            ('Serve', 'Streamlit', 'DuckDB reads Iceberg'),
        ]),
    ],
    note='Simplified paths from the repository. Quality checks gate batch gold tables; streaming checks are not implemented.',
)

FILTERS = [('all', 'All'), ('lakehouse', 'Lakehouse'), ('streaming', 'Streaming'),
           ('warehouse', 'Warehouse'), ('ai', 'AI'), ('governance', 'Governance')]

NAV = [('home', '/', 'Home'), ('projects', '/projects/', 'Projects'), ('writing', '/blog/', 'Writing'),
       ('about', '/about/', 'About'), ('contact', '/#contact', 'Contact')]

SEARCH_STATIC = [
    dict(t='Home', d='Personal workspace, project previews and contact', u='/', k='Page'),
    dict(t='Work together', d='Engineering roles and consulting conversations: lakehouses, streaming and governed AI', u='/#services', k='Page'),
    dict(t='Projects', d='All ten public projects with filters', u='/projects/', k='Page'),
    dict(t='About & experience', d='Career journey, skills, certifications, résumés', u='/about/', k='Page'),
    dict(t='Writing', d='Field notes on data engineering', u='/blog/', k='Page'),
    dict(t='Contact', d='Email, LinkedIn, GitHub, résumé downloads', u='/#contact', k='Page'),
    dict(t='Case study: one risk engine instead of six pipelines', d='Wipro insurance risk, +40% accuracy, $2M+ saved', u='/#case-studies', k='Case'),
    dict(t='Case study: sub-60-second CDC', d='Wipro satellite connectivity, 500K+ subscribers', u='/#case-studies', k='Case'),
    dict(t='Case study: self-service ingestion', d='Scadea for Citi: new sources with no code', u='/#case-studies', k='Case'),
    dict(t='Résumé: UAE & Gulf', d='PDF', u='/assets/Prabhu_Saravanan_Resume_UAE.pdf', k='Résumé'),
    dict(t='Résumé: Europe', d='PDF', u='/assets/Prabhu_Saravanan_Resume_Europe.pdf', k='Résumé'),
    dict(t='Résumé: India', d='PDF', u='/assets/Prabhu_Saravanan_Resume_India.pdf', k='Résumé'),
    dict(t='LinkedIn', d='linkedin.com/in/prabhu-saravanan-a53317226', u='https://www.linkedin.com/in/prabhu-saravanan-a53317226', k='Link'),
    dict(t='GitHub', d='github.com/saravanaprabhu1398-afk', u='https://github.com/saravanaprabhu1398-afk', k='Link'),
]
