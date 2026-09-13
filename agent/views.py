from __future__ import annotations

import json
import time

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from agent.forms import AgentQueryForm, ChallengeQueryForm, ToolPlaygroundForm
from agent.models import AgentExecution, Challenge, ChallengeAttempt, ToolExecution
from agent.services import agent_service, tool_registry
from agent.services.challenge_evaluator import evaluate_challenge

SAMPLE_PROMPTS = [
    "Calculate 25% of 480",
    "What's the weather in Hyderabad?",
    "Search for the latest AI news",
    "Convert 10 km to miles",
    "What time is it in Tokyo?",
    "Analyze this text: AgentLab teaches tool calling with Django.",
    "Convert 100 USD to INR",
    'Validate this JSON: {"ok": true, "count": 3}',
]


def _metrics():
    executions = AgentExecution.objects.all()
    total = executions.count()
    successful = executions.filter(status=AgentExecution.STATUS_SUCCESS).count()
    failed = executions.filter(status=AgentExecution.STATUS_FAILED).count()
    tool_calls = ToolExecution.objects.count()
    multi_tool = executions.filter(tool_call_count__gte=2).count()
    return {
        "total_executions": total,
        "successful": successful,
        "failed": failed,
        "tool_calls": tool_calls,
        "multi_tool_tasks": multi_tool,
    }


def _api_status():
    gemini_ok = bool(getattr(settings, "GEMINI_API_KEY", "") or "")
    serp_ok = bool(getattr(settings, "SERPAPI_API_KEY", "") or "")
    weather_ok = bool(getattr(settings, "OPENWEATHERMAP_API_KEY", "") or "")
    currency_ok = bool(getattr(settings, "CURRENCY_API_KEY", "") or "")
    return {
        "gemini": {"configured": gemini_ok, "label": "Connected" if gemini_ok else "Not Configured"},
        "serpapi": {"configured": serp_ok, "label": "Connected" if serp_ok else "Not Configured"},
        "openweather": {
            "configured": weather_ok,
            "label": "Connected" if weather_ok else "Not Configured",
        },
        "currency": {
            "configured": currency_ok,
            "label": "Connected" if currency_ok else "Demo Mode",
        },
    }


@require_http_methods(["GET", "POST"])
def dashboard(request):
    execution = None
    if request.method == "POST":
        form = AgentQueryForm(request.POST)
        if form.is_valid():
            execution = agent_service.run_agent(form.cleaned_data["query"])
            if execution.status == AgentExecution.STATUS_SUCCESS:
                messages.success(request, "The agent completed this request.")
            else:
                messages.error(request, execution.final_response or "The agent could not complete this request.")
            return redirect(f"/?run={execution.pk}#agent-response")
        messages.error(request, "Please enter a valid question.")
    else:
        initial = {}
        prefill = request.GET.get("q", "").strip()
        if prefill:
            initial["query"] = prefill
        form = AgentQueryForm(initial=initial)
        run_id = request.GET.get("run")
        if run_id:
            execution = (
                AgentExecution.objects.filter(pk=run_id)
                .prefetch_related("tool_executions")
                .first()
            )

    if not execution:
        form.fields["query"].widget.attrs["autofocus"] = True

    return render(
        request,
        "dashboard.html",
        {
            "form": form,
            "execution": execution,
            "metrics": _metrics(),
            "sample_prompts": SAMPLE_PROMPTS,
            "page_title": "Dashboard",
        },
    )


def tools_page(request):
    return render(
        request,
        "tools.html",
        {
            "tools": tool_registry.list_tools(),
            "page_title": "Tools",
        },
    )


@require_http_methods(["GET", "POST"])
def playground(request):
    choices = [(tool.name, f"{tool.name} — {tool.description[:60]}") for tool in tool_registry.list_tools()]
    result = None
    result_pretty = None
    selected_tool = None
    parsed_args = None
    elapsed = None

    if request.method == "POST":
        form = ToolPlaygroundForm(request.POST, tool_choices=choices)
        if form.is_valid():
            selected_tool = tool_registry.get_tool(form.cleaned_data["tool"])
            raw_input = form.cleaned_data["input_data"]
            try:
                parsed_args = tool_registry.parse_playground_input(selected_tool, raw_input)
                started = time.perf_counter()
                result = tool_registry.execute_tool(selected_tool.name, parsed_args)
                elapsed = round(time.perf_counter() - started, 4)
                result_pretty = json.dumps(result.get("data") or {}, indent=2, ensure_ascii=False, default=str)
                if result.get("success"):
                    messages.success(request, f"{selected_tool.name} finished successfully.")
                else:
                    messages.error(request, result.get("error") or "The tool could not complete this request.")
            except ValueError as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Please choose a tool and provide valid input.")
    else:
        initial = {}
        tool_name = request.GET.get("tool", "").strip()
        if tool_name:
            initial["tool"] = tool_name
        if request.GET.get("input"):
            initial["input_data"] = request.GET.get("input")
        form = ToolPlaygroundForm(initial=initial, tool_choices=choices)

    return render(
        request,
        "playground.html",
        {
            "form": form,
            "result": result,
            "result_pretty": result_pretty,
            "selected_tool": selected_tool,
            "parsed_args": parsed_args,
            "elapsed": elapsed,
            "page_title": "Tool Playground",
        },
    )


