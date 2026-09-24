-- 校務行政系統 (School Administration System)
-- 資料表定義 — 大學版模擬

PRAGMA foreign_keys = ON;

-- 學院
CREATE TABLE IF NOT EXISTS colleges (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  name TEXT NOT NULL
);

-- 系所
CREATE TABLE IF NOT EXISTS departments (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  college_id  INTEGER NOT NULL REFERENCES colleges(id),
  code        TEXT UNIQUE,
  name        TEXT NOT NULL,
  grad_credits INTEGER DEFAULT 128
);

-- 教職員
CREATE TABLE IF NOT EXISTS faculties (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  dept_id   INTEGER REFERENCES departments(id),   -- NULL = 通識教育中心
  name      TEXT NOT NULL,
  gender    TEXT,
  title     TEXT,      -- 教授 / 副教授 / 助理教授 / 講師 / 助教
  email     TEXT,
  office    TEXT,
  phone     TEXT,
  hire_date TEXT,
  status    TEXT DEFAULT '在職'   -- 在職 / 離職
);

-- 學生
CREATE TABLE IF NOT EXISTS students (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  dept_id        INTEGER NOT NULL REFERENCES departments(id),
  student_no     TEXT UNIQUE,
  name           TEXT NOT NULL,
  gender         TEXT,
  birth_date     TEXT,
  grade          INTEGER,      -- 1 ~ 4
  class_no       INTEGER,
  enroll_year    INTEGER,      -- 民國年（入學年），如 113
  status         TEXT DEFAULT '在學',  -- 在學 / 休學 / 退學 / 畢業 / 延畢
  address        TEXT,
  phone          TEXT,
  email          TEXT,
  guardian_name  TEXT,
  guardian_phone TEXT
);

-- 課程
CREATE TABLE IF NOT EXISTS courses (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  dept_id          INTEGER REFERENCES departments(id),  -- NULL = 通識教育中心
  code             TEXT UNIQUE,
  name             TEXT NOT NULL,
  credits          INTEGER,
  course_type      TEXT,    -- 系必修 / 系選修 / 通識 / 體育 / 核心通識
  semester         TEXT,    -- 例如 113-1
  restriction_dept INTEGER, -- NULL = 全校皆可；否則限該系
  restriction_grade TEXT,   -- NULL = 全年級；或 '1' / '2' / '1,2'
  teacher_id       INTEGER NOT NULL REFERENCES faculties(id),
  weekday          INTEGER, -- 1=一 2=二 3=三 4=四 5=五 6=六
  period_start     INTEGER, -- 起始節次（第 N 節）
  period_end       INTEGER, -- 結束節次（含）
  room             TEXT,
  max_students     INTEGER,
  status           TEXT DEFAULT '開課'   -- 開課 / 停開
);

-- 修課登記（必修自動 / 選課錄取後寫入）
CREATE TABLE IF NOT EXISTS enrollments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id  INTEGER NOT NULL REFERENCES courses(id),
  student_id INTEGER NOT NULL REFERENCES students(id),
  source     TEXT DEFAULT '選課',   -- 必修自動 / 通識自動 / 志願結算 / 加退選
  UNIQUE(course_id, student_id)
);

-- 選課登記（初選志願 / 加退選）
CREATE TABLE IF NOT EXISTS course_selections (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  course_id  INTEGER NOT NULL REFERENCES courses(id),
  priority   INTEGER,     -- 志願序 1,2,3,4
  phase      TEXT DEFAULT '初選',  -- 初選 / 加退選
  status     TEXT DEFAULT '暫選',  -- 暫選 / 候補 / 錄取 / 未錄取 / 退選
  created_at TEXT
);

-- 成績
CREATE TABLE IF NOT EXISTS grades (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id   INTEGER NOT NULL REFERENCES courses(id),
  student_id  INTEGER NOT NULL REFERENCES students(id),
  midterm     REAL,
  final       REAL,
  total       REAL,
  grade_letter TEXT,
  gpa         REAL,
  UNIQUE(course_id, student_id)
);

-- 出缺席（課程點名）
CREATE TABLE IF NOT EXISTS attendance (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id  INTEGER NOT NULL REFERENCES courses(id),
  student_id INTEGER NOT NULL REFERENCES students(id),
  date       TEXT,
  status     TEXT DEFAULT '出席',   -- 出席 / 遲到 / 曠課 / 病假 / 事假 / 公假
  UNIQUE(course_id, student_id, date)
);

-- 請假單
CREATE TABLE IF NOT EXISTS leaves (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  course_id  INTEGER REFERENCES courses(id),
  date       TEXT,
  leave_type TEXT,      -- 病假 / 事假 / 公假
  reason     TEXT,
  status     TEXT DEFAULT '審核中',  -- 審核中 / 核准 / 駁回
  created_at TEXT
);

-- 獎懲
CREATE TABLE IF NOT EXISTS rewards (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id  INTEGER NOT NULL REFERENCES students(id),
  date        TEXT,
  rtype       TEXT,     -- 嘉獎 / 小功 / 大功 / 警告 / 小過 / 大過
  reason      TEXT,
  recorder_id INTEGER,
  status      TEXT DEFAULT '核定'
);

-- 導師約談 / 輔導紀錄
CREATE TABLE IF NOT EXISTS counseling_logs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  teacher_id INTEGER NOT NULL REFERENCES faculties(id),
  date       TEXT,
  topic      TEXT,
  content    TEXT
);

-- 學雜費繳費單
CREATE TABLE IF NOT EXISTS tuition_invoices (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id   INTEGER NOT NULL REFERENCES students(id),
  semester     TEXT,
  base_fee     INTEGER,   -- 學雜費
  credit_fee   INTEGER,   -- 學分費（單價）
  credit_count INTEGER,   -- 修課學分數
  dorm_fee     INTEGER DEFAULT 0,  -- 住宿費
  total        INTEGER,
  paid         INTEGER DEFAULT 0,   -- 0 未繳 / 1 已繳
  paid_date    TEXT,
  method       TEXT
);

-- 獎助學金
CREATE TABLE IF NOT EXISTS scholarships (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id),
  name       TEXT,
  amount     INTEGER,
  semester   TEXT,
  date       TEXT,
  status     TEXT DEFAULT '核發'
);

-- 公告
CREATE TABLE IF NOT EXISTS announcements (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT,
  category   TEXT,       -- 校園公告 / 系辦公告
  content    TEXT,
  author_id  INTEGER,
  dept_id    INTEGER,
  pinned     INTEGER DEFAULT 0,
  created_at TEXT
);

-- 系統設定
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT
);

-- 登入帳號（role: admin / clerk / teacher / student）
CREATE TABLE IF NOT EXISTS users (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE,
  password TEXT,        -- sha256 hex
  role     TEXT,
  ref_id   INTEGER,     -- 對應 students.id 或 faculties.id
  name     TEXT,
  dept_id  INTEGER
);

-- 大學節次表
CREATE TABLE IF NOT EXISTS periods (
  id         INTEGER PRIMARY KEY,
  name       TEXT,
  start_time TEXT,
  end_time   TEXT,
  is_night   INTEGER DEFAULT 0
);