from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/img/logo.png", permanent=True)),
    path("admin/", admin.site.urls),
    path("", include("agent.urls")),
]
