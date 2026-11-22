"""Combine course-notes.html and quiz-print.html: each course's notes, then its exam and answer key."""
import re, os
here = os.path.dirname(os.path.abspath(__file__))
notes = open(os.path.join(here, "course-notes.html"), encoding="utf-8").read()
quiz = open(os.path.join(here, "quiz-print.html"), encoding="utf-8").read()

def body(h): return h[h.index("<body>") + 6:h.rindex("</body>")]
def sections(h, cls):
    return re.findall(r'<section class="%s"[^>]*>.*?</section>' % cls, h, flags=re.S)

nb = body(notes)
cover = re.search(r'<section class="cover">.*?</section>', nb, re.S).group(0)
chapters = sections(nb, "chapter")       # [toc, c1, c2, c3, c4]
toc, chs = chapters[0], chapters[1:]
qs = sections(body(quiz), "course")      # [exam1, key1, exam2, key2, ...]
assert len(chs) == 4 and len(qs) == 8, (len(chs), len(qs))

cover = cover.replace("<h1>เอกสารสอน 4 รายวิชา", "<h1>เอกสารสอนและข้อสอบฝึก 4 รายวิชา")
cover = cover.replace("สรุปเนื้อหาหลัก ตัวอย่างคำนวณ และแบบฝึกหัดพร้อมเฉลย",
                      "สรุปเนื้อหาหลัก ตัวอย่างคำนวณ แบบฝึกหัด และข้อสอบฝึกวิชาละ 50 ข้อพร้อมเฉลย")
how = ('<div class="box"><b>วิธีใช้:</b> อ่านเนื้อหาของแต่ละวิชาก่อน แล้วทำข้อสอบ 50 ข้อที่อยู่ท้ายวิชานั้น '
       '(ประมาณ 75 นาที ไม่เปิดเอกสาร) ตรวจกับเฉลยหน้าถัดไป ข้อที่ผิดให้กลับไปอ่านหัวข้อที่ระบุในเฉลย '
       'ข้อที่มีป้าย "เสริม" เป็นความรู้ด้านระเบียบวิธีวิจัยและการเขียนเชิงวิชาการที่ไม่ได้อยู่ในเนื้อหา</div>')
for n in range(1, 5):
    toc = toc.replace(f'<li>แบบฝึกหัด</li></ol></li>', f'<li>แบบฝึกหัด</li><li><b>ข้อสอบฝึก 50 ข้อ และเฉลย</b></li></ol>@@</li>', 1)
toc = toc.replace("@@", "")
# Seminar and Special Problems have no "แบบฝึกหัด" item: append exam entry to their lists.
toc = re.sub(r'(<li>ตัวอย่างหัวข้อ</li>)(</ol>)', r'\1<li><b>ข้อสอบฝึก 50 ข้อ และเฉลย</b></li>\2', toc)
toc = re.sub(r'(<li>แผนเวลาและเช็กลิสต์</li>)(</ol>)', r'\1<li><b>ข้อสอบฝึก 50 ข้อ และเฉลย</b></li>\2', toc)
toc = toc.replace("</ol>\n</section>", "</ol>\n" + how + "\n</section>")

def tag(s, label):  # mark quiz headings so they read as part of the course
    return s.replace('<section class="course">', '<section class="chapter">', 1).replace("<h2>", f"<h2>{label} · ", 1)
out = [cover, toc]
for i in range(4):
    out += [chs[i], tag(qs[2 * i], "ข้อสอบฝึก"), qs[2 * i + 1].replace('<section class="course">', '<section class="chapter">', 1)]

extra_css = re.search(r"<style>(.*?)</style>", quiz, re.S).group(1)
keep = "\n".join(l for l in extra_css.splitlines() if l.strip().startswith((".q", ".k", ".ref", ".grid", "h2 span")))
head = notes[:notes.index("</style>")] + "\n" + keep.replace("{{", "{").replace("}}", "}") + "\n</style>\n</head>\n<body>\n"
head = head.replace("<title>เอกสารสอน 4 รายวิชา</title>", "<title>เอกสารสอนและข้อสอบ 4 รายวิชา</title>")
open(os.path.join(here, "course-notes-with-quiz.html"), "w", encoding="utf-8").write(head + "\n".join(out) + "\n</body>\n</html>\n")
print("ok")
