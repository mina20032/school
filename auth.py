"""Authentication helpers."""
from functools import wraps
from flask import session, redirect, url_for, flash
from models import db, User


def student_required(f):
    """Require student to be logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "student_id" not in session:
            flash("الرجاء إدخال الاسم والصف للمتابعة.", "info")
            return redirect(url_for("student_login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require admin or super_admin to be logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("الرجاء تسجيل الدخول.", "warning")
            return redirect(url_for("admin_login"))
        user = db.session.get(User, session["user_id"])
        if not user:
            session.pop("user_id", None)
            session.pop("user_role", None)
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    """Require super_admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("الرجاء تسجيل الدخول.", "warning")
            return redirect(url_for("admin_login"))
        user = db.session.get(User, session["user_id"])
        if not user or user.role != "super_admin":
            flash("صلاحيات المشرف الأعلى مطلوبة.", "danger")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated
