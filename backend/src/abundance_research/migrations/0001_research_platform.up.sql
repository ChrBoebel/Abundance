CREATE TABLE abundance_research_runs (
    id TEXT PRIMARY KEY,
    inquiry JSONB NOT NULL,
    model TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('quick', 'balanced', 'thorough')),
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    report JSONB,
    evaluation JSONB,
    metrics JSONB,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE INDEX abundance_research_runs_created_at_idx
    ON abundance_research_runs (created_at DESC);

CREATE TABLE abundance_research_feedback (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES abundance_research_runs(id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL DEFAULT '',
    rating SMALLINT NOT NULL CHECK (rating BETWEEN -1 AND 1),
    note TEXT CHECK (char_length(note) <= 2000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, claim_id)
);

CREATE TABLE abundance_research_shares (
    token_digest TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES abundance_research_runs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX abundance_research_shares_run_id_idx
    ON abundance_research_shares (run_id)
    WHERE revoked_at IS NULL;

