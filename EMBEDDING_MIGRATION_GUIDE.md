# Embedding Migration Guide: OpenAI → Gemini

## Summary

The migration from OpenAI to Google Gemini changes the embedding dimensions:
- **OpenAI text-embedding-3-small**: 1536 dimensions
- **Gemini text-embedding-004**: 768 dimensions

## Impact

The codebase **automatically handles dimension changes** through dynamic detection in `graph_rag/schema_embeddings.py` (line 227):
