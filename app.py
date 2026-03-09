"""Quiz Platform - Flask application (full Arabic UI)."""
import os
import uuid
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    send_from_directory,
)
from flask_login import LoginManager, login_user, logout_user
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload
from config import GRADES, DEFAULT_SUBJECTS, SUBJECT_BY_WEEKDAY, HOME_IMAGES_ORDER
from models import db, Student, Subject, Question, Answer, User, Log
from auth import student_required, admin_required, super_admin_required

app = Flask(__name__)
app.config.from_object("config")

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "الرجاء تسجيل الدخول."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def log_action(action, user_type="system"):
    log = Log(action=action, user_type=user_type)
    db.session.add(log)
    db.session.commit()


# ---------- Static at root (e.g. /sw.js) ----------
@app.route("/sw.js")
def service_worker_js():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


# ---------- Home & Student Auth ----------

@app.route("/")
def index():
    return render_template("index.html", grades=GRADES, image_order=HOME_IMAGES_ORDER)


@app.route("/student-login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        grade = request.form.get("grade")
        if not name or not grade:
            flash("الرجاء إدخال الاسم واختيار الصف.", "danger")
            return render_template("student_login.html", grades=GRADES)
        if grade not in [g[0] for g in GRADES]:
            flash("صف غير صالح.", "danger")
            return render_template("student_login.html", grades=GRADES)
        student = Student.query.filter_by(name=name, grade=grade).first()
        if not student:
            student = Student(name=name, grade=grade)
            db.session.add(student)
            db.session.commit()
            log_action(f"تسجيل طالب جديد: {name} ({grade})", user_type="student")
        session["student_id"] = student.id
        session.permanent = True
        log_action("تسجيل دخول طالب", user_type="student")
        return redirect(url_for("student_dashboard"))
    return render_template("student_login.html", grades=GRADES)


@app.route("/student-logout")
def student_logout():
    session.pop("student_id", None)
    return redirect(url_for("index"))


# ---------- Student Dashboard ----------

@app.route("/student/dashboard")
@student_required
def student_dashboard():
    student = Student.query.get_or_404(session["student_id"])
    answers = (
        Answer.query.filter_by(student_id=student.id)
        .options(joinedload(Answer.question).joinedload(Question.subject))
        .order_by(Answer.submitted_at.desc())
        .all()
    )
    sessions = {}
    total_correct_count = 0
    for a in answers:
        sid = a.quiz_session_id or f"single-{a.id}"
        if sid not in sessions:
            subj_name = a.question.subject.name if a.question and a.question.subject else "—"
            sessions[sid] = {"correct": 0, "total": 0, "points": 0, "date": a.submitted_at, "subject": subj_name}
        sessions[sid]["total"] += 1
        if a.is_correct:
            sessions[sid]["correct"] += 1
            sessions[sid]["points"] += a.points_awarded
            total_correct_count += 1
    history = list(sessions.values())
    history.sort(key=lambda x: x["date"] or datetime.min, reverse=True)
    subjects_solved = list({h["subject"] for h in history})
    return render_template(
        "student_dashboard.html",
        student=student,
        grades=GRADES,
        history=history,
        total_correct=sum(1 for a in answers if a.is_correct),
        subjects_solved=subjects_solved,
    )


# ---------- Subjects & Quiz ----------

@app.route("/student/subjects")
@student_required
def student_subjects():
    student = Student.query.get_or_404(session["student_id"])
    # كل مادة تظهر في يومها فقط
    today_weekday = datetime.now().weekday()  # 0=الإثنين .. 6=الأحد (حسب توقيت السيرفر)
    subject_name_today = SUBJECT_BY_WEEKDAY.get(today_weekday)
    if subject_name_today:
        subjects = Subject.query.filter_by(grade=student.grade, name=subject_name_today).all()
    else:
        subjects = []
    taken_ids = {
        row[0] for row in
        db.session.query(Question.subject_id).join(Answer).filter(
            Answer.student_id == student.id
        ).distinct().all()
    }
    return render_template(
        "student_subjects.html",
        student=student,
        subjects=subjects,
        grades=GRADES,
        taken_subject_ids=taken_ids,
        subject_name_today=subject_name_today,
    )


@app.route("/student/quiz/<int:subject_id>")
@student_required
def quiz_page(subject_id):
    student = Student.query.get_or_404(session["student_id"])
    subject = Subject.query.get_or_404(subject_id)
    if subject.grade != student.grade:
        flash("هذه المادة ليست لصفك.", "danger")
        return redirect(url_for("student_subjects"))
    # المادة تظهر في يومها فقط
    today_weekday = datetime.now().weekday()
    subject_name_today = SUBJECT_BY_WEEKDAY.get(today_weekday)
    if subject_name_today != subject.name:
        flash("هذه المادة غير متاحة اليوم. يمكنك حلها في يومها المحدد.", "warning")
        return redirect(url_for("student_subjects"))
    # Prevent re-taking same quiz: already submitted for this subject?
    already_taken = (
        db.session.query(Answer.id)
        .join(Question)
        .filter(Answer.student_id == student.id, Question.subject_id == subject_id)
        .limit(1)
        .first()
    )
    if already_taken:
        flash("لقد قمت بحل هذا الاختبار مسبقاً ولا يمكن حله مرة أخرى.", "warning")
        return redirect(url_for("student_subjects"))
    questions = Question.query.filter_by(subject_id=subject_id).all()
    if not questions:
        flash("لا توجد أسئلة لهذه المادة حالياً.", "info")
        return redirect(url_for("student_subjects"))
    quiz_session_id = str(uuid.uuid4())
    session["quiz_session_id"] = quiz_session_id
    session["quiz_subject_id"] = subject_id
    session["quiz_start_time"] = datetime.utcnow().isoformat()
    quiz_minutes = request.args.get("minutes", type=int) or 10
    return render_template(
        "quiz.html",
        student=student,
        subject=subject,
        questions=questions,
        quiz_session_id=quiz_session_id,
        grades=GRADES,
        quiz_minutes=quiz_minutes,
    )


@app.route("/student/quiz/submit", methods=["POST"])
@student_required
def quiz_submit():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        if hasattr(data, "to_dict"):
            data = data.to_dict(flat=False)
        else:
            data = dict(data) if data else {}
        if "answers" not in data:
            data["answers"] = {k.replace("q_", ""): v for k, v in data.items() if k.startswith("q_")}
            if isinstance(next(iter(data["answers"].values()), None), list):
                data["answers"] = {k: v[0] if isinstance(v, list) else v for k, v in data["answers"].items()}
    quiz_session_id = data.get("quiz_session_id")
    if isinstance(quiz_session_id, list):
        quiz_session_id = quiz_session_id[0] if quiz_session_id else None
    subject_id = session.get("quiz_subject_id")
    if not quiz_session_id or str(session.get("quiz_session_id")) != str(quiz_session_id):
        return jsonify({
            "success": False,
            "error": "انتهت الجلسة أو تم التحديث. لا يمكن إرسال الإجابات.",
        }), 400
    student = Student.query.get_or_404(session["student_id"])
    subject = Subject.query.get_or_404(subject_id)
    questions = {q.id: q for q in Question.query.filter_by(subject_id=subject_id).all()}
    ip_address = request.remote_addr
    total_score = 0
    results = []
    answers_data = data.get("answers") or {}
    for qid, selected in answers_data.items():
        try:
            qid = int(qid)
        except (TypeError, ValueError):
            continue
        if qid not in questions:
            continue
        selected = selected[0] if isinstance(selected, list) else selected
        q = questions[qid]
        correct = str(q.correct_answer).upper() == str(selected).upper()
        points = q.points if correct else 0
        total_score += points
        existing = Answer.query.filter_by(
            student_id=student.id,
            question_id=qid,
            quiz_session_id=quiz_session_id,
        ).first()
        if not existing:
            ans = Answer(
                student_id=student.id,
                question_id=qid,
                selected_answer=str(selected).upper(),
                is_correct=correct,
                points_awarded=points,
                quiz_session_id=quiz_session_id,
                ip_address=ip_address,
            )
            db.session.add(ans)
        results.append({
            "question_id": qid,
            "selected": str(selected).upper(),
            "correct_answer": q.correct_answer,
            "is_correct": correct,
            "points": points,
        })
    student.total_points += total_score
    db.session.commit()
    session.pop("quiz_session_id", None)
    session.pop("quiz_subject_id", None)
    session.pop("quiz_start_time", None)
    log_action(f"تسليم اختبار: {subject.name}، النقاط: {total_score}", user_type="student")
    total_possible = sum(q.points for q in questions.values())
    if request.is_json:
        return jsonify({
            "success": True,
            "total_score": total_score,
            "results": results,
            "total_possible": total_possible,
        })
    flash(f"تم تسليم الاختبار! نتيجتك: {total_score} / {total_possible} نقطة.", "success")
    return redirect(url_for("student_dashboard"))


# ---------- Student Marathon Leaderboard ----------

@app.route("/marathon")
def marathon():
    students = Student.query.order_by(Student.total_points.desc()).all()
    grades_dict = dict(GRADES)
    return render_template("marathon.html", students=students, grades_dict=grades_dict)


# ---------- Admin: single login at /admin (hidden from students) ----------

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            session["user_id"] = user.id
            session["user_role"] = user.role
            session.permanent = True
            log_action(f"تسجيل دخول: {username} ({user.role})", user_type=user.role)
            if user.role == "super_admin":
                return redirect(url_for("super_admin_dashboard"))
            return redirect(url_for("admin_dashboard"))
        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "danger")
    return render_template("admin_login.html")


