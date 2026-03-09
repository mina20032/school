# تشغيل هذا الملف من مجلد quiz_platform (الجذر):
#   python static/images/rename_to_circles.py
"""يعيد تسمية صور واتساب في هذا المجلد إلى circle1.png ... circle6.png"""

import os
import glob
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

# أي صورة (واتساب أو غيرها) نرتبها حسب الاسم ثم نعيد التسمية
exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
files = []
for ext in exts:
    files.extend(glob.glob(ext))
files = sorted(files)

# نستبعد الملفات التي هي بالفعل circle1..circle6
circle_names = {f"circle{i}.png" for i in range(1, 7)}
to_rename = [f for f in files if f not in circle_names]

if len(to_rename) > 6:
    to_rename = to_rename[:6]

if not to_rename:
    print("لا توجد صور لإعادة التسمية (أو كل الملفات بالفعل circle1..circle6).")
    exit(0)

# ننقل إلى أسماء مؤقتة أولاً حتى لا نكتب فوق ملف
temp_names = [f"_temp_{i}.png" for i in range(1, len(to_rename) + 1)]
for src, tmp in zip(to_rename, temp_names):
    if src != tmp:
        shutil.move(src, tmp)

# ثم نعيد التسمية إلى circle1.png ... circle6.png
for i, tmp in enumerate(temp_names, start=1):
    dest = f"circle{i}.png"
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(tmp, dest)
    print(f"تم: {dest}")

print(f"تمت إعادة تسمية {len(to_rename)} صورة.")
