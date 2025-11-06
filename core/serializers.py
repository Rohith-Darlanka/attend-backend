from rest_framework import serializers
from .models import User, Attendance, Course, Session

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['uid', 'email', 'full_name', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class AttendanceSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'user', 'attendance_type', 'timestamp', 'device_id', 'location']


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'course_id', 
            'course_name', 
            'teacher_ids', 
            'teacher_names',
            'student_roll_numbers', 
            'num_students_registered',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['num_students_registered', 'created_at', 'updated_at']


class CreateCourseSerializer(serializers.Serializer):
    course_id = serializers.CharField(max_length=50)
    course_name = serializers.CharField(max_length=255)
    student_roll_numbers = serializers.ListField(
        child=serializers.CharField(max_length=50),
        allow_empty=True
    )

    def validate_course_id(self, value):
        if Course.objects.filter(course_id=value).exists():
            raise serializers.ValidationError("Course with this ID already exists.")
        return value


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = [
            'session_id',
            'course',
            'course_id_copy',
            'course_name',
            'teacher',
            'teacher_name',
            'present_roll_numbers',
            'absent_roll_numbers',
            'num_students_attended',
            'num_students_absent',
            'session_created',
            'session_ended',
            'attendance_portal_status'
        ]
        read_only_fields = [
            'session_id',
            'course_id_copy',
            'course_name',
            'teacher_name',
            'num_students_attended',
            'num_students_absent',
            'session_created'
        ]


class CreateSessionSerializer(serializers.Serializer):
    course_id = serializers.CharField(max_length=50)

    def validate_course_id(self, value):
        try:
            Course.objects.get(course_id=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course with this ID does not exist.")
        return value


class MarkAttendanceSerializer(serializers.Serializer):
    roll_number = serializers.CharField(max_length=50)

    def validate_roll_number(self, value):
        if not value.strip():
            raise serializers.ValidationError("Roll number cannot be empty.")
        return value.strip()            