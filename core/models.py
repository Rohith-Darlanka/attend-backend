from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, full_name=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, full_name=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not password:
            raise ValueError("Superuser must have a password.")
        return self.create_user(email, password, full_name, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    uid = models.AutoField(primary_key=True)  # sequential 1,2,3...
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.uid})"


class Course(models.Model):
    course_id = models.CharField(max_length=50, primary_key=True, unique=True)
    course_name = models.CharField(max_length=255)
    teacher_ids = models.JSONField(default=list, help_text="List of teacher UIDs")
    teacher_names = models.JSONField(default=list, help_text="List of teacher full names")
    student_roll_numbers = models.JSONField(default=list, help_text="List of student roll numbers")
    num_students_registered = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['course_name']
        indexes = [
            models.Index(fields=['course_name']),
        ]

    def __str__(self):
        return f"{self.course_id} - {self.course_name}"

    def save(self, *args, **kwargs):
        # Auto-update num_students_registered based on student_roll_numbers
        self.num_students_registered = len(self.student_roll_numbers)
        super().save(*args, **kwargs)


class Session(models.Model):
    session_id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    course_id_copy = models.CharField(max_length=50, editable=False)
    course_name = models.CharField(max_length=255, editable=False)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions_taught')
    teacher_name = models.CharField(max_length=150, editable=False)
    present_roll_numbers = models.JSONField(default=list, help_text="List of roll numbers present")
    absent_roll_numbers = models.JSONField(default=list, help_text="List of roll numbers absent")
    num_students_attended = models.IntegerField(default=0)
    num_students_absent = models.IntegerField(default=0)
    attendance_portal_status = models.CharField(
        max_length=3,
        choices=[('ON', 'On'), ('OFF', 'Off')],
        default='ON'
    )
    session_created = models.DateTimeField(auto_now_add=True)
    session_ended = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-session_created']
        indexes = [
            models.Index(fields=['course', 'session_created']),
            models.Index(fields=['teacher', 'session_created']),
        ]

    def __str__(self):
        return f"Session {self.session_id} - {self.course_name} by {self.teacher_name}"

    def save(self, *args, **kwargs):
        # Auto-populate denormalized fields
        if self.course:
            self.course_id_copy = self.course.course_id
            self.course_name = self.course.course_name
        
        if self.teacher:
            self.teacher_name = self.teacher.full_name or self.teacher.email
        
        # Auto-update attendance counts
        self.num_students_attended = len(self.present_roll_numbers)
        self.num_students_absent = len(self.absent_roll_numbers)
        
        super().save(*args, **kwargs)


class Attendance(models.Model):
    ATTENDANCE_TYPES = (
        ('IN', 'Check In'),
        ('OUT', 'Check Out'),
    )
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    timestamp = models.DateTimeField(auto_now_add=True)
    attendance_type = models.CharField(max_length=3, choices=ATTENDANCE_TYPES)
    device_id = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.email} {self.attendance_type} at {self.timestamp.isoformat()}"