@require_http_methods(["GET", "POST"])
def agent_playground(request):
    execution = None
    if request.method == "POST":
        form = AgentQueryForm(request.POST)
        if form.is_valid():
            execution = agent_service.run_agent(form.cleaned_data["query"])
            if execution.status == AgentExecution.STATUS_SUCCESS:
                messages.success(request, "Agent playground run complete.")
            else:
                messages.error(request, execution.final_response or "The agent run failed.")
        else:
            messages.error(request, "Please enter a valid query.")
    else:
        form = AgentQueryForm(initial={"query": request.GET.get("q", "").strip()})

    if not execution:
        form.fields["query"].widget.attrs["autofocus"] = True

    return render(
        request,
        "agent_playground.html",
        {
            "form": form,
            "execution": execution,
            "page_title": "Agent Playground",
        },
    )


def tasks(request):
    challenges = Challenge.objects.all()
    grouped = {
        "beginner": challenges.filter(difficulty=Challenge.BEGINNER),
        "intermediate": challenges.filter(difficulty=Challenge.INTERMEDIATE),
        "advanced": challenges.filter(difficulty=Challenge.ADVANCED),
    }
    return render(
        request,
        "tasks.html",
        {
            "grouped": grouped,
            "page_title": "Learning Challenges",
        },
    )


@require_http_methods(["GET", "POST"])
def challenge_detail(request, pk: int):
    challenge = get_object_or_404(Challenge, pk=pk)
    if request.method == "POST":
        form = ChallengeQueryForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            execution = agent_service.run_agent(query)
            attempt = evaluate_challenge(challenge, execution, query)
            if attempt.success:
                messages.success(request, f"Challenge scored {attempt.score}/100.")
            else:
                messages.warning(request, f"Challenge scored {attempt.score}/100. Review the feedback and try again.")
            return redirect("challenge_result", pk=attempt.pk)
        messages.error(request, "Please submit a valid challenge query.")
    else:
        initial = {}
        if request.GET.get("use_sample") == "1" and challenge.sample_query:
            initial["query"] = challenge.sample_query
        form = ChallengeQueryForm(initial=initial)

    recent = challenge.attempts.all()[:5]
    return render(
        request,
        "challenge_detail.html",
        {
            "challenge": challenge,
            "form": form,
            "recent_attempts": recent,
            "page_title": challenge.title,
        },
    )


def challenge_result(request, pk: int):
    attempt = get_object_or_404(ChallengeAttempt.objects.select_related("challenge", "agent_execution"), pk=pk)
    return render(
        request,
        "challenge_result.html",
        {
            "attempt": attempt,
            "execution": attempt.agent_execution,
            "page_title": "Challenge Result",
        },
    )


def _get_unified_executions():
    try:
        executions = list(AgentExecution.objects.prefetch_related("tool_executions").all())
    except Exception:
        executions = []
    try:
        analyses = list(PivotMindAnalysis.objects.all())
    except Exception:
        analyses = []

    combined = []
    for item in executions:
        combined.append({
            "pk": item.pk,
            "pivotmind_pk": None,
            "user_query": item.user_query,
            "final_response": item.final_response,
            "status": item.status,
            "get_status_display": item.get_status_display(),
            "tools_used": item.tools_used,
            "tool_call_count": item.tool_call_count,
            "execution_time": item.execution_time,
            "created_at": item.created_at,
        })

    for item in analyses:
        q_text = f"5-Agent Analysis on {item.dataset_name}"
        if item.user_query:
            q_text += f" — {item.user_query}"
        
        tools = ["DataDoctor", "Profiler", "HypothesisEngine", "Visualizer", "Strategist"]
        combined.append({
            "pk": f"pm_{item.pk}",
            "pivotmind_pk": item.pk,
            "user_query": q_text,
            "final_response": item.executive_summary or f"Health Score: {item.health_score}/100 ({item.health_rating}). {item.top_hypothesis.get('title', '')}",
            "status": "success",
            "get_status_display": "Success",
            "tools_used": tools,
            "tool_call_count": len(tools),
            "execution_time": item.execution_time,
            "created_at": item.created_at,
        })

    combined.sort(key=lambda x: x["created_at"], reverse=True)
    return combined


def activity(request):
    combined = _get_unified_executions()
    paginator = Paginator(combined, getattr(settings, "HISTORY_PAGE_SIZE", 8))
    page = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "activity.html",
        {
            "page": page,
            "page_title": "Activity",
        },
    )


def activity_detail(request, pk):
    pk_str = str(pk)
    if pk_str.startswith("pm_"):
        try:
            pm_id = int(pk_str.replace("pm_", ""))
            return redirect("pivotmind_detail", pk=pm_id)
        except ValueError:
            pass
    execution = get_object_or_404(AgentExecution.objects.prefetch_related("tool_executions"), pk=pk)
    return render(
        request,
        "activity_detail.html",
        {
            "execution": execution,
            "page_title": f"Execution #{execution.pk}",
        },
    )