@app.route("/admin/logout")
@admin_required
def admin_logout():
    uid = session.get("user_id")
    if uid:
        u = db.session.get(User,uid)
        if u:
            log_action(f"تسجيل خروج: {u.username}", user_type=u.role)
    session.pop("user_id", None)
    session.pop("user_role", None)
    logout_user()
    return redirect(url_for("index"))


# ---------- Admin Dashboard ----------

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    user = User.query.get_or_404(session["user_id"])
    if user.role == "super_admin":
        return redirect(url_for("super_admin_dashboard"))
    subjects = Subject.query.order_by(Subject.grade, Subject.name).all()
    students_count = Student.query.count()
    return render_template("admin_dashboard.html", user=user, subjects=subjects, students_count=students_count, grades=GRADES, default_subjects=DEFAULT_SUBJECTS)


# ---------- Admin: Subjects ----------

@app.route("/admin/subjects")
@admin_required
def admin_subjects():
    user = db.session.get(User,session["user_id"])
    subjects = Subject.query.order_by(Subject.grade, Subject.name).all()
    return render_template("admin_subjects.html", user=user, subjects=subjects, grades=GRADES)


@app.route("/admin/subjects/<int:subject_id>/delete", methods=["POST"])
@admin_required
def admin_subject_delete(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    name = subject.name
    db.session.delete(subject)
    db.session.commit()
    log_action(f"حذف مادة: {name}", user_type="admin")
    flash("تم حذف المادة.", "success")
    return redirect(url_for("admin_subjects"))


# ---------- Admin: Questions ----------

@app.route("/admin/subjects/<int:subject_id>/questions")
@admin_required
def admin_questions(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    questions = Question.query.filter_by(subject_id=subject_id).order_by(Question.id).all()
    return render_template("admin_questions.html", user=db.session.get(User,session["user_id"]), subject=subject, questions=questions)


@app.route("/admin/questions/add", methods=["GET", "POST"])
@admin_required
def admin_question_add():
    user = db.session.get(User,session["user_id"])
    subjects = Subject.query.order_by(Subject.grade, Subject.name).all()
    if request.method == "POST":
        subject_id = request.form.get("subject_id", type=int)
        question_text = (request.form.get("question_text") or "").strip()
        option_a = (request.form.get("option_a") or "").strip()
        option_b = (request.form.get("option_b") or "").strip()
        option_c = (request.form.get("option_c") or "").strip()
        option_d = (request.form.get("option_d") or "").strip()
        correct_answer = (request.form.get("correct_answer") or "A").upper()
        points = request.form.get("points", type=int) or 1
        if subject_id and question_text and option_a and option_b and option_c and option_d and correct_answer in "ABCD":
            q = Question(
                subject_id=subject_id,
                question_text=question_text,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
                correct_answer=correct_answer,
                points=points,
            )
            db.session.add(q)
            db.session.commit()
            log_action(f"إضافة سؤال لمادة id={subject_id}", user_type=user.role)
            flash("تمت إضافة السؤال.", "success")
            if request.form.get("add_another"):
                return redirect(url_for("admin_question_add", subject_id=subject_id))
            return redirect(url_for("admin_questions", subject_id=subject_id))
        flash("الرجاء تعبئة كل الحقول واختيار الإجابة الصحيحة.", "danger")
    preselected_grade = None
    sid = request.args.get("subject_id", type=int)
    if sid:
        sub = Subject.query.get(sid)
        if sub:
            preselected_grade = sub.grade
    return render_template("admin_question_form.html", user=user, subjects=subjects, question=None, grades=GRADES, preselected_grade=preselected_grade, preselected_subject_id=sid)


@app.route("/admin/questions/<int:question_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_question_edit(question_id):
    user = db.session.get(User,session["user_id"])
    question = Question.query.get_or_404(question_id)
    subjects = Subject.query.all()
    if request.method == "POST":
        question.subject_id = request.form.get("subject_id", type=int) or question.subject_id
        question.question_text = (request.form.get("question_text") or "").strip() or question.question_text
        question.option_a = (request.form.get("option_a") or "").strip() or question.option_a
        question.option_b = (request.form.get("option_b") or "").strip() or question.option_b
        question.option_c = (request.form.get("option_c") or "").strip() or question.option_c
        question.option_d = (request.form.get("option_d") or "").strip() or question.option_d
        question.correct_answer = (request.form.get("correct_answer") or "A").upper()
        question.points = request.form.get("points", type=int) or 1
        db.session.commit()
        log_action(f"تعديل سؤال id={question_id}", user_type=user.role)
        flash("تم تحديث السؤال.", "success")
        return redirect(url_for("admin_questions", subject_id=question.subject_id))
    preselected_grade = question.subject.grade if question and question.subject else None
    return render_template("admin_question_form.html", user=user, subjects=subjects, question=question, grades=GRADES, preselected_grade=preselected_grade, preselected_subject_id=question.subject_id if question else None)


@app.route("/admin/questions/<int:question_id>/delete", methods=["POST"])
@admin_required
def admin_question_delete(question_id):
    question = Question.query.get_or_404(question_id)
    subject_id = question.subject_id
    db.session.delete(question)
    db.session.commit()
    log_action(f"حذف سؤال id={question_id}", user_type="admin")
    flash("تم حذف السؤال.", "success")
    return redirect(url_for("admin_questions", subject_id=subject_id))


# ---------- Admin: Results ----------

@app.route("/admin/results")
@admin_required
def admin_results():
    user = db.session.get(User,session["user_id"])
    answers = (
        Answer.query.options(
            joinedload(Answer.student),
            joinedload(Answer.question).joinedload(Question.subject),
        )
        .order_by(Answer.submitted_at.desc())
        .limit(500)
        .all()
    )
    return render_template("admin_results.html", user=user, answers=answers)


# ---------- Super Admin ----------

@app.route("/admin/super")
@super_admin_required
def super_admin_dashboard():
    user = User.query.get_or_404(session["user_id"])
    students = Student.query.order_by(Student.created_at.desc()).all()
    users = User.query.all()
    logs = Log.query.order_by(Log.timestamp.desc()).limit(200).all()
    return render_template("super_admin_dashboard.html", user=user, students=students, users=users, logs=logs, grades=GRADES)


@app.route("/admin/super/students/<int:student_id>/delete", methods=["POST"])
@super_admin_required
def super_admin_student_delete(student_id):
    student = Student.query.get_or_404(student_id)
    name = student.name
    sid = student.id
    db.session.delete(student)
    db.session.commit()
    log_action(f"حذف طالب: {name} (id={sid})", user_type="super_admin")
    flash("تم حذف الطالب.", "success")
    return redirect(url_for("super_admin_dashboard"))


@app.route("/admin/super/admins", methods=["GET", "POST"])
@super_admin_required
def super_admin_admins():
    user = db.session.get(User,session["user_id"])
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            role = request.form.get("role") or "admin"
            if username and password and role in ("admin", "super_admin"):
                if User.query.filter_by(username=username).first():
                    flash("اسم المستخدم موجود مسبقاً.", "danger")
                else:
                    u = User(username=username, role=role)
                    u.set_password(password)
                    db.session.add(u)
                    db.session.commit()
                    log_action(f"إنشاء مستخدم: {username}", user_type="super_admin")
                    flash("تم إنشاء المستخدم.", "success")
            else:
                flash("الرجاء تعبئة كل الحقول.", "danger")
        elif action == "delete":
            uid = request.form.get("user_id", type=int)
            if uid and uid != user.id:
                u = db.session.get(User,uid)
                if u:
                    db.session.delete(u)
                    db.session.commit()
                    log_action(f"حذف مستخدم: {u.username}", user_type="super_admin")
                    flash("تم حذف المستخدم.", "success")
        elif action == "password":
            uid = request.form.get("user_id", type=int)
            new_password = request.form.get("new_password") or ""
            if uid and new_password:
                u = db.session.get(User,uid)
                if u:
                    u.set_password(new_password)
                    db.session.commit()
                    log_action(f"تغيير كلمة مرور: {u.username}", user_type="super_admin")
                    flash("تم تحديث كلمة المرور.", "success")
        return redirect(url_for("super_admin_admins"))
    users = User.query.all()
    return render_template("super_admin_admins.html", user=user, users=users)


@app.route("/admin/super/attempts")
@super_admin_required
def super_admin_attempts():
    user = db.session.get(User,session["user_id"])
    answers = (
        Answer.query.options(
            joinedload(Answer.student),
            joinedload(Answer.question).joinedload(Question.subject),
        )
        .order_by(Answer.submitted_at.desc())
        .all()
    )
    return render_template("super_admin_attempts.html", user=user, answers=answers)


# ---------- Init DB & Seed ----------

def init_db():
    with app.app_context():
        db.create_all()
        # Add missing columns to existing DB (e.g. answers.ip_address)
        try:
            db.session.execute(text("ALTER TABLE answers ADD COLUMN ip_address VARCHAR(45)"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # المواد الافتراضية: رياضيات، عربي، انجليزي، علوم، دراسات (لكل صف)
        for grade_value, _ in GRADES:
            for subj_name in DEFAULT_SUBJECTS:
                if Subject.query.filter_by(name=subj_name, grade=grade_value).first() is None:
                    db.session.add(Subject(name=subj_name, grade=grade_value))
        db.session.commit()
        # مشرف أعلى افتراضي
        if db.session.execute(select(User).where(User.username == "super")).scalar_one_or_none() is None:
            u = User(username="super", role="super_admin")
            u.set_password("super123")
            db.session.add(u)
            db.session.commit()
            print("Default super admin created: username=super, password=super123")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
