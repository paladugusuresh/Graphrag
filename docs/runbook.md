# GraphRAG Operations Runbook

## Debugging & Troubleshooting

### Planner Mismatch Debugging

When the planner returns unexpected results, use the `trace_id` for debugging:

#### 1. Find the Trace ID

Every RAG response includes a `trace_id`:
