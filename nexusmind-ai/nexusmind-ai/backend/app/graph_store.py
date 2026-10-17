"""Neo4j persistence. All Cypher is parameterized; node IDs are unique-constrained; writes use MERGE."""
import os
from neo4j import GraphDatabase

class GraphUnavailable(Exception): pass

def driver():
    uri = os.getenv("NEO4J_URI")
    if not uri: raise GraphUnavailable("NEO4J_URI is not set.")
    try:
        d = GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")))
        d.verify_connectivity(); return d
    except Exception as e:
        raise GraphUnavailable(f"Cannot reach Neo4j: {type(e).__name__}")

LABELS = {"Paper", "Finding", "Limitation", "Claim"}

def setup(d):
    with d.session() as s:
        for l in LABELS: s.run(f"CREATE CONSTRAINT {l.lower()}_id IF NOT EXISTS FOR (n:{l}) REQUIRE n.id IS UNIQUE")

def sync(d, papers, claims, edges):
    """Idempotent upsert of the in-memory corpus (labels come from a fixed allowlist, never user input)."""
    def tx(t):
        for p in papers: t.run("MERGE (n:Paper {id:$id}) SET n.title=$title, n.demo=$demo", id=p["id"], title=p["title"], demo=p.get("demo", False))
        for c in claims:
            lab = "Limitation" if c["kind"] == "limitation" else "Finding"
            t.run(f"MERGE (n:{lab} {{id:$id}}) SET n.text=$text, n.excerpt=$ex, n.page=$pg, n.paper=$paper, n.method='seed'",
                  id=c["id"], text=c["text"], ex=c["excerpt"], pg=c["page"], paper=c["paper"])
        rels = {"REPORTS_FINDING", "HAS_LIMITATION", "CONTRADICTS"}
        for s_, t_, r in edges:
            if r in rels: t.run(f"MATCH (a {{id:$a}}),(b {{id:$b}}) MERGE (a)-[:{r}]->(b)", a=s_, b=t_)
    with d.session() as s: s.execute_write(tx)

def read_graph(d):
    with d.session() as s:
        nodes = [dict(r["n"], type=list(r["n"].labels)[0]) for r in s.run("MATCH (n) RETURN n LIMIT 500")]
        edges = [{"s": r["a"], "t": r["b"], "type": r["t"]} for r in s.run("MATCH (a)-[r]->(b) RETURN a.id AS a, b.id AS b, type(r) AS t LIMIT 2000")]
    return {"nodes": nodes, "edges": edges}

def shortest_path(d, a, b):
    with d.session() as s:
        r = s.run("MATCH p=shortestPath((x {id:$a})-[*..6]-(y {id:$b})) RETURN [n IN nodes(p) | n.id] AS ids", a=a, b=b).single()
    return r["ids"] if r else None
