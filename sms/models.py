from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

# Custom User Model
class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('student', 'Student'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.user_type})"

# Department Model
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True, null=True)
    head_of_department = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']

# Subject Model
class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    credits = models.IntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(6)])
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        ordering = ['name']

# Student Model
class Student(models.Model):
    YEAR_CHOICES = (
        ('1', 'First Year'),
        ('2', 'Second Year'),
        ('3', 'Third Year'),
        ('4', 'Fourth Year'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='students')
    year = models.CharField(max_length=1, choices=YEAR_CHOICES, default='1')
    enrollment_date = models.DateField()
    date_of_birth = models.DateField(blank=True, null=True)
    parent_name = models.CharField(max_length=100, blank=True, null=True)
    parent_phone = models.CharField(max_length=15, blank=True, null=True)
    emergency_contact = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student_id} - {self.user.get_full_name()}"

    class Meta:
        ordering = ['student_id']

# Course Model (for specific semester/year courses)
class Course(models.Model):
    SEMESTER_CHOICES = (
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
    )

    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='courses')
    year = models.CharField(max_length=1, choices=Student.YEAR_CHOICES)
    semester = models.CharField(max_length=1, choices=SEMESTER_CHOICES)
    academic_year = models.CharField(max_length=9, help_text="e.g., 2023-2024")
    instructor = models.CharField(max_length=100, blank=True, null=True)
    max_marks = models.IntegerField(default=100, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject.name} - Year {self.year} Sem {self.semester} ({self.academic_year})"

    class Meta:
        unique_together = ['subject', 'year', 'semester', 'academic_year']
        ordering = ['year', 'semester', 'subject__name']

# Grade Model
class Grade(models.Model):
    GRADE_CHOICES = (
        ('A+', 'A+ (90-100)'),
        ('A', 'A (80-89)'),
        ('B+', 'B+ (70-79)'),
        ('B', 'B (60-69)'),
        ('C+', 'C+ (50-59)'),
        ('C', 'C (40-49)'),
        ('F', 'F (0-39)'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='grades')
    marks_obtained = models.FloatField(validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True)
    gpa = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(4)])
    remarks = models.TextField(blank=True, null=True)
    exam_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate grade and GPA based on marks
        percentage = (self.marks_obtained / self.course.max_marks) * 100

        if percentage >= 90:
            self.grade = 'A+'
            self.gpa = 4.0
        elif percentage >= 80:
            self.grade = 'A'
            self.gpa = 3.7
        elif percentage >= 70:
            self.grade = 'B+'
            self.gpa = 3.3
        elif percentage >= 60:
            self.grade = 'B'
            self.gpa = 3.0
        elif percentage >= 50:
            self.grade = 'C+'
            self.gpa = 2.3
        elif percentage >= 40:
            self.grade = 'C'
            self.gpa = 2.0
        else:
            self.grade = 'F'
            self.gpa = 0.0

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.student_id} - {self.course.subject.name} - {self.grade}"

    class Meta:
        unique_together = ['student', 'course']
        ordering = ['-created_at']

# Attendance Model (optional for future enhancement)
class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    is_present = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student.student_id} - {self.course.subject.name} - {self.date} - {status}"

    class Meta:
        unique_together = ['student', 'course', 'date']
        ordering = ['-date']
