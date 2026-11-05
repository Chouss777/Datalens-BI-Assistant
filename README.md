# 🔍 DataLens - Intelligent BI & NL2SQL Assistant

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black)

DataLens is a premium, AI-powered Business Intelligence assistant that allows business users to query their ERP/CRM databases using natural language (French or Arabic). It translates questions into valid PostgreSQL queries, validates them for security, executes them, and generates interactive visualizations with plain-text explanations.

## ✨ Key Features

- **Multilingual NL2SQL:** Understands French and Arabic queries.
- **Self-Correction Loop:** If a generated SQL query fails, the agent automatically reads the database error, corrects the query, and retries (up to 2 times).
- **Enterprise Security:** 
  - Uses `sqlglot` to validate queries (blocks non-SELECT statements).
  - Blocks sensitive columns (e.g., salaries, emails).
  - Executes queries using a read-only PostgreSQL role.
- **Premium UI/UX:** A sleek, dark-mode Streamlit interface with glassmorphism, real-time latency metrics, and interactive Plotly charts.
- **100% Local & Private:** Powered by Ollama (`qwen2.5-coder`), ensuring enterprise data never leaves the local machine.

## 🏗️ Architecture

1. **User Input:** Natural language (FR/AR).
2. **Semantic Layer:** Enriches the prompt with business glossary and schema.
3. **LLM (Ollama):** Generates the SQL query.
4. **Validator (SQLGlot):** Sanitizes and enforces security rules.
5. **Executor:** Runs the query on PostgreSQL (Read-Only).
6. **Visualizer & Explainer:** Generates Plotly charts and a French summary.

## 🛠️ Tech Stack

- **Backend:** Python, Streamlit
- **AI/LLM:** Ollama (Qwen2.5-Coder), Langchain concepts (Few-shot prompting)
- **Database:** PostgreSQL
- **Security:** SQLGlot, psycopg2
- **DevOps:** Docker, Docker Compose

## 🚀 How to Run Locally

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/datalens-bi-assistant.git
