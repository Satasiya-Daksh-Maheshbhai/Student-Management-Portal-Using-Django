from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Avg, Q
from django.core.files.storage import FileSystemStorage
from .models import User, Student, Department, Subject, Course, Grade
import json
import csv
import io
import pandas as pd
from datetime import date, datetime
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

def login_view(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'admin':
            return redirect('sms:admin_dashboard')
        else:
            return redirect('sms:student_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'student')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.user_type == user_type:
                login(request, user)
                if user_type == 'admin':
                    return redirect('sms:admin_dashboard')
                else:
                    return redirect('sms:student_dashboard')
            else:
                error = f"Invalid credentials for {user_type} login."
        else:
            error = "Invalid username or password."

        return render(request, 'sms/login.html', {'error': error})

    return render(request, 'sms/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('sms:login')

@login_required
def admin_dashboard(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    # Get dashboard statistics
    total_students = Student.objects.filter(is_active=True).count()
    total_courses = Course.objects.count()
    total_subjects = Subject.objects.count()
    total_grades = Grade.objects.count()

    # Calculate additional statistics
    all_grades = Grade.objects.all()
    a_grades = all_grades.filter(grade='A').count()
    failing_grades = all_grades.filter(grade='F').count()
    avg_gpa = all_grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa'] or 0

    # Get recent students (last 5)
    recent_students = Student.objects.select_related('user', 'department').order_by('-created_at')[:5]

    # Get recent grades (last 5)
    recent_grades = Grade.objects.select_related('student__user', 'course__subject').order_by('-created_at')[:5]

    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_subjects': total_subjects,
        'total_grades': total_grades,
        'a_grades': a_grades,
        'avg_gpa': round(avg_gpa, 1),
        'failing_grades': failing_grades,
        'recent_students': recent_students,
        'recent_grades': recent_grades,
    }

    return render(request, 'sms/admin_dashboard.html', context)

@login_required
def manage_students(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    students = Student.objects.select_related('user', 'department').all()
    departments = Department.objects.all()

    context = {
        'students': students,
        'departments': departments,
    }

    return render(request, 'sms/manage_students.html', context)

@login_required
def get_student_details(request, student_id):
    """Get detailed student information for the modal"""
    if request.user.user_type != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        student = Student.objects.select_related('user', 'department').get(id=student_id)

        # Get student's grades
        grades = Grade.objects.filter(student=student).select_related('course__subject')

        # Calculate GPA
        avg_gpa = grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa'] or 0

        # Get grade distribution
        grade_counts = {}
        for grade in grades:
            grade_letter = grade.grade
            grade_counts[grade_letter] = grade_counts.get(grade_letter, 0) + 1

        # Prepare student data
        student_data = {
            'id': student.id,
            'student_id': student.student_id,
            'username': student.user.username,
            'first_name': student.user.first_name,
            'last_name': student.user.last_name,
            'full_name': student.user.get_full_name(),
            'email': student.user.email,
            'date_of_birth': student.date_of_birth.strftime('%B %d, %Y') if student.date_of_birth else 'Not provided',
            'department': student.department.name,
            'year': student.get_year_display(),
            'enrollment_date': student.enrollment_date.strftime('%B %d, %Y') if student.enrollment_date else 'Not provided',
            'parent_phone': student.parent_phone or 'Not provided',
            'is_active': student.is_active,
            'avg_gpa': round(avg_gpa, 2),
            'total_grades': grades.count(),
            'grade_counts': grade_counts,
            'last_login': student.user.last_login.strftime('%B %d, %Y at %I:%M %p') if student.user.last_login else 'Never logged in',
            'date_joined': student.user.date_joined.strftime('%B %d, %Y at %I:%M %p'),
            'current_password': 'student123',
            'password_note': 'Current password: student123 (Default for all students)',
            'recent_grades': [
                {
                    'course': grade.course.subject.name,
                    'grade': grade.grade,
                    'marks': grade.marks_obtained,
                    'date': grade.created_at.strftime('%b %d, %Y')
                }
                for grade in grades.order_by('-created_at')[:5]
            ]
        }

        return JsonResponse({'success': True, 'student': student_data})

    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': 'An error occurred'}, status=500)

@login_required
def add_student(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        student_id = request.POST.get('student_id')
        department_id = request.POST.get('department')
        year = request.POST.get('year')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        enrollment_date = request.POST.get('enrollment_date')
        date_of_birth = request.POST.get('date_of_birth')
        parent_name = request.POST.get('parent_name')
        parent_phone = request.POST.get('parent_phone')

        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                user_type='student',
                phone=phone,
                address=address
            )

            # Create student profile
            department = Department.objects.get(id=department_id)
            student = Student.objects.create(
                user=user,
                student_id=student_id,
                department=department,
                year=year,
                enrollment_date=enrollment_date,
                date_of_birth=date_of_birth if date_of_birth else None,
                parent_name=parent_name,
                parent_phone=parent_phone
            )

            messages.success(request, f'Student {student_id} added successfully!')
            return redirect('sms:manage_students')

        except Exception as e:
            messages.error(request, f'Error adding student: {str(e)}')

    departments = Department.objects.all()
    context = {'departments': departments}
    return render(request, 'sms/add_student.html', context)

@login_required
def edit_student(request, student_id):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    student = get_object_or_404(Student, id=student_id)

    if request.method == 'POST':
        # Update user data
        student.user.username = request.POST.get('username')
        student.user.email = request.POST.get('email')
        student.user.first_name = request.POST.get('first_name')
        student.user.last_name = request.POST.get('last_name')
        student.user.phone = request.POST.get('phone')
        student.user.address = request.POST.get('address')

        # Update password - always set to the provided password or default
        password = request.POST.get('password')
        if password:
            student.user.set_password(password)
        else:
            # Set default password if none provided
            student.user.set_password('student123')

        student.user.save()

        # Update student data
        student.student_id = request.POST.get('student_id')
        student.department_id = request.POST.get('department')
        student.year = request.POST.get('year')
        student.enrollment_date = request.POST.get('enrollment_date')
        student.date_of_birth = request.POST.get('date_of_birth') if request.POST.get('date_of_birth') else None
        student.parent_name = request.POST.get('parent_name')
        student.parent_phone = request.POST.get('parent_phone')
        student.is_active = request.POST.get('is_active') == 'on'

        student.save()

        messages.success(request, f'Student {student.student_id} updated successfully!')
        return redirect('sms:manage_students')

    departments = Department.objects.all()
    context = {
        'student': student,
        'departments': departments,
    }
    return render(request, 'sms/edit_student.html', context)

@login_required
def delete_student(request, student_id):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    student = get_object_or_404(Student, id=student_id)

    if request.method == 'POST':
        student_name = student.user.get_full_name()
        student.user.delete()  # This will also delete the student due to CASCADE
        messages.success(request, f'Student {student_name} deleted successfully!')
        return redirect('sms:manage_students')

    context = {'student': student}
    return render(request, 'sms/delete_student.html', context)

@login_required
def manage_grades(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    grades = Grade.objects.select_related('student__user', 'course__subject', 'course__subject__department').all()
    students = Student.objects.select_related('user', 'department').filter(is_active=True)
    courses = Course.objects.select_related('subject', 'subject__department').all()

    # Calculate grade statistics
    total_grades_count = grades.count()

    # Calculate A-level grades (GPA >= 3.7, which represents A-level performance)
    a_grades = grades.filter(gpa__gte=3.7)
    a_grades_count = a_grades.count()

    # Calculate failing grades statistics
    failing_grades = grades.filter(grade='F')
    failing_grades_count = failing_grades.count()
    failing_students_count = failing_grades.values('student').distinct().count()

    # Calculate percentage of failing grades
    failing_percentage = (failing_grades_count / total_grades_count * 100) if total_grades_count > 0 else 0
    passing_grades_count = total_grades_count - failing_grades_count
    passing_percentage = 100 - failing_percentage

    # Calculate A grades percentage
    a_grades_percentage = (a_grades_count / total_grades_count * 100) if total_grades_count > 0 else 0

    # Calculate average GPA
    avg_gpa = grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa'] or 0

    context = {
        'grades': grades,
        'students': students,
        'courses': courses,
        'total_grades_count': total_grades_count,
        'a_grades_count': a_grades_count,
        'a_grades_percentage': round(a_grades_percentage, 1),
        'failing_grades_count': failing_grades_count,
        'failing_students_count': failing_students_count,
        'passing_grades_count': passing_grades_count,
        'failing_percentage': round(failing_percentage, 1),
        'passing_percentage': round(passing_percentage, 1),
        'avg_gpa': round(avg_gpa, 2),
    }

    return render(request, 'sms/manage_grades.html', context)

@login_required
def add_grade(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    if request.method == 'POST':
        student_id = request.POST.get('student')
        course_id = request.POST.get('course')
        marks_obtained = request.POST.get('marks_obtained')
        exam_date = request.POST.get('exam_date')
        remarks = request.POST.get('remarks')

        try:
            student = Student.objects.get(id=student_id)
            course = Course.objects.get(id=course_id)

            # Check if grade already exists for this student and course
            if Grade.objects.filter(student=student, course=course).exists():
                messages.error(request, 'Grade already exists for this student and course.')
                return redirect('sms:add_grade')

            grade = Grade.objects.create(
                student=student,
                course=course,
                marks_obtained=float(marks_obtained),
                exam_date=exam_date if exam_date else None,
                remarks=remarks
            )

            messages.success(request, f'Grade added successfully for {student.user.get_full_name()}!')
            return redirect('sms:manage_grades')

        except Exception as e:
            messages.error(request, f'Error adding grade: {str(e)}')

    students = Student.objects.select_related('user', 'department').filter(is_active=True)
    courses = Course.objects.select_related('subject', 'subject__department').all()

    context = {
        'students': students,
        'courses': courses,
    }
    return render(request, 'sms/add_grade.html', context)

@login_required
def edit_grade(request, grade_id):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    grade = get_object_or_404(Grade, id=grade_id)

    if request.method == 'POST':
        grade.marks_obtained = float(request.POST.get('marks_obtained'))
        grade.exam_date = request.POST.get('exam_date') if request.POST.get('exam_date') else None
        grade.remarks = request.POST.get('remarks')

        grade.save()  # This will trigger the auto-calculation of grade and GPA

        messages.success(request, f'Grade updated successfully for {grade.student.user.get_full_name()}!')
        return redirect('sms:manage_grades')

    students = Student.objects.select_related('user', 'department').filter(is_active=True)
    courses = Course.objects.select_related('subject', 'subject__department').all()

    context = {
        'grade': grade,
        'students': students,
        'courses': courses,
    }
    return render(request, 'sms/edit_grade.html', context)

@login_required
def delete_grade(request, grade_id):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    grade = get_object_or_404(Grade, id=grade_id)

    if request.method == 'POST':
        student_name = grade.student.user.get_full_name()
        course_name = grade.course.subject.name
        grade.delete()
        messages.success(request, f'Grade deleted successfully for {student_name} in {course_name}!')
        return redirect('sms:manage_grades')

    context = {'grade': grade}
    return render(request, 'sms/delete_grade.html', context)

# Course Analysis Views
@login_required
def course_analysis(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    courses = Course.objects.select_related('subject', 'subject__department').all()
    course_data = []

    for course in courses:
        grades = Grade.objects.filter(course=course)
        if grades.exists():
            avg_marks = grades.aggregate(avg_marks=Avg('marks_obtained'))['avg_marks']
            avg_gpa = grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa']
            total_students = grades.count()

            # Grade distribution
            grade_dist = {}
            for grade in grades:
                if grade.grade in grade_dist:
                    grade_dist[grade.grade] += 1
                else:
                    grade_dist[grade.grade] = 1

            course_data.append({
                'course': course,
                'avg_marks': round(avg_marks, 2) if avg_marks else 0,
                'avg_gpa': round(avg_gpa, 2) if avg_gpa else 0,
                'total_students': total_students,
                'grade_distribution': grade_dist
            })

    context = {
        'course_data': course_data,
        'courses': courses
    }
    return render(request, 'sms/course_analysis.html', context)

@login_required
def course_analysis_data(request):
    if request.user.user_type != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)

    course_id = request.GET.get('course_id')
    if course_id:
        course = get_object_or_404(Course, id=course_id)
        grades = Grade.objects.filter(course=course).select_related('student__user')

        students = []
        marks = []

        for grade in grades:
            students.append(grade.student.user.get_full_name())
            marks.append(float(grade.marks_obtained))

        data = {
            'course_name': course.subject.name,
            'students': students,
            'marks': marks,
            'max_marks': course.max_marks
        }
        return JsonResponse(data)

    # Return all courses data
    courses_data = []
    courses = Course.objects.all()

    for course in courses:
        grades = Grade.objects.filter(course=course)
        if grades.exists():
            avg_marks = grades.aggregate(avg_marks=Avg('marks_obtained'))['avg_marks']
            courses_data.append({
                'course_name': course.subject.name,
                'avg_marks': float(avg_marks) if avg_marks else 0,
                'max_marks': course.max_marks
            })

    return JsonResponse({'courses': courses_data})

# Performance Trends Views
@login_required
def performance_trends(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    # Get overall performance trends
    grades = Grade.objects.select_related('student__user', 'course__subject__department').order_by('created_at')

    # Monthly performance data
    monthly_data = {}
    for grade in grades:
        month_key = grade.created_at.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = {'total_gpa': 0, 'count': 0, 'students': set()}
        monthly_data[month_key]['total_gpa'] += grade.gpa
        monthly_data[month_key]['count'] += 1
        monthly_data[month_key]['students'].add(grade.student.id)

    # Calculate average GPA per month with trends
    trend_data = []
    prev_avg_gpa = None

    for month, data in sorted(monthly_data.items()):
        avg_gpa = data['total_gpa'] / data['count'] if data['count'] > 0 else 0
        unique_students = len(data['students'])

        # Calculate trend compared to previous month
        if prev_avg_gpa is not None:
            if avg_gpa > prev_avg_gpa:
                trend = "↗️ Improving"
                trend_class = "success"
            elif avg_gpa < prev_avg_gpa:
                trend = "↘️ Declining"
                trend_class = "danger"
            else:
                trend = "→ Stable"
                trend_class = "info"
        else:
            trend = "— N/A"
            trend_class = "muted"

        trend_data.append({
            'month': month,
            'avg_gpa': round(avg_gpa, 2),
            'student_count': unique_students,
            'grade_count': data['count'],
            'trend': trend,
            'trend_class': trend_class
        })

        prev_avg_gpa = avg_gpa

    # Calculate latest average GPA (from the most recent month with data)
    latest_avg_gpa = 0
    if trend_data:
        latest_avg_gpa = trend_data[-1]['avg_gpa']  # Last item in sorted list

    # Department-wise performance - include all departments
    all_departments = Department.objects.all()
    dept_data = []

    for department in all_departments:
        # Get grades for students belonging to this department (not course department)
        dept_grades = grades.filter(student__department=department)

        if dept_grades.exists():
            total_gpa = sum(grade.gpa for grade in dept_grades)
            count = dept_grades.count()
            avg_gpa = total_gpa / count if count > 0 else 0
            student_count = count
        else:
            avg_gpa = 0
            student_count = 0

        dept_data.append({
            'department': department.name,
            'avg_gpa': round(avg_gpa, 2),
            'student_count': student_count
        })

    # Get total number of departments
    total_departments = Department.objects.count()

    context = {
        'trend_data': trend_data,
        'dept_data': dept_data,
        'total_grades': grades.count(),
        'latest_avg_gpa': latest_avg_gpa,
        'total_departments': total_departments
    }
    return render(request, 'sms/performance_trends.html', context)

@login_required
def performance_trends_data(request):
    if request.user.user_type != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)

    grades = Grade.objects.select_related('course__subject__department').order_by('created_at')

    # Monthly trends
    monthly_data = {}
    for grade in grades:
        month_key = grade.created_at.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = []
        monthly_data[month_key].append(grade.gpa)

    months = []
    avg_gpas = []
    for month in sorted(monthly_data.keys()):
        months.append(month)
        avg_gpa = sum(monthly_data[month]) / len(monthly_data[month])
        avg_gpas.append(round(avg_gpa, 2))

    return JsonResponse({
        'months': months,
        'avg_gpas': avg_gpas
    })

# CSV Import Views
@login_required
def import_csv_data(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        import_type = request.POST.get('import_type')

        if not csv_file:
            messages.error(request, 'Please select a CSV file.')
            return redirect('sms:import_csv_data')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('sms:import_csv_data')

        try:
            # Read CSV file using pandas for better error handling
            df = pd.read_csv(csv_file)

            # Validate required columns
            if import_type == 'students':
                required_columns = ['username', 'email', 'first_name', 'last_name', 'student_id', 'department_code', 'year', 'enrollment_date']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                    return redirect('sms:import_csv_data')

                success_count, error_count, error_details = import_students_pandas(df)
            elif import_type == 'grades':
                required_columns = ['student_id', 'course_code', 'marks_obtained']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                    return redirect('sms:import_csv_data')

                success_count, error_count, predictions, error_details = import_grades_pandas(df)

            # Display results
            if success_count > 0:
                messages.success(request, f'Successfully imported {success_count} records.')
            if error_count > 0:
                error_msg = f'{error_count} records had errors and were skipped.'
                if error_details:
                    error_msg += f' First few errors: {"; ".join(error_details[:3])}'
                messages.warning(request, error_msg)

            # Show predictions if available
            if import_type == 'grades' and 'predictions' in locals() and predictions:
                context = {
                    'predictions': predictions,
                    'show_predictions': True
                }
                return render(request, 'sms/import_csv_data.html', context)

        except pd.errors.EmptyDataError:
            messages.error(request, 'The CSV file is empty.')
        except pd.errors.ParserError as e:
            messages.error(request, f'Error parsing CSV file: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error processing CSV file: {str(e)}')

    return render(request, 'sms/import_csv_data.html')

def import_students_pandas(df):
    """Import students using pandas DataFrame with improved error handling"""
    success_count = 0
    error_count = 0
    error_details = []

    # Clean the data
    df = df.dropna(subset=['username', 'email', 'student_id'])  # Remove rows with missing critical data
    df['phone'] = df['phone'].fillna('')  # Fill missing phone numbers

    for index, row in df.iterrows():
        try:
            # Validate required fields
            if not row['username'] or not row['email'] or not row['student_id']:
                error_details.append(f"Row {index + 2}: Missing required fields")
                error_count += 1
                continue

            # Check if user already exists
            if User.objects.filter(username=row['username']).exists():
                error_details.append(f"Row {index + 2}: Username '{row['username']}' already exists")
                error_count += 1
                continue

            if User.objects.filter(email=row['email']).exists():
                error_details.append(f"Row {index + 2}: Email '{row['email']}' already exists")
                error_count += 1
                continue

            if Student.objects.filter(student_id=row['student_id']).exists():
                error_details.append(f"Row {index + 2}: Student ID '{row['student_id']}' already exists")
                error_count += 1
                continue

            # Get department
            try:
                department = Department.objects.get(code=row['department_code'])
            except Department.DoesNotExist:
                error_details.append(f"Row {index + 2}: Department '{row['department_code']}' not found")
                error_count += 1
                continue

            # Parse enrollment date
            try:
                enrollment_date = pd.to_datetime(row['enrollment_date']).date()
            except:
                error_details.append(f"Row {index + 2}: Invalid enrollment date format")
                error_count += 1
                continue

            # Create user
            user = User.objects.create_user(
                username=row['username'],
                email=row['email'],
                password=row.get('password', 'student123'),
                first_name=row['first_name'],
                last_name=row['last_name'],
                user_type='student',
                phone=str(row.get('phone', ''))
            )

            # Create student profile
            Student.objects.create(
                user=user,
                student_id=row['student_id'],
                department=department,
                year=str(row['year']),
                enrollment_date=enrollment_date
            )
            success_count += 1

        except Exception as e:
            error_details.append(f"Row {index + 2}: {str(e)}")
            error_count += 1
            continue

    return success_count, error_count, error_details

def import_students_csv(csv_data):
    """Legacy function for backward compatibility"""
    success_count = 0
    error_count = 0

    for row in csv_data:
        try:
            # Create user
            user = User.objects.create_user(
                username=row['username'],
                email=row['email'],
                password=row.get('password', 'student123'),
                first_name=row['first_name'],
                last_name=row['last_name'],
                user_type='student',
                phone=row.get('phone', '')
            )

            # Create student profile
            department = Department.objects.get(code=row['department_code'])
            Student.objects.create(
                user=user,
                student_id=row['student_id'],
                department=department,
                year=row['year'],
                enrollment_date=datetime.strptime(row['enrollment_date'], '%Y-%m-%d').date()
            )
            success_count += 1

        except Exception as e:
            error_count += 1
            continue

    return success_count, error_count

def import_grades_pandas(df):
    """Import grades using pandas DataFrame with improved error handling"""
    success_count = 0
    error_count = 0
    error_details = []
    predictions = []

    # Clean the data
    df = df.dropna(subset=['student_id', 'course_code', 'marks_obtained'])

    for index, row in df.iterrows():
        try:
            # Get student
            try:
                student = Student.objects.get(student_id=row['student_id'])
            except Student.DoesNotExist:
                error_details.append(f"Row {index + 2}: Student '{row['student_id']}' not found")
                error_count += 1
                continue

            # Get or create course
            course_code = row['course_code']
            try:
                course = Course.objects.filter(subject__code=course_code).first()
                if not course:
                    raise Course.DoesNotExist()
            except Course.DoesNotExist:
                # Try to create the course if subject exists
                try:
                    subject = Subject.objects.get(code=course_code)
                    course = Course.objects.create(
                        subject=subject,
                        year='1',
                        semester='1',
                        academic_year='2024-2025'
                    )
                except Subject.DoesNotExist:
                    # Create both subject and course
                    if course_code.startswith('CS'):
                        dept_code = 'CS'
                    elif course_code.startswith('EE'):
                        dept_code = 'EE'
                    elif course_code.startswith('ME'):
                        dept_code = 'ME'
                    else:
                        dept_code = 'CS'  # Default to CS

                    try:
                        department = Department.objects.get(code=dept_code)
                        subject = Subject.objects.create(
                            name=f"{course_code} Subject",
                            code=course_code,
                            credits=3,
                            department=department
                        )
                        course = Course.objects.create(
                            subject=subject,
                            year='1',
                            semester='1',
                            academic_year='2024-2025'
                        )
                    except Department.DoesNotExist:
                        error_details.append(f"Row {index + 2}: Department for course '{course_code}' not found")
                        error_count += 1
                        continue

            # Validate marks
            try:
                marks = float(row['marks_obtained'])
                if marks < 0 or marks > course.max_marks:
                    error_details.append(f"Row {index + 2}: Invalid marks {marks} (should be 0-{course.max_marks})")
                    error_count += 1
                    continue
            except (ValueError, TypeError):
                error_details.append(f"Row {index + 2}: Invalid marks format")
                error_count += 1
                continue

            # Parse exam date
            try:
                if 'exam_date' in row and pd.notna(row['exam_date']):
                    exam_date = pd.to_datetime(row['exam_date']).date()
                else:
                    exam_date = date.today()
            except:
                exam_date = date.today()

            # Check if grade already exists
            existing_grade = Grade.objects.filter(student=student, course=course).first()
            if existing_grade:
                existing_grade.marks_obtained = marks
                existing_grade.exam_date = exam_date
                existing_grade.save()
                grade = existing_grade
            else:
                grade = Grade.objects.create(
                    student=student,
                    course=course,
                    marks_obtained=marks,
                    exam_date=exam_date
                )

            # AI-powered performance prediction
            try:
                prediction = predict_performance(student, grade)
                predictions.append({
                    'student': student,
                    'current_grade': grade,
                    'prediction': prediction
                })
            except:
                pass  # Continue even if prediction fails

            success_count += 1

        except Exception as e:
            error_details.append(f"Row {index + 2}: {str(e)}")
            error_count += 1
            continue

    return success_count, error_count, predictions, error_details

def import_grades_csv(csv_data):
    success_count = 0
    error_count = 0
    predictions = []

    for row in csv_data:
        try:
            # Get or create student
            try:
                student = Student.objects.get(student_id=row['student_id'])
            except Student.DoesNotExist:
                error_count += 1
                continue

            # Get or create course
            course_code = row['course_code']
            try:
                # Use filter().first() to handle multiple courses with same subject code
                course = Course.objects.filter(subject__code=course_code).first()
                if not course:
                    raise Course.DoesNotExist()
            except Course.DoesNotExist:
                # Try to create the course if subject exists
                try:
                    subject = Subject.objects.get(code=course_code)
                    course = Course.objects.create(
                        subject=subject,
                        year='1',  # Default year
                        semester='1',  # Default semester
                        academic_year='2024-2025'
                    )
                except Subject.DoesNotExist:
                    # Create both subject and course
                    # Determine department based on course code
                    if course_code.startswith('CS'):
                        dept_code = 'CS'
                    elif course_code.startswith('EE'):
                        dept_code = 'EE'
                    else:
                        dept_code = 'CS'  # Default to CS

                    try:
                        department = Department.objects.get(code=dept_code)
                        subject = Subject.objects.create(
                            name=f"{course_code} Subject",
                            code=course_code,
                            credits=3,
                            department=department
                        )
                        course = Course.objects.create(
                            subject=subject,
                            year='1',
                            semester='1',
                            academic_year='2024-2025'
                        )
                    except Department.DoesNotExist:
                        error_count += 1
                        continue

            marks = float(row['marks_obtained'])

            # Check if grade already exists
            existing_grade = Grade.objects.filter(student=student, course=course).first()
            if existing_grade:
                # Update existing grade
                existing_grade.marks_obtained = marks
                existing_grade.exam_date = datetime.strptime(row.get('exam_date', str(date.today())), '%Y-%m-%d').date()
                existing_grade.save()
                grade = existing_grade
            else:
                # Create new grade
                grade = Grade.objects.create(
                    student=student,
                    course=course,
                    marks_obtained=marks,
                    exam_date=datetime.strptime(row.get('exam_date', str(date.today())), '%Y-%m-%d').date()
                )

            # AI-powered performance prediction
            prediction = predict_performance(student, grade)
            predictions.append({
                'student': student,
                'current_grade': grade,
                'prediction': prediction
            })

            success_count += 1

        except Exception as e:
            error_count += 1
            continue

    return success_count, error_count, predictions

def predict_performance(student, current_grade):
    """AI-powered performance prediction using K-Nearest Neighbors classification"""
    try:
        # Get all students' historical data for training
        all_grades = Grade.objects.all().select_related('student', 'course')


        if len(all_grades) < 10:  # Need minimum data for ML
            return simple_prediction(student, current_grade)

        # Prepare training data
        features = []
        labels = []

        # Group grades by student to calculate features
        student_data = {}
        for grade in all_grades:
            sid = grade.student.id
            if sid not in student_data:
                student_data[sid] = []
            student_data[sid].append(grade)

        # Extract features for each student
        for sid, grades in student_data.items():
            if len(grades) >= 2:  # Need at least 2 grades for trend analysis
                grades_sorted = sorted(grades, key=lambda x: x.created_at)

                # Calculate features
                avg_gpa = sum(g.gpa for g in grades_sorted) / len(grades_sorted)
                latest_gpa = grades_sorted[-1].gpa
                trend = (grades_sorted[-1].gpa - grades_sorted[0].gpa) / len(grades_sorted)
                consistency = 1.0 - (max(g.gpa for g in grades_sorted) - min(g.gpa for g in grades_sorted)) / 4.0
                failing_count = sum(1 for g in grades_sorted if g.gpa < 2.0)

                features.append([avg_gpa, latest_gpa, trend, consistency, failing_count])

                # Classify performance based on latest GPA
                if latest_gpa >= 3.7:
                    labels.append('Excellent')
                elif latest_gpa >= 3.0:
                    labels.append('Best')
                elif latest_gpa >= 2.5:
                    labels.append('Better')
                else:
                    labels.append('Good')

        if len(features) < 5:  # Not enough training data
            return simple_prediction(student, current_grade)

        # Train K-Nearest Neighbors model
        features_array = np.array(features)
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features_array)

        # Ensure k is appropriate for the dataset
        k = max(1, min(5, len(features) // 2))  # At least 1, at most 5
        if k >= len(features):
            k = len(features) - 1 if len(features) > 1 else 1

        knn = KNeighborsClassifier(n_neighbors=k, weights='distance')
        knn.fit(features_scaled, labels)

        # Prepare current student's features
        student_grades = Grade.objects.filter(student=student).order_by('created_at')

        if len(student_grades) >= 1:
            grades_list = list(student_grades)
            avg_gpa = sum(g.gpa for g in grades_list) / len(grades_list)
            latest_gpa = current_grade.gpa
            trend = (current_grade.gpa - grades_list[0].gpa) / len(grades_list) if len(grades_list) > 1 else 0
            consistency = 1.0 - (max(g.gpa for g in grades_list) - min(g.gpa for g in grades_list)) / 4.0 if len(grades_list) > 1 else 1.0
            failing_count = sum(1 for g in grades_list if g.gpa < 2.0)

            current_features = np.array([[avg_gpa, latest_gpa, trend, consistency, failing_count]])
            current_features_scaled = scaler.transform(current_features)

            # Make prediction
            prediction = knn.predict(current_features_scaled)[0]
            probabilities = knn.predict_proba(current_features_scaled)[0]
            confidence = max(probabilities)

            # Get detailed analysis
            return get_ai_analysis(student, current_grade, prediction, confidence, avg_gpa, trend, consistency)

        return simple_prediction(student, current_grade)

    except Exception as e:
        # Fallback to simple prediction if ML fails
        return simple_prediction(student, current_grade)

def simple_prediction(student, current_grade):
    """Fallback prediction method when ML is not available"""
    previous_grades = Grade.objects.filter(student=student).exclude(id=current_grade.id).order_by('created_at')

    if not previous_grades.exists():
        # For new students
        if current_grade.gpa >= 3.7:
            performance_class = 'Excellent'
            recommendation = 'Outstanding start! Maintain this excellence.'
        elif current_grade.gpa >= 3.0:
            performance_class = 'Best'
            recommendation = 'Great performance! Keep up the good work.'
        elif current_grade.gpa >= 2.5:
            performance_class = 'Better'
            recommendation = 'Good foundation. Aim for consistency.'
        else:
            performance_class = 'Good'
            recommendation = 'Focus on improvement. Seek academic support.'

        # Determine risk level
        risk_levels = {
            'Excellent': 'Low',
            'Best': 'Low',
            'Better': 'Medium',
            'Good': 'High'
        }

        return {
            'ai_prediction': performance_class,
            'predicted_gpa': round(current_grade.gpa, 2),
            'confidence': 0.6,
            'confidence_level': 'Medium',
            'risk_level': risk_levels[performance_class],
            'recommendation': recommendation,
            'method': 'Rule-based (New Student)',
            'factors': ['Initial performance assessment']
        }

    # For existing students - simple average-based prediction
    grades_list = list(previous_grades) + [current_grade]
    avg_gpa = sum(g.gpa for g in grades_list) / len(grades_list)

    if avg_gpa >= 3.7:
        performance_class = 'Excellent'
    elif avg_gpa >= 3.0:
        performance_class = 'Best'
    elif avg_gpa >= 2.5:
        performance_class = 'Better'
    else:
        performance_class = 'Good'

    # Determine risk level
    risk_levels = {
        'Excellent': 'Low',
        'Best': 'Low',
        'Better': 'Medium',
        'Good': 'High'
    }

    return {
        'ai_prediction': performance_class,
        'predicted_gpa': round(avg_gpa, 2),
        'confidence': 0.7,
        'confidence_level': 'Medium',
        'risk_level': risk_levels[performance_class],
        'recommendation': f'Continue current trajectory. Average GPA: {avg_gpa:.2f}',
        'method': 'Rule-based (Historical Average)',
        'factors': [f'Based on {len(grades_list)} grades']
    }

def get_ai_analysis(student, current_grade, prediction, confidence, avg_gpa, trend, consistency):
    """Generate detailed AI analysis report"""

    # Performance-based recommendations
    recommendations = {
        'Excellent': [
            'Maintain exceptional performance standards',
            'Consider mentoring struggling peers',
            'Explore advanced coursework opportunities',
            'Prepare for leadership roles'
        ],
        'Best': [
            'Sustain current study methods',
            'Challenge yourself with harder subjects',
            'Maintain consistent effort',
            'Consider academic competitions'
        ],
        'Better': [
            'Focus on consistency improvement',
            'Identify and strengthen weak areas',
            'Develop better study habits',
            'Seek additional practice materials'
        ],
        'Good': [
            'Immediate academic intervention needed',
            'Schedule regular tutoring sessions',
            'Review fundamental concepts',
            'Develop structured study plan'
        ]
    }

    # Risk assessment based on prediction
    risk_levels = {
        'Excellent': 'Very Low',
        'Best': 'Low',
        'Better': 'Medium',
        'Good': 'High'
    }

    # Confidence level interpretation
    confidence_level = 'High' if confidence > 0.8 else 'Medium' if confidence > 0.6 else 'Low'

    # Trend analysis
    trend_description = 'Improving' if trend > 0.1 else 'Declining' if trend < -0.1 else 'Stable'

    # Generate factors
    factors = [
        f'K-NN Classification: {prediction}',
        f'Average GPA: {avg_gpa:.2f}',
        f'Performance Trend: {trend_description}',
        f'Consistency Score: {consistency:.2f}',
        f'Model Confidence: {confidence:.2f}'
    ]

    return {
        'ai_prediction': prediction,
        'predicted_gpa': round(avg_gpa, 2),
        'confidence': round(confidence, 2),
        'confidence_level': confidence_level,
        'risk_level': risk_levels[prediction],
        'recommendation': recommendations[prediction][0],
        'detailed_recommendations': recommendations[prediction],
        'trend': trend_description,
        'consistency_score': round(consistency, 2),
        'method': 'K-Nearest Neighbors ML',
        'factors': factors
    }

# At-Risk Students Views
@login_required
def at_risk_students(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    # Get students with low performance
    at_risk_students = []
    students = Student.objects.select_related('user', 'department').filter(is_active=True)

    for student in students:
        grades = Grade.objects.filter(student=student)
        if grades.exists():
            avg_gpa = grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa']
            failing_grades = grades.filter(grade='F').count()
            total_grades = grades.count()

            # Risk criteria
            is_at_risk = (
                avg_gpa < 2.5 or  # Low GPA
                failing_grades > 0 or  # Has failing grades
                (failing_grades / total_grades) > 0.3  # High failure rate
            )

            if is_at_risk:
                # Get recent performance trend
                recent_grades = grades.order_by('-created_at')[:3]
                if recent_grades.count() >= 2:
                    recent_avg = sum(g.gpa for g in recent_grades) / len(recent_grades)
                    older_grades = grades.exclude(
                        id__in=[g.id for g in recent_grades]
                    )
                    if older_grades.exists():
                        older_avg = older_grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa']
                        trend = 'Improving' if recent_avg > older_avg else 'Declining'
                    else:
                        trend = 'New Student'
                else:
                    trend = 'Insufficient Data'

                # Risk level calculation
                if avg_gpa < 1.5 or failing_grades >= 2:
                    risk_level = 'Critical'
                elif avg_gpa < 2.0 or failing_grades >= 1:
                    risk_level = 'High'
                else:
                    risk_level = 'Medium'

                at_risk_students.append({
                    'student': student,
                    'avg_gpa': round(avg_gpa, 2),
                    'failing_grades': failing_grades,
                    'total_grades': total_grades,
                    'trend': trend,
                    'risk_level': risk_level,
                    'last_grade': grades.order_by('-created_at').first()
                })

    # Sort by risk level and GPA
    risk_order = {'Critical': 0, 'High': 1, 'Medium': 2}
    at_risk_students.sort(key=lambda x: (risk_order[x['risk_level']], x['avg_gpa']))

    # Calculate risk level counts
    critical_count = sum(1 for student in at_risk_students if student['risk_level'] == 'Critical')
    high_count = sum(1 for student in at_risk_students if student['risk_level'] == 'High')
    medium_count = sum(1 for student in at_risk_students if student['risk_level'] == 'Medium')

    context = {
        'at_risk_students': at_risk_students,
        'total_at_risk': len(at_risk_students),
        'critical_count': critical_count,
        'high_count': high_count,
        'medium_count': medium_count,
    }
    return render(request, 'sms/at_risk_students.html', context)

# Admin Panel Redirect
@login_required
def admin_panel(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    # Redirect to Django admin
    return redirect('/admin/')

# Quick Actions Views
@login_required
def assignment_tracking(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    # Get all grades as assignments
    assignments = Grade.objects.select_related('student__user', 'course__subject').all()

    context = {
        'assignments': assignments,
        'total_assignments': assignments.count(),
        'pending_assignments': assignments.filter(grade='F').count(),
        'completed_assignments': assignments.exclude(grade='F').count(),
    }
    return render(request, 'sms/assignment_tracking.html', context)

@login_required
def data_export(request):
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('sms:login')

    export_type = request.GET.get('type')

    if export_type == 'students':
        return export_students_csv(request)
    elif export_type == 'grades':
        return export_grades_csv(request)
    elif export_type == 'performance':
        return export_performance_csv(request)
    else:
        # Show export page with statistics
        context = {
            'total_students': Student.objects.filter(is_active=True).count(),
            'total_grades': Grade.objects.count(),
            'total_departments': Department.objects.count(),
            'total_courses': Course.objects.count(),
        }
        return render(request, 'sms/data_export.html', context)

def export_students_csv(request):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Name', 'Email', 'Department', 'Year', 'Phone', 'Enrollment Date', 'Status'])

    students = Student.objects.select_related('user', 'department').all()
    for student in students:
        writer.writerow([
            student.student_id,
            student.user.get_full_name(),
            student.user.email,
            student.department.name,
            student.get_year_display(),
            student.user.phone or 'N/A',
            student.enrollment_date,
            'Active' if student.is_active else 'Inactive'
        ])

    return response

def export_grades_csv(request):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="grades_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Course', 'Subject Code', 'Marks Obtained', 'Max Marks', 'Grade', 'GPA', 'Exam Date'])

    grades = Grade.objects.select_related('student__user', 'course__subject').all()
    for grade in grades:
        writer.writerow([
            grade.student.student_id,
            grade.student.user.get_full_name(),
            grade.course.subject.name,
            grade.course.subject.code,
            grade.marks_obtained,
            grade.course.max_marks,
            grade.grade,
            grade.gpa,
            grade.exam_date or 'N/A'
        ])

    return response

def export_performance_csv(request):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="performance_analysis.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Department', 'Average GPA', 'Total Grades', 'Failing Grades', 'Risk Level'])

    students = Student.objects.select_related('user', 'department').filter(is_active=True)
    for student in students:
        grades = Grade.objects.filter(student=student)
        if grades.exists():
            avg_gpa = grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa']
            failing_grades = grades.filter(grade='F').count()

            # Determine risk level
            if avg_gpa < 2.0 or failing_grades > 0:
                risk_level = 'High'
            elif avg_gpa < 2.5:
                risk_level = 'Medium'
            else:
                risk_level = 'Low'

            writer.writerow([
                student.student_id,
                student.user.get_full_name(),
                student.department.name,
                round(avg_gpa, 2),
                grades.count(),
                failing_grades,
                risk_level
            ])

    return response

@login_required
def student_dashboard(request):
    if request.user.user_type != 'student':
        messages.error(request, 'Access denied. Student privileges required.')
        return redirect('sms:login')

    try:
        student = request.user.student_profile
        grades = Grade.objects.filter(student=student).select_related('course__subject')

        # Calculate overall GPA
        avg_gpa = grades.aggregate(avg_gpa=Avg('gpa'))['avg_gpa'] or 0

        # Check for failing grades (F grades)
        failing_grades = grades.filter(grade='F')
        failing_count = failing_grades.count()

        # Create alert messages for failing grades
        if failing_count > 0:
            failing_subjects = [f"{grade.course.subject.name} (Year {grade.course.year}, Sem {grade.course.semester})" for grade in failing_grades]
            if failing_count == 1:
                messages.warning(request, f'⚠️ Academic Alert: You have received an F grade in {failing_subjects[0]}. Please contact your instructor or academic advisor for support.')
            else:
                subjects_list = ", ".join(failing_subjects)
                messages.error(request, f'🚨 Critical Academic Alert: You have received F grades in {failing_count} courses: {subjects_list}. Immediate action required - please contact your academic advisor.')

        context = {
            'student': student,
            'grades': grades,
            'avg_gpa': round(avg_gpa, 2),
            'failing_count': failing_count,
            'failing_grades': failing_grades,
        }

        return render(request, 'sms/student_dashboard.html', context)
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found. Please contact administrator.')
        return redirect('sms:login')

@login_required
def student_performance(request):
    if request.user.user_type != 'student':
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        student = request.user.student_profile
        grades = Grade.objects.filter(student=student).select_related('course__subject')

        # Prepare data for chart
        subjects = []
        marks = []

        for grade in grades:
            subjects.append(grade.course.subject.name)
            marks.append(float(grade.marks_obtained))

        data = {
            'subjects': subjects,
            'marks': marks,
        }

        return JsonResponse(data)
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student profile not found'}, status=404)
