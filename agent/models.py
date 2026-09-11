from django.db import models


class AgentExecution(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    user_query = models.TextField()
    final_response = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    tool_call_count = models.PositiveIntegerField(default=0)
    execution_time = models.FloatField(default=0.0, help_text="Total seconds")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Execution #{self.pk}: {self.user_query[:60]}"

    @property
    def is_multi_tool(self) -> bool:
        return self.tool_call_count >= 2

    @property
    def tools_used(self):
        names = []
        for item in self.tool_executions.all():
            if item.tool_name not in names:
                names.append(item.tool_name)
        return names


class ToolExecution(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    agent_execution = models.ForeignKey(
        AgentExecution,
        on_delete=models.CASCADE,
        related_name="tool_executions",
    )
    tool_name = models.CharField(max_length=80)
    arguments = models.JSONField(default=dict, blank=True)
    result_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    execution_time = models.FloatField(default=0.0, help_text="Seconds")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.tool_name} ({self.status})"


class Challenge(models.Model):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    DIFFICULTY_CHOICES = [
        (BEGINNER, "Beginner"),
        (INTERMEDIATE, "Intermediate"),
        (ADVANCED, "Advanced"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES)
    expected_tools = models.JSONField(default=list, help_text="List of expected tool names")
    points = models.PositiveIntegerField(default=100)
    sample_query = models.CharField(max_length=400, blank=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.order}. {self.title}"


class ChallengeAttempt(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="attempts")
    submitted_query = models.TextField()
    selected_tools = models.JSONField(default=list)
    score = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False)
    feedback = models.TextField(blank=True)
    breakdown = models.JSONField(default=dict, blank=True)
    agent_execution = models.ForeignKey(
        AgentExecution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="challenge_attempts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Attempt on {self.challenge.title} ({self.score})"


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
