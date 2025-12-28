from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import asyncio
from datetime import datetime, timedelta
import json
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/memory")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class RealtimeAggregator:
    def __init__(self):
        self.refresh_interval = 60
        
    async def start(self):
        while True:
            try:
                await self.refresh_materialized_views()
                await self.update_cold_storage()
                await self.cleanup_old_data()
                await asyncio.sleep(self.refresh_interval)
            except Exception as e:
                print(f"Aggregator error: {e}")
                await asyncio.sleep(5)
    
    async def refresh_materialized_views(self):
        with engine.begin() as conn:
            conn.execute(text("""
                REFRESH MATERIALIZED VIEW CONCURRENTLY execution_metrics_1min;
                REFRESH MATERIALIZED VIEW CONCURRENTLY incident_heatmap;
                REFRESH MATERIALIZED VIEW CONCURRENTLY strategy_efficacy;
            """))
    
    async def update_cold_storage(self):
        with engine.begin() as conn:
            conn.execute(text("""
                WITH to_cold AS (
                    SELECT id 
                    FROM executions 
                    WHERE cold_storage = false 
                    AND created_at < NOW() - INTERVAL '7 days'
                    ORDER BY created_at 
                    LIMIT 1000
                )
                UPDATE executions 
                SET cold_storage = true 
                WHERE id IN (SELECT id FROM to_cold);
            """))
    
    async def cleanup_old_data(self):
        with engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM executions 
                WHERE cold_storage = true 
                AND created_at < NOW() - INTERVAL '30 days';
                
                DELETE FROM incidents 
                WHERE resolved = true 
                AND resolved_at < NOW() - INTERVAL '14 days';
            """))
    
    def get_realtime_metrics(self, domain: str = None):
        with engine.begin() as conn:
            query = text("""
                SELECT 
                    domain,
                    strategy,
                    COUNT(*) as execution_count,
                    AVG((metrics->>'latency')::float) as avg_latency,
                    SUM(CASE WHEN (metrics->>'success')::boolean THEN 1 ELSE 0 END) as success_count
                FROM execution_metrics_1min
                WHERE timestamp > NOW() - INTERVAL '5 minutes'
                {domain_filter}
                GROUP BY domain, strategy
                ORDER BY execution_count DESC
            """.format(domain_filter=f"AND domain = '{domain}'" if domain else ""))
            
            result = conn.execute(query)
            return [dict(row) for row in result]

# Schema SQL for materialized views
MATERIALIZED_VIEWS_SQL = """
CREATE MATERIALIZED VIEW execution_metrics_1min AS
SELECT 
    domain,
    strategy,
    date_trunc('minute', created_at) as timestamp,
    COUNT(*) as count,
    AVG((metrics->>'latency')::float) as avg_latency,
    SUM(CASE WHEN (metrics->>'success')::boolean THEN 1 ELSE 0 END) as success_count
FROM executions
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY domain, strategy, date_trunc('minute', created_at);

CREATE MATERIALIZED VIEW incident_heatmap AS
SELECT 
    domain,
    ltree_path,
    COUNT(*) as incident_count,
    AVG(severity) as avg_severity,
    MAX(created_at) as last_incident
FROM incidents
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY domain, ltree_path;

CREATE MATERIALIZED VIEW strategy_efficacy AS
SELECT 
    e.strategy,
    e.domain,
    COUNT(*) as total_executions,
    SUM(CASE WHEN (e.metrics->>'success')::boolean THEN 1 ELSE 0 END) as successful_executions,
    AVG((e.metrics->>'latency')::float) as avg_latency,
    ARRAY_AGG(DISTINCT i.id) as incident_ids
FROM executions e
LEFT JOIN incidents i ON e.domain = i.domain 
    AND i.created_at BETWEEN e.created_at - INTERVAL '5 minutes' AND e.created_at + INTERVAL '5 minutes'
WHERE e.created_at > NOW() - INTERVAL '1 day'
GROUP BY e.strategy, e.domain;

CREATE INDEX idx_execution_metrics_time ON execution_metrics_1min (timestamp);
CREATE INDEX idx_incident_heatmap_domain ON incident_heatmap (domain);
CREATE INDEX idx_strategy_efficacy ON strategy_efficacy (strategy, domain);
"""

if __name__ == "__main__":
    aggregator = RealtimeAggregator()
    asyncio.run(aggregator.start())
