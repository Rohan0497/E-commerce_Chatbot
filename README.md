# 💬 E-commerce Chatbot · GenAI RAG with Llama 3.3 + Groq

An intelligent e-commerce assistant that understands customer intent, answers FAQs,  
and runs live product queries against your store database.  
It uses a semantic router to classify queries, a RAG-style FAQ flow,  
and an LLM-to-SQL flow for product search.  

Built with Llama 3.3 via Groq, Streamlit, ChromaDB, SQLite, and Hugging Face embeddings.

> Currently supports two intents: `faq` (policies, general info) and `sql` (product listings).  
> Ships with a sample SQLite database and scraping utilities.

---

##  Features

-  **Semantic intent routing** → routes user messages to `faq` or `sql`
-  **FAQ (RAG)** → retrieves top FAQ entries from **ChromaDB** and answers strictly from that context
-  **LLM-to-SQL** → generates safe `SELECT` queries tagged with `<SQL>…</SQL>` and verbalizes tabular results
-  **Real-time data** → grounded in your **SQLite** product database
-  **Streamlit UI** → minimal chat interface to interact end-to-end
-  **Extensible** → add more routes (orders, returns) or switch databases easily

---

Folder structure
```
E-commerce_Chatbot/
├─ app/                          # Main chatbot package
│  ├─ config.py                  # Env + constants
│  ├─ router.py                  # Semantic router setup
│  ├─ faq.py                     # FAQ RAG flow
│  ├─ sql.py                     # SQL generation & answer
│  ├─ smalltalk.py               # Small-talk handler
│  └─ resources/
│     └─ faq_data.csv
│
├─ tests/                        # Unit tests (pytest)
├─ Scripts/                # Scripts / notebooks for product data
├─ db.sqlite                     # Sample SQLite product DB
├─ requirements.txt
├─ README.md
└─ LICENSE
```
---

This chatbot currently supports two intents:

- **faq**: Triggered when users ask questions related to the platform's policies or general information. eg. Is online payment available?
- **sql**: Activated when users request product listings or information based on real-time database queries. eg. Show me all nike shoes below Rs. 3000.


![product screenshot](app/resources/product-ss.png)

---

## Architecture

**Flow overview**

1. **Streamlit UI** captures user query  
2. **Semantic Router** (Hugging Face encoder) decides intent → `faq` or `sql`
3. **FAQ path** → retrieve top-k context from ChromaDB → Groq LLM answers *only* from context  
4. **SQL path** → Groq LLM emits `<SQL>…</SQL>` → extract → run `SELECT` on SQLite → Groq LLM summarizes results  
5. **Response** is rendered back to the chat UI

![architecture diagram of the e-commerce chatbot](app/resources/architecture-diagram.png)

## Agentic Runtime Overview
The Streamlit UI now delegates commerce questions to a lightweight agent loop:

- Tools live in app/tools/ (FAQ, SQL, memory, web) and expose a shared ToolSpec signature.
- Agent (app/agent.py) plans, executes one tool per step, records a trace, and retries SQL once when results are empty.
- Session memory persists simple preferences (brand, price ceiling) via app/tools/memory.py.
- When semantic_router is unavailable, app/router.py falls back to a keyword router so tests keep passing locally.

Each agent answer ends with a Trace: ... line; see tests/test_agent.py for concrete expectations.

```mermaid
flowchart LR
    user([User Query]) --> ui[Streamlit Chat UI]
    ui --> router{Intent Router}
    router -->|Small talk| smalltalk[talk() helper]
    router -->|Commerce| agent[Agent Loop]

    subgraph Agent Loop
        agent --> plan[Plan + Memory Hints]
        plan --> act{Select Tool}
        act -->|FAQ| faq_tools[faq_search / faq_answer]
        act -->|Products| sql_tools[sql_generate / sql_run / verbalize]
        act -->|Web| web_tool[web_search (stub)]
        act --> memory_tools[memory_get / memory_set]
    end

    faq_tools --> chroma[(Chroma FAQ Store)]
    sql_tools --> db[(SQLite Product DB)]
    sql_tools -->|Results| agent
    memory_tools --> agent
    agent --> response[Final Answer + Trace]
    smalltalk --> response
    chroma --> agent

    response --> ui
```

### Set-up & Execution

1. Run the following command to install all dependencies. 

    ```bash
    pip install -r requirements.txt
    ```

1. Inside app folder, create a .env file with your GROQ credentials as follows:
    ```text
    GROQ_MODEL=<Add the model name, e.g. llama-3.3-70b-versatile>
    GROQ_API_KEY=<Add your groq api key here>
    ```

1. Launch Streamlit from the project root (recommended):

    ```bash
    python -m streamlit run app/main.py
    ```

    The app also inserts the repository root into `sys.path`, so `streamlit run app/main.py` continues to work if you prefer that command.

---

##  How It Works

### 🔹 Router
Uses a sentence-transformer encoder (`all-MiniLM-L6-v2`) to embed and route each query.

### 🔹 FAQ Flow
- Ingest your FAQ CSV → create a ChromaDB collection  
- For a new query, retrieve top-K relevant FAQs  
- Concatenate answers into a context window  
- Ask the Groq LLM to generate an answer only from that context

### 🔹 SQL Flow
- Groq LLM produces a safe SQL query wrapped in `<SQL></SQL>`  
- Only executes **SELECT** queries against the SQLite database  
- The resulting dataframe is converted to natural-language output by another Groq call

---
##  Testing

Run all tests:
```bash
pytest -q
```

- Unit tests cover routing, FAQ pipeline, SQL pipeline, and small-talk handler  
- Tests use mocked Groq clients and temporary SQLite DBs

---

##  Data & Scraping

- `db.sqlite` → sample product table  
  Columns: `product_link`, `title`, `brand`, `price`, `discount`, `avg_rating`, `total_ratings`  
- `web-scrapping/` → optional scripts or notebooks for collecting product data

---

## Tech Stack

- LLM: Llama 3.3 via Groq API  
- UI: Streamlit  
- Routing: semantic-router + Hugging Face encoder  
- Vector DB: ChromaDB  
- SQL DB: SQLite  
- Language: Python 3.10+

---

## Safety & Constraints

- Guardrail: only **SELECT** statements are executed against the database  
- FAQ answers are limited to retrieved context; if unknown → “I don’t know”

---

## Roadmap

- Add order status and returns intents  
- Introduce user sessions / chat memory  
- Migrate SQLite → PostgreSQL  
- Add evaluation harness for LLM→SQL accuracy  
- Integrate vector product search (ChromaDB)  
- Deploy demo (Streamlit Cloud)
<!-- - Dockerfile + GitHub Actions CI/CD   -->

---

## Credits

  
Inspired by community implementations and tutorials (Codebasics series)

---

## License

Apache 2.0 — see LICENSE.


---

##  Appendix — FAQ CSV Format

- question,answer
- What is your return policy?,You can return any item within 30 days of delivery if it's in original condition.
- Do you offer Cash on Delivery?,Yes, COD is available at checkout in select locations.
