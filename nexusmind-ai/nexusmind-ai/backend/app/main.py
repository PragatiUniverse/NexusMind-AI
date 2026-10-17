"""NexusMind AI backend (MVP core). In-memory store; all seed records are SYNTHETIC demo data."""
import hashlib, os, re, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="NexusMind AI")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
MAX = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
now = lambda: datetime.now(timezone.utc).isoformat()

# REAL papers (metadata checked against arXiv). Claim text is a paraphrase of each abstract; each excerpt is a
# short verbatim quote from the arXiv abstract. Links between claims are AI-INFERRED and unverified.
PAPERS = {
 "p1": {"id": "p1", "title": "MemGPT: Towards LLMs as Operating Systems", "authors": "Packer et al.", "year": 2023, "arxiv": "2310.08560", "doi": "10.48550/arXiv.2310.08560", "demo": False, "status": "ready"},
 "p2": {"id": "p2", "title": "Generative Agents: Interactive Simulacra of Human Behavior", "authors": "Park et al.", "year": 2023, "arxiv": "2304.03442", "doi": "10.48550/arXiv.2304.03442", "demo": False, "status": "ready"},
 "p3": {"id": "p3", "title": "Lost in the Middle: How Language Models Use Long Contexts", "authors": "Liu et al.", "year": 2023, "arxiv": "2307.03172", "doi": "10.1162/tacl_a_00638", "demo": False, "status": "ready"}}
CLAIMS = [
 {"id": "c1", "paper": "p1", "text": "Paging data between a limited context window and external storage, like OS virtual memory, extends usable context for language models.", "excerpt": "we propose virtual context management", "page": 1, "kind": "finding"},
 {"id": "c2", "paper": "p2", "text": "Agents can store experiences, synthesize them into higher-level reflections, and retrieve them to plan behavior.", "excerpt": "synthesize those memories over time into higher-level reflections", "page": 1, "kind": "finding"},
 {"id": "c3", "paper": "p3", "text": "Language model performance can degrade significantly depending on where relevant information sits in a long input.", "excerpt": "performance can degrade significantly when changing the position of relevant information", "page": 1, "kind": "finding"}]
CONTRA = {"x1": {"id": "x1", "a": "c1", "b": "c3", "status": "unresolved", "inferred": True,
  "note": "AI-inferred candidate tension, unverified. c3 studies position sensitivity inside one long input; c1 avoids long inputs by paging. They may not conflict at all."}}
EDGES = [("p1","c1","REPORTS_FINDING"),("p2","c2","REPORTS_FINDING"),("p3","c3","REPORTS_FINDING"),("c1","c3","CONTRADICTS")]
STOP = set("the a of and in to is are what which how for on with".split())
tok = lambda s: {w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2}

@app.get("/health")
def health(): return {"status": "ok", "store": "memory", "neo4j": "not configured", "llm": "not configured"}

@app.get("/api/papers")
def papers(): return list(PAPERS.values())

@app.post("/api/papers/upload")
async def upload(file: UploadFile = File(...)):
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Only PDF files are accepted.")
    data = await file.read()
    if len(data) > MAX: raise HTTPException(413, "File too large.")
    if not data.startswith(b"%PDF"): raise HTTPException(422, "File is not a valid PDF.")
    fp = hashlib.sha256(data).hexdigest()
    if any(p.get("fp") == fp for p in PAPERS.values()): raise HTTPException(409, "Duplicate paper.")
    import fitz
    try: doc = fitz.open(stream=data, filetype="pdf")
    except Exception: raise HTTPException(422, "Could not read PDF.")
    text = "".join(pg.get_text() for pg in doc).strip()
    if len(text) < 200: raise HTTPException(422, "No extractable text (likely a scanned PDF). OCR is not supported.")
    pid = uuid.uuid4().hex[:8]
    PAPERS[pid] = {"id": pid, "title": (file.filename or "Untitled")[:200], "fp": fp, "text": text,
                   "pages": len(doc), "status": "text_extracted", "demo": False, "created": now()}
    return {k: v for k, v in PAPERS[pid].items() if k != "text"}

class Ask(BaseModel): question: str = Field(min_length=5, max_length=1000)

@app.post("/api/research/ask")
def ask(q: Ask):
    qt = tok(q.question)
    hits = sorted(((len(qt & tok(c["text"])), c) for c in CLAIMS), key=lambda x: -x[0])
    hits = [c for s, c in hits if s > 0][:5]
    if not hits: return {"answer": "Insufficient evidence in the indexed corpus.", "citations": []}
    ids = {c["id"] for c in hits}
    conflicts = [x for x in CONTRA.values() if x["a"] in ids or x["b"] in ids]
    return {"answer": "Keyword-retrieved evidence (no LLM configured); no synthesis performed.",
            "citations": [{"claim": c["id"], "paper": c["paper"], "excerpt": c["excerpt"], "page": c["page"]} for c in hits],
            "conflicts": conflicts}

@app.get("/api/graph")
def graph():
    nodes = [{"id": p["id"], "type": "Paper", "label": p["title"]} for p in PAPERS.values()] + \
            [{"id": c["id"], "type": c["kind"].capitalize(), "label": c["text"]} for c in CLAIMS]
    return {"nodes": nodes, "edges": [{"s": s, "t": t, "type": r} for s, t, r in EDGES], "demo": True}

@app.get("/api/contradictions")
def contradictions(): return list(CONTRA.values())

class Review(BaseModel): status: str = Field(pattern="^(confirmed|unresolved|not_a_contradiction)$")

@app.post("/api/contradictions/{cid}/review")
def review(cid: str, r: Review):
    if cid not in CONTRA: raise HTTPException(404, "Unknown contradiction.")
    CONTRA[cid]["status"] = r.status; return CONTRA[cid]

@app.get("/api/research-gaps")
def gaps():
    ev = [c for c in CLAIMS if c["id"] in ("c1", "c3")]
    return [{"title": "Does tiered memory paging reduce position sensitivity in long-context use?",
             "papers": sorted({c["paper"] for c in ev}), "evidence": [c["excerpt"] for c in ev], "inferred": True,
             "note": "AI-inferred candidate gap within the indexed corpus only. The papers do not state it; novelty needs human literature review."}]
