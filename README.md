# AgentLab

**Teach AI to Choose the Right Tool.**

AgentLab is an educational multi-tool AI agent built **only with Django**. Learners submit a question through an HTML form. Django sends that question to Google Gemini with a catalog of tools. The model selects a function, Django executes it, optionally chains more tools, stores a full activity timeline, and renders the result with Django templates.

There is no React, Vue, JavaScript, AJAX, or REST frontend. Every interaction is:

`HTML form → Django POST → agent loop → database → template`

## Features

- Gemini tool/function calling as the primary router (not a giant `if/elif` chain)
- Nine tools: calculator, web search, weather, unit converter, date/time, currency, text analyzer, JSON validator, Wikipedia knowledge search
- Multi-tool chaining with a maximum call limit
- Safe execution metadata (query, tool, arguments, status, summary, timing) — no hidden chain-of-thought
- Tool playground and agent playground
- 20 scored learning challenges
- Activity timelines, paginated history, API status, learning mode, developer console
- CSRF, form validation, output escaping, safe math (no `eval()`), API timeouts

## Architecture

```
User Query
    ↓
Django View / Form
    ↓
Gemini Agent + tool schemas
    ↓
Tool Selection (function calling)
    ↓
Tool Registry → Python tool
    ↓
Tool Result stored as ToolExecution
    ↓
Additional tool if the model requests it
    ↓
Final Answer stored as AgentExecution
    ↓
Django Template
```

### Function calling

Each tool publishes a JSON schema that Gemini uses as a function declaration. Django sends those declarations with the user query. When Gemini returns function calls, Django validates arguments, runs the Python function, and sends the tool result back. The loop stops when Gemini returns a normal text answer or the call limit is reached.

### Tool architecture

Tools live in `agent/tools/`. The registry in `agent/services/tool_registry.py` holds name, description, category, schema, and callable. Adding a tool means writing a module and appending it to `_TOOL_MODULES`.

### Multi-tool chaining

One user query can produce several tool calls — including the same tool twice (two cities) or a pipeline (weather → unit converter). `AGENT_MAX_TOOL_CALLS` (default 8) prevents infinite loops.

## Project structure

```
manage.py
requirements.txt
.env.example
config/                 Django project settings and URLs
agent/
  models.py
  views.py
  forms.py
  services/             agent loop, registry, challenge scoring, HTTP helper
  tools/                one module per tool
  management/commands/  seed_challenges
  tests/
templates/              Django templates only
static/css/style.css
```

## Available tools

| Tool | Type | Notes |
|---|---|---|
| `calculator` | Local | AST math, percentages, no `eval()` |
| `web_search` | SerpAPI | Titles, URLs, snippets, sources |
| `weather` | OpenWeatherMap | Temp, feels like, condition, humidity, wind |
| `unit_converter` | Local | km/miles, m/ft, kg/lb, C/F, L/gal |
| `get_datetime` | Local | Date, time, timezone, weekday, day counts |
| `currency_converter` | Live or demo | Demo rates are labelled and never pretended to be live |
| `analyze_text` | Local | Characters, words, sentences, paragraphs |
| `validate_json` | Local | Valid/invalid, pretty print, structure |
| `knowledge_search` | Wikipedia public API | Encyclopedic lookup |

## Installation

Python 3.10+ works; 3.11+ is recommended.

```bash
cd SITS_Project
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Environment variables

Copy the example file and add keys you have. Leave others blank.

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret (change in production) |
| `DJANGO_DEBUG` | `true` for local development |
| `GEMINI_API_KEY` | Required to run the agent |
| `GEMINI_MODEL` | Defaults to `gemini-3.6-flash` |
| `SERPAPI_API_KEY` | Web search |
| `OPENWEATHERMAP_API_KEY` | Weather |
| `CURRENCY_API_KEY` | Live FX via ExchangeRate-API; blank = demo mode |

Never commit `.env`. Keys are never shown in the UI — only Connected / Not Configured / Demo Mode.

### API setup

1. **Google Gemini** — create a key at [Google AI Studio](https://aistudio.google.com/apikey)
2. **SerpAPI** — serpapi.com for live search
3. **OpenWeatherMap** — openweathermap.org current weather API
4. **Currency** — optional ExchangeRate-API v6 key

If an external API is missing, AgentLab says it is not configured. It does not invent weather, search, or FX results. Local tools keep working.

## Database setup

SQLite is the default.

```bash
python manage.py migrate
python manage.py seed_challenges
```

Create a staff user only if you want Django admin:

```bash
python manage.py createsuperuser
```

## Running the server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Running tests

Tests mock Gemini and HTTP. They do not need real API keys.

```bash
python manage.py test
```

## How to add a new tool

1. Create `agent/tools/my_tool.py` with `NAME`, `DESCRIPTION`, `CATEGORY`, `SCHEMA`, and `execute()`
2. Register the module in `agent/services/tool_registry.py`
3. Try it in the Tool Playground
4. Add unit tests
5. Add a challenge in `seed_challenges` and run the command again

The in-app guide is at `/add-a-tool/`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Agent says Gemini is not configured | `GEMINI_API_KEY` in `.env`, then restart the server |
| Weather / search fail with “not configured” | Add the matching key; local tools are independent |
| Currency mentions DEMO MODE | Expected until `CURRENCY_API_KEY` is set |
| Invalid city / JSON / math | Friendly form and tool errors; no stack traces |
| Challenge score is low | Compare expected tools on the task card with the activity timeline |
| Pages look unstyled | Confirm `static/css/style.css` exists and `DEBUG` is true |

## Security notes

- CSRF on every POST form
- Django form validation and tool-argument validation
- Calculator uses `ast` only
- API calls use timeouts
- Templates escape output by default
- No shell, no `eval()`, no arbitrary Python execution
