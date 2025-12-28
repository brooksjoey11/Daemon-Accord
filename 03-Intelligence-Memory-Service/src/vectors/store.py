import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import psycopg2
from psycopg2.extras import Json
from psycopg2.pool import ThreadedConnectionPool
import pgvector.psycopg2
from pgvector.psycopg2 import register_vector
import uuid
import json

class VectorStore:
    def __init__(self, 
                 db_host: str = "localhost",
                 db_port: int = 5432,
                 db_name: str = "vector_db",
                 db_user: str = "postgres",
                 db_password: str = "password",
                 pool_size: int = 20):
        
        self.connection_string = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"
        self.pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=pool_size,
            dsn=self.connection_string
        )
        self._initialize_database()
        self._create_indexes()
        
    def _initialize_database(self):
        """Initialize database with pgvector extension and required tables"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Enable pgvector extension
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create embeddings table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        domain VARCHAR(255) NOT NULL,
                        artifact_type VARCHAR(50) NOT NULL,
                        artifact_id VARCHAR(255),
                        content_hash VARCHAR(64),
                        embedding vector(384),
                        model_version VARCHAR(50) NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Create embeddings index for faster similarity search
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_domain_type 
                    ON embeddings(domain, artifact_type)
                """)
                
                # Create composite index for common queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_metadata 
                    ON embeddings USING gin(metadata)
                """)
                
                # Create vector index for similarity search
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_vector 
                    ON embeddings USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                
                conn.commit()
                register_vector(conn)
                
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def _create_indexes(self):
        """Create additional performance indexes"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Index for timestamp-based queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_created 
                    ON embeddings(created_at DESC)
                """)
                
                # Index for content hash lookups
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_hash 
                    ON embeddings(content_hash)
                """)
                
                # Partial index for active embeddings
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_active 
                    ON embeddings(domain, artifact_type) 
                    WHERE metadata->>'status' = 'active'
                """)
                
                conn.commit()
        except Exception as e:
            conn.rollback()
        finally:
            self.pool.putconn(conn)
    
    def store_embeddings(self, artifacts: List[Dict]) -> Dict:
        """Store multiple embeddings with their metadata"""
        start_time = datetime.utcnow()
        stored_ids = []
        skipped = []
        
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                for artifact in artifacts:
                    try:
                        # Check if similar embedding already exists
                        if self._should_skip_artifact(cur, artifact):
                            skipped.append({
                                'artifact_id': artifact.get('artifact_id'),
                                'reason': 'duplicate_or_similar_exists'
                            })
                            continue
                        
                        # Generate ID
                        embedding_id = uuid.uuid4()
                        
                        # Prepare embedding array
                        embedding_array = artifact.get('embedding')
                        if embedding_array is not None:
                            embedding_array = np.array(embedding_array, dtype=np.float32)
                        
                        # Insert embedding
                        cur.execute("""
                            INSERT INTO embeddings 
                            (id, domain, artifact_type, artifact_id, content_hash, 
                             embedding, model_version, metadata, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            RETURNING id
                        """, (
                            embedding_id,
                            artifact.get('domain', 'default'),
                            artifact.get('artifact_type', 'unknown'),
                            artifact.get('artifact_id'),
                            artifact.get('content_hash'),
                            embedding_array,
                            artifact.get('model_version', 'unknown'),
                            Json(artifact.get('metadata', {}))
                        ))
                        
                        stored_ids.append(str(embedding_id))
                        
                    except Exception as e:
                        skipped.append({
                            'artifact_id': artifact.get('artifact_id'),
                            'reason': str(e)[:100]
                        })
                        continue
                
                conn.commit()
                
                elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                return {
                    'stored_count': len(stored_ids),
                    'skipped_count': len(skipped),
                    'stored_ids': stored_ids,
                    'skipped': skipped[:10],  # Limit output
                    'storage_time_ms': round(elapsed, 2),
                    'batch_size': len(artifacts),
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def _should_skip_artifact(self, cursor, artifact: Dict) -> bool:
        """Check if artifact should be skipped (duplicate or similar exists)"""
        domain = artifact.get('domain', 'default')
        artifact_type = artifact.get('artifact_type', 'unknown')
        content_hash = artifact.get('content_hash')
        artifact_id = artifact.get('artifact_id')
        
        # Check by content hash
        if content_hash:
            cursor.execute("""
                SELECT COUNT(*) FROM embeddings 
                WHERE domain = %s AND artifact_type = %s AND content_hash = %s
                AND created_at > NOW() - INTERVAL '7 days'
            """, (domain, artifact_type, content_hash))
            count = cursor.fetchone()[0]
            if count > 0:
                return True
        
        # Check by artifact ID
        if artifact_id:
            cursor.execute("""
                SELECT COUNT(*) FROM embeddings 
                WHERE domain = %s AND artifact_type = %s AND artifact_id = %s
                AND created_at > NOW() - INTERVAL '1 day'
            """, (domain, artifact_type, artifact_id))
            count = cursor.fetchone()[0]
            if count > 0:
                return True
        
        # Check for very similar embeddings
        embedding = artifact.get('embedding')
        if embedding:
            embedding_array = np.array(embedding, dtype=np.float32)
            cursor.execute("""
                SELECT COUNT(*) FROM embeddings 
                WHERE domain = %s AND artifact_type = %s 
                AND embedding IS NOT NULL
                AND created_at > NOW() - INTERVAL '1 day'
                AND embedding <=> %s < 0.1
            """, (domain, artifact_type, embedding_array))
            count = cursor.fetchone()[0]
            if count > 0:
                return True
        
        return False
    
    def get_embedding(self, embedding_id: str) -> Optional[Dict]:
        """Retrieve embedding by ID"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, domain, artifact_type, artifact_id, content_hash,
                           embedding, model_version, metadata, created_at, updated_at
                    FROM embeddings 
                    WHERE id = %s
                """, (uuid.UUID(embedding_id),))
                
                row = cur.fetchone()
                if row:
                    return {
                        'id': str(row[0]),
                        'domain': row[1],
                        'artifact_type': row[2],
                        'artifact_id': row[3],
                        'content_hash': row[4],
                        'embedding': row[5].tolist() if row[5] is not None else None,
                        'model_version': row[6],
                        'metadata': row[7],
                        'created_at': row[8].isoformat() if row[8] else None,
                        'updated_at': row[9].isoformat() if row[9] else None
                    }
                return None
                
        finally:
            self.pool.putconn(conn)
    
    def update_embedding_metadata(self, embedding_id: str, metadata_updates: Dict) -> bool:
        """Update embedding metadata"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Get current metadata
                cur.execute("""
                    SELECT metadata FROM embeddings WHERE id = %s
                """, (uuid.UUID(embedding_id),))
                
                row = cur.fetchone()
                if not row:
                    return False
                
                current_metadata = row[0] or {}
                
                # Merge updates
                updated_metadata = {**current_metadata, **metadata_updates}
                
                # Update
                cur.execute("""
                    UPDATE embeddings 
                    SET metadata = %s, updated_at = NOW()
                    WHERE id = %s
                """, (Json(updated_metadata), uuid.UUID(embedding_id)))
                
                conn.commit()
                return cur.rowcount > 0
                
        except Exception as e:
            conn.rollback()
            return False
        finally:
            self.pool.putconn(conn)
    
    def delete_embedding(self, embedding_id: str) -> bool:
        """Delete embedding by ID"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM embeddings WHERE id = %s
                """, (uuid.UUID(embedding_id),))
                
                conn.commit()
                return cur.rowcount > 0
                
        except Exception as e:
            conn.rollback()
            return False
        finally:
            self.pool.putconn(conn)
    
    def bulk_delete(self, domain: str = None, artifact_type: str = None, 
                   older_than_days: int = 30) -> Dict:
        """Bulk delete embeddings based on criteria"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                conditions = []
                params = []
                
                if domain:
                    conditions.append("domain = %s")
                    params.append(domain)
                
                if artifact_type:
                    conditions.append("artifact_type = %s")
                    params.append(artifact_type)
                
                if older_than_days > 0:
                    conditions.append("created_at < NOW() - INTERVAL '%s days'")
                    params.append(str(older_than_days))
                
                if not conditions:
                    return {'deleted_count': 0, 'message': 'No conditions specified'}
                
                # Get count before deletion
                count_query = f"""
                    SELECT COUNT(*) FROM embeddings 
                    WHERE {' AND '.join(conditions)}
                """
                cur.execute(count_query, params)
                count_before = cur.fetchone()[0]
                
                # Perform deletion
                delete_query = f"""
                    DELETE FROM embeddings 
                    WHERE {' AND '.join(conditions)}
                    RETURNING id
                """
                cur.execute(delete_query, params)
                
                deleted_ids = [str(row[0]) for row in cur.fetchall()]
                
                conn.commit()
                
                return {
                    'deleted_count': len(deleted_ids),
                    'count_before': count_before,
                    'sample_deleted_ids': deleted_ids[:10],
                    'criteria': {
                        'domain': domain,
                        'artifact_type': artifact_type,
                        'older_than_days': older_than_days
                    },
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)
    
    def get_embedding_stats(self, domain: str = None) -> Dict:
        """Get statistics about stored embeddings"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                stats = {}
                
                # Total counts
                if domain:
                    cur.execute("""
                        SELECT COUNT(*) as total, 
                               COUNT(DISTINCT artifact_type) as types,
                               MIN(created_at) as oldest,
                               MAX(created_at) as newest
                        FROM embeddings 
                        WHERE domain = %s
                    """, (domain,))
                else:
                    cur.execute("""
                        SELECT COUNT(*) as total, 
                               COUNT(DISTINCT artifact_type) as types,
                               COUNT(DISTINCT domain) as domains,
                               MIN(created_at) as oldest,
                               MAX(created_at) as newest
                        FROM embeddings
                    """)
                
                row = cur.fetchone()
                if row:
                    stats['total_embeddings'] = row[0]
                    stats['artifact_types'] = row[1]
                    if not domain:
                        stats['domains'] = row[2]
                        stats['oldest'] = row[3].isoformat() if row[3] else None
                    stats['newest'] = row[4].isoformat() if row[4] else None
                
                # Count by artifact type
                if domain:
                    cur.execute("""
                        SELECT artifact_type, COUNT(*) as count
                        FROM embeddings 
                        WHERE domain = %s
                        GROUP BY artifact_type
                        ORDER BY count DESC
                        LIMIT 10
                    """, (domain,))
                else:
                    cur.execute("""
                        SELECT artifact_type, COUNT(*) as count
                        FROM embeddings 
                        GROUP BY artifact_type
                        ORDER BY count DESC
                        LIMIT 10
                    """)
                
                stats['by_artifact_type'] = [
                    {'type': row[0], 'count': row[1]} 
                    for row in cur.fetchall()
                ]
                
                # Storage size estimate
                cur.execute("""
                    SELECT pg_size_pretty(pg_total_relation_size('embeddings')) as table_size,
                           pg_size_pretty(pg_indexes_size('embeddings')) as index_size
                """)
                size_row = cur.fetchone()
                if size_row:
                    stats['storage_size'] = {
                        'table': size_row[0],
                        'indexes': size_row[1]
                    }
                
                # Model version distribution
                cur.execute("""
                    SELECT model_version, COUNT(*) as count
                    FROM embeddings 
                    GROUP BY model_version
                    ORDER BY count DESC
                    LIMIT 5
                """)
                stats['model_versions'] = [
                    {'version': row[0], 'count': row[1]} 
                    for row in cur.fetchall()
                ]
                
                # Recent activity
                cur.execute("""
                    SELECT COUNT(*) as last_hour
                    FROM embeddings 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)
                stats['recent_activity'] = {
                    'last_hour': cur.fetchone()[0]
                }
                
                return stats
                
        finally:
            self.pool.putconn(conn)
    
    def vacuum_and_analyze(self):
        """Perform maintenance operations"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Analyze for query planner
                cur.execute("ANALYZE embeddings")
                
                # Vacuum to reclaim space
                cur.execute("VACUUM (VERBOSE, ANALYZE) embeddings")
                
                # Reindex for performance
                cur.execute("REINDEX INDEX idx_embeddings_vector")
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Maintenance error: {e}")
        finally:
            self.pool.putconn(conn)
    
    def get_connection_stats(self) -> Dict:
        """Get connection pool statistics"""
        return {
            'pool_minconn': self.pool.minconn,
            'pool_maxconn': self.pool.maxconn,
            'connections_active': self.pool._used,
            'connections_idle': self.pool.maxconn - self.pool._used,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def close(self):
        """Close all connections"""
        self.pool.closeall()
