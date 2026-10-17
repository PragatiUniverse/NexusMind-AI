"""NexusMind AI on Streamlit. Reuses the backend modules directly (no separate API server needed)."""
import hashlib, os, sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "backend"))
try:  # Streamlit secrets -> env vars (LLM_API_KEY, NEO4J_URI, ...)
    for k, v in st.secrets.items():
        if isinstance(v, str): os.environ.setdefault(k, v)
except Exception:
    pass
from app import main as m, extras, llm, openalex, graph_store  # noqa: E402

st.set_page_config(page_title="NexusMind AI", page_icon="🕸️", layout="wide")
st.sidebar.title("NexusMind AI")
page = st.sidebar.radio("Navigate", ["Overview", "Research Library", "Knowledge Graph", "Research Detective", "Contradiction Radar",
                                     "Research Gap Explorer", "Hypothesis Studio", "Reports", "Settings"], label_visibility="collapsed")
st.info("3 real arXiv papers. Claims are paraphrased from abstracts; excerpts are short verbatim abstract quotes; "
        "cross-paper links are AI-inferred and unverified.")
title = lambda pid: m.PAPERS[pid]["title"]

if page == "Overview":
    st.header("Find what connects your research")
    st.caption("Don't just read research. Discover what connects it, challenges it, and comes next.")
    a, b, c = st.columns(3)
    a.metric("Papers indexed", len(m.PAPERS)); b.metric("Claims extracted", len(m.CLAIMS)); c.metric("Graph relationships", len(m.EDGES))
    st.subheader("Candidate research gaps")
    for g in m.gaps(): st.markdown(f"**{g['title']}**  \n{g['note']}")

elif page == "Research Library":
    st.header("Research Library")
    for p in m.PAPERS.values():
        with st.expander(f"{p['title']} ({p.get('year', 'n/a')})"):
            st.write({k: v for k, v in p.items() if k not in ("text", "fp")})
            for cl in [c for c in m.CLAIMS if c["paper"] == p["id"]]:
                st.markdown(f"- {cl['text']}  \n  *p.{cl['page']}: \"{cl['excerpt']}\"*")
    st.subheader("Upload a PDF")
    f = st.file_uploader("PDF only", type=["pdf"])
    if f:
        data = f.getvalue()
        if len(data) > m.MAX: st.error("File too large.")
        elif not data.startswith(b"%PDF"): st.error("Not a valid PDF.")
        elif any(p.get("fp") == hashlib.sha256(data).hexdigest() for p in m.PAPERS.values()): st.warning("Duplicate paper.")
        else:
            import fitz
            doc = fitz.open(stream=data, filetype="pdf"); text = "".join(pg.get_text() for pg in doc).strip()
            if len(text) < 200: st.error("No extractable text (likely scanned). OCR is not supported.")
            else:
                pid = hashlib.sha256(data).hexdigest()[:8]
                m.PAPERS[pid] = {"id": pid, "title": f.name, "fp": hashlib.sha256(data).hexdigest(), "text": text,
                                 "pages": len(doc), "status": "text_extracted", "demo": False}
                st.success(f"Text extracted ({len(doc)} pages). Not analyzed until processed.")
                if llm.configured() and st.button("Extract claims with LLM"):
                    st.write(extras.process(pid))
                elif not llm.configured(): st.caption("Set LLM_API_KEY in secrets to enable claim extraction.")
    st.subheader("Search OpenAlex")
    q = st.text_input("Search scholarly metadata")
    if q:
        try:
            for r in openalex.search(q): st.markdown(f"**{r['title']}** ({r['year']})  \n{', '.join(r['authors'])}  \n{r['doi'] or ''}")
        except Exception: st.error("OpenAlex request failed.")

