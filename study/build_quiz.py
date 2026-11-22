"""Build the practice exam: interactive page (quiz.html) and printable PDF source (quiz-print.html)."""
import json, random, html, collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quiz_data import COURSES, Q

from quiz_data2 import Q2

LET = "กขคง"
DRANK = {"ง่าย": 0, "ปานกลาง": 1, "ยาก": 2}
def sec(ref):
    return (9, 9) if ref == "เสริม" else tuple(int(p) for p in (ref.split(".") + ["0"])[:2])

ALL = Q + Q2
items = []
random.seed(11)
for cid, _, _ in COURSES:
    qs = [q for q in ALL if q[0] == cid]
    assert len(qs) == 50, (cid, len(qs))
    qs.sort(key=lambda q: (sec(q[1]), DRANK[q[2]]))
    targets = [0] * 13 + [1] * 13 + [2] * 12 + [3] * 12
    random.shuffle(targets)
    for i, (c, ref, diff, q, ok, wrong, exp) in enumerate(qs):
        assert len(wrong) == 3 and ok not in wrong, q
        opts = list(wrong); opts.insert(targets[i], ok)
        items.append(dict(n=i + 1, c=c, ref=ref, diff=diff, q=q, opts=opts, a=targets[i], exp=exp))
    print(cid, collections.Counter(LET[x["a"]] for x in items if x["c"] == cid),
          collections.Counter(x["diff"] for x in items if x["c"] == cid))
stems = [x["q"] for x in items]
assert len(set(stems)) == len(stems), "duplicate stem"

here = os.path.dirname(os.path.abspath(__file__))
courses = [dict(id=a, code=b, name=n) for a, b, n in COURSES]

# ---------- interactive page ----------
page = open(os.path.join(here, "quiz_template.html"), encoding="utf-8").read()
page = page.replace("/*DATA*/", "const COURSES=" + json.dumps(courses, ensure_ascii=False) +
                    ";\nconst ITEMS=" + json.dumps(items, ensure_ascii=False) + ";")
open(os.path.join(here, "quiz.html"), "w", encoding="utf-8").write(page)

# ---------- printable ----------
def sheet(nums, fill=None):
    cells = []
    for n in nums:
        cells.append(f"<td><b>{n}.</b> {fill[n] if fill else '____'}</td>")
        if n % 10 == 0 and n < max(nums):
            cells.append("</tr><tr>")
    return '<table class="grid"><tr>' + "".join(cells) + "</tr></table>"

parts = []
for cid, code, name in COURSES:
    qs = [x for x in items if x["c"] == cid]
    parts.append(f'<section class="course"><h2>{code} · {name} <span>(50 ข้อ)</span></h2>')
    parts.append("<h3>กระดาษคำตอบ</h3>" + sheet(range(1, 51)))
    parts.append('<h3>ข้อสอบ</h3>')
    for x in qs:
        o = "".join(f"<li><b>{LET[k]}.</b> {v}</li>" for k, v in enumerate(x["opts"]))
        parts.append(f'<div class="q"><p><b>{x["n"]}.</b> {x["q"]}</p><ol>{o}</ol></div>')
    parts.append("</section>")
    parts.append(f'<section class="course"><h2>เฉลย · {code} {name}</h2>')
    parts.append(sheet(range(1, 51), {x["n"]: LET[x["a"]] for x in qs}))
    parts.append("<h3>คำอธิบาย</h3>")
    for x in qs:
        parts.append(f'<div class="k"><b>{x["n"]}. ตอบ {LET[x["a"]]}</b> <span class="ref">หัวข้อ {x["ref"]} · {x["diff"]}</span><br>{x["exp"]}</div>')
    parts.append("</section>")

rows = "".join(f"<tr><td>{code}</td><td>{name}</td><td>50</td></tr>" for cid, code, name in COURSES)
printable = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><title>ข้อสอบฝึก 4 รายวิชา</title>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&display=swap" rel="stylesheet">
<style>
@page {{ size: A4; }}
body {{ font-family:'Sarabun','Loma',sans-serif; font-size:11pt; line-height:1.55; color:#1d2421; margin:0; }}
h1 {{ color:#0a7f4f; font-size:20pt; margin:0 0 4px; }}
h2 {{ background:#0a7f4f; color:#fff; font-size:14pt; padding:5px 10px; border-radius:4px; margin:0 0 10px; }}
h2 span {{ font-weight:400; font-size:11pt; }}
h3 {{ color:#0a7f4f; border-bottom:1.5px solid #0a7f4f; font-size:12.5pt; margin:14px 0 6px; break-after:avoid; }}
.course {{ break-before:page; }}
.q {{ break-inside:avoid; margin:0 0 10px; }}
.q p {{ margin:0 0 2px; }}
.q ol {{ list-style:none; margin:0; padding-left:22px; }}
.q li {{ margin:1px 0; }}
.k {{ break-inside:avoid; margin:0 0 8px; font-size:10.5pt; }}
.ref {{ color:#5b6660; font-size:9.5pt; }}
.intro {{ background:#e7f5ee; border-left:4px solid #0a7f4f; padding:8px 12px; margin:12px 0; }}
table {{ border-collapse:collapse; width:100%; font-size:10.5pt; }}
td,th {{ border:1px solid #cfd8d3; padding:4px 6px; text-align:left; }}
th {{ background:#e7f5ee; }}
.grid td {{ text-align:center; }}
</style></head><body>
<h1>ข้อสอบฝึก 4 รายวิชา</h1>
<p>ปรนัย 4 ตัวเลือก วิชาละ 50 ข้อ รวม 200 ข้อ · อ้างอิงหัวข้อตามเอกสารสอน <i>course-notes.pdf</i></p>
<table><tr><th>รหัสวิชา</th><th>ชื่อวิชา</th><th>จำนวนข้อ</th></tr>{rows}</table>
<div class="intro"><b>วิธีใช้:</b> ทำทีละวิชา จับเวลาประมาณ 75 นาทีต่อวิชา โดยไม่เปิดเอกสาร แล้วตรวจกับเฉลยที่อยู่ถัดจากข้อสอบของแต่ละวิชา ข้อที่ผิดให้กลับไปอ่านหัวข้อที่ระบุในเฉลย ข้อคำนวณควรใช้เครื่องคิดเลข<br>
ข้อที่ระบุหัวข้อ \"เสริม\" เป็นความรู้ด้านระเบียบวิธีวิจัยและการเขียนเชิงวิชาการที่ไม่ได้อยู่ในเอกสารสอน</div>
{''.join(parts)}
</body></html>"""
open(os.path.join(here, "quiz-print.html"), "w", encoding="utf-8").write(printable)
