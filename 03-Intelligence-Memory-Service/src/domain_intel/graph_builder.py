from neo4j import GraphDatabase, basic_auth
from datetime import datetime, timedelta
import networkx as nx
from collections import defaultdict, deque
import hashlib
import json
from typing import Dict, List, Any, Tuple, Optional
import asyncio
import aiohttp

class DomainGraph:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(
            neo4j_uri, 
            auth=basic_auth(neo4j_user, neo4j_password),
            max_connection_lifetime=3600
        )
        self.in_memory_graph = nx.DiGraph()
        self.domain_cache = defaultdict(dict)
        self.relationship_weights = self._initialize_weights()
        self._initialize_constraints()
        
    def _initialize_constraints(self):
        """Initialize Neo4j constraints"""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:Subdomain) REQUIRE s.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (i:IP) REQUIRE i.address IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:CDN) REQUIRE c.provider IS UNIQUE")
    
    def _initialize_weights(self) -> Dict:
        """Initialize relationship weights"""
        return {
            'subdomain_of': 0.8,
            'resolves_to': 0.9,
            'uses_cdn': 0.7,
            'behind_waf': 0.6,
            'similar_fingerprint': 0.5,
            'geographic_proximity': 0.4,
            'temporal_correlation': 0.3,
            'success_correlation': 0.6
        }
    
    async def build_graph(self, domain_data: Dict) -> Dict:
        """Build or update domain graph relationships"""
        start_time = datetime.utcnow()
        domain = domain_data.get('domain', '')
        
        if not domain:
            return {'error': 'No domain provided', 'relationships': []}
        
        # Extract graph data
        graph_components = self._extract_graph_components(domain_data)
        
        # Build relationships
        relationships = await self._build_relationships(domain, graph_components)
        
        # Update Neo4j
        await self._update_neo4j_graph(domain, graph_components, relationships)
        
        # Update in-memory graph
        self._update_in_memory_graph(domain, graph_components, relationships)
        
        # Cache domain data
        self.domain_cache[domain] = {
            'components': graph_components,
            'relationships': relationships,
            'updated_at': datetime.utcnow()
        }
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'domain': domain,
            'relationships': relationships,
            'relationship_count': len(relationships),
            'components_extracted': len(graph_components),
            'graph_update_time_ms': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _extract_graph_components(self, domain_data: Dict) -> Dict:
        """Extract graph components from domain data"""
        components = defaultdict(list)
        
        # Subdomains
        subdomains = domain_data.get('subdomains', [])
        components['subdomains'] = [{'name': sd, 'type': 'subdomain'} for sd in subdomains]
        
        # IP addresses
        ips = domain_data.get('resolved_ips', [])
        components['ips'] = [{'address': ip, 'type': 'ipv4' if '.' in ip else 'ipv6'} for ip in ips]
        
        # CDN detection
        cdn_info = domain_data.get('cdn', {})
        if cdn_info.get('detected', False):
            components['cdn'] = [{
                'provider': cdn_info.get('provider', 'unknown'),
                'type': cdn_info.get('type', 'reverse_proxy'),
                'confidence': cdn_info.get('confidence', 0.5)
            }]
        
        # WAF detection
        waf_info = domain_data.get('waf', {})
        if waf_info.get('detected', False):
            components['waf'] = [{
                'provider': waf_info.get('provider', 'unknown'),
                'type': waf_info.get('type', 'cloud'),
                'signatures': waf_info.get('signatures', [])
            }]
        
        # TLS information
        tls_info = domain_data.get('tls', {})
        if tls_info:
            components['tls'] = [{
                'version': tls_info.get('version', 'TLS_1.2'),
                'cipher_suite': tls_info.get('cipher_suite', ''),
                'cert_issuer': tls_info.get('cert_issuer', '')
            }]
        
        # Header patterns
        headers = domain_data.get('response_headers', {})
        if headers:
            components['headers'] = [{
                'server': headers.get('server', ''),
                'x_powered_by': headers.get('x-powered-by', ''),
                'content_type': headers.get('content-type', '')
            }]
        
        # Geographic information
        geo_info = domain_data.get('geographic', {})
        if geo_info:
            components['geo'] = [{
                'country': geo_info.get('country', ''),
                'region': geo_info.get('region', ''),
                'city': geo_info.get('city', ''),
                'asn': geo_info.get('asn', '')
            }]
        
        # Execution patterns
        exec_patterns = domain_data.get('execution_patterns', {})
        if exec_patterns:
            components['patterns'] = [{
                'success_rate': exec_patterns.get('success_rate', 0.0),
                'avg_response_time': exec_patterns.get('avg_response_time_ms', 0),
                'error_distribution': exec_patterns.get('error_distribution', {})
            }]
        
        return dict(components)
    
    async def _build_relationships(self, domain: str, components: Dict) -> List[Dict]:
        """Build relationship objects with strength scores"""
        relationships = []
        
        # Subdomain relationships
        for subdomain in components.get('subdomains', []):
            strength = self.relationship_weights['subdomain_of']
            relationships.append({
                'source': domain,
                'target': subdomain['name'],
                'type': 'SUBDOMAIN_OF',
                'strength': strength,
                'properties': {'created_at': datetime.utcnow().isoformat()}
            })
        
        # IP resolution relationships
        for ip in components.get('ips', []):
            strength = self.relationship_weights['resolves_to']
            relationships.append({
                'source': domain,
                'target': ip['address'],
                'type': 'RESOLVES_TO',
                'strength': strength,
                'properties': {'type': ip['type'], 'created_at': datetime.utcnow().isoformat()}
            })
        
        # CDN relationships
        for cdn in components.get('cdn', []):
            strength = self.relationship_weights['uses_cdn'] * cdn.get('confidence', 0.5)
            relationships.append({
                'source': domain,
                'target': cdn['provider'],
                'type': 'USES_CDN',
                'strength': strength,
                'properties': {'cdn_type': cdn['type'], 'created_at': datetime.utcnow().isoformat()}
            })
        
        # WAF relationships
        for waf in components.get('waf', []):
            strength = self.relationship_weights['behind_waf']
            relationships.append({
                'source': domain,
                'target': waf['provider'],
                'type': 'BEHIND_WAF',
                'strength': strength,
                'properties': {'waf_type': waf['type'], 'created_at': datetime.utcnow().isoformat()}
            })
        
        # Find similar fingerprints
        similar_domains = await self._find_similar_fingerprints(domain, components)
        for similar_domain in similar_domains:
            strength = self.relationship_weights['similar_fingerprint']
            relationships.append({
                'source': domain,
                'target': similar_domain,
                'type': 'SIMILAR_FINGERPRINT',
                'strength': strength,
                'properties': {
                    'similarity_score': 0.8,  # Would calculate actual similarity
                    'created_at': datetime.utcnow().isoformat()
                }
            })
        
        # Geographic proximity
        geo_data = components.get('geo', [])
        if geo_data:
            geo_relationships = await self._find_geographic_proximity(domain, geo_data[0])
            relationships.extend(geo_relationships)
        
        return relationships
    
    async def _find_similar_fingerprints(self, domain: str, components: Dict) -> List[str]:
        """Find domains with similar fingerprints"""
        # Simplified - would use actual fingerprint comparison
        similar = []
        
        # Compare TLS configurations
        tls_data = components.get('tls', [])
        if tls_data:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (d:Domain)-[:USES_TLS]->(t:TLS)
                    WHERE t.version = $version AND t.cipher_suite = $cipher
                    RETURN d.name as domain
                    LIMIT 5
                """, version=tls_data[0].get('version'), cipher=tls_data[0].get('cipher_suite', ''))
                
                similar = [record['domain'] for record in result if record['domain'] != domain]
        
        return similar[:10]
    
    async def _find_geographic_proximity(self, domain: str, geo_data: Dict) -> List[Dict]:
        """Find domains in geographic proximity"""
        relationships = []
        
        country = geo_data.get('country', '')
        if country:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (d:Domain)-[:LOCATED_IN]->(g:Geo)
                    WHERE g.country = $country AND d.name <> $domain
                    RETURN d.name as domain, g.city as city
                    LIMIT 5
                """, country=country, domain=domain)
                
                for record in result:
                    strength = self.relationship_weights['geographic_proximity']
                    if record['city'] == geo_data.get('city', ''):
                        strength *= 1.2
                    
                    relationships.append({
                        'source': domain,
                        'target': record['domain'],
                        'type': 'GEOGRAPHIC_PROXIMITY',
                        'strength': strength,
                        'properties': {
                            'country': country,
                            'city': record['city'],
                            'created_at': datetime.utcnow().isoformat()
                        }
                    })
        
        return relationships
    
    async def _update_neo4j_graph(self, domain: str, components: Dict, relationships: List[Dict]):
        """Update Neo4j graph database"""
        with self.driver.session() as session:
            # Create or update domain node
            session.run("""
                MERGE (d:Domain {name: $domain})
                SET d.updated_at = $timestamp,
                    d.component_count = $component_count
            """, domain=domain, timestamp=datetime.utcnow().isoformat(), 
               component_count=len(components))
            
            # Create component nodes and relationships
            for comp_type, comp_list in components.items():
                for comp in comp_list:
                    if comp_type == 'subdomains':
                        session.run("""
                            MERGE (sd:Subdomain {name: $name})
                            MERGE (d:Domain {name: $domain})
                            MERGE (sd)-[:SUBDOMAIN_OF]->(d)
                        """, name=comp['name'], domain=domain)
                    
                    elif comp_type == 'ips':
                        session.run("""
                            MERGE (ip:IP {address: $address})
                            SET ip.type = $type
                            MERGE (d:Domain {name: $domain})
                            MERGE (d)-[:RESOLVES_TO]->(ip)
                        """, address=comp['address'], type=comp['type'], domain=domain)
                    
                    elif comp_type == 'cdn':
                        session.run("""
                            MERGE (cdn:CDN {provider: $provider})
                            SET cdn.type = $type
                            MERGE (d:Domain {name: $domain})
                            MERGE (d)-[:USES_CDN {confidence: $confidence}]->(cdn)
                        """, provider=comp['provider'], type=comp['type'], 
                           domain=domain, confidence=comp.get('confidence', 0.5))
                    
                    elif comp_type == 'waf':
                        session.run("""
                            MERGE (waf:WAF {provider: $provider})
                            SET waf.type = $type
                            MERGE (d:Domain {name: $domain})
                            MERGE (d)-[:BEHIND_WAF]->(waf)
                        """, provider=comp['provider'], type=comp['type'], domain=domain)
            
            # Create relationships between domains
            for rel in relationships:
                if rel['type'] in ['SIMILAR_FINGERPRINT', 'GEOGRAPHIC_PROXIMITY']:
                    session.run(f"""
                        MERGE (d1:Domain {{name: $source}})
                        MERGE (d2:Domain {{name: $target}})
                        MERGE (d1)-[r:{rel['type']}]->(d2)
                        SET r.strength = $strength,
                            r.created_at = $created_at
                    """, source=rel['source'], target=rel['target'], 
                       strength=rel['strength'], created_at=datetime.utcnow().isoformat())
    
    def _update_in_memory_graph(self, domain: str, components: Dict, relationships: List[Dict]):
        """Update in-memory graph for fast queries"""
        # Add domain node
        self.in_memory_graph.add_node(domain, type='domain', updated_at=datetime.utcnow())
        
        # Add relationships
        for rel in relationships:
            self.in_memory_graph.add_edge(
                rel['source'], 
                rel['target'],
                type=rel['type'],
                strength=rel['strength'],
                created_at=datetime.utcnow()
            )
        
        # Limit graph size
        if len(self.in_memory_graph) > 10000:
            # Remove oldest nodes
            nodes_by_age = sorted(
                self.in_memory_graph.nodes(data=True),
                key=lambda x: x[1].get('updated_at', datetime.min)
            )
            nodes_to_remove = nodes_by_age[:1000]
            self.in_memory_graph.remove_nodes_from([n[0] for n in nodes_to_remove])
    
    async def query_relationships(self, domain: str, depth: int = 2) -> Dict:
        """Query domain relationships up to specified depth"""
        # Try in-memory graph first
        if domain in self.in_memory_graph:
            try:
                ego_graph = nx.ego_graph(self.in_memory_graph, domain, radius=depth)
                relationships = []
                
                for source, target, data in ego_graph.edges(data=True):
                    relationships.append({
                        'source': source,
                        'target': target,
                        'type': data.get('type', 'UNKNOWN'),
                        'strength': data.get('strength', 0.0),
                        'created_at': data.get('created_at', datetime.min).isoformat()
                    })
                
                return {
                    'domain': domain,
                    'depth': depth,
                    'relationship_count': len(relationships),
                    'relationships': relationships,
                    'source': 'memory_cache'
                }
            except:
                pass
        
        # Fall back to Neo4j
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (d:Domain {name: $domain})-[*1..$depth]-(connected)
                UNWIND relationships(path) as rel
                RETURN DISTINCT 
                    startNode(rel).name as source,
                    endNode(rel).name as target,
                    type(rel) as type,
                    rel.strength as strength,
                    rel.created_at as created_at
                LIMIT 100
            """, domain=domain, depth=depth)
            
            relationships = []
            for record in result:
                relationships.append({
                    'source': record['source'],
                    'target': record['target'],
                    'type': record['type'],
                    'strength': record['strength'] or 0.0,
                    'created_at': record['created_at'] or datetime.utcnow().isoformat()
                })
            
            return {
                'domain': domain,
                'depth': depth,
                'relationship_count': len(relationships),
                'relationships': relationships,
                'source': 'neo4j'
            }
    
    async def find_clusters(self, min_relationships: int = 3) -> List[Dict]:
        """Find domain clusters based on relationships"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d1:Domain)-[r]-(d2:Domain)
                WITH d1, d2, count(r) as rel_count
                WHERE rel_count >= $min_rels
                RETURN d1.name as domain1, d2.name as domain2, rel_count
                ORDER BY rel_count DESC
                LIMIT 50
            """, min_rels=min_relationships)
            
            clusters = defaultdict(set)
            for record in result:
                clusters[record['domain1']].add(record['domain2'])
                clusters[record['domain2']].add(record['domain1'])
            
            # Merge overlapping clusters
            merged_clusters = []
            for domain, related in clusters.items():
                found = False
                for cluster in merged_clusters:
                    if domain in cluster['domains']:
                        cluster['domains'].update(related)
                        cluster['size'] = len(cluster['domains'])
                        found = True
                        break
                
                if not found:
                    merged_clusters.append({
                        'domains': {domain}.union(related),
                        'size': len({domain}.union(related)),
                        'center': domain
                    })
            
            return merged_clusters
    
    async def get_domain_neighbors(self, domain: str, relationship_type: str = None) -> Dict:
        """Get direct neighbors of domain"""
        if relationship_type:
            query = """
                MATCH (d:Domain {name: $domain})-[r]->(neighbor)
                WHERE type(r) = $rel_type
                RETURN neighbor.name as neighbor, type(r) as type, r.strength as strength
                LIMIT 50
            """
            params = {'domain': domain, 'rel_type': relationship_type}
        else:
            query = """
                MATCH (d:Domain {name: $domain})-[r]-(neighbor)
                RETURN neighbor.name as neighbor, type(r) as type, r.strength as strength
                LIMIT 100
            """
            params = {'domain': domain}
        
        with self.driver.session() as session:
            result = session.run(query, **params)
            
            neighbors = []
            for record in result:
                neighbors.append({
                    'neighbor': record['neighbor'],
                    'relationship_type': record['type'],
                    'strength': record['strength'] or 0.0
                })
            
            return {
                'domain': domain,
                'neighbor_count': len(neighbors),
                'neighbors': neighbors
            }
    
    async def clean_old_data(self, days_old: int = 30):
        """Clean data older than specified days"""
        cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
        
        with self.driver.session() as session:
            # Remove old relationships
            session.run("""
                MATCH ()-[r]-()
                WHERE r.created_at < $cutoff
                DELETE r
            """, cutoff=cutoff_date)
            
            # Remove orphaned nodes
            session.run("""
                MATCH (n)
                WHERE NOT (n)--()
                DELETE n
            """)
        
        # Clean cache
        domains_to_remove = []
        for domain, data in self.domain_cache.items():
            if data.get('updated_at', datetime.min) < datetime.utcnow() - timedelta(days=days_old):
                domains_to_remove.append(domain)
        
        for domain in domains_to_remove:
            del self.domain_cache[domain]
    
    def get_graph_stats(self) -> Dict:
        """Get graph statistics"""
        with self.driver.session() as session:
            # Node counts
            node_counts = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
            """)
            
            labels = {}
            for record in node_counts:
                labels[record['label']] = record['count']
            
            # Relationship counts
            rel_counts = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
            """)
            
            relationships = {}
            for record in rel_counts:
                relationships[record['type']] = record['count']
            
            # Memory graph stats
            memory_nodes = self.in_memory_graph.number_of_nodes()
            memory_edges = self.in_memory_graph.number_of_edges()
            
            return {
                'neo4j_nodes_by_type': labels,
                'neo4j_relationships_by_type': relationships,
                'memory_graph_nodes': memory_nodes,
                'memory_graph_edges': memory_edges,
                'cache_size': len(self.domain_cache),
                'timestamp': datetime.utcnow().isoformat()
            }
