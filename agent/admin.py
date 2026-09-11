from django.contrib import admin

from .models import AgentExecution, Challenge, ChallengeAttempt, ToolExecution


@admin.register(AgentExecution)
class AgentExecutionAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "tool_call_count", "execution_time", "created_at")
    list_filter = ("status",)
    search_fields = ("user_query", "final_response")
    readonly_fields = ("created_at",)


@admin.register(ToolExecution)
class ToolExecutionAdmin(admin.ModelAdmin):
    list_display = ("id", "agent_execution", "tool_name", "status", "execution_time", "created_at")
    list_filter = ("status", "tool_name")
    search_fields = ("tool_name", "result_summary")


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "difficulty", "points")
    list_filter = ("difficulty",)
    search_fields = ("title", "description")


@admin.register(ChallengeAttempt)
class ChallengeAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "challenge", "score", "success", "created_at")
    list_filter = ("success",)
    search_fields = ("submitted_query", "feedback")
