from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView
from core import views
from core.views import (
    AttendanceViewSet,
    RegisterView,
    CookieLoginView,
    LogoutView,
    UserDetailView,
    erripuka_view,
    # Course views
    CreateCourseView,
    CourseListView,
    CourseDetailView,
    # Session views
    CreateSessionView,
    EndSessionView,
    MarkAttendanceView,
    SessionListView,
    SessionDetailView,
    ActiveSessionsView,
    # ML views
    linear_regression_prediction,
    random_forest_classification,
    kmeans_clustering,
    ml_models_info,
)


router = routers.DefaultRouter()
router.register(r'attendance', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Authentication Routes ---
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/login/', CookieLoginView.as_view(), name='cookie_login'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/user/', UserDetailView.as_view(), name='user-detail'),

    # --- Course Routes ---
    path('api/courses/create/', CreateCourseView.as_view(), name='create-course'),
    path('api/courses/', CourseListView.as_view(), name='course-list'),
    path('api/courses/<str:course_id>/', CourseDetailView.as_view(), name='course-detail'),

    # --- Session Routes ---
    path('api/sessions/create/', CreateSessionView.as_view(), name='create-session'),
    path('api/sessions/', SessionListView.as_view(), name='session-list'),
    path('api/sessions/active/', ActiveSessionsView.as_view(), name='active-sessions'),
    path('api/sessions/<int:session_id>/', SessionDetailView.as_view(), name='session-detail'),
    path('api/sessions/<int:session_id>/end/', EndSessionView.as_view(), name='end-session'),

    # --- Student Attendance Route ---
    path('api/attendance/mark/', MarkAttendanceView.as_view(), name='mark-attendance'),

    # --- Attendance API (legacy) ---
    path('api/', include(router.urls)),
    path('api/erripuka/', erripuka_view, name='erripuka'),

    #-- Next API ---
        # ML Models endpoints
    path('api/ml/linear-regression/', views.linear_regression_prediction, name='ml-linear-regression'),
    path('api/ml/random-forest/', views.random_forest_classification, name='ml-random-forest'),
    path('api/ml/kmeans/', views.kmeans_clustering, name='ml-kmeans'),
    path('api/ml/info/', views.ml_models_info, name='ml-models-info'),
]