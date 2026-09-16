from django.urls import path

from . import views

urlpatterns = [
    # PivotMind Workspace Routes
    path("", views.pivotmind_dashboard, name="pivotmind_dashboard"),
    path("upload/", views.pivotmind_upload, name="pivotmind_upload"),
    path("analysis/<int:pk>/", views.pivotmind_detail, name="pivotmind_detail"),
    path("analysis/<int:pk>/chat/", views.pivotmind_chat, name="pivotmind_chat"),
]