def history(request):
    combined = _get_unified_executions()
    paginator = Paginator(combined, getattr(settings, "HISTORY_PAGE_SIZE", 8))
    page = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "history.html",
        {
            "page": page,
            "page_title": "History",
        },
    )


def settings_page(request):
    return render(
        request,
        "settings.html",
        {
            "page_title": "Display & Interface Settings",
        },
    )


def learning(request):
    return render(request, "learning.html", {"page_title": "Learning Mode"})


def developer(request):
    tools = tool_registry.list_tools()
    usage = {
        row["tool_name"]: row["total"]
        for row in ToolExecution.objects.values("tool_name").annotate(total=Count("id"))
    }
    failed = {
        row["tool_name"]: row["total"]
        for row in ToolExecution.objects.filter(status=ToolExecution.STATUS_FAILED)
        .values("tool_name")
        .annotate(total=Count("id"))
    }
    tool_rows = []
    for tool in tools:
        tool_rows.append(
            {
                "tool": tool,
                "schema_pretty": json.dumps(tool.gemini_declaration(), indent=2),
                "usage": usage.get(tool.name, 0),
                "failed": failed.get(tool.name, 0),
            }
        )

    challenge_stats = {
        "total": Challenge.objects.count(),
        "attempts": ChallengeAttempt.objects.count(),
        "passed": ChallengeAttempt.objects.filter(success=True).count(),
        "average_score": 0,
    }
    scores = list(ChallengeAttempt.objects.values_list("score", flat=True))
    if scores:
        challenge_stats["average_score"] = round(sum(scores) / len(scores), 1)

    return render(
        request,
        "developer.html",
        {
            "tool_rows": tool_rows,
            "api_status": _api_status(),
            "challenge_stats": challenge_stats,
            "failed_executions": AgentExecution.objects.filter(status=AgentExecution.STATUS_FAILED).count(),
            "page_title": "Developer Console",
        },
    )


def add_tool_guide(request):
    return render(request, "add_tool.html", {"page_title": "Add a Tool"})


# --- PivotMind Views ---
from agent.forms import PivotMindUploadForm
from agent.models import PivotMindAnalysis
from agent.pivotmind.pipeline import PivotMindPipeline
import os
import pandas as pd


def pivotmind_dashboard(request):
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


@require_http_methods(["GET", "POST"])
def pivotmind_upload(request):
    if request.method == "POST":
        form = PivotMindUploadForm(request.POST, request.FILES)
        if form.is_valid():
            user_query = form.cleaned_data.get("user_query", "").strip()
            file_obj = request.FILES.get("dataset_file")
            demo_name = form.cleaned_data.get("demo_dataset")

            try:
                if file_obj:
                    filename = file_obj.name
                    if filename.endswith(".csv"):
                        df = pd.read_csv(file_obj)
                    elif filename.endswith((".xlsx", ".xls")):
                        df = pd.read_excel(file_obj)
                    else:
                        messages.error(request, "Unsupported file format. Please upload a CSV or Excel file.")
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

                # Sync to AgentExecution table for activity & history tracking
                try:
                    agent_exec = AgentExecution.objects.create(
                        user_query=f"5-Agent Analysis on {filename}" + (f": {user_query}" if user_query else ""),
                        final_response=result["executive_summary"],
                        status=AgentExecution.STATUS_SUCCESS,
                        tool_call_count=5,
                        execution_time=result["execution_time_seconds"],
                    )
                    tools_meta = [
                        ("DataDoctor", {"dataset": filename}, f"Health Score: {result['health_score']}/100 ({result['rating']})"),
                        ("DatasetProfiler", {"rows": result["profile_data"]["shape"][0], "cols": result["profile_data"]["shape"][1]}, "Low-token Schema & Stat Profile"),
                        ("HypothesisEngine", {"user_query": user_query}, result["top_hypothesis"].get("title", "Autopilot Hypotheses")),
                        ("Visualizer", {"target": result["top_hypothesis"].get("target_visualization", "bar_chart")}, result["viz_report"].get("status", "success")),
                        ("ExecutiveStrategist", {"domain": filename}, "Executive Strategic Synthesis"),
                    ]
                    for t_name, t_args, t_sum in tools_meta:
                        ToolExecution.objects.create(
                            agent_execution=agent_exec,
                            tool_name=t_name,
                            arguments=t_args,
                            result_summary=t_sum,
                            status=ToolExecution.STATUS_SUCCESS,
                            execution_time=round(result["execution_time_seconds"] / 5, 2),
                        )
                except Exception as sync_err:
                    logger.warning("Could not sync PivotMind run to AgentExecution: %s", sync_err)

                messages.success(request, f"PivotMind pipeline executed successfully in {result['execution_time_seconds']}s.")
                return redirect("pivotmind_detail", pk=analysis.pk)

            except Exception as exc:
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


from django.http import JsonResponse
from agent.pivotmind.chat_assistant import PivotMindChatAssistant


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

    from agent.templatetags.agent_extras import format_agent_html

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



