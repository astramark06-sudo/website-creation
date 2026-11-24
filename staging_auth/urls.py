from django.contrib.auth.views import LogoutView
from .login_guard import LocalLoginView
from django.urls import path
from . import views, html_views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", LocalLoginView.as_view(template_name="staging_auth/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("assets/staging.css", html_views.stylesheet, name="staging-style"),
    path("workspaces/<slug:slug>/", html_views.workspace_page, name="workspace"),
    path("workspaces/<slug:slug>/tables/<slug:table>/", html_views.collection_page, name="collection"),
    path("workspaces/<slug:slug>/tables/<slug:table>/<int:item_id>/edit/", html_views.edit_page, name="edit-record"),
    path("workspaces/<slug:slug>/tables/<slug:table>/<int:item_id>/delete/", html_views.delete_page, name="delete-record"),
    path("workspaces/<slug:slug>/members/", html_views.members_page, name="members"),
    path("api/workspaces/<slug:slug>/schema/", views.schema_view),
    path("api/workspaces/<slug:slug>/tables/<slug:table>/", views.record_view),
    path("api/workspaces/<slug:slug>/export/", views.export_view),
    path("api/workspaces/<slug:slug>/members/", views.members_view),
]
