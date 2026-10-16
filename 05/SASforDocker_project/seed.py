"""seed.py — 產生擬真種子資料（大學版）

執行方式: python seed.py
隨機生成約 224 名學生、57 位教職員、170+ 課程、成績、點名、
選課、繳費單、獎助學金、獎懲、公告等，展現各模組資料。

會自動檢查 database 是否已有資料，避免重複產生（--force 可重建）。
"""
import os
import random
import sys
import datetime

from db import get_conn, hash_pw, init_db, is_seeded, DB_PATH

RNG = random.Random(2026)

SEMESTER = "113-1"
SCHOOL_NAME = "國立海嶼大學"

# ---------------------------------------------------------------- 校務資料

COLLEGES = [
    (1, "SE", "理工學院"),
    (2, "MGT", "管理學院"),
    (3, "HU", "人文社會學院"),
    (4, "HN", "健康護理學院"),
]

# (college_id, code, name, 代表課名清單)
DEPT_DATA = [
    (1, 11, "資訊工程學系", [
        "程式設計(一)", "計算機概論", "微積分(一)", "離散數學", "線性代數",
        "資料結構", "物件導向程式設計", "數位系統設計", "機率與統計", "作業系統",
        "演算法", "計算機組織", "資料庫系統", "網路概論", "軟體工程",
        "專題製作(一)", "人工智慧導論", "資訊安全導論", "雲端運算概論", "嵌入式系統",
    ]),
    (1, 12, "電機工程學系", [
        "微積分(一)", "普通物理(一)", "電路學(一)", "工程數學(一)", "數位邏輯設計",
        "電子學(一)", "電機機械", "訊號與系統", "電磁學(一)", "控制系統",
        "通訊原理", "微處理機系統", "電力系統導論", "半導體元件導論", "綠能科技概論",
        "機器人導論", "高頻電路設計", "自動控制實習", "智慧電網概論", "系統晶片設計導論",
    ]),
    (2, 21, "企業管理學系", [
        "管理學", "經濟學(一)", "會計學(一)", "統計學", "企業概論",
        "行銷管理", "人力資源管理", "財務管理", "作業管理", "組織行為",
        "策略管理", "消費者行為", "商業溝通", "企業倫理", "電子商務概論",
        "創新與創業管理", "國際企業管理", "商管專題(一)", "資料分析導論", "服務業管理",
    ]),
    (2, 22, "觀光管理學系", [
        "觀光學概論", "餐旅經營管理", "旅館管理", "旅行業管理", "觀光心理與行為",
        "遊憩資源規劃", "航空運輸管理", "節慶與活動管理", "觀光英文", "餐旅服務實務",
        "觀光行銷", "導覽解說實務", "會議與展覽管理", "休閒產業分析", "島嶼觀光特論",
        "永續旅遊規劃", "民宿經營管理", "觀光統計分析", "導遊領隊實務(一)", "遊程規劃設計",
    ]),
    (3, 31, "應用英語學系", [
        "英語會話(一)", "英語聽講練習", "英文文法與句型", "英文閱讀與寫作(一)", "英語發音練習",
        "語言學概論", "西洋文學概論", "翻譯入門", "商用英文(一)", "英語教學概論",
        "跨文化溝通", "新聞英文", "英語簡報技巧", "觀光英語概論", "第二外語概論",
        "文學導讀", "電腦輔助翻譯", "職場英語會話", "英語語言史", "戲劇選讀",
    ]),
    (4, 41, "護理學系", [
        "人體解剖學", "生理學(一)", "護理學導論", "基本護理學", "藥理學",
        "內外科護理學(一)", "產科護理學", "小兒科護理學", "社區衛生護理學", "精神科護理學",
        "護理行政", "護理研究概論", "老人護理學", "長期照護概論", "急重症護理學",
        "護理倫理與法律", "健康促進", "護理專業實習(一)", "營養學概論", "感染管制概論",
    ]),
    (4, 42, "社會工作學系", [
        "社會工作概論", "社會學", "心理學", "社會福利概論", "社會統計",
        "社會工作倫理", "個案工作", "團體工作", "社區工作", "社會心理學",
        "方案設計與評估", "家庭社會工作", "老人社會工作", "身心障礙社會工作", "社會政策與立法",
        "社工實習(一)", "諮商理論與技術", "性別與社會工作", "志願服務管理", "社會資源運用",
    ]),
]

