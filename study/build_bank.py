"""Build the Commercial Banking chapter guide (PDF source) and chapter quiz page from bank_chapters.py."""
import os, re, json, random, collections, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from bank_chapters import CH

LET = "กขคง"; DR = {"ง่าย": 0, "ปานกลาง": 1, "ยาก": 2}
random.seed(3)
items = []
for ch in CH:
    qs = sorted(ch["questions"], key=lambda q: (q[0], DR[q[1]]))
    n = len(qs); base = [k for k in range(4) for _ in range(n // 4)] + list(range(n % 4))
    random.shuffle(base)
    for i, (ref, diff, q, ok, wrong, exp) in enumerate(qs):
        assert len(wrong) == 3 and ok not in wrong and len(set(wrong)) == 3, q
        opts = list(wrong); opts.insert(base[i], ok)
        items.append(dict(n=i + 1, c=ch["id"], ref=ref, diff=diff, q=q, opts=opts, a=base[i], exp=exp))
    print(ch["id"], n, collections.Counter(LET[x["a"]] for x in items if x["c"] == ch["id"]),
          collections.Counter(x["diff"] for x in items if x["c"] == ch["id"]))

# ---------- printable guide ----------
notes = open(os.path.join(here, "course-notes.html"), encoding="utf-8").read()
css = re.search(r"<style>(.*?)</style>", notes, re.S).group(1)
css += """
.q { break-inside: avoid; margin: 0 0 10px; } .q p { margin: 0 0 2px; }
.q ol { list-style: none; margin: 0; padding-left: 22px; } .q li { margin: 1px 0; }
.k { break-inside: avoid; margin: 0 0 8px; font-size: 10.5pt; } .ref { color: #5b6660; font-size: 9.5pt; }
.grid td { text-align: center; } h2 span { font-weight: 400; font-size: 11pt; }
"""
def sheet(qs, fill=False):
    cells = []
    for x in qs:
        cells.append(f"<td><b>{x['n']}.</b> {LET[x['a']] if fill else '____'}</td>")
        if x["n"] % 10 == 0 and x["n"] < len(qs): cells.append("</tr><tr>")
    return '<table class="grid"><tr>' + "".join(cells) + "</tr></table>"

body = []
body.append(f"""<section class="cover">
<div class="small">03759441 การธนาคารพาณิชย์ (Commercial Banking) · หมู่ 850</div>
<h1>สรุปบทเรียนและแบบทดสอบ<br>การธนาคารพาณิชย์ บทที่ 1–{len(CH)}</h1>
<p class="sub">เรียบเรียงตามสไลด์ของ ผศ.ดร.สิตาภา บัวเกษ พร้อมแบบทดสอบท้ายบทและเฉลย</p>
<table><tr><th>บท</th><th>เรื่อง</th><th>แบบทดสอบ</th></tr>
{''.join(f"<tr><td>{c['no']}</td><td>{c['title']}<br><span class='small'>{c['en']}</span></td><td>{len(c['questions'])} ข้อ</td></tr>" for c in CH)}
</table>
<div class="box" style="margin-top:18px"><b>วิธีใช้:</b> อ่านสรุปของแต่ละบท แล้วทำแบบทดสอบท้ายบทโดยไม่เปิดเอกสาร ตรวจกับเฉลยหน้าถัดไป ข้อที่ผิดให้กลับไปอ่านหัวข้อที่ระบุในเฉลย · โจทย์คำนวณในแบบทดสอบบทที่ 3 ใช้ "ธนาคาร B" ซึ่งเป็นตัวเลขสมมติชุดใหม่ ไม่ซ้ำกับตัวอย่างในสไลด์</div>
<div class="warn">เอกสารนี้สรุปจากสไลด์เพื่อการทบทวน ใช้คู่กับสไลด์และคำอธิบายของอาจารย์ในชั้นเรียน</div>
</section>""")
for ch in CH:
    qs = [x for x in items if x["c"] == ch["id"]]
    body.append(f'<section class="chapter"><h2>บทที่ {ch["no"]} · {ch["title"]} <span>{ch["en"]}</span></h2>{ch["html"]}</section>')
    ex = [f'<section class="chapter"><h2>แบบทดสอบท้ายบทที่ {ch["no"]} <span>({len(qs)} ข้อ)</span></h2><h3>กระดาษคำตอบ</h3>{sheet(qs)}<h3>ข้อสอบ</h3>']
    for x in qs:
        o = "".join(f"<li><b>{LET[k]}.</b> {v}</li>" for k, v in enumerate(x["opts"]))
        ex.append(f'<div class="q"><p><b>{x["n"]}.</b> {x["q"]}</p><ol>{o}</ol></div>')
    ex.append("</section>")
    ex.append(f'<section class="chapter"><h2>เฉลยแบบทดสอบบทที่ {ch["no"]}</h2>{sheet(qs, True)}<h3>คำอธิบาย</h3>')
    for x in qs:
        ex.append(f'<div class="k"><b>{x["n"]}. ตอบ {LET[x["a"]]}</b> <span class="ref">หัวข้อ {x["ref"]} · {x["diff"]}</span><br>{x["exp"]}</div>')
    ex.append("</section>")
    body += ex
html = f"""<!doctype html><html lang="th"><head><meta charset="utf-8"><title>การธนาคารพาณิชย์ บทที่ 1–{len(CH)}</title>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>{css}</style></head><body>
{''.join(body)}
</body></html>"""
open(os.path.join(here, "bank-chapters.html"), "w", encoding="utf-8").write(html)

# ---------- interactive quiz ----------
t = open(os.path.join(here, "quiz_template.html"), encoding="utf-8").read()
courses = [dict(id=c["id"], code=f"บทที่ {c['no']}", name=c["title"]) for c in CH]
t = t.replace("/*DATA*/", "const COURSES=" + json.dumps(courses, ensure_ascii=False) + ";\nconst ITEMS=" + json.dumps(items, ensure_ascii=False) + ";")
t = t.replace("<title>ข้อสอบฝึกการเงิน 4 วิชา</title>", "<title>แบบทดสอบการธนาคารพาณิชย์</title>")
t = t.replace("<h1>ข้อสอบฝึก 4 รายวิชาการเงิน</h1>", "<h1>แบบทดสอบท้ายบท การธนาคารพาณิชย์</h1>")
t = re.sub(r'<p class="lede">.*?</p>', f'<p class="lede">03759441 · บทที่ 1–{len(CH)} ตามสไลด์ของอาจารย์ บทละ 20 ข้อ เลือกคำตอบแล้วเฉลยจะขึ้นทันที คะแนนแยกตามบทบอกว่าควรกลับไปทบทวนหัวข้อใด</p>', t, flags=re.S)
t = t.replace('const KEY = "fin4-quiz-v2";', 'const KEY = "bank-ch-quiz-v1";')
assert "bank-ch-quiz-v1" in t and "แบบทดสอบท้ายบท" in t
open(os.path.join(here, "bank-quiz.html"), "w", encoding="utf-8").write(t)
print("built")
