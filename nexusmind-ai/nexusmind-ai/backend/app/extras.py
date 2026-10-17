import io
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from . import llm, openalex, graph_store

router = APIRouter()
HISTORY: list = []  # saved investigations (in memory)

def _m():
    from . import main; return main

@router.get("/api/graph/neo4j/sync")
def neo_sync():
    m = _m()
    try:
        d = graph_store.driver(); graph_store.setup(d); graph_store.sync(d, list(m.PAPERS.values()), m.CLAIMS, m.EDGES); return graph_store.read_graph(d)
    except graph_store.GraphUnavailable as e:
        raise HTTPException(503, str(e))

@router.get("/api/graph/path")
def path(a: str, b: str):
    try: ids = graph_store.shortest_path(graph_store.driver(), a, b)
    except graph_store.GraphUnavailable as e: raise HTTPException(503, str(e))
    return {"path": ids}

class Search(BaseModel): query: str = Field(min_length=2, max_length=200)

@router.post("/api/papers/search")
def oa(s: Search):
    try: return openalex.search(s.query)
    except Exception: raise HTTPException(502, "OpenAlex request failed.")

@router.post("/api/papers/{pid}/process")
def process(pid: str):
    m = _m(); p = m.PAPERS.get(pid)
    if not p or "text" not in p: raise HTTPException(404, "Upload a PDF first.")
    if not llm.configured(): raise HTTPException(503, "LLM_API_KEY is not set; extraction needs an LLM.")
    items = llm.extract_claims(p["text"])
    for i in items:
        m.CLAIMS.append({"id": f"{pid}-{len(m.CLAIMS)}", "paper": pid, "text": i["text"], "excerpt": i["excerpt"], "page": None, "kind": i["kind"]})
        m.EDGES.append((pid, m.CLAIMS[-1]["id"], "HAS_LIMITATION" if i["kind"] == "limitation" else "REPORTS_FINDING"))
    p["status"] = "processed" if items else "no_verified_claims"
    return {"status": p["status"], "claims_saved": len(items)}

class Hyp(BaseModel): gap_title: str = Field(min_length=3, max_length=300)

@router.post("/api/hypotheses/generate")
def hypothesis(h: Hyp):
    gap = next((g for g in _m().gaps() if g["title"] == h.gap_title), None)
    if not gap: raise HTTPException(404, "Unknown gap.")
    return {"status": "PROPOSED, not tested; no experimental results exist.",
     "research_question": f"Can the limitation '{gap['title']}' be reduced?",
     "hypothesis": f"A method that mitigates '{gap['title']}' will outperform the baselines on a task sensitive to it.",
     "null_hypothesis": "There is no difference versus baselines.",
     "independent_variables": ["memory strategy"], "dependent_variables": ["task accuracy"],
     "baselines": [{"name": "systems from papers: " + ", ".join(gap["papers"]), "label": "source-supported"}],
     "datasets": [{"name": "to be chosen by researcher", "label": "AI-proposed"}],
     "ablations": ["remove each component"], "confounders": ["benchmark size", "model choice"],
     "reproducibility": ["fix seeds", "publish prompts", "log versions"], "evidence": gap["evidence"], "note": gap["note"]}

def _report_md():
    m = _m(); L = ["# NexusMind research report", "", "> Generated from the indexed corpus. Demo records are synthetic.", "", "## Papers analyzed"]
    L += [f"- {p['title']} ({p.get('year','n/a')}){' [demo]' if p.get('demo') else ''}" for p in m.PAPERS.values()]
    L += ["", "## Main findings"] + [f"- {c['text']} ({m.PAPERS[c['paper']]['title']}, p.{c['page']})" for c in m.CLAIMS if c["kind"] == "finding"]
    L += ["", "## Contradictions"] + [f"- {m.CONTRA[k]['a']} vs {m.CONTRA[k]['b']}: {m.CONTRA[k]['status']}. {m.CONTRA[k]['note']}" for k in m.CONTRA]
    L += ["", "## Repeated limitations / candidate gaps"] + [f"- {g['title']} ({len(g['papers'])} papers)" for g in m.gaps()]
    L += ["", "## Limitations of this analysis", "Keyword retrieval only unless an LLM is configured. Gaps are candidates within this corpus; novelty needs human review."]
    return "\n".join(L)

@router.post("/api/reports/generate")
def report():
    md = _report_md(); HISTORY.append({"id": len(HISTORY) + 1, "markdown": md}); return HISTORY[-1]

@router.get("/api/reports")
def reports(): return HISTORY

@router.get("/api/reports/{rid}/export")
def export(rid: int, format: str = "md"):
    r = next((x for x in HISTORY if x["id"] == rid), None)
    if not r: raise HTTPException(404, "Unknown report.")
    if format == "md": return Response(r["markdown"], media_type="text/markdown")
    if format != "pdf": raise HTTPException(422, "format must be md or pdf")
    import fitz
    doc = fitz.open(); text = r["markdown"]
    for i in range(0, len(text), 3000):
        pg = doc.new_page(); pg.insert_textbox(fitz.Rect(50, 50, 545, 790), text[i:i + 3000], fontsize=10)
    return Response(doc.tobytes(), media_type="application/pdf")
