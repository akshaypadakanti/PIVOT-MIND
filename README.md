# PivotMind Analytics Workspace

**5-Agent Automated AI Data Analytics & Insights Engine**

PivotMind is an autonomous 5-agent data analytics workspace built with **Django**, **Google Gemini**, and **Plotly**. Users upload a CSV dataset or select a demo dataset, and PivotMind automatically audits data health, profiles statistical distributions, formulates hypotheses, generates interactive charts, and drafts an executive strategic summary.

---

## 🤖 5 Autonomous AI Agents

1. **DataDoctor Agent**: Audits data cleanliness, calculates a Health Score (0-100), and flags missing values, duplicate rows, and outlier anomalies.
2. **DatasetProfiler Agent**: Creates low-token schema summaries and statistical profiles for LLM consumption.
3. **HypothesisEngine Agent**: Formulates testable data hypotheses automatically (or based on custom user queries).
4. **Visualizer Agent**: Generates interactive Plotly visualizations for data insights.
5. **ExecutiveStrategist Agent**: Synthesizes key findings into a clear strategic business report.

---

## ⚡ Quick Start

### 1. Installation

```bash
# Clone the repository and navigate into the directory
git clone <repository-url>
cd PivotMind

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Setup

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Add your **Google Gemini API Key** in `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
```

### 3. Database & Local Server

```bash
python manage.py migrate
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 🚀 Deploy to Vercel

1. Push your code to GitHub.
2. Import the repository in [Vercel](https://vercel.com/new).
3. Set Build Command: `bash build.sh`
4. Add Environment Variable: `GEMINI_API_KEY`
5. Click **Deploy**!
