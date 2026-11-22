"""Build the practice exam: interactive page (quiz.html) and printable PDF source (quiz-print.html)."""
import json, random, html, collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quiz_data import COURSES, Q

LET = "กขคง"
random.seed(11)
targets = [0] * 13 + [1] * 13 + [2] * 12 + [3] * 12
random.shuffle(targets)
assert len(Q) == 50, len(Q)

items = []
for i, (c, ref, diff, q, ok, wrong, exp) in enumerate(Q):
    t = targets[i]
    opts = list(wrong)
    opts.insert(t, ok)
    items.append(dict(n=i + 1, c=c, ref=ref, diff=diff, q=q, opts=opts, a=t, exp=exp))

print("answer spread:", collections.Counter(LET[x["a"]] for x in items))
print("per course:", collections.Counter(x["c"] for x in items))
print("difficulty:", collections.Counter(x["diff"] for x in items))

here = os.path.dirname(os.path.abspath(__file__))
courses = [dict(id=a, code=b, name=n) for a, b, n in COURSES]

# ---------- interactive page ----------
page = open(os.path.join(here, "quiz_template.html"), encoding="utf-8").read()
page = page.replace("/*DATA*/", "const COURSES=" + json.dumps(courses, ensure_ascii=False) +
                    ";\nconst ITEMS=" + json.dumps(items, ensure_ascii=False) + ";")
open(os.path.join(here, "quiz.html"), "w", encoding="utf-8").write(page)

# ---------- printable ----------
e = lambda s: s  # questions already contain intended inline markup (<sub>)
parts = []
for cid, code, name in COURSES:
    qs = [x for x in items if x["c"] == cid]
    parts.append(f'<section class="course"><h2>{code} · {name} <span>({len(qs)} ข้อ)</span></h2>')
    for x in qs:
        o = "".join(f"<li><b>{LET[k]}.</b> {e(v)}</li>" for k, v in enumerate(x["opts"]))
        parts.append(f'<div class="q"><p><b>{x["n"]}.</b> {e(x["q"])}</p><ol>{o}</ol></div>')
    parts.append("</section>")
key = ['<section class="course"><h2>เฉลยและคำอธิบาย</h2>']
for cid, code, name in COURSES:
    key.append(f"<h3>{code} · {name}</h3>")
    for x in [y for y in items if y["c"] == cid]:
        key.append(f'<div class="k"><b>{x["n"]}. ตอบ {LET[x["a"]]}</b> <span class="ref">หัวข้อ {x["ref"]} · {x["diff"]}</span><br>{e(x["exp"])}</div>')
key.append("</section>")

grid = "".join(f"<td><b>{x['n']}</b> {LET[x['a']]}</td>" + ("</tr><tr>" if x["n"] % 10 == 0 and x["n"] < 50 else "") for x in items)

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
<p>ปรนัย 4 ตัวเลือก รวม 50 ข้อ · อ้างอิงหัวข้อตามเอกสารสอน <i>course-notes.pdf</i></p>
<table><tr><th>รหัสวิชา</th><th>ชื่อวิชา</th><th>จำนวนข้อ</th><th>ข้อที่</th></tr>
{''.join(f"<tr><td>{code}</td><td>{name}</td><td>{sum(1 for x in items if x['c']==cid)}</td><td>{min(x['n'] for x in items if x['c']==cid)}–{max(x['n'] for x in items if x['c']==cid)}</td></tr>" for cid,code,name in COURSES)}
</table>
<div class="intro"><b>วิธีใช้:</b> ทำข้อสอบโดยไม่เปิดเอกสาร จับเวลาประมาณ 75 นาที แล้วตรวจกับเฉลยท้ายเล่ม ข้อที่ผิดให้กลับไปอ่านหัวข้อที่ระบุในเฉลย ข้อคำนวณควรใช้เครื่องคิดเลข</div>
<h3>กระดาษคำตอบ</h3>
<table class="grid"><tr>{''.join(f"<td>{n}. ____</td>" + ("</tr><tr>" if n % 10 == 0 and n < 50 else "") for n in range(1,51))}</tr></table>
{''.join(parts)}
{''.join(key)}
<h3>ตารางเฉลยย่อ</h3><table class="grid"><tr>{grid}</tr></table>
</body></html>"""
open(os.path.join(here, "quiz-print.html"), "w", encoding="utf-8").write(printable)