GEN_ED_COURSES = [  # (name, course_type, credits, min_grade, max_grade)
    ("大一國文", "通識", 2, 1, 1),
    ("大一英文", "通識", 2, 1, 1),
    ("體育(一)", "體育", 2, 1, 2),
    ("資訊素養", "核心通識", 2, 1, 4),
    ("環境與永續", "核心通識", 2, 1, 4),
    ("生命教育", "核心通識", 2, 1, 4),
    ("海洋文化導論", "核心通識", 2, 1, 4),
]

CORE_GEN_ED_SEQ = 3  # 前 3 筆為通識/體育，其餘為核心通識

# 每系/年級必修人數
REQ_PER_GRADE = 5
# 每系系選修門數
DEP_ELECTIVES = 4

SURNAMES = list("陳林黃張李王吳劉蔡楊許鄭謝郭洪邱曾廖賴徐周葉蘇莊江呂何羅高蕭潘簡朱鍾游彭詹胡施沈盧余趙顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁卓馬董唐藍蔣石紀姚連馮歐陽程湯田古甘姜齊")
TITLES_WEIGHT = ["教授"] * 18 + ["副教授"] * 22 + ["助理教授"] * 28 + ["講師"] * 20 + ["助教"] * 12

MALE_GIVEN = ["家豪", "志明", "俊宏", "建宏", "國豪", "文傑", "俊傑", "柏翰", "冠宇", "庭宇",
              "宗翰", "育成", "孟哲", "子軒", "承翰", "宇軒", "柏凱", "彥廷", "睿霖", "維哲",
              "鈞皓", "宗諺", "立宏", "秉宸", "祐誠", "廷恩", "博宇", "俊宇", "書豪", "哲銘"]
FEMALE_GIVEN = ["雅婷", "怡君", "欣怡", "宜靜", "婉婷", "佳穎", "嘉惠", "惠如", "淑芬", "美玲",
                "玉潔", "佩珊", "曉雯", "靜怡", "思涵", "心怡", "珮琪", "郁婷", "依珊", "芳儀",
                "姿吟", "筱婷", "于晴", "宜臻", "詩涵", "采薇", "昱萱", "品涵", "芷菱", "孟恬"]


def rand_name(rng):
    gender = rng.choice(["男", "女"])
    sur = rng.choice(SURNAMES)
    given = rng.choice(MALE_GIVEN if gender == "男" else FEMALE_GIVEN)
    return sur + given, gender


def rand_date(rng, year, y0, y1):
    m = rng.randint(y0, y1)
    d = rng.randint(1, 28)
    return f"{year}-{m:02d}-{d:02d}"


def overlaps(as_, ae, bs, be):
    return not (ae < bs or be < as_)


def pick_block(rng, occupied, count, max_start=9):
    """隨機挑一個不衝突的 (weekday, start, end)。occupied 為 (wd, s, e) 列表。"""
    for _ in range(400):
        wd = rng.randint(1, 5)
        s = rng.randint(1, max_start - count + 1)
        e = s + count - 1
        if all(not (wd == ow and overlaps(s, e, os_, oe)) for (ow, os_, oe) in occupied):
            occupied.append((wd, s, e))
            return wd, s, e
    raise RuntimeError("無法安排不衝突時段")


def grade_letter_gpa(total):
    if total >= 90: return "A+", 4.3
    if total >= 85: return "A", 4.0
    if total >= 80: return "A-", 3.7
    if total >= 77: return "B+", 3.3
    if total >= 73: return "B", 3.0
    if total >= 70: return "B-", 2.7
    if total >= 67: return "C+", 2.3
    if total >= 63: return "C", 2.0
    if total >= 60: return "C-", 1.7
    if total >= 50: return "D", 1.0
    return "F", 0.0


