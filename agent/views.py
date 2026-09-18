from __future__ import annotations

import io
import json
import logging
import os
import time

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
import pandas as pd

from agent.db_utils import ensure_db_migrated
from agent.forms import PivotMindUploadForm
from agent.models import PivotMindAnalysis
from agent.pivotmind.chat_assistant import PivotMindChatAssistant
from agent.pivotmind.pipeline import PivotMindPipeline

logger = logging.getLogger(__name__)


def pivotmind_dashboard(request):
    ensure_db_migrated()
    try:
        analyses = list(PivotMindAnalysis.objects.all())
        total_count = len(analyses)
        avg_score = round(sum(a.health_score for a in analyses) / total_count, 1) if total_count > 0 else 0.0
        recent_analyses = analyses[:10]
    except Exception:
        recent_analyses = []
        total_count = 0
        avg_score = 0.0

    return render(
        request,
        "pivotmind/dashboard.html",
        {
            "analyses": recent_analyses,
            "total_analyses": total_count,
            "avg_score": avg_score,
            "page_title": "PivotMind Pipeline",
        },
    )


def parse_uploaded_dataset(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Robustly parses uploaded dataset bytes supporting:
    - Multi-sheet Excel files (automatically picks the primary data sheet)
    - Semicolon (;), Tab (\\t), Pipe (|), and Comma (,) separated CSVs
    - Multi-encoding fallback (utf-8, utf-8-sig, latin1, cp1252, iso-8859-1)
    - Auto-skipping leading title/metadata rows
    """
    fname_lower = filename.lower()
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252", "iso-8859-1"]

    if fname_lower.endswith((".xlsx", ".xls")):
        try:
            sheets_dict = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
            best_df = pd.DataFrame()
            max_cells = -1
            for sheet_name, sheet_df in sheets_dict.items():
                if sheet_df is not None and not sheet_df.empty:
                    cleaned = sheet_df.dropna(how="all").dropna(how="all", axis=1)
                    cells = cleaned.shape[0] * cleaned.shape[1]
                    if cells > max_cells:
                        max_cells = cells
                        best_df = cleaned
            if not best_df.empty:
                return best_df
        except Exception as exc:
            logger.warning("Multi-sheet excel parse fallback: %s", exc)

        try:
            return pd.read_excel(io.BytesIO(file_bytes))
        except Exception:
            pass

    # For CSV / TSV / Semicolon / Pipe separated files
    separators = [";", "\t", "|", ",", None]
    for sep in separators:
        for enc in encodings:
            try:
                kwargs = {"encoding": enc}
                if sep is None:
                    kwargs["sep"] = None
                    kwargs["engine"] = "python"
                else:
                    kwargs["sep"] = sep

                df = pd.read_csv(io.BytesIO(file_bytes), **kwargs)
                if df is not None and not df.empty and len(df.columns) > 1:
                    return df
            except Exception:
                pass

    # Retry skipping leading metadata lines if initial parse failed
    for skiprows in range(1, 6):
        for sep in separators:
            for enc in encodings:
                try:
                    kwargs = {"encoding": enc, "skiprows": skiprows}
                    if sep is None:
                        kwargs["sep"] = None
                        kwargs["engine"] = "python"
                    else:
                        kwargs["sep"] = sep

                    df = pd.read_csv(io.BytesIO(file_bytes), **kwargs)
                    if df is not None and not df.empty and len(df.columns) > 1:
                        return df
                except Exception:
                    pass

    # Last resort fallback: return any single-column or unparsed dataframe if non-empty
    for enc in encodings:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

    return pd.DataFrame()


@require_http_methods(["GET", "POST"])
def pivotmind_upload(request):
    ensure_db_migrated()
    if request.method == "POST":

        form = PivotMindUploadForm(request.POST, request.FILES)
        if form.is_valid():
            user_query = form.cleaned_data.get("user_query", "").strip()
            file_obj = request.FILES.get("dataset_file")
            demo_name = form.cleaned_data.get("demo_dataset")

            try:
                if file_obj:
                    filename = file_obj.name
                    file_bytes = file_obj.read()
                    file_obj.seek(0)

                    df = parse_uploaded_dataset(file_bytes, filename)

                    if df is None or df.empty:
                        messages.error(request, "The uploaded dataset appears to be empty or unparseable. Please check the file.")
                        return render(request, "pivotmind/upload.html", {"form": form, "page_title": "PivotMind Upload"})

                elif demo_name:
                    filename = demo_name
                    demo_path = os.path.join(settings.BASE_DIR, "agent", "pivotmind", "demo_data", demo_name)
                    df = pd.read_csv(demo_path)
                else:
                    messages.error(request, "Please provide a valid dataset.")
                    return render(request, "pivotmind/upload.html", {"form": form, "page_title": "PivotMind Upload"})



                # Execute 5-agent PivotMind pipeline
                pipeline = PivotMindPipeline(df=df, dataset_name=filename, user_query=user_query)
                result = pipeline.run()

                upload_dir = os.path.join(settings.BASE_DIR, "agent", "pivotmind", "user_uploads")
                os.makedirs(upload_dir, exist_ok=True)
                clean_fname = "".join(c for c in filename if c.isalnum() or c in (".", "_", "-")).rstrip()
                saved_filename = f"analysis_{int(time.time())}_{clean_fname}.csv"
                saved_file_path = os.path.join(upload_dir, saved_filename)
                try:
                    df.to_csv(saved_file_path, index=False)
                except Exception:
                    saved_file_path = ""

                # Persist to database
                analysis = PivotMindAnalysis.objects.create(
                    title=f"Analysis: {filename}",
                    dataset_name=filename,
                    user_query=user_query,
                    autopilot_mode=result["autopilot_mode"],
                    health_score=result["health_score"],
                    health_rating=result["rating"],
                    row_count=result["profile_data"]["shape"][0],
                    column_count=result["profile_data"]["shape"][1],
                    doctor_report=result["doctor_report"],
                    profile_summary=result["low_token_summary"],
                    hypotheses_report=result["hypotheses_report"],
                    top_hypothesis=result["top_hypothesis"],
                    viz_report=result["viz_report"],
                    all_visualizations=result.get("all_visualizations", []),
                    executive_summary=result["executive_summary"],
                    execution_time=result["execution_time_seconds"],
                    saved_file_path=saved_file_path,
                )

                messages.success(request, f"PivotMind pipeline executed successfully in {result['execution_time_seconds']}s.")
                return redirect("pivotmind_detail", pk=analysis.pk)

            except Exception as exc:
                logger.error("Pipeline execution failed: %s", str(exc), exc_info=True)
                messages.error(request, f"Pipeline execution failed: {str(exc)}")
                return render(request, "pivotmind/upload.html", {"form": form, "page_title": "PivotMind Upload"})
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PivotMindUploadForm()

    return render(
        request,
        "pivotmind/upload.html",
        {
            "form": form,
            "page_title": "PivotMind Upload & Autopilot",
        },
    )


def pivotmind_detail(request, pk: int):
    analysis = get_object_or_404(PivotMindAnalysis, pk=pk)
    return render(
        request,
        "pivotmind/detail.html",
        {
            "analysis": analysis,
            "page_title": f"PivotMind #{analysis.pk}: {analysis.dataset_name}",
        },
    )


@require_http_methods(["POST"])
def pivotmind_chat(request, pk: int):
    analysis = get_object_or_404(PivotMindAnalysis, pk=pk)
    question = request.POST.get("question", "").strip()

    if not question and request.body:
        try:
            body_data = json.loads(request.body.decode("utf-8"))
            question = body_data.get("question", "").strip()
        except Exception:
            pass

    if not question:
        return JsonResponse({"error": "Please enter a question."}, status=400)

    # Load dataset into dataframe with robust fallback priority
    filename = analysis.dataset_name
    demo_path = os.path.join(settings.BASE_DIR, "agent", "pivotmind", "demo_data", filename)
    saved_path = getattr(analysis, "saved_file_path", "") or ""

    df = pd.DataFrame()
    try:
        if saved_path and os.path.exists(saved_path):
            df = pd.read_csv(saved_path)
        elif os.path.exists(demo_path):
            df = pd.read_csv(demo_path)
        else:
            sample_rows = analysis.doctor_report.get("sample_rows", [])
            if sample_rows:
                df = pd.DataFrame(sample_rows)
    except Exception:
        df = pd.DataFrame()

    chat_bot = PivotMindChatAssistant(
        df=df,
        profile_summary=analysis.profile_summary,
        dataset_name=analysis.dataset_name,
    )
    res = chat_bot.ask(question)

    def format_agent_html(text: str) -> str:
        if not text:
            return ""
        import html
        escaped = html.escape(text)
        return f"<div class='agent-formatted-text'>{escaped.replace('\n', '<br>')}</div>"

    ans_text = res.get("answer", "")
    ans_html = format_agent_html(ans_text)
    chart_rep = res.get("chart_report") or {}

    return JsonResponse({
        "success": res.get("success", True),
        "answer": ans_text,
        "answer_html": ans_html,
        "chart_report": chart_rep,
        "viz_html": chart_rep.get("fig_html"),
        "fig_json": chart_rep.get("fig_json"),
    })
