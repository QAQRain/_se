# SAS_project — 製作進度與重啟指引

Launcher-only? 否：此專案完整可運行（Flask + SQLite SPA，深色校務行政系統）。

啟動方式：`python app.py` → http://localhost:5000
第一次啟動自動建庫＋種子資料。容器內需先：`apk add --no-cache python3 py3-pip py3-flask`（每次重啟要重裝）

重疾（重新產生乾淨資料）：`python3 seed.py --force`（會清空並重建 224/57/183，選課階段回到 closed）

## Demo 帳號
admin/admin123（系統管理員）、clerk/clerk123（行政）、teacher/teacher123（教師）、student/student123（學生 11311001 馮美玲）；其餘教師/學生帳號＝名字拼音/學號，密碼 123456。

## 已完成
- [x] schema.sql（大學版全部資料表：學院/系/學生/教職員/課程/修課/選課/成績/點名/請假/獎懲/約談/繳費/獎學金/公告/帳號/節次）
- [x] db.py（SQLite：WAL、busy_timeout=5000、thread-local 連線管理，request 結束 `close_all()` 防鎖庫）
- [x] seed.py（隨機擬真：224 學生 / 57 教職員 / 183 課程 / 2016 修課；通識同名課程只自動修一班、核心通識上限 60、demo 學生 23 學分 9 門課）
- [x] app.py（Flask 後端：登入權限 4 角色、儀表板、學生/教職員/課程 CRUD、課表、點名、請假、成績/GPA（4.3 制）、選課（初選上限 4 志願＋學分上限 28＋加退選＋志願結算）、財務、獎懲、約談（學生求助自動導向系上輔導教師）、公告、CSV 報表含 UTF-8 檔案名）
- [x] templates/index.html（深色 SPA 殼：登入頁＋側欄布局，Tailwind/Chart.js 走 CDN）
- [x] static/app.js（hash 路由＋各模組畫面：圖表、CRUD、課表網格、選課、點名、成績、報表下載；`node --check` 通過）
- [x] static/style.css（深色主題＋回應式兩欄＋表格樣式）
- [x] 後端全 API 已用 Node（fetch）實測通過（82 項測試：36 形狀＋6 欄位＋40 掃描；含選課全流程與權限拒絕），最終資料庫為 `seed.py --force` 後的乾淨狀態
- [x] README.md

## 前端與欄位對應注意（下次維護必看）
- `/api/students/<id>` 回 `profile/courses/transcript/rewards/leaves/summary`（無 `data` key）；`/api/transcript/<sid>` 回頂層 `rows/summary/student`。
- student dashboard 回 `base{enrolled,credits,gpa,credits_max,unread}`、`attendance`(dict)、`grade_dist{hi,mid,lo}`。
- 學生自我檢視頁：`/api/students` 列表 row 用 `student_no/name/grade/dept_name`；課程名單 `/api/courses/<id>/roster` row 用 `id`（非 student_id）。
- 成績/點名/請假 row：`grades?course_id`、`attendance?course_id` 用 `student_id`；請假學生欄位是 `sname`；獎懲學生欄位 `name`；諮商用 `sname`/`content`/`date`/`tname`/`topic`；獎學金用 `sname`（後端已 alias）。
- CSV：`downloadCsv()` 解析 `filename*=UTF-8''`，檔案名含中文、無法 latin-1 的文字一律走這條。
- 選課 API：`selection/apply` 送 `{selections:[{course_id,priority}]}`（≤4）；`settle` 依志願序＋名額錄取，學分上限 28。

## 已知注意事項
- Flask 3 已移除 `@app.before_first_request`；首次啟動由 module import 時 `ensure_initialized()` 自動建庫＋種子。
- `pkill` 請用 `pkill -f '^python3 app\.py'`，且與啟動拆成兩個指令，否則會誤殺 shell 自己。
- 容器每次重啟需重裝 python3/flask。
- 2026-09-23 全面盤點修正：`timetable?who=deptgrade` 改讀 `dept`/`grade` 參數（原先解析 `id` 會 500）；教師寫入成績/點名/請假核准均限自己課程（防越權）；學生請假須選課程（送 `course_id`），教師才會看到並可核准；`counseling` 教師端缺失 `teacher_id` 時自動派系上輔導教師；`toast()` 不再覆蓋定位 class；CSS 加 Tailwind 離線退路樣式。