from django.urls import path
from . import views

app_name = 'sms'

urlpatterns = [
    # Authentication URLs
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage-students/', views.manage_students, name='manage_students'),
    path('student-details/<int:student_id>/', views.get_student_details, name='get_student_details'),
    path('add-student/', views.add_student, name='add_student'),
    path('edit-student/<int:student_id>/', views.edit_student, name='edit_student'),
    path('delete-student/<int:student_id>/', views.delete_student, name='delete_student'),
    path('manage-grades/', views.manage_grades, name='manage_grades'),
    path('add-grade/', views.add_grade, name='add_grade'),
    path('edit-grade/<int:grade_id>/', views.edit_grade, name='edit_grade'),
    path('delete-grade/<int:grade_id>/', views.delete_grade, name='delete_grade'),
    
    # Student URLs
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student-performance/', views.student_performance, name='student_performance'),

    # New Admin URLs
    path('course-analysis/', views.course_analysis, name='course_analysis'),
    path('course-analysis-data/', views.course_analysis_data, name='course_analysis_data'),
    path('performance-trends/', views.performance_trends, name='performance_trends'),
    path('performance-trends-data/', views.performance_trends_data, name='performance_trends_data'),
    path('import-csv-data/', views.import_csv_data, name='import_csv_data'),
    path('at-risk-students/', views.at_risk_students, name='at_risk_students'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),

    # Quick Actions URLs
    path('assignment-tracking/', views.assignment_tracking, name='assignment_tracking'),
    path('data-export/', views.data_export, name='data_export'),
]
