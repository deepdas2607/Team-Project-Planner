from django.urls import path

from factwise.views import (
    BoardDetailView,
    BoardExportView,
    BoardListView,
    TaskStatusView,
    TaskView,
    TeamDetailView,
    TeamListView,
    TeamMembersView,
    TeamUsersListView,
    UserDetailView,
    UserListView,
    UserTeamsView,
)


urlpatterns = [
    # User endpoints: create/list/describe/update and list user's teams
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<str:id>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<str:id>/teams/', UserTeamsView.as_view(), name='user-teams'),
    # Team endpoints: create, update, manage members and list users
    path('teams/', TeamListView.as_view(), name='team-list'),
    path('teams/<str:id>/', TeamDetailView.as_view(), name='team-detail'),
    path('teams/<str:id>/members/', TeamMembersView.as_view(), name='team-members'),
    path('teams/<str:id>/users/', TeamUsersListView.as_view(), name='team-users'),
    # Board endpoints: create/list/close and export reports
    path('boards/', BoardListView.as_view(), name='board-list'),
    path('boards/<str:id>/', BoardDetailView.as_view(), name='board-detail'),
    path('boards/<str:id>/export/', BoardExportView.as_view(), name='board-export'),
    # Task endpoints: add tasks and update their status
    path('tasks/', TaskView.as_view(), name='task-list'),
    path('tasks/status/', TaskStatusView.as_view(), name='task-status'),
]