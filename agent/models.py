from django.db import models


class PivotMindAnalysis(models.Model):
    title = models.CharField(max_length=200, default="PivotMind Analysis")
    dataset_name = models.CharField(max_length=200, blank=True)
    user_query = models.TextField(blank=True)
    autopilot_mode = models.BooleanField(default=True)
    health_score = models.FloatField(default=0.0)
    health_rating = models.CharField(max_length=40, default="Fair")
    row_count = models.PositiveIntegerField(default=0)
    column_count = models.PositiveIntegerField(default=0)

    doctor_report = models.JSONField(default=dict, blank=True)
    profile_summary = models.TextField(blank=True)
    hypotheses_report = models.JSONField(default=dict, blank=True)
    top_hypothesis = models.JSONField(default=dict, blank=True)
    viz_report = models.JSONField(default=dict, blank=True)
    all_visualizations = models.JSONField(default=list, blank=True)
    executive_summary = models.TextField(blank=True)
    saved_file_path = models.CharField(max_length=500, blank=True)

    execution_time = models.FloatField(default=0.0, help_text="Total seconds")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PivotMind Analysis #{self.pk}: {self.dataset_name} ({self.health_score}/100)"
