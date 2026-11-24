from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", LoginView.as_view(template_name="staging_auth/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("api/workspaces/<slug:slug>/schema/", views.schema_view),
    path("api/workspaces/<slug:slug>/tables/<slug:table>/", views.record_view),
    path("api/workspaces/<slug:slug>/export/", views.export_view),
    path("api/workspaces/<slug:slug>/members/", views.members_view),
]
