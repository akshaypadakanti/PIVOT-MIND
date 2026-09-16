from django.contrib import admin

from .models import PivotMindAnalysis


@admin.register(PivotMindAnalysis)
class PivotMindAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset_name", "health_score", "health_rating", "row_count", "column_count", "created_at")
    list_filter = ("health_rating", "autopilot_mode")
    search_fields = ("title", "dataset_name", "user_query", "executive_summary")
    readonly_fields = ("created_at",)
