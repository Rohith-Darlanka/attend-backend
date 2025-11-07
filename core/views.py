from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import get_user_model
from django.utils import timezone
from .authentication import CookieJWTAuthentication

from .models import Attendance, Course, Session
from .serializers import (
    AttendanceSerializer,
    RegisterSerializer,
    UserSerializer,
    CourseSerializer,
    CreateCourseSerializer,
    SessionSerializer,
    CreateSessionSerializer,
    MarkAttendanceSerializer
)

User = get_user_model()

# ---------------- USER DETAIL -----------------
class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------- REGISTER -----------------
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


# ---------------- COOKIE LOGIN -----------------
class CookieLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response({"message": "Login successful"}, status=status.HTTP_200_OK)

        max_age = 7 * 24 * 60 * 60  # 7 days in seconds

        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=max_age,
            httponly=True,
            secure=True,  # True in production with HTTPS
            samesite="None",
            path="/",
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=max_age,
            httponly=True,
            secure=True,  # True in production with HTTPS
            samesite="None",
            path="/",
        )

        return response


# ---------------- LOGOUT -----------------
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # ✅ Don't authenticate on logout

    def post(self, request):
        try:
            response = Response(
                {"message": "Logged out successfully"},
                status=status.HTTP_200_OK
            )

            # ✅ IMPORTANT: delete_cookie() does NOT accept 'httponly' parameter!
            # Only accepts: key, path, domain, samesite, secure
            response.delete_cookie(
                key='access_token',
                path='/',
                samesite='None',
                secure=True,
            )
            
            response.delete_cookie(
                key='refresh_token',
                path='/',
                samesite='None',
                secure=True,
            )

            return response

        except Exception as e:
            # Log error for debugging in Render logs
            print(f"Logout error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return Response(
                {"error": f"Logout failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
# ---------------- ATTENDANCE -----------------
class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Attendance.objects.all()
        return Attendance.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ---------------- COURSE MANAGEMENT -----------------
class CreateCourseView(APIView):
    """
    POST /api/courses/create/
    Body: {
        "course_id": "CS101",
        "course_name": "Introduction to Computer Science",
        "student_roll_numbers": ["S001", "S002", "S003"]
    }
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        serializer = CreateCourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        
        # Create the course
        course = Course.objects.create(
            course_id=serializer.validated_data['course_id'],
            course_name=serializer.validated_data['course_name'],
            teacher_ids=[user.uid],
            teacher_names=[user.full_name or user.email],
            student_roll_numbers=serializer.validated_data['student_roll_numbers']
        )

        return Response(
            CourseSerializer(course).data,
            status=status.HTTP_201_CREATED
        )


class CourseListView(APIView):
    """
    GET /api/courses/
    Returns all courses created by the authenticated user (teacher)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        user = request.user
        courses = Course.objects.filter(teacher_ids__contains=[user.uid])
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CourseDetailView(APIView):
    """
    GET /api/courses/<course_id>/
    Returns details of a specific course
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, course_id):
        try:
            course = Course.objects.get(course_id=course_id)
            serializer = CourseSerializer(course)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )


# ---------------- SESSION MANAGEMENT -----------------
class CreateSessionView(APIView):
    """
    POST /api/sessions/create/
    Body: {
        "course_id": "CS101"
    }
    Creates a new session with attendance portal ON
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request):
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course_id = serializer.validated_data['course_id']
        user = request.user

        try:
            course = Course.objects.get(course_id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is a teacher of this course
        if user.uid not in course.teacher_ids:
            return Response(
                {"error": "You are not authorized to create sessions for this course"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Calculate absent roll numbers (all registered students initially)
        absent_roll_numbers = course.student_roll_numbers.copy()

        # Create session
        session = Session.objects.create(
            course=course,
            teacher=user,
            attendance_portal_status='ON',
            present_roll_numbers=[],
            absent_roll_numbers=absent_roll_numbers
        )

        return Response(
            SessionSerializer(session).data,
            status=status.HTTP_201_CREATED
        )


class EndSessionView(APIView):
    """
    POST /api/sessions/<session_id>/end/
    Ends a session and turns attendance portal OFF
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def post(self, request, session_id):
        try:
            session = Session.objects.get(session_id=session_id)
        except Session.DoesNotExist:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is the teacher who created this session
        if session.teacher.uid != request.user.uid:
            return Response(
                {"error": "You are not authorized to end this session"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if session is already ended
        if session.attendance_portal_status == 'OFF':
            return Response(
                {"error": "Session is already ended"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # End the session
        session.attendance_portal_status = 'OFF'
        session.session_ended = timezone.now()
        session.save()

        return Response(
            {
                "message": "Session ended successfully",
                "session": SessionSerializer(session).data
            },
            status=status.HTTP_200_OK
        )


class MarkAttendanceView(APIView):
    """
    POST /api/attendance/mark/
    Body: {
        "roll_number": "S001"
    }
    Student marks their attendance in active sessions
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = MarkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        roll_number = serializer.validated_data['roll_number']

        # Find all active sessions (attendance portal ON)
        active_sessions = Session.objects.filter(attendance_portal_status='ON')

        if not active_sessions.exists():
            return Response(
                {"error": "No active sessions available"},
                status=status.HTTP_404_NOT_FOUND
            )

        marked_sessions = []
        not_registered_courses = []

        for session in active_sessions:
            course = session.course
            
            # Check if roll number is registered in this course
            if roll_number not in course.student_roll_numbers:
                not_registered_courses.append({
                    "course_id": course.course_id,
                    "course_name": course.course_name,
                    "session_id": session.session_id
                })
                continue

            # Check if already marked present
            if roll_number in session.present_roll_numbers:
                marked_sessions.append({
                    "session_id": session.session_id,
                    "course_name": session.course_name,
                    "status": "already_marked",
                    "message": "Attendance already marked for this session"
                })
                continue

            # Mark attendance
            session.present_roll_numbers.append(roll_number)
            
            # Remove from absent list if present
            if roll_number in session.absent_roll_numbers:
                session.absent_roll_numbers.remove(roll_number)
            
            session.save()

            marked_sessions.append({
                "session_id": session.session_id,
                "course_name": session.course_name,
                "status": "success",
                "message": "Attendance marked successfully"
            })

        response_data = {
            "roll_number": roll_number,
            "marked_sessions": marked_sessions
        }

        if not_registered_courses:
            response_data["not_registered_in"] = not_registered_courses

        if not marked_sessions:
            return Response(
                {
                    "error": "Roll number not registered in any active sessions",
                    "not_registered_in": not_registered_courses
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(response_data, status=status.HTTP_200_OK)


class SessionListView(APIView):
    """
    GET /api/sessions/
    Returns all sessions created by the authenticated user (teacher)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        user = request.user
        sessions = Session.objects.filter(teacher=user)
        serializer = SessionSerializer(sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SessionDetailView(APIView):
    """
    GET /api/sessions/<session_id>/
    Returns details of a specific session
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request, session_id):
        try:
            session = Session.objects.get(session_id=session_id)
            serializer = SessionSerializer(session)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Session.DoesNotExist:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class ActiveSessionsView(APIView):
    """
    GET /api/sessions/active/
    Returns all sessions with attendance portal ON
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        active_sessions = Session.objects.filter(attendance_portal_status='ON')
        serializer = SessionSerializer(active_sessions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------- SIMPLE BACKEND TEST -----------------
@api_view(['GET'])
@permission_classes([AllowAny])
def erripuka_view(request):
    return Response({"message": "erripuka"})

# ============================================================
# ✅ MACHINE LEARNING FEATURES (NEWLY ADDED)
# ============================================================

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, accuracy_score, silhouette_score
from datetime import datetime
import json


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def linear_regression_prediction(request):
    """
    Linear Regression for Attendance Trend Analysis
    Predicts future attendance rates based on historical data
    """
    try:
        data = request.data
        sessions = data.get('sessions', [])
        
        if len(sessions) < 3:
            return Response({
                'error': 'Need at least 3 sessions for regression analysis'
            }, status=400)
        
        # Prepare data
        df = pd.DataFrame(sessions)
        df['date'] = pd.to_datetime(df['session_created'])
        df = df.sort_values('date')
        
        df['attendance_rate'] = (
            df['num_students_attended'] / 
            (df['num_students_attended'] + df['num_students_absent'])
        ) * 100
        
        X = np.arange(len(df)).reshape(-1, 1)
        y = df['attendance_rate'].values
        
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)
        
        r2 = r2_score(y, y_pred)
        
        future_X = np.arange(len(df), len(df) + 5).reshape(-1, 1)
        future_predictions = np.clip(model.predict(future_X), 0, 100)
        
        historical_data = []
        for i, row in df.iterrows():
            historical_data.append({
                'session_id': row['session_id'],
                'date': row['date'].strftime('%Y-%m-%d'),
                'actual': round(row['attendance_rate'], 2),
                'predicted': round(y_pred[list(df.index).index(i)], 2)
            })
        
        future_data = []
        for i, pred in enumerate(future_predictions):
            future_data.append({
                'session': f'Session {len(df) + i + 1}',
                'predicted': round(pred, 2),
                'confidence': round(max(60, 95 - (i * 7)), 2)
            })
        
        slope = model.coef_[0]
        trend = 'Improving' if slope > 0.5 else 'Declining' if slope < -0.5 else 'Stable'
        
        return Response({
            'model': 'Linear Regression',
            'algorithm': 'scikit-learn LinearRegression',
            'metrics': {
                'r2_score': round(r2, 4),
                'slope': round(slope, 4),
                'intercept': round(model.intercept_, 2),
                'equation': f'y = {slope:.4f}x + {model.intercept_:.2f}'
            },
            'trend': trend,
            'historical_data': historical_data,
            'future_predictions': future_data,
            'sessions_analyzed': len(df)
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def random_forest_classification(request):
    """
    Random Forest for Student Risk Classification
    Classifies students as Pass/Fail based on attendance patterns
    """
    try:
        data = request.data
        sessions = data.get('sessions', [])
        
        if len(sessions) < 2:
            return Response({'error': 'Need at least 2 sessions for classification'}, status=400)
        
        student_records = {}
        for session in sessions:
            for roll in session.get('present_roll_numbers', []):
                student_records.setdefault(roll, {'present': 0, 'absent': 0, 'sessions': []})
                student_records[roll]['present'] += 1
                student_records[roll]['sessions'].append(1)
            for roll in session.get('absent_roll_numbers', []):
                student_records.setdefault(roll, {'present': 0, 'absent': 0, 'sessions': []})
                student_records[roll]['absent'] += 1
                student_records[roll]['sessions'].append(0)
        
        if len(student_records) < 5:
            return Response({'error': 'Need at least 5 students for classification'}, status=400)
        
        features, labels, students = [], [], []
        for roll, record in student_records.items():
            total = record['present'] + record['absent']
            if total == 0:
                continue
            rate = (record['present'] / total) * 100
            
            consistency = 0
            if len(record['sessions']) > 1:
                consecutive = 0
                max_consecutive = 0
                for attended in record['sessions']:
                    if attended:
                        consecutive += 1
                        max_consecutive = max(max_consecutive, consecutive)
                    else:
                        consecutive = 0
                consistency = (max_consecutive / len(record['sessions'])) * 100
            
            features.append([rate, record['present'], record['absent'], consistency])
            labels.append(1 if rate >= 75 else 0)
            students.append(roll)
        
        X, y = np.array(features), np.array(labels)
        
        model = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, class_weight='balanced'
        )
        
        if len(X) >= 10:
            X_train, X_test, y_train, y_test, _, students_test = train_test_split(
                X, y, students, test_size=0.2, random_state=42
            )
            model.fit(X_train, y_train)
            accuracy = accuracy_score(y_test, model.predict(X_test))
        else:
            model.fit(X, y)
            accuracy = accuracy_score(y, model.predict(X))
        
        predictions = model.predict(X)
        probabilities = model.predict_proba(X)
        
        feature_names = ['Attendance Rate', 'Present Count', 'Absent Count', 'Consistency']
        importance = dict(zip(feature_names, model.feature_importances_))
        
        classifications, pass_students, fail_students = [], [], []
        for i, roll in enumerate(students):
            pred = predictions[i]
            prob = probabilities[i]
            student_data = {
                'roll': roll,
                'attendance_rate': round(features[i][0], 2),
                'present': int(features[i][1]),
                'absent': int(features[i][2]),
                'consistency': round(features[i][3], 2),
                'prediction': 'Pass' if pred == 1 else 'Fail',
                'confidence': round(max(prob) * 100, 2),
            }
            classifications.append(student_data)
            (pass_students if pred == 1 else fail_students).append(student_data)
        
        return Response({
            'model': 'Random Forest Classifier',
            'algorithm': 'scikit-learn RandomForestClassifier',
            'metrics': {
                'accuracy': round(accuracy * 100, 2),
                'total_students': len(students),
                'pass_predictions': len(pass_students),
                'fail_predictions': len(fail_students)
            },
            'feature_importance': {k: round(v * 100, 2) for k, v in importance.items()},
            'classifications': classifications,
            'pass_students': pass_students,
            'fail_students': fail_students,
            'sessions_analyzed': len(sessions)
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kmeans_clustering(request):
    """
    K-Means Clustering for Student Segmentation
    Groups students into performance clusters
    """
    try:
        data = request.data
        sessions = data.get('sessions', [])
        n_clusters = data.get('n_clusters', 4)
        
        if len(sessions) < 2:
            return Response({'error': 'Need at least 2 sessions for clustering'}, status=400)
        
        student_records = {}
        for session in sessions:
            for roll in session.get('present_roll_numbers', []):
                student_records.setdefault(roll, {'present': 0, 'absent': 0, 'sessions': []})
                student_records[roll]['present'] += 1
                student_records[roll]['sessions'].append(1)
            for roll in session.get('absent_roll_numbers', []):
                student_records.setdefault(roll, {'present': 0, 'absent': 0, 'sessions': []})
                student_records[roll]['absent'] += 1
                student_records[roll]['sessions'].append(0)
        
        if len(student_records) < n_clusters:
            return Response({'error': f'Need at least {n_clusters} students for {n_clusters} clusters'}, status=400)
        
        features, students = [], []
        for roll, record in student_records.items():
            total = record['present'] + record['absent']
            if total == 0:
                continue
            rate = (record['present'] / total) * 100
            
            consistency = 0
            if len(record['sessions']) > 1:
                consecutive = 0
                max_consecutive = 0
                for attended in record['sessions']:
                    if attended:
                        consecutive += 1
                        max_consecutive = max(max_consecutive, consecutive)
                    else:
                        consecutive = 0
                consistency = (max_consecutive / len(record['sessions'])) * 100
            
            features.append([rate, consistency, total])
            students.append(roll)
        
        X = np.array(features)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(X_scaled)
        silhouette = silhouette_score(X_scaled, cluster_labels)
        centers = scaler.inverse_transform(kmeans.cluster_centers_)
        
        clusters = {}
        for i in range(n_clusters):
            cluster_students = []
            cluster_indices = np.where(cluster_labels == i)[0]
            for idx in cluster_indices:
                cluster_students.append({
                    'roll': students[idx],
                    'attendance_rate': round(features[idx][0], 2),
                    'consistency': round(features[idx][1], 2),
                    'total_sessions': int(features[idx][2])
                })
            cluster_students.sort(key=lambda x: x['attendance_rate'], reverse=True)
            
            avg_rate = centers[i][0]
            if avg_rate >= 90:
                cluster_name = 'Excellent (90–100%)'
            elif avg_rate >= 80:
                cluster_name = 'Good (80–89%)'
            elif avg_rate >= 70:
                cluster_name = 'Satisfactory (70–79%)'
            elif avg_rate >= 60:
                cluster_name = 'Needs Improvement (60–69%)'
            else:
                cluster_name = 'At Risk (<60%)'
            
            clusters[f'cluster_{i}'] = {
                'name': cluster_name,
                'center': {
                    'attendance_rate': round(centers[i][0], 2),
                    'consistency': round(centers[i][1], 2),
                    'avg_sessions': round(centers[i][2], 2)
                },
                'size': len(cluster_students),
                'students': cluster_students
            }
        
        sorted_clusters = dict(sorted(
            clusters.items(), key=lambda x: x[1]['center']['attendance_rate'], reverse=True
        ))
        
        return Response({
            'model': 'K-Means Clustering',
            'algorithm': 'scikit-learn KMeans',
            'metrics': {
                'n_clusters': n_clusters,
                'silhouette_score': round(silhouette, 4),
                'total_students': len(students),
                'inertia': round(kmeans.inertia_, 2)
            },
            'clusters': sorted_clusters,
            'sessions_analyzed': len(sessions)
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ml_models_info(request):
    """
    Returns information about available ML models
    """
    return Response({
        'available_models': [
            {
                'id': 'linear-regression',
                'name': 'Linear Regression',
                'description': 'Predicts future attendance trends using historical data',
                'type': 'Regression',
                'endpoint': '/api/ml/linear-regression/',
                'min_sessions': 3
            },
            {
                'id': 'random-forest',
                'name': 'Random Forest Classifier',
                'description': 'Classifies students as Pass/Fail based on attendance patterns',
                'type': 'Classification',
                'endpoint': '/api/ml/random-forest/',
                'min_students': 5
            },
            {
                'id': 'kmeans',
                'name': 'K-Means Clustering',
                'description': 'Groups students into performance clusters',
                'type': 'Clustering',
                'endpoint': '/api/ml/kmeans/',
                'min_students': 4
            }
        ]
    })