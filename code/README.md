# Support Triage Agent — Code Documentation

## Architecture Overview

This is a **multi-agent triage pipeline** that processes support tickets across three ecosystems (HackerRank, Claude, Visa) using a combination of rule-based agents and LLM-powered reasoning.

### Pipeline Flow

```
Ticket Input
    │
    ├─→ DomainRouterAgent      → Identifies company (HackerRank/Claude/Visa)
    ├─→ IntentAgent            → Classifies request type (product_issue/bug/feature_request/invalid)
    ├─→ PromptInjectionAgent   → Detects malicious instructions
    ├─→ RiskAgent              → Assesses risk level and flags (fraud, billing, security, etc.)
    ├─→ MultiRequestAgent      → Splits tickets with multiple sub-requests
    ├─→ RetrievalAgent (TF-IDF) → Retrieves relevant corpus documents
    │       │
    │       └─→ Domain-scoped filtering (only docs from the right ecosystem)
    │
    └─→ LLM Triage (Groq/Llama 3.3 70B)
            │
            ├─→ Generates grounded response from corpus evidence
            ├─→ Decides reply vs. escalate with chain-of-thought reasoning
            ├─→ Classifies product area and request type
            │
            └─→ Verification Agent (LLM)
                    └─→ Checks response is grounded in corpus (no hallucinations)
```

### Key Design Decisions

1. **LLM + Rule-Based Hybrid**: Rule-based agents handle deterministic tasks (domain routing, risk detection, prompt injection), while the LLM handles nuanced decisions (reply vs. escalate, response generation).

2. **Domain-Scoped Retrieval**: Retrieved corpus documents are filtered by the ticket's domain to prevent cross-domain contamination (e.g., a Claude ticket pulling HackerRank docs).

3. **Grounding Verification**: A second LLM pass verifies that responses are faithful to the corpus evidence, preventing hallucinated policies or fabricated steps.

4. **Graceful Fallback**: If the LLM is unavailable, the agent falls back to rule-based response generation from corpus matches.

5. **Dual API Key Rotation**: Supports two Groq API keys with automatic rotation on rate limits for uninterrupted processing.

## Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point — orchestrates the full pipeline |
| `agent.py` | Rule-based agents (DomainRouter, Intent, Risk, PromptInjection, MultiRequest, Escalation, Decision) |
| `llm_agent.py` | LLM-powered triage agent with Groq/Llama integration, response verification |
| `retriever.py` | TF-IDF corpus retrieval with domain-aware chunking |
| `corpus_analyzer.py` | Corpus coverage analysis and reporting |
| `eval.py` | Sample evaluation (accuracy metrics against sample_support_tickets.csv) |
| `sample_calibration.py` | Detailed calibration analysis with failure categorization |
| `validate.py` | Output validation (schema, constraints, hallucination checks) |
| `requirements.txt` | Python dependencies |

## Setup & Run

### Prerequisites

- Python 3.10+
- A Groq API key (free at https://console.groq.com/keys)

### Installation

```bash
cd code
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` in the repo root and add your API key:

```bash
cp ../.env.example ../.env
# Edit .env and set GROQ_API_KEY=gsk_your_key_here
```

### Running

```bash
# Full LLM-powered pipeline (recommended)
python main.py

# With judge validation mode (runs sample eval first)
python main.py --judge-mode

# Rule-based only (no API calls)
python main.py --no-llm

# Run sample evaluation standalone
python eval.py

# Run validation on output
python validate.py
```

### Outputs

- `support_tickets/output.csv` — Agent predictions for all tickets
- `log.txt` — Detailed execution log with reasoning traces
- `audit_trace.csv` — Machine-readable audit trail
- `corpus_report.txt` — Corpus coverage analysis
- `sample_eval_report.txt` — Sample evaluation metrics (judge mode)

## Agent Capabilities

### What It Handles Well
- FAQ-style questions with corpus answers → replies with grounded instructions
- Multi-request tickets → splits and processes each sub-request
- Prompt injection → detects and escalates
- High-risk tickets (fraud, security, account compromise) → escalates with routing
- Out-of-scope/spam tickets → replies with "invalid" classification
- Cross-domain inference when company field is "None"

### Escalation Logic
The agent escalates when:
- Issue requires human-only actions (refunds, score adjustments, account recovery)
- Corpus has no relevant evidence
- Security/fraud/legal risk detected
- Prompt injection detected
- Issue is too vague for safe automated response

### Safety Features
- Responses are grounded exclusively in the provided corpus
- LLM verification pass checks for hallucinated claims
- Prompt injection detection with 10+ malicious patterns
- Risk assessment with 11 flag types and weighted penalties
- No external web calls for ground-truth answers
