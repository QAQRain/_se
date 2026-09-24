"""app.py — 校務行政系統 (School Administration System) 主程式

啟動方式: python app.py  →  http://localhost:5000
第一次啟動會自動建立資料庫與種子資料。

登入 demo 帳號：
  admin    / admin123    教務處
  clerk    / clerk123    系辦
  teacher  / teacher123  教師
  student  / student123  學生
"""
import os
import csv
import io
import datetime
from functools import wraps

from flask import Flask, request, session, jsonify, Response

from db import get_conn, hash_pw, init_db, is_seeded, rows_to_list, row_to_dict, close_all
import seed

app = Flask(__name__)
app.secret_key = os.environ.get("SAS_SECRET_KEY", "sas-dev-secret-key-change-me")

WEEKDAY_NAMES = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}
GRADE_REG = {"A+": 4.3, "A": 4.0, "A-": 3.7, "B+": 3.3, "B": 3.0, "B-": 2.7,
             "C+": 2.3, "C": 2.0, "C-": 1.7, "D": 1.0, "F": 0.0}


# ---------------------------------------------------------------- 基礎工具
def setting(key, default=None):
    conn = get_conn()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else default


def school_name():
    return setting("school_name", "校務行政系統")


def current_semester():
    return setting("current_semester", "113-1")


def selection_phase():
    return setting("selection_phase", "closed")


def grade_info(total):
    if total >= 90: return "A+", 4.3, True
    if total >= 85: return "A", 4.0, True
    if total >= 80: return "A-", 3.7, True
    if total >= 77: return "B+", 3.3, True
    if total >= 73: return "B", 3.0, True
    if total >= 70: return "B-", 2.7, True
    if total >= 67: return "C+", 2.3, True
    if total >= 63: return "C", 2.0, True
    if total >= 60: return "C-", 1.7, True
    if total >= 50: return "D", 1.0, True
    return "F", 0.0, False


def overlaps(as_, ae, bs, be):
    return not (ae < bs or be < as_)


def ok(data=None, **extra):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def current_user():
    return session.get("user")


# ---------------------------------------------------------------- 權限裝飾器
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return err("請先登入", 401)
        return fn(*args, **kwargs)
    return wrapper


