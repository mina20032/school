"""Database models for the quiz platform."""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Student(db.Model):
    """Student model."""
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    grade = db.Column(db.String(50), nullable=False)
    total_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    answers = db.relationship("Answer", backref="student", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (db.Index("ix_students_grade", "grade"),)

    def __repr__(self):
        return f"<Student {self.name}>"


class Subject(db.Model):
    """Subject model."""
    __tablename__ = "subjects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    grade = db.Column(db.String(50), nullable=False)

    questions = db.relationship("Question", backref="subject", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (db.Index("ix_subjects_grade", "grade"),)

    def __repr__(self):
        return f"<Subject {self.name}>"


class Question(db.Model):
    """Question model."""
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    points = db.Column(db.Integer, default=1)

    answers = db.relationship("Answer", backref="question", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (db.Index("ix_questions_subject_id", "subject_id"),)

    def __repr__(self):
        return f"<Question {self.id}>"


class Answer(db.Model):
    """Student answer record."""
    __tablename__ = "answers"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    selected_answer = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    points_awarded = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    quiz_session_id = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    __table_args__ = (
        db.Index("ix_answers_student_id", "student_id"),
        db.Index("ix_answers_question_id", "question_id"),
        db.Index("ix_answers_submitted_at", "submitted_at"),
    )

    def __repr__(self):
        return f"<Answer student={self.student_id} question={self.question_id}>"


class User(UserMixin, db.Model):
    """Admin or Super Admin user (username + password, no email)."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin or super_admin

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    @property
    def is_super_admin(self):
        return self.role == "super_admin"

    def __repr__(self):
        return f"<User {self.username}>"


class Log(db.Model):
    """System activity log."""
    __tablename__ = "logs"
    id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(20), nullable=False, default="system")  # student, admin, super_admin, system
    action = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index("ix_logs_timestamp", "timestamp"),)

    def __repr__(self):
        return f"<Log {self.action}>"
