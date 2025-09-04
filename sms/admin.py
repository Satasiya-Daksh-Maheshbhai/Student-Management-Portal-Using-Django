from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Subject, Student, Course, Grade, Attendance

# Custom User Admin
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_staff', 'is_active')
    list_filter = ('user_type', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'phone', 'address', 'profile_picture')
        }),
    )

# Department Admin
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head_of_department', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'code', 'head_of_department')
    ordering = ('name',)

# Subject Admin
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'credits', 'created_at')
    list_filter = ('department', 'credits', 'created_at')
    search_fields = ('name', 'code', 'department__name')
    ordering = ('name',)

# Student Admin
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'get_full_name', 'department', 'year', 'is_active', 'enrollment_date')
    list_filter = ('department', 'year', 'is_active', 'enrollment_date')
    search_fields = ('student_id', 'user__first_name', 'user__last_name', 'user__email')
    ordering = ('student_id',)

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'

# Course Admin
class CourseAdmin(admin.ModelAdmin):
    list_display = ('subject', 'year', 'semester', 'academic_year', 'instructor', 'max_marks')
    list_filter = ('year', 'semester', 'academic_year', 'subject__department')
    search_fields = ('subject__name', 'instructor', 'academic_year')
    ordering = ('year', 'semester', 'subject__name')

# Grade Admin
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'marks_obtained', 'grade', 'gpa', 'exam_date')
    list_filter = ('grade', 'course__year', 'course__semester', 'course__academic_year', 'exam_date')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name', 'course__subject__name')
    ordering = ('-created_at',)

# Attendance Admin
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'date', 'is_present')
    list_filter = ('is_present', 'date', 'course__subject__department')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name', 'course__subject__name')
    ordering = ('-date',)

# Register models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(Grade, GradeAdmin)
admin.site.register(Attendance, AttendanceAdmin)