def roles_allowed(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u:
                return err("請先登入", 401)
            if u["role"] not in roles:
                return err("無權限執行此操作", 403)
            return fn(*args, **kwargs)
        return wrapper
    return deco


# ---------------------------------------------------------------- 認證
@app.post("/api/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = get_conn()
    r = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not r or r["password"] != hash_pw(password):
        return err("帳號或密碼錯誤", 401)
    user = {"id": r["id"], "username": r["username"], "role": r["role"],
            "ref_id": r["ref_id"], "name": r["name"], "dept_id": r["dept_id"]}
    session["user"] = user
    return ok(user=user)


@app.get("/api/me")
@login_required
def me():
    u = session.get("user")
    extra = {}
    if u["role"] == "student":
        conn = get_conn()
        r = conn.execute("""SELECT s.*, d.name AS dept_name, c.name AS college_name
                            FROM students s JOIN departments d ON d.id=s.dept_id
                            JOIN colleges c ON c.id=d.college_id WHERE s.id=?""",
                         (u["ref_id"],)).fetchone()
        conn.close()
        if r:
            extra["profile"] = row_to_dict(r)
    elif u["role"] == "teacher":
        conn = get_conn()
        r = conn.execute("""SELECT f.*, COALESCE(d.name,'通識教育中心') AS dept_name
                            FROM faculties f LEFT JOIN departments d ON d.id=f.dept_id WHERE f.id=?""",
                         (u["ref_id"],)).fetchone()
        conn.close()
        if r:
            extra["profile"] = row_to_dict(r)
    return ok(user=u, **extra)


@app.post("/api/logout")
def logout():
    session.clear()
    return ok()


# ---------------------------------------------------------------- 儀表板
@app.get("/api/dashboard")
@login_required
def dashboard():
    conn = get_conn()
    u = current_user()
    sem = current_semester()

    def q(sql, *args):
        return conn.execute(sql, args).fetchone()

    if u["role"] == "student":
        sid = u["ref_id"]
        base = dict(
            enrolled=q("SELECT COUNT(*) n FROM enrollments WHERE student_id=?", sid)["n"],
            credits=q("SELECT COALESCE(SUM(c.credits),0) s FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=?", sid)["s"],
            gpa=q("""SELECT ROUND(COALESCE(SUM(g.gpa*c.credits)/NULLIF(SUM(c.credits),0),0),2) g
                     FROM grades g JOIN courses c ON c.id=g.course_id WHERE g.student_id=?""", sid)["g"],
            unread=q("SELECT COUNT(*) n FROM announcements a WHERE a.dept_id IS NULL OR a.dept_id = (SELECT dept_id FROM students WHERE id=?)", sid)["n"],
            credits_max=28,
        )
        attend = q("""SELECT status, COUNT(*) n FROM attendance WHERE student_id=? GROUP BY status""", sid)
        rows = {r["status"]: r["n"] for r in conn.execute("""SELECT status, COUNT(*) n FROM attendance WHERE student_id=?""", (sid,)).fetchall()}
        dist = q("""SELECT COUNT(*) n, SUM(CASE WHEN g.total>=80 THEN 1 ELSE 0 END) hi,
                    SUM(CASE WHEN g.total>=60 AND g.total<80 THEN 1 ELSE 0 END) mid,
                    SUM(CASE WHEN g.total<60 THEN 1 ELSE 0 END) lo FROM grades g WHERE g.student_id=?""", sid)
        conn.close()
        return ok(base=base, attendance=rows, grade_dist={"hi": dist["hi"] or 0, "mid": dist["mid"] or 0, "lo": dist["lo"] or 0})

    # admin / clerk / teacher 共用總覽（clerk 依系所；teacher 依自身課程）
    scope = ""
    args = []
    if u["role"] == "clerk":
        scope = "WHERE s.dept_id=?"
        args.append(u["dept_id"])
    elif u["role"] == "teacher":
        scope = "WHERE s.id IN (SELECT DISTINCT e.student_id FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE c.teacher_id=?)"
        args.append(u["ref_id"])

    base = dict(
        students=q(f"SELECT COUNT(*) n FROM students s {scope}", *args)["n"],
        faculties=q(f"SELECT COUNT(*) n FROM faculties f WHERE f.status='在職' {('AND f.dept_id=?' if u['role']=='clerk' else '')}",
                    *([u["dept_id"]] if u["role"] == "clerk" else []))["n"],
        courses=q("SELECT COUNT(*) n FROM courses WHERE status='開課' AND semester=?", sem)["n"],
    )
    if u["role"] == "teacher":
        base["credits"] = q("SELECT COALESCE(SUM(c.credits),0) s FROM courses c WHERE c.teacher_id=?", u["ref_id"])["s"]

    # 各系人數（bar）
    dept_counts = rows_to_list(conn.execute(
        """SELECT d.name, COUNT(s.id) n FROM departments d LEFT JOIN students s ON s.dept_id=d.id
           WHERE s.status='在學' GROUP BY d.id ORDER BY d.id""").fetchall())
    # 缺曠統計（doughnut）
    atts = rows_to_list(conn.execute(
        """SELECT a.status, COUNT(*) n FROM attendance a
           JOIN courses c ON c.id=a.course_id WHERE 1=1 AND a.status != '出席' GROUP BY a.status""").fetchall())
    if u["role"] == "clerk":
        atts = rows_to_list(conn.execute(
            """SELECT a.status, COUNT(*) n FROM attendance a
               JOIN courses c ON c.id=a.course_id JOIN students s ON s.id=a.student_id
               WHERE s.dept_id=? AND a.status != '出席' GROUP BY a.status""", (u["dept_id"],)).fetchall())
    elif u["role"] == "teacher":
        atts = rows_to_list(conn.execute(
            """SELECT a.status, COUNT(*) n FROM attendance a
               JOIN courses c ON c.id=a.course_id
               WHERE c.teacher_id=? AND a.status != '出席' GROUP BY a.status""", (u["ref_id"],)).fetchall())
    # 繳費率（doughnut）
    inv_sql = "SELECT SUM(CASE WHEN paid=1 THEN 1 ELSE 0 END) pd, COUNT(*) tot FROM tuition_invoices"
    inv = conn.execute(inv_sql).fetchone()
    if u["role"] == "clerk":
        inv = conn.execute("SELECT SUM(CASE WHEN i.paid=1 THEN 1 ELSE 0 END) pd, COUNT(*) tot FROM tuition_invoices i JOIN students s ON s.id=i.student_id WHERE s.dept_id=?", (u["dept_id"],)).fetchone()
    # 成績分布（bar）
    dist = conn.execute("""SELECT
        SUM(CASE WHEN g.total>=90 THEN 1 ELSE 0 END) a,
        SUM(CASE WHEN g.total>=80 AND g.total<90 THEN 1 ELSE 0 END) b,
        SUM(CASE WHEN g.total>=70 AND g.total<80 THEN 1 ELSE 0 END) c,
        SUM(CASE WHEN g.total>=60 AND g.total<70 THEN 1 ELSE 0 END) d,
        SUM(CASE WHEN g.total<60 THEN 1 ELSE 0 END) f FROM grades g""").fetchone()
    conn.close()
    return ok(base=base, dept_counts=dept_counts, attendance=atts,
              payment={"paid": inv["pd"] or 0, "unpaid": (inv["tot"] or 0) - (inv["pd"] or 0)},
              grade_dist={"90+": dist["a"] or 0, "80-89": dist["b"] or 0, "70-79": dist["c"] or 0,
                          "60-69": dist["d"] or 0, "<60": dist["f"] or 0})


# ---------------------------------------------------------------- 學院/系所
@app.get("/api/colleges")
@login_required
def colleges():
    conn = get_conn()
    rows = conn.execute("""SELECT c.id, c.name, COUNT(DISTINCT d.id) dept_count,
        (SELECT COUNT(*) FROM students s JOIN departments d2 ON d2.id=s.dept_id WHERE d2.college_id=c.id AND s.status='在學') student_count
        FROM colleges c LEFT JOIN departments d ON d.college_id=c.id GROUP BY c.id ORDER BY c.id""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.get("/api/departments")
@login_required
def departments():
    conn = get_conn()
    rows = conn.execute("""SELECT d.*, c.name college_name,
        (SELECT COUNT(*) FROM students s WHERE s.dept_id=d.id AND s.status='在學') student_count,
        (SELECT COUNT(*) FROM faculties f WHERE f.dept_id=d.id AND f.status='在職') faculty_count
        FROM departments d JOIN colleges c ON c.id=d.college_id ORDER BY d.id""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


# ---------------------------------------------------------------- 學生
@app.get("/api/students")
@login_required
@roles_allowed("admin", "clerk", "teacher")
def students():
    u = current_user()
    q = request.args.get("q", "").strip()
    dept = request.args.get("dept", "").strip()
    grade = request.args.get("grade", "").strip()
    status = request.args.get("status", "").strip()
    where, args = [], []
    if u["role"] == "clerk":
        where.append("s.dept_id=?")
        args.append(u["dept_id"])
    if q:
        like = f"%{q}%"
        where.append("(s.name LIKE ? OR s.student_no LIKE ?)")
        args += [like, like]
    if dept:
        where.append("s.dept_id=?")
        args.append(dept)
    if grade:
        where.append("s.grade=?")
        args.append(grade)
    if status:
        where.append("s.status=?")
        args.append(status)
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    rows = conn.execute(f"""SELECT s.*, d.name dept_name
        FROM students s JOIN departments d ON d.id=s.dept_id {wsql} ORDER BY s.dept_id, s.grade, s.student_no LIMIT 500""",
                        args).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/students")
@login_required
@roles_allowed("admin", "clerk")
def create_student():
    d = request.get_json(force=True, silent=True) or {}
    need = ["dept_id", "name", "grade"]
    if not all(d.get(k) for k in need):
        return err("缺少必要欄位（系所/姓名/年級）")
    conn = get_conn()
    gen_enroll_year = 113
    cur = conn.execute("""INSERT INTO students
        (dept_id,student_no,name,gender,birth_date,grade,class_no,enroll_year,status,address,phone,email,guardian_name,guardian_phone)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["dept_id"], d.get("student_no"), d["name"], d.get("gender"), d.get("birth_date"),
         d["grade"], d.get("class_no"), d.get("enroll_year") or gen_enroll_year, d.get("status") or "在學",
         d.get("address"), d.get("phone"), d.get("email"), d.get("guardian_name"), d.get("guardian_phone")))
    sid = cur.lastrowid
    conn.execute("INSERT INTO users (username,password,role,ref_id,name,dept_id) VALUES (?,?, 'student', ?,?,?)",
                 (d.get("student_no") or f"U{sid}", hash_pw("123456"), sid, d["name"], d["dept_id"]))
    conn.commit()
    conn.close()
    return ok(id=sid, message="已新增學生")


@app.put("/api/students/<int:sid>")
@login_required
@roles_allowed("admin", "clerk")
def update_student(sid):
    d = request.get_json(force=True, silent=True) or {}
    allowed = ["student_no", "name", "gender", "birth_date", "grade", "class_no", "enroll_year",
               "status", "address", "phone", "email", "guardian_name", "guardian_phone", "dept_id"]
    sets = [f"{k}=?" for k in allowed if k in d]
    if not sets:
        return err("沒有可更新的欄位")
    conn = get_conn()
    args = [d[k] for k in allowed if k in d]
    args.append(sid)
    conn.execute(f"UPDATE students SET {', '.join(sets)} WHERE id=?", args)
    conn.commit()
    conn.close()
    return ok(message="已更新")


@app.delete("/api/students/<int:sid>")
@login_required
@roles_allowed("admin")
def delete_student(sid):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE ref_id=? AND role='student'", (sid,))
    conn.execute("DELETE FROM enrollments WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM grades WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM course_selections WHERE student_id=?", (sid,))
    conn.execute("DELETE FROM students WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return ok(message="已刪除")


@app.get("/api/students/<int:sid>")
@login_required
def student_detail(sid):
    conn = get_conn()
    r = conn.execute("""SELECT s.*, d.name dept_name, c.name college_name
        FROM students s JOIN departments d ON d.id=s.dept_id JOIN colleges c ON c.id=d.college_id
        WHERE s.id=?""", (sid,)).fetchone()
    if not r:
        conn.close()
        return err("找不到學生", 404)
    enroll = rows_to_list(conn.execute("""SELECT c.*, e.source, f.name teacher_name FROM enrollments e
        JOIN courses c ON c.id=e.course_id LEFT JOIN faculties f ON f.id=c.teacher_id
        WHERE e.student_id=? ORDER BY c.weekday, c.period_start""", (sid,)).fetchall())
    trans = rows_to_list(conn.execute("""SELECT c.name cname, c.credits, g.midterm, g.final, g.total, g.grade_letter, g.gpa
        FROM grades g JOIN courses c ON c.id=g.course_id WHERE g.student_id=? ORDER BY c.id""", (sid,)).fetchall())
    rewards = rows_to_list(conn.execute("SELECT * FROM rewards WHERE student_id=? ORDER BY date DESC", (sid,)).fetchall())
    leaves = rows_to_list(conn.execute("SELECT * FROM leaves WHERE student_id=? ORDER BY created_at DESC", (sid,)).fetchall())
    summary = conn.execute("""SELECT
        COALESCE(SUM(CASE WHEN g.gpa>0 THEN c.credits ELSE 0 END),0) pass_credits,
        ROUND(COALESCE(SUM(g.gpa*c.credits)/NULLIF(SUM(c.credits),0),0),2) gpa,
        COALESCE(SUM(c.credits),0) total_credits
        FROM grades g JOIN courses c ON c.id=g.course_id WHERE g.student_id=?""", (sid,)).fetchone()
    conn.close()
    return ok(profile=row_to_dict(r), courses=enroll, transcript=trans, rewards=rewards,
              leaves=leaves, summary=dict(summary))


# ---------------------------------------------------------------- 教職員
@app.get("/api/faculties")
@login_required
def faculties():
    conn = get_conn()
    rows = conn.execute("""SELECT f.*, COALESCE(d.name,'通識教育中心') dept_name
        FROM faculties f LEFT JOIN departments d ON d.id=f.dept_id ORDER BY f.id""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/faculties")
@login_required
@roles_allowed("admin")
def create_faculty():
    d = request.get_json(force=True, silent=True) or {}
    if not d.get("name"):
        return err("缺少姓名")
    conn = get_conn()
    cur = conn.execute("""INSERT INTO faculties (dept_id,name,gender,title,email,office,phone,hire_date,status)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (d.get("dept_id"), d["name"], d.get("gender"), d.get("title"), d.get("email"),
         d.get("office"), d.get("phone"), d.get("hire_date"), d.get("status") or "在職"))
    conn.commit()
    conn.close()
    return ok(id=cur.lastrowid, message="已新增教職員")


@app.put("/api/faculties/<int:fid>")
@login_required
@roles_allowed("admin")
def update_faculty(fid):
    d = request.get_json(force=True, silent=True) or {}
    allowed = ["dept_id", "name", "gender", "title", "email", "office", "phone", "hire_date", "status"]
    sets = [f"{k}=?" for k in allowed if k in d]
    if not sets:
        return err("沒有可更新的欄位")
    conn = get_conn()
    conn.execute(f"UPDATE faculties SET {', '.join(sets)} WHERE id=?", [d[k] for k in allowed if k in d] + [fid])
    conn.commit()
    conn.close()
    return ok(message="已更新")


@app.delete("/api/faculties/<int:fid>")
@login_required
@roles_allowed("admin")
def delete_faculty(fid):
    conn = get_conn()
    conn.execute("DELETE FROM faculties WHERE id=?", (fid,))
    conn.execute("DELETE FROM users WHERE ref_id=? AND role='teacher' AND username LIKE 't%'", (fid,))
    conn.commit()
    conn.close()
    return ok(message="已刪除")


# ---------------------------------------------------------------- 課程
@app.get("/api/courses")
@login_required
def courses():
    u = current_user()
    dept = request.args.get("dept", "").strip()
    ctype = request.args.get("type", "").strip()
    grade = request.args.get("grade", "").strip()
    teacher = request.args.get("teacher", "").strip()
    semester = request.args.get("semester", "").strip() or current_semester()
    where = ["c.semester=?"]
    args = [semester]
    if u["role"] == "teacher":
        where.append("c.teacher_id=?")
        args.append(u["ref_id"])
    elif u["role"] == "clerk":
        where.append("(c.dept_id=? OR c.dept_id IS NULL)")
        args.append(u["dept_id"])
    if dept:
        where.append("(c.dept_id=? OR c.dept_id IS NULL)")
        args.append(dept)
    if ctype:
        where.append("c.course_type=?")
        args.append(ctype)
    if teacher:
        where.append("c.teacher_id=?")
        args.append(teacher)
    if grade:
        where.append("(c.restriction_grade IS NULL OR c.restriction_grade LIKE ?)")
        args.append(f"%{grade}%")
    wsql = " AND ".join(where)
    conn = get_conn()
    rows = conn.execute(f"""SELECT c.*, f.name teacher_name, COALESCE(d.name,'通識教育中心') dept_name,
        (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) enrolled
        FROM courses c LEFT JOIN faculties f ON f.id=c.teacher_id
        LEFT JOIN departments d ON d.id=c.dept_id WHERE {wsql} ORDER BY c.id""", args).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.get("/api/courses/<int:cid>")
@login_required
def course_detail(cid):
    conn = get_conn()
    r = conn.execute("""SELECT c.*, f.name teacher_name, COALESCE(d.name,'通識教育中心') dept_name
        FROM courses c LEFT JOIN faculties f ON f.id=c.teacher_id
        LEFT JOIN departments d ON d.id=c.dept_id WHERE c.id=?""", (cid,)).fetchone()
    if not r:
        conn.close()
        return err("找不到課程", 404)
    enrolled = conn.execute("SELECT COUNT(*) n FROM enrollments WHERE course_id=?", (cid,)).fetchone()["n"]
    conn.close()
    return ok(**{**dict(r), "enrolled": enrolled})


@app.post("/api/courses")
@login_required
@roles_allowed("admin", "clerk")
def create_course():
    d = request.get_json(force=True, silent=True) or {}
    need = ["name", "credits", "course_type", "teacher_id", "weekday", "period_start", "period_end"]
    if not all(d.get(k) is not None for k in need):
        return err("缺少必要欄位")
    u = current_user()
    dept_id = d.get("dept_id")
    if u["role"] == "clerk":
        if d.get("course_type") == "系必修" or d.get("course_type") == "系選修":
            dept_id = u["dept_id"]
    conn = get_conn()
    code = d.get("code") or f"{'DE'}{datetime.datetime.now().strftime('%H%M%S')}"
    cur = conn.execute("""INSERT INTO courses
        (dept_id,code,name,credits,course_type,semester,restriction_dept,restriction_grade,
         teacher_id,weekday,period_start,period_end,room,max_students,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dept_id, code, d["name"], d["credits"], d["course_type"], d.get("semester") or current_semester(),
         d.get("restriction_dept"), d.get("restriction_grade"), d["teacher_id"],
         d["weekday"], d["period_start"], d["period_end"], d.get("room"),
         d.get("max_students") or 30, d.get("status") or "開課"))
    conn.commit()
    conn.close()
    return ok(id=cur.lastrowid, message="已開設課程")


@app.put("/api/courses/<int:cid>")
@login_required
@roles_allowed("admin", "clerk")
def update_course(cid):
    d = request.get_json(force=True, silent=True) or {}
    allowed = ["dept_id", "code", "name", "credits", "course_type", "semester", "restriction_dept",
               "restriction_grade", "teacher_id", "weekday", "period_start", "period_end",
               "room", "max_students", "status"]
    sets = [f"{k}=?" for k in allowed if k in d]
    if not sets:
        return err("沒有可更新的欄位")
    conn = get_conn()
    conn.execute(f"UPDATE courses SET {', '.join(sets)} WHERE id=?", [d[k] for k in allowed if k in d] + [cid])
    conn.commit()
    conn.close()
    return ok(message="已更新")


@app.delete("/api/courses/<int:cid>")
@login_required
@roles_allowed("admin", "clerk")
def delete_course(cid):
    conn = get_conn()
    conn.execute("DELETE FROM grades WHERE course_id=?", (cid,))
    conn.execute("DELETE FROM attendance WHERE course_id=?", (cid,))
    conn.execute("DELETE FROM enrollments WHERE course_id=?", (cid,))
    conn.execute("DELETE FROM course_selections WHERE course_id=?", (cid,))
    conn.execute("DELETE FROM courses WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return ok(message="已刪除")


@app.get("/api/courses/<int:cid>/roster")
@login_required
def course_roster(cid):
    conn = get_conn()
    rows = conn.execute("""SELECT s.id, s.student_no, s.name, s.grade, s.dept_id, d.name dept_name, e.source
        FROM enrollments e JOIN students s ON s.id=e.student_id
        JOIN departments d ON d.id=s.dept_id WHERE e.course_id=? ORDER BY s.student_no""", (cid,)).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


# ---------------------------------------------------------------- 課表
@app.get("/api/timetable")
@login_required
def timetable():
    u = current_user()
    who = request.args.get("who", "student")
    ref = request.args.get("id", "")
    conn = get_conn()
    if who == "teacher":
        tid = int(ref or u[("ref_id" if u["role"] == "teacher" else "ref_id")])
        rows = conn.execute("""SELECT c.name, c.code, c.credits, c.course_type, c.weekday, c.period_start,
            c.period_end, c.room, f.name teacher_name, c.id course_id
            FROM courses c LEFT JOIN faculties f ON f.id=c.teacher_id WHERE c.teacher_id=? AND c.status='開課'
            ORDER BY c.weekday, c.period_start""", (tid,)).fetchall()
    elif who == "deptgrade":
        dept = request.args.get("dept", "")
        grade = request.args.get("grade", "") or None
        sid_list = [r["id"] for r in conn.execute("""SELECT id FROM students
            WHERE dept_id=? AND (grade=? OR ? IS NULL) AND status='在學'""", (dept, grade, grade)).fetchall()]
        if not sid_list:
            rows = []
        else:
            marks = ",".join("?" * len(sid_list))
            rows = conn.execute(f"""SELECT DISTINCT c.name, c.code, c.credits, c.course_type, c.weekday, c.period_start,
                c.period_end, c.room, f.name teacher_name, c.id course_id
                FROM enrollments e JOIN courses c ON c.id=e.course_id
                LEFT JOIN faculties f ON f.id=c.teacher_id WHERE e.student_id IN ({marks})
                ORDER BY c.weekday, c.period_start""", sid_list).fetchall()
    else:  # student
        sid = int(ref or (u["ref_id"] if u["role"] == "student" else 0))
        rows = conn.execute("""SELECT c.name, c.code, c.credits, c.course_type, c.weekday, c.period_start,
            c.period_end, c.room, f.name teacher_name, c.id course_id
            FROM enrollments e JOIN courses c ON c.id=e.course_id
            LEFT JOIN faculties f ON f.id=c.teacher_id WHERE e.student_id=? AND c.status='開課'
            ORDER BY c.weekday, c.period_start""", (sid,)).fetchall()
    conn.close()
    return ok(courses=rows_to_list(rows), weekday_names=WEEKDAY_NAMES)


# ---------------------------------------------------------------- 出缺席
@app.get("/api/attendance")
@login_required
def attendance():
    u = current_user()
    course_id = request.args.get("course_id", "").strip()
    date = request.args.get("date", "").strip()
    student_id = request.args.get("student_id", "").strip()
    conn = get_conn()
    if course_id:
        rows = conn.execute("""SELECT a.id, a.student_id, a.status, a.date, s.name, s.student_no
            FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.course_id=?
            ORDER BY a.date DESC LIMIT 2000""", (course_id,)).fetchall()
    elif student_id:
        rows = conn.execute("""SELECT a.date, a.status, c.name cname, c.credits, f.name teacher_name
            FROM attendance a JOIN courses c ON c.id=a.course_id LEFT JOIN faculties f ON f.id=c.teacher_id
            WHERE a.student_id=? ORDER BY a.date DESC LIMIT 500""", (student_id,)).fetchall()
    elif u["role"] in ("admin", "clerk"):
        rows = conn.execute("""SELECT a.date, a.status, COUNT(*) n FROM attendance a WHERE a.status!='出席'
            GROUP BY a.date, a.status ORDER BY a.date DESC LIMIT 500""").fetchall()
    else:
        rows = []
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/attendance/save")
@login_required
@roles_allowed("admin", "teacher", "clerk")
def attendance_save():
    d = request.get_json(force=True, silent=True) or {}
    course_id = d.get("course_id")
    date = d.get("date")
    rows = d.get("rows") or []
    if not course_id or not date or not rows:
        return err("缺少資料")
    conn = get_conn()
    if current_user()["role"] == "teacher":
        mine = conn.execute("SELECT id FROM courses WHERE id=? AND teacher_id=?", (course_id, current_user()["ref_id"])).fetchone()
        if not mine:
            conn.close()
            return err("只能為自己授課的課程點名")
    for r in rows:
        conn.execute("""INSERT INTO attendance (course_id,student_id,date,status) VALUES (?,?,?,?)
            ON CONFLICT(course_id,student_id,date) DO UPDATE SET status=excluded.status""",
                     (course_id, r["student_id"], date, r.get("status") or "出席"))
    conn.commit()
    conn.close()
    return ok(message="點名已儲存")


# ---------------------------------------------------------------- 請假
@app.get("/api/leaves")
@login_required
def leaves():
    u = current_user()
    conn = get_conn()
    if u["role"] == "student":
        rows = conn.execute("SELECT * FROM leaves WHERE student_id=? ORDER BY created_at DESC", (u["ref_id"],)).fetchall()
    elif u["role"] == "teacher":
        rows = conn.execute("""SELECT l.*, s.name sname, s.student_no FROM leaves l JOIN students s ON s.id=l.student_id
            WHERE l.course_id IN (SELECT id FROM courses WHERE teacher_id=?)
            ORDER BY l.created_at DESC""", (u["ref_id"],)).fetchall()
    else:
        rows = conn.execute("""SELECT l.*, s.name sname, s.student_no, d.name dept_name FROM leaves l
            JOIN students s ON s.id=l.student_id JOIN departments d ON d.id=s.dept_id
            ORDER BY l.created_at DESC""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/leaves")
@login_required
@roles_allowed("student")
def create_leave():
    d = request.get_json(force=True, silent=True) or {}
    if not d.get("date") or not d.get("leave_type"):
        return err("缺少日期或假別")
    conn = get_conn()
    conn.execute("""INSERT INTO leaves (student_id,course_id,date,leave_type,reason,status,created_at)
        VALUES (?,?,?,?,?, '審核中', ?)""",
        (current_user()["ref_id"], d.get("course_id"), d["date"], d["leave_type"],
         d.get("reason"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return ok(message="已送出請假申請")


@app.put("/api/leaves/<int:lid>")
@login_required
@roles_allowed("admin", "clerk", "teacher")
def review_leave(lid):
    d = request.get_json(force=True, silent=True) or {}
    status = d.get("status")
    if status not in ("核准", "駁回"):
        return err("狀態錯誤")
    conn = get_conn()
    if current_user()["role"] == "teacher":
        lv = conn.execute("""SELECT course_id FROM leaves WHERE id=?""", (lid,)).fetchone()
        if not lv:
            conn.close()
            return err("找不到該請假申請", 404)
        in_scope = conn.execute("""SELECT 1 FROM courses c WHERE c.id=? AND c.teacher_id=?""",
                                (lv["course_id"], current_user()["ref_id"])).fetchone()
        if not in_scope:
            conn.close()
            return err("只能核准自己課程的請假")
    conn.execute("UPDATE leaves SET status=? WHERE id=?", (status, lid))
    conn.commit()
    conn.close()
    return ok(message="已處理")


# ---------------------------------------------------------------- 成績
@app.get("/api/grades")
@login_required
def grades():
    u = current_user()
    course_id = request.args.get("course_id", "").strip()
    if not course_id:
        return err("缺少 course_id")
    conn = get_conn()
    if u["role"] in ("admin", "clerk"):
        rows = conn.execute("""SELECT g.*, s.name, s.student_no FROM grades g
            JOIN students s ON s.id=g.student_id WHERE g.course_id=? ORDER BY s.student_no""", (course_id,)).fetchall()
    else:
        rows = conn.execute("""SELECT g.*, s.name, s.student_no FROM grades g
            JOIN students s ON s.id=g.student_id WHERE g.course_id=?
            AND s.id IN (SELECT e.student_id FROM enrollments e JOIN courses c ON c.id=e.course_id
                         WHERE c.teacher_id=?) ORDER BY s.student_no""", (course_id, u["ref_id"])).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/grades/save")
@login_required
@roles_allowed("admin", "teacher", "clerk")
def grades_save():
    d = request.get_json(force=True, silent=True) or {}
    course_id = d.get("course_id")
    rows = d.get("rows") or []
    if not course_id:
        return err("缺少 course_id")
    conn = get_conn()
    if current_user()["role"] == "teacher":
        mine = conn.execute("SELECT id FROM courses WHERE id=? AND teacher_id=?", (course_id, current_user()["ref_id"])).fetchone()
        if not mine:
            conn.close()
            return err("只能為自己授課的課程登錄成績")
    conn = get_conn()
    for r in rows:
        sid = r.get("student_id")
        mid = r.get("midterm")
        fin = r.get("final")
        total, letter, gpa = None, None, None
        if mid is not None and fin is not None:
            try:
                total = round(0.4 * float(mid) + 0.6 * float(fin))
                letter, gpa, _ = grade_info(total)
            except (TypeError, ValueError):
                total, letter, gpa = None, None, None
        conn.execute("""INSERT INTO grades (course_id,student_id,midterm,final,total,grade_letter,gpa)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(course_id,student_id) DO UPDATE SET
              midterm=excluded.midterm, final=excluded.final,
              total=excluded.total, grade_letter=excluded.grade_letter, gpa=excluded.gpa""",
                     (course_id, sid, mid, fin, total, letter, gpa))
    conn.commit()
    conn.close()
    return ok(message="成績已儲存")


@app.get("/api/grades/statistics")
@login_required
def grades_statistics():
    course_id = request.args.get("course_id", "").strip()
    if not course_id:
        return err("缺少 course_id")
    conn = get_conn()
    r = conn.execute("""SELECT COUNT(*) n, ROUND(AVG(total),1) avg, MIN(total) mn, MAX(total) mx
        FROM grades WHERE course_id=?""", (course_id,)).fetchone()
    dist = conn.execute("""SELECT
        SUM(CASE WHEN total>=90 THEN 1 ELSE 0 END) a,
        SUM(CASE WHEN total>=80 AND total<90 THEN 1 ELSE 0 END) b,
        SUM(CASE WHEN total>=70 AND total<80 THEN 1 ELSE 0 END) c,
        SUM(CASE WHEN total>=60 AND total<70 THEN 1 ELSE 0 END) d,
        SUM(CASE WHEN total<60 THEN 1 ELSE 0 END) f FROM grades WHERE course_id=?""", (course_id,)).fetchone()
    conn.close()
    return ok(stat=dict(r), dist={"90+": dist["a"] or 0, "80-89": dist["b"] or 0, "70-79": dist["c"] or 0,
                                  "60-69": dist["d"] or 0, "<60": dist["f"] or 0})


@app.get("/api/transcript/<int:sid>")
@login_required
def transcript(sid):
    u = current_user()
    if u["role"] == "student" and u["ref_id"] != sid:
        return err("無法查看他人成績單", 403)
    conn = get_conn()
    rows = conn.execute("""SELECT c.name cname, c.code, c.credits, c.course_type, c.semester,
        g.midterm, g.final, g.total, g.grade_letter, g.gpa, f.name teacher_name
        FROM grades g JOIN courses c ON c.id=g.course_id LEFT JOIN faculties f ON f.id=c.teacher_id
        WHERE g.student_id=? ORDER BY c.id""", (sid,)).fetchall()
    sum_r = conn.execute("""SELECT
        COALESCE(SUM(CASE WHEN g.gpa>0 THEN c.credits ELSE 0 END),0) pass_credits,
        ROUND(COALESCE(SUM(g.gpa*c.credits)/NULLIF(SUM(c.credits),0),0),2) gpa,
        COALESCE(SUM(c.credits),0) total_credits,
        COALESCE(SUM(CASE WHEN c.course_type='系必修' AND g.gpa>0 THEN c.credits ELSE 0 END),0) req_credits
        FROM grades g JOIN courses c ON c.id=g.course_id WHERE g.student_id=?""", (sid,)).fetchone()
    stu = row_to_dict(conn.execute("""SELECT s.*, d.name dept_name FROM students s
        JOIN departments d ON d.id=s.dept_id WHERE s.id=?""", (sid,)).fetchone())
    conn.close()
    return ok(student=stu, rows=rows_to_list(rows), summary=dict(sum_r))


# ---------------------------------------------------------------- 選課
@app.get("/api/selection/status")
@login_required
def selection_status():
    return ok(phase=selection_phase(), semester=current_semester(),
              student_max=4, credit_cap=28)


@app.post("/api/selection/open")
@login_required
@roles_allowed("admin")
def selection_open():
    d = request.get_json(force=True, silent=True) or {}
    phase = d.get("phase")
    if phase not in ("closed", "initial", "add_drop"):
        return err("選課狀態錯誤")
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('selection_phase',?)", (phase,))
    conn.commit()
    conn.close()
    return ok(phase=phase)


def student_eligible_courses(conn, sid):
    stu = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not stu:
        return []
    enrolled = {r["course_id"] for r in conn.execute("SELECT course_id FROM enrollments WHERE student_id=?", (sid,)).fetchall()}
    pending = [r["course_id"] for r in conn.execute(
        "SELECT course_id FROM course_selections WHERE student_id=? AND status='暫選'", (sid,)).fetchall()]
    rows = conn.execute("""SELECT c.*, f.name teacher_name, COALESCE(d.name,'通識教育中心') dept_name,
        (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) enrolled_count
        FROM courses c LEFT JOIN faculties f ON f.id=c.teacher_id
        LEFT JOIN departments d ON d.id=c.dept_id
        WHERE c.status='開課' AND c.semester=? AND c.course_type IN ('系選修','核心通識')
        ORDER BY c.id""", (current_semester(),)).fetchall()
    out = []
    for c in rows:
        if c["id"] in enrolled:
            continue
        if c["course_type"] == "系選修" and c["restriction_dept"] and c["restriction_dept"] != stu["dept_id"]:
            continue
        if c["restriction_grade"] and str(stu["grade"]) not in c["restriction_grade"].split(","):
            continue
        full = c["enrolled_count"] >= c["max_students"]
        clash = False
        for eid in enrolled:
            h = conn.execute("SELECT * FROM courses WHERE id=?", (eid,)).fetchone()
            if h and h["weekday"] == c["weekday"] and overlaps(
                    c["period_start"], c["period_end"], h["period_start"], h["period_end"]):
                clash = True
                break
        seats = max(c["max_students"] - c["enrolled_count"], 0)
        out.append({**dict(c), "full": full, "clash": clash, "seats": seats, "pending": c["id"] in pending})
    return out


@app.get("/api/selection/catalog")
@login_required
@roles_allowed("student")
def selection_catalog():
    conn = get_conn()
    items = student_eligible_courses(conn, current_user()["ref_id"])
    conn.close()
    return ok(items=items)


@app.post("/api/selection/apply")
@login_required
@roles_allowed("student")
def selection_apply():
    if selection_phase() != "initial":
        return err("目前非初選時段，無法登記志願")
    d = request.get_json(force=True, silent=True) or {}
    picks = d.get("selections") or []
    if len(picks) > 4:
        return err("初選至多登記 4 個志願")
    sid = current_user()["ref_id"]
    conn = get_conn()
    items = student_eligible_courses(conn, sid)
    by_id = {i["id"]: i for i in items}
    # 檢查重複 / 資格 / 衝堂
    seen = set()
    for pick in picks:
        cid = pick.get("course_id")
        priority = pick.get("priority")
        if not cid or not priority or cid in seen:
            return err("志願資料格式錯誤")
        if cid not in by_id:
            return err("課程不開放選課")
        if by_id[cid]["clash"]:
            return err(f"{by_id[cid]['name']} 與已修課程衝堂")
        seen.add(cid)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM course_selections WHERE student_id=? AND phase='初選'", (sid,))
    for pick in picks:
        conn.execute("""INSERT INTO course_selections (student_id,course_id,priority,phase,status,created_at)
            VALUES (?,?,?, '初選', '暫選', ?)""",
                     (sid, pick["course_id"], pick["priority"], now))
    conn.commit()
    conn.close()
    return ok(message="志願已送出")


@app.post("/api/selection/settle")
@login_required
@roles_allowed("admin")
def selection_settle():
    if selection_phase() != "initial":
        return err("目前非初選時段，無法結算")
    conn = get_conn()
    sem = current_semester()
    course_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM courses WHERE semester=? AND course_type IN ('系選修','核心通識') AND status='開課'", (sem,)).fetchall()]
    for cid in course_ids:
        c = conn.execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone()
        enrolled_count = conn.execute("SELECT COUNT(*) n FROM enrollments WHERE course_id=?", (cid,)).fetchone()["n"]
        cap = c["max_students"]
        # 各志願輪依（priority, created_at）排序挑人
        cands = conn.execute("""SELECT student_id, priority FROM course_selections
            WHERE course_id=? AND status='暫選' ORDER BY priority, created_at""", (cid,)).fetchall()
        for cd in cands:
            if enrolled_count >= cap:
                conn.execute("UPDATE course_selections SET status='候補' WHERE course_id=? AND student_id=?",
                             (cid, cd["student_id"]))
                continue
            # 學分上限檢查
            cur_cred = conn.execute("""SELECT COALESCE(SUM(c2.credits),0) s FROM enrollments e
                JOIN courses c2 ON c2.id=e.course_id WHERE e.student_id=?""", (cd["student_id"],)).fetchone()["s"]
            if cur_cred + c["credits"] > 28:
                conn.execute("UPDATE course_selections SET status='未錄取' WHERE course_id=? AND student_id=?",
                             (cid, cd["student_id"]))
                continue
            conn.execute("UPDATE course_selections SET status='錄取' WHERE course_id=? AND student_id=?",
                         (cid, cd["student_id"]))
            conn.execute("INSERT INTO enrollments (course_id,student_id,source) VALUES (?,?, '志願結算')",
                         (cid, cd["student_id"]))
            enrolled_count += 1
    # 未處理的志願標記未錄取
    conn.execute("""UPDATE course_selections SET status='未錄取' WHERE
        (status='暫選' OR status='候補') AND id IN
        (SELECT cs.id FROM course_selections cs WHERE cs.phase='初選')""")
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('selection_phase','add_drop')")
    conn.commit()
    conn.close()
    return ok(message="結算完成，已進入加退選時段")


@app.post("/api/selection/add")
@login_required
@roles_allowed("student")
def selection_add():
    if selection_phase() != "add_drop":
        return err("目前非加退選時段")
    d = request.get_json(force=True, silent=True) or {}
    cid = d.get("course_id")
    sid = current_user()["ref_id"]
    conn = get_conn()
    items = student_eligible_courses(conn, sid)
    by_id = {i["id"]: i for i in items}
    c = by_id.get(cid)
    if not c:
        conn.close()
        return err("此課程不可加選（資格不符/已修/不存在）")
    if c["full"]:
        conn.close()
        return err("名額已滿")
    if c["clash"]:
        conn.close()
        return err("與已修課程衝堂")
    cur_cred = conn.execute("""SELECT COALESCE(SUM(c2.credits),0) s FROM enrollments e
        JOIN courses c2 ON c2.id=e.course_id WHERE e.student_id=?""", (sid,)).fetchone()["s"]
    if cur_cred + c["credits"] > 28:
        conn.close()
        return err("超過每學期學分上限 (28)")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO enrollments (course_id,student_id,source) VALUES (?,?, '加退選')", (cid, sid))
    conn.execute("INSERT INTO course_selections (student_id,course_id,priority,phase,status,created_at) VALUES (?,?,NULL, '加退選','錄取',?)",
                 (sid, cid, now))
    conn.commit()
    conn.close()
    return ok(message="加選成功")


@app.post("/api/selection/drop")
@login_required
@roles_allowed("student")
def selection_drop():
    d = request.get_json(force=True, silent=True) or {}
    cid = d.get("course_id")
    sid = current_user()["ref_id"]
    conn = get_conn()
    en = conn.execute("""SELECT e.id, c.course_type FROM enrollments e JOIN courses c ON c.id=e.course_id
        WHERE e.course_id=? AND e.student_id=?""", (cid, sid)).fetchone()
    if not en:
        conn.close()
        return err("未修習此課程")
    if en["course_type"] in ("系必修", "通識", "體育"):
        conn.close()
        return err("必修/通識/體育課程不可退選")
    conn.execute("UPDATE course_selections SET status='退選' WHERE student_id=? AND course_id=?",
                 (sid, cid))
    conn.execute("DELETE FROM grades WHERE course_id=? AND student_id=?", (cid, sid))
    conn.execute("DELETE FROM attendance WHERE course_id=? AND student_id=?", (cid, sid))
    conn.execute("DELETE FROM enrollments WHERE course_id=? AND student_id=?", (cid, sid))
    conn.commit()
    conn.close()
    return ok(message="已退選")


@app.get("/api/selection/me")
@login_required
@roles_allowed("student")
def selection_me():
    sid = current_user()["ref_id"]
    conn = get_conn()
    rows = conn.execute("""SELECT cs.*, c.name, c.code, c.credits, c.weekday, c.period_start, c.period_end,
        c.course_type, f.name teacher_name, c.max_students,
        (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) enrolled_count
        FROM course_selections cs JOIN courses c ON c.id=cs.course_id
        LEFT JOIN faculties f ON f.id=c.teacher_id WHERE cs.student_id=?
        ORDER BY cs.phase DESC, cs.status, cs.created_at""", (sid,)).fetchall()
    enrolled_extra = conn.execute("""SELECT c.*, e.source, f.name teacher_name FROM enrollments e
        JOIN courses c ON c.id=e.course_id LEFT JOIN faculties f ON f.id=c.teacher_id
        WHERE e.student_id=? AND e.source='加退選' ORDER BY c.id""", (sid,)).fetchall()
    conn.close()
    return ok(selections=rows_to_list(rows), enrolled_extra=rows_to_list(enrolled_extra))


@app.get("/api/selection/popularity")
@login_required
@roles_allowed("admin", "clerk")
def selection_popularity():
    conn = get_conn()
    rows = conn.execute("""SELECT c.id, c.name, c.code, c.credits, c.max_students, c.weekday, c.period_start, c.period_end,
        f.name teacher_name,
        (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) enrolled_count,
        (SELECT COUNT(*) FROM course_selections cs WHERE cs.course_id=c.id AND cs.status!='退選') apply_count
        FROM courses c LEFT JOIN faculties f ON f.id=c.teacher_id
        WHERE c.semester=? AND c.course_type IN ('系選修','核心通識')
        ORDER BY apply_count DESC""", (current_semester(),)).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


# ---------------------------------------------------------------- 財務
@app.get("/api/invoices")
@login_required
@roles_allowed("admin", "clerk")
def invoices():
    u = current_user()
    dept = request.args.get("dept", "").strip()
    paid = request.args.get("paid", "").strip()
    q = request.args.get("q", "").strip()
    where, args = [], []
    if u["role"] == "clerk":
        where.append("s.dept_id=?")
        args.append(u["dept_id"])
    if dept:
        where.append("s.dept_id=?")
        args.append(dept)
    if paid:
        where.append("i.paid=?")
        args.append(paid)
    if q:
        like = f"%{q}%"
        where.append("(s.name LIKE ? OR s.student_no LIKE ?)")
        args += [like, like]
    wsql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    rows = conn.execute(f"""SELECT i.*, s.name, s.student_no, d.name dept_name FROM tuition_invoices i
        JOIN students s ON s.id=i.student_id JOIN departments d ON d.id=s.dept_id {wsql}
        ORDER BY i.paid, s.dept_id, s.student_no LIMIT 800""", args).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.get("/api/invoices/me")
@login_required
@roles_allowed("student")
def invoices_me():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tuition_invoices WHERE student_id=? ORDER BY semester", (current_user()["ref_id"],)).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.put("/api/invoices/<int:iid>")
@login_required
@roles_allowed("admin", "clerk")
def invoice_update(iid):
    d = request.get_json(force=True, silent=True) or {}
    paid = d.get("paid")
    method = d.get("method")
    conn = get_conn()
    if paid is not None:
        conn.execute("UPDATE tuition_invoices SET paid=?, paid_date=?, method=? WHERE id=?",
                     (1 if paid else 0, datetime.date.today().isoformat() if paid else None, method or "現場收費", iid))
    conn.commit()
    conn.close()
    return ok(message="已更新繳費狀態")


@app.get("/api/scholarships")
@login_required
@roles_allowed("admin", "clerk")
def scholarships():
    conn = get_conn()
    rows = conn.execute("""SELECT sc.*, s.name sname, s.student_no, d.name dept_name FROM scholarships sc
        JOIN students s ON s.id=sc.student_id JOIN departments d ON d.id=s.dept_id
        ORDER BY sc.date DESC""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.get("/api/scholarships/me")
@login_required
@roles_allowed("student")
def scholarships_me():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM scholarships WHERE student_id=? ORDER BY date DESC", (current_user()["ref_id"],)).fetchall()
    conn.close()
    return ok(rows_to_list(rows))


# ---------------------------------------------------------------- 獎懲
@app.get("/api/rewards")
@login_required
def rewards():
    u = current_user()
    conn = get_conn()
    if u["role"] == "student":
        rows = conn.execute("""SELECT r.*, COALESCE(f.name,'') recorder_name FROM rewards r
            LEFT JOIN faculties f ON f.id=r.recorder_id
            WHERE r.student_id=? ORDER BY r.date DESC""", (u["ref_id"],)).fetchall()
    else:
        rows = conn.execute("""SELECT r.*, s.name, s.student_no, d.name dept_name FROM rewards r
            JOIN students s ON s.id=r.student_id JOIN departments d ON d.id=s.dept_id
            ORDER BY r.date DESC LIMIT 600""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/rewards")
@login_required
@roles_allowed("admin", "clerk")
def create_reward():
    d = request.get_json(force=True, silent=True) or {}
    if not d.get("student_id") or not d.get("rtype"):
        return err("缺少資料")
    conn = get_conn()
    conn.execute("""INSERT INTO rewards (student_id,date,rtype,reason,recorder_id,status)
        VALUES (?,?,?,?,?, '核定')""",
        (d["student_id"], d.get("date") or datetime.date.today().isoformat(), d["rtype"], d.get("reason"),
         current_user().get("id")))
    conn.commit()
    conn.close()
    return ok(message="已登錄")


@app.delete("/api/rewards/<int:rid>")
@login_required
@roles_allowed("admin", "clerk")
def delete_reward(rid):
    conn = get_conn()
    conn.execute("DELETE FROM rewards WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return ok(message="已刪除")


# ---------------------------------------------------------------- 輔導紀錄
@app.get("/api/counseling")
@login_required
def counseling():
    u = current_user()
    conn = get_conn()
    if u["role"] == "student":
        rows = conn.execute("""SELECT cl.*, f.name tname FROM counseling_logs cl
            JOIN faculties f ON f.id=cl.teacher_id WHERE cl.student_id=? ORDER BY cl.date DESC""", (u["ref_id"],)).fetchall()
    elif u["role"] == "teacher":
        rows = conn.execute("""SELECT cl.*, s.name sname, s.student_no FROM counseling_logs cl
            JOIN students s ON s.id=cl.student_id WHERE cl.teacher_id=? ORDER BY cl.date DESC""", (u["ref_id"],)).fetchall()
    else:
        rows = conn.execute("""SELECT cl.*, s.name sname, s.student_no, f.name tname FROM counseling_logs cl
            JOIN students s ON s.id=cl.student_id JOIN faculties f ON f.id=cl.teacher_id
            ORDER BY cl.date DESC LIMIT 600""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/counseling")
@login_required
@roles_allowed("admin", "clerk", "teacher", "student")
def create_counseling():
    d = request.get_json(force=True, silent=True) or {}
    u = current_user()
    if u["role"] == "student":
        sid = u["ref_id"]
        content = d.get("message") or d.get("content")
        if not content:
            return err("請輸入訊息內容")
        tid = conn_find_counselor(sid)
        if not tid:
            return err("目前無可指派的輔導教師")
        conn = get_conn()
        conn.execute("""INSERT INTO counseling_logs (student_id,teacher_id,date,topic,content)
            VALUES (?,?,?,?,?)""",
            (sid, tid, datetime.date.today().isoformat(), "學生求助", content))
        conn.commit()
        conn.close()
        return ok(message="已送出，輔導教師會盡快回覆")
    if not d.get("student_id") or not d.get("content"):
        return err("缺少資料")
    teacher_id = d.get("teacher_id") or conn_find_counselor(d["student_id"])
    if u["role"] == "teacher":
        teacher_id = u["ref_id"]
    conn = get_conn()
    conn.execute("""INSERT INTO counseling_logs (student_id,teacher_id,date,topic,content)
        VALUES (?,?,?,?,?)""",
        (d["student_id"], teacher_id, d.get("date") or datetime.date.today().isoformat(),
         d.get("topic"), d["content"]))
    conn.commit()
    conn.close()
    return ok(message="已儲存約談紀錄")


# ---------------------------------------------------------------- 公告
@app.get("/api/announcements")
@login_required
def announcements():
    u = current_user()
    conn = get_conn()
    if u["role"] == "student":
        sid = u["ref_id"]
        rows = conn.execute("""SELECT a.*, COALESCE(d.name,'全校') scope FROM announcements a
            LEFT JOIN departments d ON d.id=a.dept_id
            WHERE a.dept_id IS NULL OR a.dept_id=(SELECT dept_id FROM students WHERE id=?)
            ORDER BY a.pinned DESC, a.created_at DESC""", (sid,)).fetchall()
    else:
        rows = conn.execute("""SELECT a.*, COALESCE(d.name,'全校') scope FROM announcements a
            LEFT JOIN departments d ON d.id=a.dept_id ORDER BY a.pinned DESC, a.created_at DESC""").fetchall()
    conn.close()
    return ok(rows_to_list(rows))


@app.post("/api/announcements")
@login_required
@roles_allowed("admin", "clerk")
def create_announcement():
    d = request.get_json(force=True, silent=True) or {}
    if not d.get("title") or not d.get("content"):
        return err("缺少標題或內容")
    u = current_user()
    dept_id = d.get("dept_id")
    if u["role"] == "clerk":
        dept_id = u["dept_id"]
    conn = get_conn()
    conn.execute("""INSERT INTO announcements (title,category,content,author_id,dept_id,pinned,created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (d["title"], d.get("category") or "校園公告", d["content"], u.get("id"), dept_id,
         1 if d.get("pinned") else 0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    return ok(message="已發布")


@app.delete("/api/announcements/<int:aid>")
@login_required
@roles_allowed("admin", "clerk")
def delete_announcement(aid):
    conn = get_conn()
    conn.execute("DELETE FROM announcements WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return ok(message="已刪除")


# ---------------------------------------------------------------- 報表（CSV）
@app.get("/api/reports/<name>.csv")
@login_required
def csv_report(name):
    u = current_user()
    conn = get_conn()
    buf = io.StringIO()
    writer = csv.writer(buf)
    if name == "students":
        cols = ["學號", "姓名", "性別", "系所", "年級", "座號", "狀態", "電話", "Email"]
        writer.writerow(cols)
        rows = conn.execute("""SELECT s.student_no, s.name, s.gender, d.name, s.grade, s.class_no, s.status, s.phone, s.email
            FROM students s JOIN departments d ON d.id=s.dept_id ORDER BY s.dept_id, s.student_no""").fetchall()
        for r in rows:
            writer.writerow(list(r))
        fname = "學生名冊"
    elif name == "courses":
        cols = ["課程代碼", "課程名稱", "類別", "學分", "星期", "節次", "教室", "教師", "上限", "已選", "狀態"]
        tscope = ""
        targs = ()
        if u["role"] == "teacher":
            tscope = " WHERE c.teacher_id=?"
            targs = (u["ref_id"],)
        rows = conn.execute(f"""SELECT c.code, c.name, c.course_type, c.credits, c.weekday,
            c.period_start || '~' || c.period_end, c.room, f.name,
            c.max_students, (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id), c.status
            FROM courses c LEFT JOIN faculties f ON f.id=c.teacher_id{tscope} ORDER BY c.id""", targs).fetchall()
        writer.writerow(cols)
        for r in rows:
            writer.writerow(list(r))
        fname = "課程清單"
    elif name == "grades":
        course_id = request.args.get("course_id", "")
        cols = ["學號", "姓名", "期中", "期末", "總分", "等第", "GPA"]
        rows = conn.execute("""SELECT s.student_no, s.name, g.midterm, g.final, g.total, g.grade_letter, g.gpa
            FROM grades g JOIN students s ON s.id=g.student_id WHERE g.course_id=? ORDER BY s.student_no""",
            (course_id,)).fetchall()
        writer.writerow(cols)
        for r in rows:
            writer.writerow(list(r))
        cname = conn.execute("SELECT name FROM courses WHERE id=?", (course_id,)).fetchone()
        fname = f"成績_{cname['name'] if cname else course_id}"
    elif name == "invoices":
        cols = ["學號", "姓名", "學雜費", "學分費", "學分數", "住宿費", "總額", "繳費狀態", "繳費日"]
        rows = conn.execute("""SELECT s.student_no, s.name, i.base_fee, i.credit_fee, i.credit_count, i.dorm_fee,
            i.total, i.paid, i.paid_date FROM tuition_invoices i JOIN students s ON s.id=i.student_id
            ORDER BY s.dept_id, s.student_no""").fetchall()
        writer.writerow(cols)
        for r in rows:
            rr = list(r)
            rr[7] = "已繳" if rr[7] else "未繳"
            writer.writerow(rr)
        fname = "學雜費繳費清單"
    elif name == "transcript":
        student_id = request.args.get("student_id", "")
        stu = conn.execute("SELECT s.name, d.name dn FROM students s JOIN departments d ON d.id=s.dept_id WHERE s.id=?", (student_id,)).fetchone()
        cols = ["課程名稱", "學分", "期中", "期末", "總分", "等第", "GPA"]
        rows = conn.execute("""SELECT c.name, c.credits, g.midterm, g.final, g.total, g.grade_letter, g.gpa
            FROM grades g JOIN courses c ON c.id=g.course_id WHERE g.student_id=? ORDER BY c.id""", (student_id,)).fetchall()
        writer.writerow(cols)
        for r in rows:
            writer.writerow(list(r))
        fname = f"成績單_{stu['name'] if stu else student_id}"
    else:
        conn.close()
        return err("未知報表")
    conn.close()
    today = datetime.date.today().isoformat()
    from urllib.parse import quote
    ascii_name = f"report_{today}.csv"
    encoded = quote(f"{fname}_{today}.csv")
    resp = Response("\ufeff" + buf.getvalue(), mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
    return resp


# ---------------------------------------------------------------- 設定
@app.get("/api/settings")
@login_required
def settings_api():
    return ok(school=school_name(), semester=current_semester(), phase=selection_phase())


# ---------------------------------------------------------------- 靜態首頁
@app.route("/")
def index_route():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


def conn_find_counselor(student_id):
    conn = get_conn()
    try:
        row = conn.execute("""SELECT id FROM faculties
            WHERE dept_id=(SELECT dept_id FROM students WHERE id=?)
            AND status='在職' ORDER BY id LIMIT 1""", (student_id,)).fetchone()
        if not row:
            row = conn.execute("SELECT id FROM faculties ORDER BY id LIMIT 1").fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# 首次啟動初始化：資料庫不存在時自動建立並產生種子資料
def ensure_initialized():
    if not is_seeded():
        seed.main(force=False)


@app.teardown_request
def _close_conns(exc):
    close_all()


ensure_initialized()

if __name__ == "__main__":
    init_db()
    if not is_seeded():
        seed.main(force=False)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)