def main(force=False):
    if is_seeded() and not force:
        print("[seed] 資料庫已有資料，略過。若要重建請加 --force")
        return
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    conn = get_conn()
    rng = RNG

    # ---------------- 節次表
    day = [(1, "第1節", "08:10", "09:00"), (2, "第2節", "09:10", "10:00"),
           (3, "第3節", "10:10", "11:00"), (4, "第4節", "11:10", "12:00"),
           (5, "第5節", "13:10", "14:00"), (6, "第6節", "14:10", "15:00"),
           (7, "第7節", "15:10", "16:00"), (8, "第8節", "16:10", "17:00"),
           (9, "第9節", "17:10", "18:00")]
    night = [(10, "第A節", "18:30", "19:20"), (11, "第B節", "19:30", "20:20"),
             (12, "第C節", "20:30", "21:20")]
    for pid, name, st, et in day + night:
        conn.execute("INSERT INTO periods (id,name,start_time,end_time,is_night) VALUES (?,?,?,?,?)",
                     (pid, name, st, et, 1 if pid >= 10 else 0))

    # ---------------- 學院 / 系所
    for cid, code, name in COLLEGES:
        conn.execute("INSERT INTO colleges (id,code,name) VALUES (?,?,?)", (cid, code, name))
    dept_rows = []
    for college_id, code, name, _ in DEPT_DATA:
        cur = conn.execute(
            "INSERT INTO departments (college_id,code,name,grad_credits) VALUES (?,?,?,?)",
            (college_id, code, name, 128))
        dept_rows.append({"id": cur.lastrowid, "code": code, "name": name})
    dept_by_code = {d["code"]: d["id"] for d in dept_rows}

    # ---------------- 教職員
    teacher_busy = {}   # faculty_id -> [(wd,s,e)]
    room_busy = {}      # room -> [(wd,s,e)]
    room_pool = ["教學大樓", "理工大樓", "人文大樓", "管理大樓", "實驗大樓"]
    fac_by_dept = {}
    fac_ids = []
    for d in dept_rows:
        fac_by_dept.setdefault(d["id"], [])
        for _ in range(7):
            name, g = rand_name(rng)
            cur = conn.execute(
                """INSERT INTO faculties
                   (dept_id,name,gender,title,email,office,phone,hire_date,status)
                   VALUES (?,?,?,?,?,?,?,?, '在職')""",
                (d["id"], name, g, rng.choice(TITLES_WEIGHT),
                 f"{d['code']}f{len(fac_ids)+1}@niu.edu.tw",
                 f"{rng.choice(room_pool)} {rng.randint(201, 899)}",
                 f"082-31{rng.randint(3000, 3999)}",
                 f"{rng.randint(1998, 2022)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"))
            fac_ids.append(cur.lastrowid)
            fac_by_dept[d["id"]].append(cur.lastrowid)
            teacher_busy[cur.lastrowid] = []
    # 通識中心教師（dept_id NULL）
    gen_fac_ids = []
    for _ in range(8):
        name, g = rand_name(rng)
        cur = conn.execute(
            """INSERT INTO faculties
               (dept_id,name,gender,title,email,office,phone,hire_date,status)
               VALUES (NULL,?,?,?,?,?,?,?, '在職')""",
            (name, g, rng.choice(TITLES_WEIGHT), f"gen{len(gen_fac_ids)+1}@niu.edu.tw",
             f"通識教育中心 {rng.randint(101, 599)}",
             f"082-31{rng.randint(2000, 2999)}",
             f"{rng.randint(2000, 2022)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"))
        gen_fac_ids.append(cur.lastrowid)
        teacher_busy[cur.lastrowid] = []

    # ---------------- 學生
    student_ids = []          # list of dict
    demo_student = None
    dept_global_seq = {d["id"]: 0 for d in dept_rows}
    for d in dept_rows:
        for grade in range(1, 5):
            group_key = (d["id"], grade)
            occupied_group = []
            for seq_class in range(1, 9):
                dept_global_seq[d["id"]] += 1
                seq = dept_global_seq[d["id"]]
                name, g = rand_name(rng)
                enroll_year = 113
                birth_ad = 2006 - (grade - 1)
                student_no = f"{enroll_year}{d['code']}{seq:03d}"
                birth = rand_date(rng, birth_ad, 1, 12)
                cur = conn.execute(
                    """INSERT INTO students
                       (dept_id,student_no,name,gender,birth_date,grade,class_no,
                        enroll_year,status,address,phone,email,guardian_name,guardian_phone)
                       VALUES (?,?,?,?,?,?,?,?, '在學',?,?,?,?,?)""",
                    (d["id"], student_no, name, g, birth, grade, seq, enroll_year,
                     f"{rng.choice(['金門縣金寧鄉','金門縣金城鎮','金門縣金沙鎮','金門縣金湖鎮'])} {rng.randint(1,399)}號",
                     f"09{rng.randint(10,99)}-{rng.randint(100,999)}-{rng.randint(100,999)}",
                     f"{student_no}@niu.edu.tw",
                     rand_name(rng)[0], f"09{rng.randint(10,99)}-{rng.randint(100,999)}-{rng.randint(100,999)}"))
                sid = cur.lastrowid
                student_ids.append({"id": sid, "dept_id": d["id"], "grade": grade,
                                    "no": student_no, "name": name})
                conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?,?,?,?,?)",
                             (student_no, hash_pw("123456"), "student", sid, name, d["id"]))
                if demo_student is None and d["code"] == 11 and grade == 1:
                    demo_student = sid
                occupied_group.append(None)  # 佔位，group 衝突用 group_busy

    # group(系+年級) 已佔用時段（必修不互撞）
    group_busy = {(d["id"], g): [] for d in dept_rows for g in range(1, 5)}

    # ---------------- 課程
    course_rows = []
    course_seq = 0
    for d in dept_rows:
        dept_id, dept_code = d["id"], d["code"]
        pool = DEPT_DATA[[i for i, x in enumerate(DEPT_DATA) if x[1] == dept_code][0]][3]
        # 必修：每年級 REQ_PER_GRADE 門
        for grade in range(1, 5):
            group_key = (dept_id, grade)
            for i in range(REQ_PER_GRADE):
                cname = pool[(grade - 1) * REQ_PER_GRADE + i]
                cred = 3
                wd, ps, pe = pick_block(rng, group_busy[group_key], cred)
                teacher = rng.choice(fac_by_dept[dept_id])
                t_occ = teacher_busy[teacher]
                if any(ow == wd and overlaps(ps, pe, os_, oe) for (ow, os_, oe) in t_occ):
                    wd2, ps2, pe2 = pick_block(rng, teacher_busy[teacher], cred)
                    if any(ow == wd2 and overlaps(ps2, pe2, os_, oe) for (ow, os_, oe) in group_busy[group_key]):
                        pass  # 與同班課衝突機率極低，接受
                    else:
                        wd, ps, pe = wd2, ps2, pe2
                teacher_busy[teacher].append((wd, ps, pe))
                room = f"{rng.choice(room_pool)} {rng.randint(101, 899)}"
                if not any(ow == wd and overlaps(ps, pe, os_, oe) for (ow, os_, oe) in room_busy.setdefault(room, [])):
                    room_busy[room].append((wd, ps, pe))
                course_seq += 1
                code = f"{dept_code}{course_seq:03d}"
                cur = conn.execute(
                    """INSERT INTO courses
                       (dept_id,code,name,credits,course_type,semester,restriction_dept,
                        restriction_grade,teacher_id,weekday,period_start,period_end,room,max_students,status)
                       VALUES (?,?,?,?, '系必修', ?, ?, ?, ?, ?, ?, ?, ?, 60, '開課')""",
                    (dept_id, code, cname, cred, SEMESTER, dept_id, str(grade),
                     teacher, wd, ps, pe, room))
                course_rows.append({"id": cur.lastrowid, "dept_id": dept_id,
                                    "grade": grade, "type": "系必修",
                                    "credits": cred, "name": cname})
        # 系選修：DEP_ELECTIVES 門（全年級）
        for i in range(DEP_ELECTIVES):
            cname = pool[len(pool) // 2 + i]
            cred = rng.choice([2, 3])
            wd, ps, pe = pick_block(rng, [], cred)
            teacher = rng.choice(fac_by_dept[dept_id])
            if any(ow == wd and overlaps(ps, pe, os_, oe) for (ow, os_, oe) in teacher_busy[teacher]):
                wd, ps, pe = pick_block(rng, teacher_busy[teacher], cred)
            teacher_busy[teacher].append((wd, ps, pe))
            room = f"{rng.choice(room_pool)} {rng.randint(101, 899)}"
            course_seq += 1
            code = f"{dept_code}{course_seq:03d}"
            cur = conn.execute(
                """INSERT INTO courses
                   (dept_id,code,name,credits,course_type,semester,restriction_dept,
                    restriction_grade,teacher_id,weekday,period_start,period_end,room,max_students,status)
                   VALUES (?,?,?,?, '系選修', ?, ?, NULL, ?, ?, ?, ?, ?, ?, '開課')""",
                (dept_id, code, cname, cred, SEMESTER, dept_id,
                 teacher, wd, ps, pe, room, rng.randint(20, 35)))
            course_rows.append({"id": cur.lastrowid, "dept_id": dept_id,
                                "grade": None, "type": "系選修",
                                "credits": cred, "name": cname})

    # 通識 / 體育 / 核心通識（通識教育中心，dept_id NULL）
    gen_course_defs = [
        ("大一國文", "通識", 2, 2), ("大一英文", "通識", 2, 2),
        ("體育(一)", "體育", 2, 2), ("體育(二)", "體育", 2, 1),
        ("資訊素養", "核心通識", 2, 2), ("環境與永續", "核心通識", 2, 2),
        ("生命教育", "核心通識", 2, 2), ("海洋文化導論", "核心通識", 2, 2),
    ]
    # 國文/英文 限大一；體育限大一~大二；核心通識全年級
    cname_meta = {"大一國文": "1", "大一英文": "1", "體育(一)": "1,2", "體育(二)": "1,2", "資訊素養": None,
                  "環境與永續": None, "生命教育": None, "海洋文化導論": None}
    for i, (cname, ctype, cred, sections) in enumerate(gen_course_defs):
        for s in range(1, sections + 1):
            wd, ps, pe = pick_block(rng, [], cred)
            teacher = rng.choice(gen_fac_ids)
            if any(ow == wd and overlaps(ps, pe, os_, oe) for (ow, os_, oe) in teacher_busy[teacher]):
                wd, ps, pe = pick_block(rng, teacher_busy[teacher], cred)
            teacher_busy[teacher].append((wd, ps, pe))
            room = f"{rng.choice(room_pool)} {rng.randint(101, 899)}"
            course_seq += 1
            code = f"GE{course_seq:03d}"
            cur = conn.execute(
                """INSERT INTO courses
                   (dept_id,code,name,credits,course_type,semester,restriction_dept,
                    restriction_grade,teacher_id,weekday,period_start,period_end,room,max_students,status)
                   VALUES (NULL,?,?,?,?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, '開課')""",
                (code, cname, cred, ctype, SEMESTER, cname_meta[cname],
                 teacher, wd, ps, pe, room, 60 if ctype in ("通識", "體育", "核心通識") else rng.randint(20, 35)))
            course_rows.append({"id": cur.lastrowid, "dept_id": None,
                                "grade": cname_meta[cname], "type": ctype,
                                "credits": cred, "name": cname})

    # 重建完整課程資訊（含時段，供衝堂檢查）
    course_map = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM courses").fetchall()}

    def check_clash(sid, cid):
        """檢查該生已修課程與目標課程是否衝堂。"""
        target = {k: course_map[cid][k] for k in ("weekday", "period_start", "period_end")}
        for e in conn.execute("SELECT course_id FROM enrollments WHERE student_id=?", (sid,)).fetchall():
            h = course_map[e["course_id"]]
            if h.get("weekday") == target["weekday"] and \
               overlaps(target["period_start"], target["period_end"], h["period_start"], h["period_end"]):
                return True
        return False

    # ---------------- 必修 / 通識自動修課
    def enroll(student_id, course_id, source):
        conn.execute("INSERT INTO enrollments (course_id,student_id,source) VALUES (?,?,?) ON CONFLICT DO NOTHING",
                     (course_id, student_id, source))

    seen_enrolled = set()

    def course_credits(sid):
        row = conn.execute(
            "SELECT COALESCE(SUM(c.credits),0) AS s FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=?",
            (sid,)).fetchone()
        return row["s"]

    for c in course_rows:
        if c["type"] == "系必修":
            for st in student_ids:
                if st["dept_id"] == c["dept_id"] and st["grade"] == c["grade"]:
                    enroll(st["id"], c["id"], "必修自動")
        elif c["type"] == "通識" or c["type"] == "體育":
            for st in student_ids:
                take = (c["name"] in ("大一國文", "大一英文") and st["grade"] == 1) or \
                       (c["name"].startswith("體育") and st["grade"] in (1, 2))
                if take and (st["id"], c["name"]) not in seen_enrolled:
                    seen_enrolled.add((st["id"], c["name"]))
                    enroll(st["id"], c["id"], "通識自動")

    # ---------------- 已結算的選課（加退選時段已錄取）+ 歷史選課登記
    sel_history = []
    for st in student_ids:
        cur_cred = course_credits(st["id"])
        if cur_cred > 22:
            continue
        # 可選清單：本系選修 + 核心通識（排除已修）
        avail = [c for c in course_rows
                 if c["type"] in ("系選修", "核心通識")
                 and (c["type"] == "系選修" and c["dept_id"] == st["dept_id"] or c["type"] == "核心通識")]
        rng.shuffle(avail)
        got = 0
        for c in avail:
            if cur_cred >= 26 or got >= 2:
                break
            # 檢查衝堂
            has = [e["course_id"] for e in conn.execute(
                "SELECT course_id FROM enrollments WHERE student_id=?", (st["id"],)).fetchall()]
            clash = False
            for hc in has:
                h = course_map[hc]
                if h["weekday"] == course_map[c["id"]]["weekday"] and \
                   overlaps(course_map[c["id"]]["period_start"], course_map[c["id"]]["period_end"],
                            h["period_start"], h["period_end"]):
                    clash = True
                    break
            if clash:
                continue
            enroll(st["id"], c["id"], "加退選")
            sel_history.append((st["id"], c["id"], "加退選", "錄取"))
            cur_cred += c["credits"]
            got += 1

    # 加入歷史選課登記（含未錄取）
    for st in rng.sample(student_ids, 60):
        if not sel_history:
            break
        # 隨機挑一筆他人已錄取課程作為「未錄取」歷史
        cand = rng.choice([c for c in course_rows if c["type"] in ("系選修", "核心通識")])
        conn.execute("INSERT INTO course_selections (student_id,course_id,priority,phase,status,created_at) VALUES (?,?,?, '初選', '未錄取', ?)",
                     (st["id"], cand["id"], 1, "2024-09-05 10:00:00"))

    # ---------------- 成績
    ability = {}
    grade_rows = []
    for st in student_ids:
        ability[st["id"]] = min(99, max(30, round(rng.gauss(76, 8))))
    for e in conn.execute("SELECT course_id, student_id FROM enrollments").fetchall():
        cid, sid = e["course_id"], e["student_id"]
        ab = ability[sid] + rng.gauss(0, 8)
        mid = min(100, max(0, round(ab + rng.gauss(0, 6))))
        fin = min(100, max(0, round(ab + rng.gauss(0, 6))))
        total = min(100, max(0, round(0.4 * mid + 0.6 * fin)))
        letter, gpa = grade_letter_gpa(total)
        conn.execute(
            "INSERT INTO grades (course_id,student_id,midterm,final,total,grade_letter,gpa) VALUES (?,?,?,?,?,?,?)",
            (cid, sid, mid, fin, total, letter, gpa))
        grade_rows.append((cid, sid, c["credits"] if (c := course_map.get(cid)) else 0, gpa))

    # ---------------- 出缺席（113-1 期中四周）
    week_dates = {}
    base = datetime.date(2024, 11, 4)   # 週一
    for w in range(4):
        for off in range(5):
            day = base + datetime.timedelta(days=w * 7 + off)
            week_dates.setdefault(day.weekday() + 1, []).append(day)
    absent_weights = [("出席", 920), ("遲到", 25), ("曠課", 18), ("病假", 22), ("事假", 10), ("公假", 5)]
    for e in conn.execute("SELECT course_id, student_id FROM enrollments").fetchall():
        cid, sid = e["course_id"], e["student_id"]
        wd = course_map[cid]["weekday"]
        for day in week_dates.get(wd, []):
            status = rng.choices([w for w, _ in absent_weights],
                                 weights=[w for _, w in absent_weights])[0]
            conn.execute(
                "INSERT INTO attendance (course_id,student_id,date,status) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                (cid, sid, day.isoformat(), status))

    # ---------------- 請假單（含學生 demo 一張待審）
    conn.execute("""INSERT INTO leaves (student_id,course_id,date,leave_type,reason,status,created_at)
                    VALUES (?,?,?, '病假', '感冒發燒，居家休息', '審核中', ?)""",
                 (demo_student, None, "2024-12-04", "2024-12-03 22:14:00"))
    for _ in range(8):
        st = rng.choice(student_ids)
        conn.execute("""INSERT INTO leaves (student_id,course_id,date,leave_type,reason,status,created_at)
                        VALUES (?,?,?,?,?,?,?)""",
                     (st["id"], None, rand_date(rng, 2024, 10, 12), rng.choice(["病假", "事假", "公假"]),
                      rng.choice(["身體不適就醫", "家中有事", "參加校外活動"]),
                      rng.choice(["核准", "核准", "駁回"]), "2024-12-01 09:00:00"))

    # ---------------- 獎懲
    for st in rng.sample(student_ids, 26):
        rtype = rng.choices(["嘉獎", "小功", "大功", "警告", "小過"], weights=[40, 25, 10, 18, 7])[0]
        reason = rng.choice(["熱心服務同學", "協助校園活動圓滿完成", "競賽表現優異", "曠課達規定時數", "違反宿舍規定"])
        conn.execute("INSERT INTO rewards (student_id,date,rtype,reason,recorder_id,status) VALUES (?,?,?,?,?, '核定')",
                     (st["id"], rand_date(rng, 2024, 9, 12), rtype, reason, None))

    # ---------------- 導師約談
    for _ in range(14):
        st = rng.choice(student_ids)
        teacher = rng.choice(fac_by_dept[st["dept_id"]])
        conn.execute("INSERT INTO counseling_logs (student_id,teacher_id,date,topic,content) VALUES (?,?,?,?,?)",
                     (st["id"], teacher, rand_date(rng, 2024, 10, 12),
                      rng.choice(["學業適應", "選課諮詢", "生涯規劃", "人際困擾"]),
                      rng.choice(["了解學業狀況並給予讀書建議", "說明系所選修課程規劃", "討論未來職涯方向", "傾聽並提供情緒支持"])))

    # ---------------- 學雜費繳費單
    invoice_demo = None
    for st in student_ids:
        credits = course_credits(st["id"])
        base = rng.randint(26000, 32000)
        credit_fee = 1500
        dorm = rng.choices([0, 12000], weights=[60, 40])[0]
        total = base + credit_fee * credits + dorm
        paid = rng.random() < 0.8
        paid_date = rand_date(rng, 2024, 9, 9) if paid else None
        cur = conn.execute(
            """INSERT INTO tuition_invoices (student_id,semester,base_fee,credit_fee,credit_count,dorm_fee,total,paid,paid_date,method)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (st["id"], SEMESTER, base, credit_fee, credits, dorm, total, 1 if paid else 0,
             paid_date, rng.choice(["超商繳費", "信用卡", "銀行轉帳"]) if paid else None))
        if st["id"] == demo_student:
            invoice_demo = cur.lastrowid

    # ---------------- 獎助學金（每系 GPA 最高者書卷獎）
    gpa_avg = {}
    for (cid, sid, credits_g, gpa) in grade_rows:
        gpa_avg.setdefault(sid, []).append((credits_g, gpa))
    per_dept = {}
    for sid, items in gpa_avg.items():
        wsum = sum(c * g for c, g in items)
        wc = sum(c for c, _ in items) or 1
        school = 0
        # 找到該生系所
        st = next((s for s in student_ids if s["id"] == sid), None)
        if st:
            d = st["dept_id"]
            school = per_dept.get(d, (0, 0))[1]
            if wc and (wsum / wc) > school:
                per_dept[d] = (sid, wsum / wc)
    for d, (sid, _) in per_dept.items():
        this_name = next((s["name"] for s in student_ids if s["id"] == sid), "")
        conn.execute("INSERT INTO scholarships (student_id,name,amount,semester,date,status) VALUES (?,?,?,?,?, '核發')",
                     (sid, "成績優秀書卷獎", 10000, SEMESTER, "2025-01-20"))
        # 顯示用（fetch 時 join student name）

    # ---------------- 公告
    notices = [
        ("113-1 學期註冊繳費通知", "校園公告", "請全體同學於 9 月 15 日前完成註冊繳費，逾期將影響選課權益。", True),
        ("113-1 學期選課日程公告", "校園公告", "初選：9/2-9/6；加退選：9/16-9/20。請把握時間完成選課作業。", True),
        ("圖書館新書上架", "校園公告", "本學期新購入專業書籍共 380 冊，歡迎同學踴躍借閱。", False),
        ("運動會報名開始", "校園公告", "113 學年度全校運動會訂於 11/15 舉行，即日起受理報名。", False),
        ("宿舍網路維護通知", "校園公告", "本週六 00:00-06:00 宿舍網路維護，暫停服務。", False),
        ("英語檢定獎勵方案", "校園公告", "通過多益、全民英檢者可申請獎勵金，詳情請洽語言中心。", False),
        ("期中預警輔導即將展開", "校園公告", "請導師於 11 月底前完成期中預警學生約談。", False),
        ("校外工讀資訊", "校園公告", "本週新增 5 筆校外工讀機會，請至就輔中心查閱。", False),
    ]
    for title, cat, content, pin in notices:
        conn.execute("INSERT INTO announcements (title,category,content,author_id,dept_id,pinned,created_at) VALUES (?,?,?,?,NULL,?,?)",
                     (title, cat, content, None, 1 if pin else 0, "2024-09-01 09:00:00"))
    conn.execute("INSERT INTO announcements (title,category,content,author_id,dept_id,pinned,created_at) VALUES (?,'系辦公告',?,NULL,?,1,?)",
                 ("資訊工程學系系辦公告：113-1 系選修加簽登記開始", "系友座談會將於本月 20 日舉行，歡迎系友與同學報名。",
                  dept_by_code[11], "2024-09-03 10:00:00"))
    for d in dept_rows[1:]:
        conn.execute("INSERT INTO announcements (title,category,content,author_id,dept_id,pinned,created_at) VALUES (?, '系辦公告', ?, NULL, ?, 0, ?)",
                     (f"{d['name']}系學會招募新血", "113-1 學期系學會招募開始，歡迎大一新生踴躍加入。", d["id"], "2024-09-04 12:00:00"))

    # ---------------- 系統使用者
    conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?,?,?,?,?)",
                 ("admin", hash_pw("admin123"), "admin", None, "黃志強（教務處）", None))
    demo_teacher = fac_by_dept[dept_by_code[11]][0]
    demo_teacher_name = conn.execute("SELECT name FROM faculties WHERE id=?", (demo_teacher,)).fetchone()["name"]
    conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?,?,?,?,?)",
                 ("clerk", hash_pw("clerk123"), "clerk", None, "李雅芳（工學群系辦）", dept_by_code[11]))
    conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?,?,?,?,?)",
                 ("teacher", hash_pw("teacher123"), "teacher", demo_teacher, demo_teacher_name, dept_by_code[11]))
    demo_name = conn.execute("SELECT name FROM students WHERE id=?", (demo_student,)).fetchone()["name"]
    conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?,?,?,?,?)",
                 ("student", hash_pw("student123"), "student", demo_student, demo_name, dept_by_code[11]))
    # 每位教師帳號
    for fid in fac_ids + gen_fac_ids:
        conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?, 'teacher', ?,?,?)",
                     (f"t{fid}", hash_pw("123456"), fid,
                      conn.execute("SELECT name FROM faculties WHERE id=?", (fid,)).fetchone()["name"],
                      conn.execute("SELECT dept_id FROM faculties WHERE id=?", (fid,)).fetchone()["dept_id"]))

    # ---------------- settings
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('school_name',?)", (SCHOOL_NAME,))
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('current_semester',?)", (SEMESTER,))
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('selection_phase',?)", ("closed",))

    conn.commit()
    conn.close()

    n_students = len(student_ids)
    n_courses = len(course_rows)
    n_fac = len(fac_ids) + len(gen_fac_ids)
    print(f"[seed] 完成：{n_students} 學生 / {n_fac} 教職員 / {n_courses} 課程")
    print(f"[seed] demo 帳號：admin/admin123  clerk/clerk123  teacher/teacher123  student/student123")


if __name__ == "__main__":
    main(force="--force" in sys.argv)