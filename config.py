"""Application configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(BASE_DIR, 'quiz.db')}"
).replace("postgres://", "postgresql://", 1)
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
PERMANENT_SESSION_LIFETIME = 86400  # 24 hours

# Grades: (value, Arabic label)
GRADES = [
    ("first_prep", "الصف الأول الإعدادي"),
    ("second_prep", "الصف الثاني الإعدادي"),
    ("third_prep", "الصف الثالث الإعدادي"),
]

# المواد الافتراضية (تُنشأ تلقائياً لكل صف) — ترتيب العرض
DEFAULT_SUBJECTS = ["عربي", "انجليزي", "علوم", "دراسات", "رياضيات"]

# كل مادة تظهر للطلاب في يوم محدد فقط (weekday: 0=الإثنين .. 6=الأحد)
SUBJECT_BY_WEEKDAY = {
    0: "انجليزي",   # الإثنين
    1: "علوم",      # الثلاثاء
    2: "رياضيات",   # الأربعاء
    3: "دراسات",    # الخميس
    4: None,        # الجمعة
    5: None,        # السبت
    6: "عربي",      # الأحد
}

# ترتيب صور الصفحة الرئيسية: أول 3 = عمود اليمين (من فوق لتحت)، التالي 3 = عمود الشمال
# غيّر الأرقام كما تريد (مثلاً [2,1,4, 3,6,5] أو [3,1,2, 5,4,6])
HOME_IMAGES_ORDER = [4, 5, 2, 3 ,1 , 6]
