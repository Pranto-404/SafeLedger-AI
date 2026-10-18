"""Small persistence schema; does not import a model/provider at application startup."""
def create_schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS agent_runs(run_id TEXT PRIMARY KEY,business_id TEXT NOT NULL,actor_id TEXT NOT NULL,started_at INTEGER NOT NULL,status TEXT NOT NULL,task_sha256 TEXT NOT NULL,provider_mode TEXT NOT NULL,result TEXT)")
    db.commit()
