"""
Remote Lover – AI‑Enhanced Job Board (v5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Fast loading – no AI work on initial load
• AI matching only when you click "Match Jobs"
• Clean descriptions (HTML stripped)
• Filter: Exclude US‑only jobs
• Sort by AI Match, Score, Date
• Dark mode, responsive cards, export, archive
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import sqlite3
from pathlib import Path
import subprocess
import sys
import os
import re
import html
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ─── Constants ───
DB_PATH = Path("data/jobs.db")
PAGE_SIZE = 12

# ─── Clean HTML (also used in app) ───
def clean_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ─── Database ───
def get_db_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_jobs():
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("""
            SELECT id, title, company, location, url, source,
                   score, status, type, posted_at, saved,
                   salary_min, salary_max, salary_text, content, seen_at
            FROM jobs
            ORDER BY score DESC
        """, conn)
    except Exception as e:
        print(f"Query error: {e}")
        df = pd.DataFrame()
    conn.close()
    if df.empty:
        return df
    df['status'] = df['status'].fillna('new').replace('', 'new')
    df['type'] = df['type'].fillna('job')
    df['score'] = df['score'].fillna(0).astype(int)
    df['seen_at'] = df['seen_at'].fillna(datetime.now().isoformat())
    df['salary_display'] = df.apply(
        lambda r: f"${r['salary_min']:,.0f}" if r['salary_min'] and r['salary_min'] == r['salary_max'] else
                  f"${r['salary_min']:,.0f}-${r['salary_max']:,.0f}" if r['salary_min'] and r['salary_max'] else
                  r['salary_text'] or "",
        axis=1
    )
    # Clean the content if it was not cleaned in the scraper
    df['content'] = df['content'].apply(lambda x: clean_html(x) if x else "")
    df['summary'] = df['content'].apply(lambda x: (x[:180] + '...') if len(x) > 180 else x)
    return df

# ─── AI Match Engine ───
class MatchEngine:
    def __init__(self):
        self.vectorizer = None
        self.job_vectors = None
        self.df = None
        self.is_fitted = False

    def fit(self, df):
        if df.empty:
            self.is_fitted = False
            return
        texts = df['content'].fillna('').tolist()
        enhanced = [f"{row['title']} {row['company']} {row['content']}".strip() for _, row in df.iterrows()]
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=5000, min_df=2)
        self.job_vectors = self.vectorizer.fit_transform(enhanced)
        self.df = df
        self.is_fitted = True

    def match_resume(self, resume_text: str, top_n: int = 100) -> pd.DataFrame:
        if not self.is_fitted or not resume_text:
            return pd.DataFrame()
        resume_vec = self.vectorizer.transform([resume_text])
        similarities = cosine_similarity(resume_vec, self.job_vectors).flatten()
        result_df = self.df.copy()
        result_df['match_score'] = (similarities * 100).round(2)
        result_df = result_df[result_df['match_score'] > 0]
        return result_df[['id', 'match_score']].sort_values('match_score', ascending=False).head(top_n)

match_engine = MatchEngine()

# ─── App ───
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
app.title = "Remote Lover"

# ─── Job Card ───
def job_card(job):
    score = job.get('score', 0)
    score_color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#f44336"
    match = job.get('match_score', None)
    match_badge = ""
    if match is not None and match > 60:
        match_badge = html.Span(f"🤖 {match:.0f}% match", className="badge bg-info ms-2")
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Span(job.get('company', 'Unknown'), className="text-muted small text-uppercase fw-bold"),
                html.Span(job.get('type', 'job').upper(), className="badge bg-success ms-2"),
                match_badge,
            ], className="d-flex justify-content-between align-items-start"),
            html.H5(
                html.A(job.get('title', 'Untitled'), href=job.get('url', '#'), target="_blank", className="text-dark text-decoration-none"),
                className="mt-2"
            ),
            html.P(job.get('summary', ''), className="text-muted small", style={"flex": "1"}),
            html.Div([
                html.Span(f"📍 {job.get('location', 'Remote')}", className="me-2"),
                html.Span(f"💰 {job.get('salary_display', 'N/A')}", className="me-2"),
                html.Span(f"📡 {job.get('source', '')}", className="me-2"),
            ], className="text-muted small d-flex flex-wrap gap-2"),
            html.Hr(),
            html.Div([
                html.Span(f"⭐ {score}", style={"color": score_color, "fontWeight": "bold"}),
                html.A("Apply →", href=job.get('url', '#'), target="_blank", className="btn btn-success btn-sm ms-auto"),
            ], className="d-flex justify-content-between align-items-center mt-2"),
        ], className="d-flex flex-column", style={"height": "100%"})
    ], className="h-100 shadow-sm")

# ─── Sidebar ───
filters_sidebar = html.Div([
    html.H5("🔍 Filters", className="mb-3"),
    html.Label("Status"),
    dcc.Dropdown(
        id="status-filter",
        options=[
            {"label": "New", "value": "new"},
            {"label": "Viewed", "value": "viewed"},
            {"label": "Applied", "value": "applied"},
            {"label": "Interview", "value": "interview"},
            {"label": "Offer", "value": "offer"},
            {"label": "Rejected", "value": "rejected"},
        ],
        value=["new", "viewed", "applied"],
        multi=True,
        className="mb-3"
    ),
    html.Label("Min Score"),
    dcc.Slider(
        id="score-slider",
        min=0, max=100, value=0, step=5,
        marks={0: "0", 25: "25", 50: "50", 75: "75", 100: "100"},
        className="mb-3"
    ),
    html.Label("Type"),
    dcc.Dropdown(
        id="type-filter",
        options=[{"label": "Job", "value": "job"}, {"label": "Task", "value": "task"}],
        value=["job", "task"],
        multi=True,
        className="mb-3"
    ),
    html.Label("Date Range"),
    dcc.Dropdown(
        id="date-filter",
        options=[
            {"label": "All", "value": "All"},
            {"label": "7 days", "value": "7"},
            {"label": "30 days", "value": "30"},
            {"label": "90 days", "value": "90"},
        ],
        value="All",
        className="mb-3"
    ),
    html.Label("Search"),
    dbc.Input(id="search-input", type="text", placeholder="Search jobs...", className="mb-3"),
    html.Label("Sort by"),
    dcc.Dropdown(
        id="sort-filter",
        options=[
            {"label": "Highest Score", "value": "score"},
            {"label": "Most Recent", "value": "seen_at"},
            {"label": "Easiest First", "value": "easiest"},
            {"label": "AI Match", "value": "match"},
        ],
        value="score",
        className="mb-3"
    ),
    html.Hr(),
    html.Label("Location Filter"),
    dcc.Dropdown(
        id="location-filter",
        options=[
            {"label": "All", "value": "all"},
            {"label": "Remote (anywhere)", "value": "remote"},
            {"label": "Exclude US‑only", "value": "exclude_us"},
        ],
        value="all",
        className="mb-3"
    ),
    html.Hr(),
    html.Label("📄 Paste your resume for AI matching:"),
    dbc.Textarea(id="resume-text", placeholder="Paste your skills, experience, keywords...", className="mb-2", rows=3),
    dbc.Button("🔍 Match Jobs", id="match-btn", color="info", className="w-100 mb-2", size="sm"),
    html.Div(id="match-status", className="text-center small text-muted"),
    html.Hr(),
    dbc.Button("🔄 Refresh Jobs", id="refresh-btn", color="primary", className="w-100 mb-2"),
    dbc.Button("📥 Export CSV", id="export-btn", color="secondary", className="w-100 mb-2"),
    dbc.Button("📦 Archive Old Jobs", id="archive-btn", color="warning", className="w-100"),
    dcc.Download(id="download-csv"),
    html.Div(id="refresh-status", className="text-center mt-2 small text-muted"),
    html.Div(id="archive-status", className="text-center mt-1 small text-muted"),
], style={"padding": "20px"})

# ─── Modals ─── (AI Blog, Archived) same as before ───
ai_blog_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("📝 AI Job Market Blog")),
    dbc.ModalBody(id="ai-blog-content", children="Click 'Generate Blog' to see insights."),
    dbc.ModalFooter([
        dbc.Button("Generate Blog", id="generate-blog-btn", color="primary", className="me-2"),
        dbc.Button("Close", id="close-ai-blog", className="ms-auto", color="secondary"),
    ])
], id="ai-blog-modal", size="lg", is_open=False)

archived_modal = dbc.Modal([
    dbc.ModalHeader(dbc.ModalTitle("📦 Archived Jobs")),
    dbc.ModalBody(id="archived-jobs-body"),
    dbc.ModalFooter([
        dbc.Button("Close", id="close-archived", className="ms-auto", color="secondary"),
    ])
], id="archived-modal", size="lg", is_open=False)

# ─── Layout ───
app.layout = dbc.Container([
    dcc.Store(id="full-data-store", data=[]),
    dcc.Store(id="filtered-data-store", data=[]),
    dcc.Store(id="match-scores-store", data={}),
    dcc.Interval(id="scraper-poll-interval", interval=1000, disabled=True),

    # Header
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div("❤️", className="bg-primary text-white rounded p-2 me-2", style={"fontSize": "1.5rem"}),
                html.H1("Remote Lover", className="h3 mb-0", style={"color": "#1a1a2e"}),
                html.Span("🌍", className="ms-2 text-muted"),
                html.Span("No geo‑restrictions", className="text-muted ms-2 d-none d-sm-inline"),
            ], className="d-flex align-items-center"),
        ], width="auto"),
        dbc.Col([
            html.Div([
                html.Span(id="total-jobs-badge", className="me-3"),
                html.Span(id="new-jobs-badge", className="me-3"),
                html.Span(id="avg-score-badge", className="me-3"),
                dbc.Button("🌙", id="dark-mode-toggle", color="light", size="sm", className="ms-2"),
            ], className="d-flex align-items-center justify-content-end flex-wrap"),
        ], width="auto", className="ms-auto"),
    ], className="bg-white p-3 rounded-3 shadow-sm mb-4 d-flex align-items-center justify-content-between flex-wrap"),

    # Main content
    dbc.Row([
        dbc.Col(filters_sidebar, xs=12, md=3, lg=2),
        dbc.Col([
            dcc.Loading(
                id="loading-jobs",
                type="default",
                children=[
                    html.Div(id="job-cards-container"),
                    html.Div([
                        html.Div(id="pagination-info", className="text-muted me-3"),
                        dbc.Pagination(
                            id="pagination-component",
                            active_page=1,
                            max_value=1,
                            size="sm",
                            className="d-inline-flex"
                        ),
                    ], className="d-flex align-items-center justify-content-center flex-wrap"),
                ]
            )
        ], xs=12, md=9, lg=10),
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Button("📝 AI Job Market Blog", id="open-ai-blog", color="info", className="me-2"),
            dbc.Button("📦 Show Archived Jobs", id="open-archived", color="secondary"),
        ], className="text-center mt-4"),
    ]),

    ai_blog_modal,
    archived_modal,

    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P(f"❤️ Remote Lover · Updated: {datetime.now().strftime('%H:%M:%S')}", className="text-center text-muted small")
        ])
    ]),

], fluid=True, className="bg-light min-vh-100", id="main-container")

# ─── Callbacks ───

# 1. Initial load
@app.callback(
    Output("full-data-store", "data"),
    Output("total-jobs-badge", "children"),
    Output("new-jobs-badge", "children"),
    Output("avg-score-badge", "children"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=False,
)
def load_initial_data(_):
    df = load_jobs()
    if df.empty:
        return [], "📊 0 jobs", "🆕 0 new", "⭐ 0.0 avg"
    global match_engine
    match_engine.fit(df)
    records = df.to_dict('records')
    total = len(df)
    new_count = len(df[df['status'] == 'new'])
    avg_score = df['score'].mean()
    return records, f"📊 {total} jobs", f"🆕 {new_count} new", f"⭐ {avg_score:.1f} avg"

# 2. Filter data with location filter
@app.callback(
    Output("filtered-data-store", "data"),
    Output("pagination-component", "max_value"),
    Output("pagination-component", "active_page"),
    Output("pagination-info", "children"),
    Input("full-data-store", "data"),
    Input("status-filter", "value"),
    Input("score-slider", "value"),
    Input("type-filter", "value"),
    Input("date-filter", "value"),
    Input("search-input", "value"),
    Input("sort-filter", "value"),
    Input("location-filter", "value"),
    Input("match-scores-store", "data"),
    State("pagination-component", "active_page"),
    prevent_initial_call=True,
)
def update_filtered_data(full_data_json, status, min_score, job_type, date_range, search, sort_by, location_filter, match_scores_json, current_page):
    if not full_data_json:
        return [], 1, 1, "No jobs found"
    df = pd.DataFrame(full_data_json)
    match_df = None
    if match_scores_json:
        match_df = pd.DataFrame(list(match_scores_json.items()), columns=['id', 'match_score'])

    # Apply location filter
    if location_filter == "exclude_us":
        # remove jobs with location containing "US" or "United States" (case insensitive)
        df = df[~df['location'].str.contains(r'\bUS\b|\bUnited States\b', case=False, na=False)]
    elif location_filter == "remote":
        df = df[df['location'].str.contains(r'remote|anywhere|global', case=False, na=False)]

    filtered = filter_dataframe(df, status, min_score, job_type, date_range, search, sort_by, match_df)
    total = len(filtered)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total > 0 else 1
    current_page = min(current_page, total_pages) if current_page else 1
    filtered_records = filtered.to_dict('records') if not filtered.empty else []
    start = (current_page - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    info = f"Showing {start+1}–{end} of {total} jobs" if total > 0 else "No jobs match your filters"
    return filtered_records, total_pages, current_page, info

def filter_dataframe(df, status, min_score, job_type, date_range, search, sort_by, match_scores=None):
    if df.empty:
        return df
    filtered = df.copy()
    if match_scores is not None:
        filtered = filtered.merge(match_scores, on='id', how='left')
        filtered['match_score'] = filtered['match_score'].fillna(0)
    else:
        filtered['match_score'] = 0

    if status:
        filtered = filtered[filtered['status'].isin(status)]
    if min_score:
        filtered = filtered[filtered['score'] >= min_score]
    if job_type:
        filtered = filtered[filtered['type'].isin(job_type)]
    if date_range != "All":
        days = int(date_range)
        cutoff = datetime.now() - timedelta(days=days)
        filtered = filtered[pd.to_datetime(filtered['seen_at'], errors='coerce') >= cutoff]
    if search:
        search_lower = search.lower()
        filtered = filtered[
            filtered['title'].str.lower().str.contains(search_lower, na=False) |
            filtered['company'].str.lower().str.contains(search_lower, na=False)
        ]
    if sort_by == "score":
        filtered = filtered.sort_values('score', ascending=False)
    elif sort_by == "seen_at":
        filtered = filtered.sort_values('seen_at', ascending=False)
    elif sort_by == "easiest":
        filtered = filtered.sort_values(['type', 'score'], ascending=[True, False])
    elif sort_by == "match" and 'match_score' in filtered.columns:
        filtered = filtered.sort_values('match_score', ascending=False)
    return filtered

# 3. Render cards
@app.callback(
    Output("job-cards-container", "children"),
    Input("filtered-data-store", "data"),
    Input("pagination-component", "active_page"),
)
def render_cards(filtered_json, page):
    if not filtered_json:
        return html.Div("No jobs found. Run the scraper.", className="text-center text-muted")
    df = pd.DataFrame(filtered_json)
    total = len(df)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    page_df = df.iloc[start:end]
    if page_df.empty:
        return html.Div("No jobs on this page.", className="text-center text-muted")
    cards = []
    for _, job in page_df.iterrows():
        cards.append(dbc.Col(job_card(job), xs=12, sm=6, lg=4, className="mb-4"))
    return html.Div(cards, className="row")

# 4. AI Match
@app.callback(
    Output("match-scores-store", "data"),
    Output("match-status", "children"),
    Input("match-btn", "n_clicks"),
    State("resume-text", "value"),
    State("full-data-store", "data"),
    prevent_initial_call=True,
)
def compute_match(n_clicks, resume_text, full_data_json):
    if not n_clicks or not resume_text or not full_data_json:
        return {}, "Paste your resume and click Match."
    df = pd.DataFrame(full_data_json)
    if df.empty:
        return {}, "No jobs to match."
    global match_engine
    if not match_engine.is_fitted:
        match_engine.fit(df)
    match_df = match_engine.match_resume(resume_text, top_n=len(df))
    if match_df.empty:
        return {}, "No matches found (try different keywords)."
    scores_dict = match_df.set_index('id')['match_score'].to_dict()
    return scores_dict, f"✅ {len(match_df)} jobs matched (scores shown as 🤖)"

# ─── Refresh, Archive, Export, Dark mode, Blog, Archived modals ───
# (same as previous, just re-use them; I'll include the critical ones)

# Refresh button (non‑blocking)
scraper_process = None
scraper_running = False

@app.callback(
    Output("refresh-status", "children"),
    Output("scraper-poll-interval", "disabled"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def start_scraper(n_clicks):
    global scraper_process, scraper_running
    if scraper_running:
        return "⏳ Already running...", True
    try:
        scraper_process = subprocess.Popen(
            [sys.executable, "run.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        scraper_running = True
        return "⏳ Scraping in progress...", False
    except Exception as e:
        return f"❌ Error: {e}", True

@app.callback(
    Output("refresh-status", "children", allow_duplicate=True),
    Output("scraper-poll-interval", "disabled", allow_duplicate=True),
    Output("full-data-store", "data", allow_duplicate=True),
    Output("total-jobs-badge", "children", allow_duplicate=True),
    Output("new-jobs-badge", "children", allow_duplicate=True),
    Output("avg-score-badge", "children", allow_duplicate=True),
    Input("scraper-poll-interval", "n_intervals"),
    prevent_initial_call=True,
)
def poll_scraper(n):
    global scraper_process, scraper_running
    if not scraper_running or scraper_process is None:
        return "✅ Idle", True, no_update, no_update, no_update, no_update
    retcode = scraper_process.poll()
    if retcode is None:
        return no_update, False, no_update, no_update, no_update, no_update
    scraper_running = False
    stdout, stderr = scraper_process.communicate()
    if retcode != 0:
        return f"❌ Failed: {stderr}", True, no_update, no_update, no_update, no_update
    df = load_jobs()
    if df.empty:
        return "⚠️ No jobs found", True, [], "📊 0 jobs", "🆕 0 new", "⭐ 0.0 avg"
    global match_engine
    match_engine.fit(df)
    records = df.to_dict('records')
    total = len(df)
    new_count = len(df[df['status'] == 'new'])
    avg_score = df['score'].mean()
    return "✅ Refreshed!", True, records, f"📊 {total} jobs", f"🆕 {new_count} new", f"⭐ {avg_score:.1f} avg"

# Archive
@app.callback(
    Output("archive-status", "children"),
    Input("archive-btn", "n_clicks"),
    prevent_initial_call=True,
)
def archive_old_jobs(n_clicks):
    if not n_clicks:
        return ""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        c.execute("""
            INSERT INTO jobs_archive (id, hash, title, company, location, url, source, posted_at, score, type, salary_text)
            SELECT id, hash, title, company, location, url, source, posted_at, score, type, salary_text
            FROM jobs WHERE seen_at < ?
        """, (cutoff,))
        moved = c.rowcount
        c.execute("DELETE FROM jobs WHERE seen_at < ?", (cutoff,))
        conn.commit()
        conn.close()
        if moved:
            df = load_jobs()
            if not df.empty:
                global match_engine
                match_engine.fit(df)
            return f"✅ Archived {moved} jobs (older than 90 days)."
        return "ℹ️ No jobs to archive."
    except Exception as e:
        return f"❌ Archive error: {e}"

# Export
@app.callback(
    Output("download-csv", "data"),
    Input("export-btn", "n_clicks"),
    State("full-data-store", "data"),
    prevent_initial_call=True,
)
def export_csv(n_clicks, full_data):
    if not n_clicks or not full_data:
        return no_update
    df = pd.DataFrame(full_data)
    if df.empty:
        return no_update
    return dict(
        content=df.to_csv(index=False),
        filename=f"remote_jobs_{datetime.now().strftime('%Y%m%d')}.csv"
    )

# Dark mode, Blog, Archived modals – same as before (include them)
@app.callback(
    Output("main-container", "className"),
    Input("dark-mode-toggle", "n_clicks"),
    State("main-container", "className"),
)
def toggle_dark(n, current_class):
    if n is None:
        return current_class or "bg-light min-vh-100"
    if "bg-dark" in current_class:
        return current_class.replace("bg-dark", "bg-light").replace("text-white", "")
    else:
        return current_class + " bg-dark text-white"

@app.callback(
    Output("ai-blog-modal", "is_open"),
    Input("open-ai-blog", "n_clicks"),
    Input("close-ai-blog", "n_clicks"),
    State("ai-blog-modal", "is_open"),
)
def toggle_ai_blog(open_clicks, close_clicks, is_open):
    if open_clicks or close_clicks:
        return not is_open
    return is_open

@app.callback(
    Output("ai-blog-content", "children"),
    Input("generate-blog-btn", "n_clicks"),
    State("full-data-store", "data"),
    prevent_initial_call=True,
)
def generate_blog(n, full_data):
    if not n or not full_data:
        return "Click 'Generate Blog' to see insights."
    df = pd.DataFrame(full_data)
    if df.empty:
        return "No data to generate insights."
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ GEMINI_API_KEY not set."
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        top_companies = df['company'].value_counts().head(5).to_dict()
        top_roles = df['title'].value_counts().head(5).to_dict()
        avg_score = df['score'].mean()
        total = len(df)
        prompt = f"Write a short blog (200-300 words) about remote job market trends based on: total jobs {total}, average score {avg_score:.1f}, top companies {top_companies}, top roles {top_roles}. Use markdown."
        response = model.generate_content(prompt)
        return dcc.Markdown(response.text)
    except Exception as e:
        return f"⚠️ AI blog unavailable: {e}"

@app.callback(
    Output("archived-modal", "is_open"),
    Input("open-archived", "n_clicks"),
    Input("close-archived", "n_clicks"),
    State("archived-modal", "is_open"),
)
def toggle_archived(open_clicks, close_clicks, is_open):
    if open_clicks or close_clicks:
        return not is_open
    return is_open

@app.callback(
    Output("archived-jobs-body", "children"),
    Input("open-archived", "n_clicks"),
    prevent_initial_call=True,
)
def load_archived(n):
    if not n:
        return html.Div("No archived jobs.")
    try:
        conn = get_db_connection()
        archived_df = pd.read_sql_query("""
            SELECT title, company, location, posted_at, archived_at
            FROM jobs_archive
            ORDER BY archived_at DESC
            LIMIT 100
        """, conn)
        conn.close()
        if archived_df.empty:
            return html.Div("No archived jobs yet.")
        return dbc.Table.from_dataframe(archived_df, striped=True, bordered=True, hover=True, size="sm")
    except Exception:
        return html.Div("Error loading archived jobs.")

# ─── Run ───
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