elif page == "Knowledge Graph":
    st.header("Knowledge Graph")
    col = {"p": "#2dd4bf", "f": "#a78bfa"}
    dot = ["digraph{bgcolor=transparent;rankdir=LR;node[style=filled,fontcolor=black,fontsize=10,shape=box]"]
    for p in m.PAPERS.values(): dot.append(f'"{p["id"]}"[label="{p["title"][:30]}",fillcolor="{col["p"]}"]')
    for c in m.CLAIMS: dot.append(f'"{c["id"]}"[label="{c["text"][:40]}…",fillcolor="{col["f"]}"]')
    for s_, t_, r in m.EDGES: dot.append(f'"{s_}"->"{t_}"[label="{r}",fontsize=8,fontcolor=white,color="{"#f87171" if r == "CONTRADICTS" else "#8b95b8"}"{",style=dashed" if r == "CONTRADICTS" else ""}]')
    st.graphviz_chart("\n".join(dot) + "}")
    cid = st.selectbox("Inspect a claim", [c["id"] for c in m.CLAIMS], format_func=lambda i: next(c["text"][:60] for c in m.CLAIMS if c["id"] == i))
    c = next(c for c in m.CLAIMS if c["id"] == cid)
    st.write(f"Source: {title(c['paper'])}, p.{c['page']}"); st.write(f"Excerpt: \"{c['excerpt']}\"")

elif page == "Research Detective":
    st.header("Research Detective")
    q = st.text_input("Ask a question", placeholder="How do language models use long context, and what extends it?")
    if q:
        try: r = m.ask(m.Ask(question=q))
        except Exception: st.error("Question must be 5 to 1000 characters.")
        else:
            st.write(r["answer"])
            for c in r["citations"]: st.markdown(f"- **{title(c['paper'])}**, p.{c['page']}: \"{c['excerpt']}\"")
            for x in r.get("conflicts", []): st.warning(f"Possible conflict flagged ({x['status']}): {x['note']}")

elif page == "Contradiction Radar":
    st.header("Contradiction Radar")
    for x in m.CONTRA.values():
        a, b = (next(c for c in m.CLAIMS if c["id"] == x[k]) for k in ("a", "b"))
        st.markdown(f"**A:** {a['text']}  \n*{title(a['paper'])}, p.{a['page']}: \"{a['excerpt']}\"*")
        st.markdown(f"**B:** {b['text']}  \n*{title(b['paper'])}, p.{b['page']}: \"{b['excerpt']}\"*")
        st.caption(x["note"])
        s = st.radio("Review status", ["confirmed", "unresolved", "not_a_contradiction"], index=["confirmed", "unresolved", "not_a_contradiction"].index(x["status"]), key=x["id"], horizontal=True)
        if s != x["status"]: m.review(x["id"], m.Review(status=s)); st.rerun()

elif page == "Research Gap Explorer":
    st.header("Research Gap Explorer")
    for g in m.gaps():
        st.subheader(g["title"]); st.write(g["note"])
        st.write("Papers: " + "; ".join(title(p) for p in g["papers"]))
        for e in g["evidence"]: st.markdown(f"- \"{e}\"")

elif page == "Hypothesis Studio":
    st.header("Hypothesis Studio")
    gap = st.selectbox("Candidate gap", [g["title"] for g in m.gaps()])
    if st.button("Draft hypothesis"):
        h = extras.hypothesis(extras.Hyp(gap_title=gap))
        st.warning(h["status"])
        st.markdown(f"**Research question:** {h['research_question']}  \n**Hypothesis:** {h['hypothesis']}  \n**Null:** {h['null_hypothesis']}")
        st.json({k: h[k] for k in ("independent_variables", "dependent_variables", "baselines", "datasets", "ablations", "confounders", "reproducibility")})

elif page == "Reports":
    st.header("Reports")
    if st.button("Generate report"): st.session_state["md"] = extras.report()["markdown"]
    if "md" in st.session_state:
        md = st.session_state["md"]; st.markdown(md)
        st.download_button("Download Markdown", md, "report.md", "text/markdown")
        import fitz
        doc = fitz.open()
        for i in range(0, len(md), 3000): doc.new_page().insert_textbox(fitz.Rect(50, 50, 545, 790), md[i:i + 3000], fontsize=10)
        st.download_button("Download PDF", doc.tobytes(), "report.pdf", "application/pdf")

else:
    st.header("Settings")
    st.write({"LLM configured": llm.configured(), "Neo4j configured": bool(os.getenv("NEO4J_URI"))})
    if os.getenv("NEO4J_URI") and st.button("Sync to Neo4j"):
        try: d = graph_store.driver(); graph_store.setup(d); graph_store.sync(d, list(m.PAPERS.values()), m.CLAIMS, m.EDGES); st.success("Synced.")
        except graph_store.GraphUnavailable as e: st.error(str(e))
    st.caption("State is held in server memory and shared by all visitors; it resets on restart. No authentication.")
