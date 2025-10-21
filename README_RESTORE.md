# GraphRAG Project (Restored from Dump)
Some files were restored from code blocks; others are placeholders.

## Quick Start
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -c "from graph_rag.schema_catalog import generate_schema_allow_list; generate_schema_allow_list()"
uvicorn main:app --reload --port 8000
