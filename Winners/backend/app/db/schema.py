from app.db.connection import db_manager

SCHEMA_SQL = """
-- 1. Cases Table
CREATE TABLE IF NOT EXISTS cases (
    case_id VARCHAR(64) PRIMARY KEY,
    query TEXT NOT NULL,
    as_of_date VARCHAR(10) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'INITIALIZED',
    event_verified BOOLEAN DEFAULT FALSE,
    verification_details TEXT,
    active_run INT DEFAULT 1,
    active_round INT DEFAULT 1,
    retrieved_documents JSONB DEFAULT '[]'::jsonb,
    timeline JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Claims Table
CREATE TABLE IF NOT EXISTS claims (
    claim_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    agent VARCHAR(16) NOT NULL,
    round_num INT DEFAULT 1,
    run_num INT DEFAULT 1,
    statement TEXT NOT NULL,
    claim_type VARCHAR(32) NOT NULL DEFAULT 'SOURCED_FACT',
    country VARCHAR(64) DEFAULT 'general',
    sector VARCHAR(64) DEFAULT 'general',
    bound_type VARCHAR(16) DEFAULT 'HIGH',
    numerical_estimate VARCHAR(64),
    citations JSONB DEFAULT '[]'::jsonb,
    citation_snippets JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(32) DEFAULT 'PENDING',
    ruling_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Attacks Table (Cross-Examination)
CREATE TABLE IF NOT EXISTS attacks (
    attack_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    attacker VARCHAR(16) NOT NULL,
    target_claim_id VARCHAR(64) NOT NULL,
    target_agent VARCHAR(16) NOT NULL,
    argument TEXT NOT NULL,
    counter_citations JSONB DEFAULT '[]'::jsonb,
    counter_snippets JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Defenses Table (Concessions & Defense)
CREATE TABLE IF NOT EXISTS defenses (
    defense_id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    defender VARCHAR(16) NOT NULL,
    attack_id VARCHAR(64) NOT NULL,
    target_claim_id VARCHAR(64) NOT NULL,
    action VARCHAR(16) NOT NULL,
    reasoning TEXT NOT NULL,
    new_citations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Rulings Table
CREATE TABLE IF NOT EXISTS rulings (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    claim_id VARCHAR(64) NOT NULL,
    ruling VARCHAR(32) NOT NULL,
    claim_type VARCHAR(32) NOT NULL,
    judge_rationale TEXT NOT NULL,
    verified_citations JSONB DEFAULT '[]'::jsonb,
    confidence_score NUMERIC(4, 3) DEFAULT 0.85,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Executive Briefings Table
CREATE TABLE IF NOT EXISTS executive_briefings (
    case_id VARCHAR(64) PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
    as_of_date VARCHAR(10) NOT NULL,
    incident_name TEXT NOT NULL,
    executive_summary TEXT NOT NULL,
    established_findings JSONB DEFAULT '[]'::jsonb,
    contested_findings JSONB DEFAULT '[]'::jsonb,
    conceded_findings JSONB DEFAULT '[]'::jsonb,
    exposure_table JSONB DEFAULT '[]'::jsonb,
    next_quarter_outlook TEXT NOT NULL,
    stated_assumptions JSONB DEFAULT '[]'::jsonb,
    source_hygiene_report JSONB DEFAULT '{}'::jsonb,
    all_citations JSONB DEFAULT '[]'::jsonb,
    author VARCHAR(64) DEFAULT 'Odin, Supreme Allfather Bench',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Audit Log Table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(64),
    agent VARCHAR(16) NOT NULL,
    action VARCHAR(64) NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_claims_case_id ON claims(case_id);
CREATE INDEX IF NOT EXISTS idx_attacks_case_id ON attacks(case_id);
CREATE INDEX IF NOT EXISTS idx_rulings_case_id ON rulings(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_case_id ON audit_log(case_id);
CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases(created_at DESC);
"""

def init_db() -> bool:
    """
    Initializes Neon PostgreSQL database schema safely.
    Creates all required tables and indexes if they do not exist.
    Never drops or mutates existing tables.
    """
    print("[Neon DB] Initializing database schema...")
    try:
        with db_manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
        print("[Neon DB] Schema verification and initialization complete.")
        return True
    except Exception as e:
        print(f"[Neon DB] Error initializing schema: {e}")
        return False
