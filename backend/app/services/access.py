"""Record-level policy shared by student and upload endpoints.

Admins/counselors have institution-wide access; faculty are class scoped;
students may access only their explicitly linked profile.
"""
from fastapi import HTTPException
from app.models.student import Student
from app.models.user import UserRole


def ensure_student_access(db, user, student_id):
    student = db.query(Student).filter(Student.id == student_id).first()
    if student is None:
        raise HTTPException(404, "Student not found")
    if user.role == UserRole.student and student.user_id != user.id:
        raise HTTPException(403, "Access denied")
    if user.role == UserRole.faculty and (
        not user.assigned_class or student.class_name != user.assigned_class
    ):
        raise HTTPException(403, "Student is outside your assigned class")
    if user.role not in (UserRole.admin, UserRole.counselor, UserRole.faculty, UserRole.student):
        raise HTTPException(403, "Access denied")
    return student
