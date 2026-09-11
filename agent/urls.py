from django.urls import path

from . import views

urlpatterns = [
    # PivotMind Standalone Workspace Routes
    path("", views.pivotmind_dashboard, name="pivotmind_dashboard"),
    path("upload/", views.pivotmind_upload, name="pivotmind_upload"),
    path("analysis/<int:pk>/", views.pivotmind_detail, name="pivotmind_detail"),
    path("analysis/<int:pk>/chat/", views.pivotmind_chat, name="pivotmind_chat"),
    
    # Legacy AgentLab routes (retained for backward compatibility and test suite)
    path("agentlab/dashboard/", views.dashboard, name="dashboard"),
    path("tools/", views.tools_page, name="tools"),
    path("playground/", views.playground, name="playground"),
    path("playground/agent/", views.agent_playground, name="agent_playground"),
    path("tasks/", views.tasks, name="tasks"),
    path("tasks/<int:pk>/", views.challenge_detail, name="challenge_detail"),
    path("tasks/results/<int:pk>/", views.challenge_result, name="challenge_result"),
    path("activity/", views.activity, name="activity"),
    path("activity/<int:pk>/", views.activity_detail, name="activity_detail"),
    path("history/", views.history, name="history"),
    path("settings/", views.settings_page, name="settings"),
    path("learning/", views.learning, name="learning"),
    path("developer/", views.developer, name="developer"),
    path("add-a-tool/", views.add_tool_guide, name="add_tool"),
]
