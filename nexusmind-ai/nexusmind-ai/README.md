# NexusMind AI
- `frontend/`: UI (static, no build). `backend/`: FastAPI API. `DEMO.md`: judging script.
Run both: `cp .env.example .env && docker compose up --build` then open http://localhost:5173 (API docs at :8000/docs).
Without Docker: see `backend/README.md` and `frontend/README.md`.
Implemented: PDF upload checks, keyword-grounded Q&A with citations, graph/contradiction/gap endpoints with review, Neo4j sync and path, OpenAlex search, LLM extraction (verbatim-excerpt validated), hypotheses, Markdown/PDF reports.
Verification: code compiles; tests, Neo4j, OpenAlex and LLM calls have NOT been run. Seed data: 3 real arXiv papers (MemGPT 2310.08560, Generative Agents 2304.03442, Lost in the Middle 2307.03172); claims paraphrased, excerpts short abstract quotes, cross-paper links AI-inferred.
Missing: React/TypeScript frontend, authentication, embeddings.

## Deploy on Streamlit Community Cloud
1. Push this folder to a GitHub repo (root must contain `streamlit_app.py` and `requirements.txt`).
2. On share.streamlit.io choose "New app", pick the repo, set main file `streamlit_app.py`.
3. Optional secrets (App settings > Secrets, TOML): `LLM_API_KEY = "..."`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
Local: `pip install -r requirements.txt && streamlit run streamlit_app.py`.
Streamlit runs the backend modules in-process, so no separate API server is needed. State is in memory, shared by visitors, and resets on restart.
