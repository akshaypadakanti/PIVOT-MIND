"""Shared navigation context for templates."""


def navigation(request):
    return {
        "nav_items": [
            ("pivotmind_dashboard", "Workspace Dashboard"),
            ("pivotmind_upload", "New Analysis"),
        ]
    }

