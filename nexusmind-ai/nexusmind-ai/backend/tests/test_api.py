from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
def test_health(): assert c.get("/health").json()["status"] == "ok"
def test_bad_upload(): assert c.post("/api/papers/upload", files={"file": ("a.txt", b"hi", "text/plain")}).status_code == 415
def test_insufficient(): assert "Insufficient" in c.post("/api/research/ask", json={"question": "zzzz qqqq xxxx"}).json()["answer"]
def test_review():
    assert c.post("/api/contradictions/x1/review", json={"status": "confirmed"}).json()["status"] == "confirmed"
    assert c.post("/api/contradictions/x1/review", json={"status": "bad"}).status_code == 422
def test_gaps(): assert len(c.get("/api/research-gaps").json()) == 1
def test_neo4j_missing():
    assert c.get("/api/graph/neo4j/sync").status_code == 503
def test_process_needs_llm():
    assert c.post("/api/papers/p1/process").status_code == 404
def test_hypothesis_labels():
    g = c.get("/api/research-gaps").json()[0]["title"]
    h = c.post("/api/hypotheses/generate", json={"gap_title": g}).json()
    assert "PROPOSED" in h["status"] and h["datasets"][0]["label"] == "AI-proposed"
def test_report_export():
    r = c.post("/api/reports/generate").json()
    assert c.get(f"/api/reports/{r['id']}/export?format=md").status_code == 200
