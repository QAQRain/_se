/* ===========================================================
   AniDex 動漫資料站 — 主程式
   純前端、無框架、無建置步驟
   =========================================================== */
(function () {
  "use strict";

  /* ── 資料 ───────────────────────────────────────────── */
  var DATA = Array.isArray(window.ANIME_DATA) ? window.ANIME_DATA : [];
  var ZH = window.TITLES_ZH || {};
  var BY_ID = {};
  DATA.forEach(function (a) { BY_ID[a.id] = a; });

  var MAX_PICK = 4;
  var PICK_KEY = "anidex-picks";

  var STATUS_ZH = {
    FINISHED: "已完結",
    RELEASING: "連載中",
    NOT_YET_RELEASED: "未播出",
    CANCELLED: "已取消",
    HIATUS: "停播"
  };
  var FMT_ZH = {
    TV: "電視動畫",
    TV_SHORT: "短篇動畫",
    MOVIE: "劇場版",
    OVA: "OVA",
    ONA: "網路動畫",
    SPECIAL: "特別篇",
    MUSIC: "音樂"
  };
  var GENRE_ZH = {
    Action: "動作",
    Adventure: "冒險",
    Comedy: "喜劇",
    Drama: "劇情",
    Ecchi: "情色",
    Fantasy: "奇幻",
    Horror: "恐怖",
    "Mahou Shoujo": "魔法少女",
    Mecha: "機甲",
    Music: "音樂",
    Mystery: "懸疑",
    Psychological: "心理",
    Romance: "戀愛",
    "Sci-Fi": "科幻",
    "Slice of Life": "日常",
    Sports: "運動",
    Supernatural: "超自然",
    Thriller: "驚悚"
  };
  var SORT_OPTIONS = [
    ["pop", "人氣（高到低）"],
    ["score", "評分（高到低）"],
    ["year", "年份（新到舊）"],
    ["year-asc", "年份（舊到新）"],
    ["title", "名稱排序"]
  ];

  /* ── DOM ────────────────────────────────────────────── */
  var $view = document.getElementById("view");
  var $search = document.getElementById("search");
  var $comparebar = document.getElementById("comparebar");

  /* ── 小工具 ─────────────────────────────────────────── */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // 全角／半角、破折號差異會讓同一個標題對不上，先正規化再比對
  function normKey(s) {
    return String(s || "")
      .replace(/[\uFF01-\uFF5E]/g, function (ch) {
        return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0);
      })
      .replace(/[\u2010-\u2015\u2212\u3000]/g, function (ch) {
        return ch === "\u3000" ? " " : "-";
      });
  }

  var ZH_NORM = {};
  Object.keys(ZH).forEach(function (k) { ZH_NORM[normKey(k)] = ZH[k]; });
  var ZH_KEYS = Object.keys(ZH_NORM).sort(function (x, y) { return y.length - x.length; });

  function zhName(a) {
    var jaN = normKey(a.ja);
    var enN = normKey(a.en);
    if (jaN && ZH_NORM[jaN]) return ZH_NORM[jaN];
    // 日文原名帶季數或副標時，用最長的對照表前綴比對
    if (jaN) {
      for (var i = 0; i < ZH_KEYS.length; i++) {
        var k = ZH_KEYS[i];
        if (k.length >= 3 && jaN.indexOf(k) === 0) return ZH_NORM[k];
      }
    }
    if (enN && ZH_NORM[enN]) return ZH_NORM[enN];
    return a.ja || a.en || "未命名作品";
  }

  function altName(a) {
    var primary = zhName(a);
    if (a.ja && a.ja !== primary) return a.ja;
    if (a.en && a.en !== primary) return a.en;
    return "";
  }

  function scoreText(a) {
    if (!a.score) return "—";
    return (a.score / 10).toFixed(1);
  }

  function genreText(g) {
    return GENRE_ZH[g] || g;
  }

  function fmtNum(n) {
    return Number(n || 0).toLocaleString("zh-TW");
  }

  function parseHash() {
    var raw = location.hash.replace(/^#/, "") || "/";
    var i = raw.indexOf("?");
    var path = i >= 0 ? raw.slice(0, i) : raw;
    var params = new URLSearchParams(i >= 0 ? raw.slice(i + 1) : "");
    if (!path) path = "/";
    return { path: path, params: params };
  }

  function makeHash(path, params) {
    var qs = params.toString();
    return "#" + path + (qs ? "?" + qs : "");
  }

  function go(path, params, replace) {
    var hash = makeHash(path, params);
    if (location.hash === hash) return;
    if (replace) {
      try {
        history.replaceState(null, "", hash);
        return;
      } catch (e) {
        // file:// 開啟時部分瀏覽器不允許 replaceState，退回修改 hash
      }
    }
    location.hash = hash;
  }

  var FILTER_IDS = {
    "f-genre": "g",
    "f-ys": "ys",
    "f-ye": "ye",
    "f-min": "min",
    "f-status": "st",
    "f-sort": "sort"
  };

  function syncFilterInputs(params) {
    Object.keys(FILTER_IDS).forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      var v = params.get(FILTER_IDS[id]) || "";
      if (el.value !== v) el.value = v;
    });
  }

  /* ── 比較清單 ───────────────────────────────────────── */
  function getPicks() {
    var raw;
    try { raw = JSON.parse(localStorage.getItem(PICK_KEY) || "[]"); }
    catch (e) { raw = []; }
    if (!Array.isArray(raw)) return [];
    return raw.filter(function (id) { return BY_ID[id]; }).slice(0, MAX_PICK);
  }

  function setPicks(arr) {
    var ids = arr.filter(function (id) { return BY_ID[id]; }).slice(0, MAX_PICK);
    try { localStorage.setItem(PICK_KEY, JSON.stringify(ids)); } catch (e) { /* 忽略 */ }
    document.querySelectorAll(".pick").forEach(function (btn) {
      var on = ids.indexOf(Number(btn.dataset.id)) >= 0;
      btn.classList.toggle("on", on);
      btn.textContent = on ? "✓" : "+";
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.title = on ? "移出比較" : "加入比較";
    });
    renderCompareBar();
    return ids;
  }

  function togglePick(id) {
    id = Number(id);
    var ids = getPicks();
    var i = ids.indexOf(id);
    if (i >= 0) ids.splice(i, 1);
    else {
      if (ids.length >= MAX_PICK) {
        alert("最多只能比較 " + MAX_PICK + " 部作品，請先移除一部。");
        return;
      }
      ids.push(id);
    }
    setPicks(ids);
  }

  function renderCompareBar() {
    if (!$comparebar) return;
    var ids = getPicks();
    var onCompare = parseHash().path === "/compare";
    if (!ids.length || onCompare) {
      $comparebar.hidden = true;
      return;
    }
    $comparebar.hidden = false;
    document.getElementById("comparebar-count").textContent = String(ids.length);
    document.getElementById("comparebar-list").innerHTML = ids.map(function (id) {
      var a = BY_ID[id];
      return '<span class="mini">' +
        (a.img ? '<img src="' + esc(a.img) + '" alt="" referrerpolicy="no-referrer">' : "") +
        '<span>' + esc(zhName(a)) + '</span>' +
        '<button type="button" data-remove="' + a.id + '" aria-label="移除">×</button>' +
        '</span>';
    }).join("");
    document.getElementById("comparebar-go").href = "#/compare";
  }

  /* ── 列表頁 ─────────────────────────────────────────── */
  function allGenres() {
    var set = {};
    DATA.forEach(function (a) {
      (a.genres || []).forEach(function (g) { set[g] = (set[g] || 0) + 1; });
    });
    return Object.keys(set).sort(function (x, y) {
      return set[y] - set[x];
    });
  }

  function filterAndSort(params) {
    var q = (params.get("q") || "").trim().toLowerCase();
    var g = params.get("g") || "";
    var ys = Number(params.get("ys") || 0);
    var ye = Number(params.get("ye") || 0);
    var min = Number(params.get("min") || 0);
    var st = params.get("st") || "";
    var sort = params.get("sort") || "pop";

    var list = DATA.filter(function (a) {
      if (q) {
        var hay = (zhName(a) + " " + (a.ja || "") + " " + (a.en || "")).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      if (g && (a.genres || []).indexOf(g) < 0) return false;
      if (ys && (!a.year || a.year < ys)) return false;
      if (ye && (!a.year || a.year > ye)) return false;
      if (min && a.score < min * 10) return false;
      if (st && a.status !== st) return false;
      return true;
    });

    list.sort(function (a, b) {
      if (sort === "score") {
        return (b.score - a.score) || (b.pop - a.pop);
      }
      if (sort === "year") {
        return (b.year - a.year) || (b.pop - a.pop);
      }
      if (sort === "year-asc") {
        return (a.year || 9999) - (b.year || 9999) || (b.pop - a.pop);
      }
      if (sort === "title") {
        return zhName(a).localeCompare(zhName(b), "zh-Hant-TW");
      }
      return (b.pop - a.pop) || (b.score - a.score);
    });

    return list;
  }

  function cardHtml(a, picked) {
    var name = zhName(a);
    var alt = altName(a);
    var sc = a.score ? (a.score / 10).toFixed(1) : "—";
    return '<article class="card">' +
      '<a class="card-cover" href="#/a/' + a.id + '" aria-label="' + esc(name) + '">' +
        (a.img
          ? '<img src="' + esc(a.img) + '" alt="' + esc(name) + ' 封面" loading="lazy" referrerpolicy="no-referrer">'
          : "") +
        '<span class="score-badge' + (a.score && a.score < 70 ? " low" : "") + '">' + sc + '</span>' +
      '</a>' +
      '<button class="pick' + (picked ? " on" : "") + '" type="button" data-id="' + a.id + '" ' +
        'aria-pressed="' + (picked ? "true" : "false") + '" title="' + (picked ? "移出比較" : "加入比較") + '">' +
        (picked ? "✓" : "+") + '</button>' +
      '<div class="card-body">' +
        '<a class="card-title" href="#/a/' + a.id + '">' + esc(name) + '</a>' +
        (alt ? '<span class="card-sub">' + esc(alt) + '</span>' : "") +
        '<span class="card-meta">' +
          '<span>' + (a.year || "—") + '</span>' +
          '<span>' + (a.eps ? a.eps + " 話" : (FMT_ZH[a.fmt] || "—")) + '</span>' +
        '</span>' +
      '</div>' +
    '</article>';
  }

  function renderGrid(params) {
    var grid = document.getElementById("grid");
    var countEl = document.getElementById("result-count");
    if (!grid) return;
    var list = filterAndSort(params);
    var picks = getPicks();
    if (countEl) {
      countEl.innerHTML = "共 <strong>" + list.length + "</strong> 部作品" +
        (DATA.length !== list.length ? "（全部 " + DATA.length + " 部）" : "");
    }
    if (!list.length) {
      grid.innerHTML = '<div class="empty" style="grid-column:1/-1"><strong>找不到符合條件的作品</strong>' +
        '試著放寬年份、評分或清除關鍵字。</div>';
      return;
    }
    var html = [];
    for (var i = 0; i < list.length; i++) {
      html.push(cardHtml(list[i], picks.indexOf(list[i].id) >= 0));
    }
    grid.innerHTML = html.join("");
  }

  function filtersHtml(params) {
    var genres = allGenres();
    var opts = genres.map(function (g) {
      return '<option value="' + esc(g) + '"' + (params.get("g") === g ? " selected" : "") + '>' +
        esc(genreText(g)) + "（" + g + "）</option>";
    }).join("");

    var sortOpts = SORT_OPTIONS.map(function (o) {
      return '<option value="' + o[0] + '"' + ((params.get("sort") || "pop") === o[0] ? " selected" : "") + '>' +
        o[1] + "</option>";
    }).join("");

    var stOpts = Object.keys(STATUS_ZH).map(function (k) {
      return '<option value="' + k + '"' + (params.get("st") === k ? " selected" : "") + '>' +
        STATUS_ZH[k] + "</option>";
    }).join("");

    var minOpts = [["", "不限"], ["6", "6.0 以上"], ["7", "7.0 以上"], ["7.5", "7.5 以上"],
      ["8", "8.0 以上"], ["8.5", "8.5 以上"], ["9", "9.0 以上"]].map(function (o) {
      return '<option value="' + o[0] + '"' + (params.get("min") === o[0] ? " selected" : "") + '>' +
        o[1] + "</option>";
    }).join("");

    return '<div class="filters">' +
      '<div class="field"><label for="f-genre">類型</label>' +
        '<select id="f-genre"><option value="">全部類型</option>' + opts + "</select></div>" +
      '<div class="field range"><label>年份區間</label><div class="range-row">' +
        '<input id="f-ys" type="number" inputmode="numeric" placeholder="起始" min="1950" max="2030" value="' + esc(params.get("ys") || "") + '">' +
        '<span class="muted">–</span>' +
        '<input id="f-ye" type="number" inputmode="numeric" placeholder="結束" min="1950" max="2030" value="' + esc(params.get("ye") || "") + '">' +
      "</div></div>" +
      '<div class="field"><label for="f-min">最低評分</label><select id="f-min">' + minOpts + "</select></div>" +
      '<div class="field"><label for="f-status">狀態</label>' +
        '<select id="f-status"><option value="">全部狀態</option>' + stOpts + "</select></div>" +
      '<div class="field"><label for="f-sort">排序</label><select id="f-sort">' + sortOpts + "</select></div>" +
      '<div class="filters-foot">' +
        '<span id="result-count" class="result-count"></span>' +
        '<button id="f-reset" class="btn btn-sm btn-ghost" type="button">重設篩選</button>' +
      "</div>" +
    "</div>";
  }

  function bindFilters() {
    var map = {
      "f-genre": "g",
      "f-ys": "ys",
      "f-ye": "ye",
      "f-min": "min",
      "f-status": "st",
      "f-sort": "sort"
    };
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      var evt = el.tagName === "SELECT" ? "change" : "input";
      el.addEventListener(evt, function () {
        var params = parseHash().params;
        var key = map[id];
        var val = el.value.trim();
        if (val) params.set(key, val);
        else params.delete(key);
        go("/", params, true);
        renderGrid(params);
      });
    });

    var reset = document.getElementById("f-reset");
    if (reset) {
      reset.addEventListener("click", function () {
        $search.value = "";
        var empty = new URLSearchParams();
        go("/", empty, true);
        syncFilterInputs(empty);
        renderGrid(empty);
      });
    }
  }

  function renderList(params) {
    var already = $view.dataset.page === "list";
    if (!already) {
      $view.dataset.page = "list";
      $view.innerHTML =
        '<div class="page-head">' +
          "<h1>作品列表</h1>" +
          "<p>收錄 AniList 人氣前 " + DATA.length + " 名動畫，可用關鍵字、類型、年份、評分與狀態篩選。</p>" +
        "</div>" +
        filtersHtml(params) +
        '<div id="grid" class="grid"></div>';
      bindFilters();
    } else {
      // 只同步篩選列的值，不重建輸入框（避免正在輸入時失焦）
      syncFilterInputs(params);
    }
    renderGrid(params);
  }

  /* ── 詳情頁 ─────────────────────────────────────────── */
  function renderDetail(id) {
    var a = BY_ID[id];
    $view.dataset.page = "detail";
    if (!a) {
      $view.innerHTML = '<div class="empty"><strong>找不到這部作品</strong>' +
        '<a href="#/">回到作品列表</a></div>';
      return;
    }
    var picked = getPicks().indexOf(a.id) >= 0;
    var name = zhName(a);
    var alt = altName(a);
    var rows = [
      ["評分", a.score ? (a.score / 10).toFixed(1) + " / 10（AniList " + a.score + " 分）" : "尚無評分"],
      ["人氣", fmtNum(a.pop) + " 人收藏"],
      ["年份", a.year || "未知"],
      ["形式", FMT_ZH[a.fmt] || a.fmt || "—"],
      ["集數", a.eps ? a.eps + " 話" : "—"],
      ["單集長度", a.dur ? a.dur + " 分鐘" : "—"],
      ["狀態", STATUS_ZH[a.status] || a.status || "—"],
      ["製作公司", a.studio || "—"]
    ];
    var rowsHtml = rows.map(function (r) {
      return "<tr><th>" + esc(r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>";
    }).join("");

    var tags = (a.genres || []).map(function (g) {
      return '<span class="tag">' + esc(genreText(g)) + "</span>";
    }).join("");

    $view.innerHTML =
      '<div class="page-head"><a href="#/" class="muted">← 回到作品列表</a></div>' +
      '<div class="detail">' +
        '<div class="detail-cover">' +
          (a.img ? '<img src="' + esc(a.img) + '" alt="' + esc(name) + ' 封面" referrerpolicy="no-referrer">' : "") +
        "</div>" +
        "<div>" +
          "<h1>" + esc(name) + "</h1>" +
          (alt ? '<p class="alt-title">' + esc(alt) + "</p>" : "") +
          '<div class="detail-actions">' +
            '<button id="detail-pick" class="btn ' + (picked ? "btn-ghost" : "btn-primary") + '" type="button" data-id="' + a.id + '">' +
              (picked ? "✓ 已加入比較" : "+ 加入比較") + "</button>" +
            (a.id ? '<a class="btn btn-ghost" href="#/compare">查看比較清單</a>' : "") +
          "</div>" +
          '<table class="info-table"><tbody>' + rowsHtml + "</tbody></table>" +
          '<div class="tags" style="margin-top:16px">' + tags + "</div>" +
          (a.desc ? '<div class="desc"><h3>作品簡介（英文原文）</h3>' + esc(a.desc) + "</div>" : "") +
        "</div>" +
      "</div>";

    var pickBtn = document.getElementById("detail-pick");
    if (pickBtn) {
      pickBtn.addEventListener("click", function () {
        togglePick(a.id);
        var nowPicked = getPicks().indexOf(a.id) >= 0;
        pickBtn.className = "btn " + (nowPicked ? "btn-ghost" : "btn-primary");
        pickBtn.textContent = nowPicked ? "✓ 已加入比較" : "+ 加入比較";
      });
    }
    window.scrollTo(0, 0);
  }

  /* ── 比較頁 ─────────────────────────────────────────── */
  function renderCompare() {
    $view.dataset.page = "compare";
    var ids = getPicks();
    if (!ids.length) {
      $view.innerHTML = '<div class="page-head"><h1>比較清單</h1>' +
        "<p>尚未選擇作品。回到列表點卡片右上角的「+」即可加入比較（最多 " + MAX_PICK + " 部）。</p></div>" +
        '<div class="empty"><strong>比較清單是空的</strong><a href="#/">前往作品列表挑選</a></div>';
      return;
    }

    var items = ids.map(function (id) { return BY_ID[id]; });
    var bestScore = Math.max.apply(null, items.map(function (a) { return a.score || 0; }));
    var bestPop = Math.max.apply(null, items.map(function (a) { return a.pop || 0; }));

    function row(label, fn) {
      return "<tr><th>" + esc(label) + "</th>" + items.map(function (a) {
        return "<td>" + fn(a) + "</td>";
      }).join("") + "</tr>";
    }

    var head = "<tr><th></th>" + items.map(function (a) {
      return '<th class="ct-cover">' +
        (a.img ? '<img src="' + esc(a.img) + '" alt="" referrerpolicy="no-referrer">' : "") +
        '<a class="ct-title" href="#/a/' + a.id + '">' + esc(zhName(a)) + "</a>" +
        "</th>";
    }).join("") + "</tr>";

    var body = "";
    body += row("評分", function (a) {
      var cls = a.score && a.score === bestScore ? ' class="best"' : "";
      return "<span" + cls + ">" + (a.score ? (a.score / 10).toFixed(1) : "—") + "</span>";
    });
    body += row("人氣", function (a) {
      var cls = a.pop && a.pop === bestPop ? ' class="best"' : "";
      return "<span" + cls + ">" + fmtNum(a.pop) + "</span>";
    });
    body += row("年份", function (a) { return esc(a.year || "—"); });
    body += row("形式", function (a) { return esc(FMT_ZH[a.fmt] || a.fmt || "—"); });
    body += row("集數", function (a) { return a.eps ? a.eps + " 話" : "—"; });
    body += row("單集長度", function (a) { return a.dur ? a.dur + " 分鐘" : "—"; });
    body += row("狀態", function (a) { return esc(STATUS_ZH[a.status] || a.status || "—"); });
    body += row("製作公司", function (a) { return esc(a.studio || "—"); });
    body += row("類型", function (a) {
      return (a.genres || []).map(function (g) { return esc(genreText(g)); }).join("、");
    });

    $view.innerHTML =
      '<div class="page-head"><h1>作品比較</h1>' +
        "<p>並列比較 " + items.length + " 部作品（最多 " + MAX_PICK + " 部）。綠色代表該列數值最高。</p></div>" +
      '<div class="compare-wrap"><table class="compare-table">' +
        "<thead>" + head + "</thead><tbody>" + body + "</tbody></table></div>" +
      '<div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap">' +
        '<a class="btn btn-ghost" href="#/">繼續挑選</a>' +
        '<button id="compare-clear" class="btn btn-ghost" type="button">清空比較</button>' +
      "</div>";

    var clear = document.getElementById("compare-clear");
    if (clear) {
      clear.addEventListener("click", function () {
        setPicks([]);
        renderCompare();
      });
    }
    window.scrollTo(0, 0);
  }

  /* ── 路由 ───────────────────────────────────────────── */
  function route() {
    var st = parseHash();
    var path = st.path;

    if (path === "/" || path === "") {
      renderList(st.params);
    } else if (path.indexOf("/a/") === 0) {
      renderDetail(Number(path.slice(3)));
    } else if (path === "/compare") {
      renderCompare();
    } else {
      $view.dataset.page = "404";
      $view.innerHTML = '<div class="empty"><strong>找不到這個頁面</strong><a href="#/">回到作品列表</a></div>';
    }
    renderCompareBar();
  }

  /* ── 事件 ───────────────────────────────────────────── */
  document.addEventListener("click", function (e) {
    var pick = e.target.closest(".pick");
    if (pick) {
      e.preventDefault();
      togglePick(pick.dataset.id);
      return;
    }
    var remove = e.target.closest("[data-remove]");
    if (remove) {
      e.preventDefault();
      var ids = getPicks().filter(function (id) { return id !== Number(remove.dataset.remove); });
      setPicks(ids);
      return;
    }
  });

  if ($comparebar) {
    document.getElementById("comparebar-clear").addEventListener("click", function () {
      setPicks([]);
    });
  }

  // 搜尋框：即時更新網址，但只在列表頁生效
  var searchTimer = null;
  if ($search) {
    $search.addEventListener("input", function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () {
        var q = $search.value.trim();
        var st = parseHash();
        if (st.path !== "/") {
          location.hash = makeHash("/", new URLSearchParams(q ? [["q", q]] : []));
          return;
        }
        var params = st.params;
        if (q) params.set("q", q);
        else params.delete("q");
        go("/", params, true);
        renderGrid(params);
      }, 180);
    });
  }

  window.addEventListener("hashchange", route);

  /* ── 啟動 ───────────────────────────────────────────── */
  function boot() {
    if (!DATA.length) {
      $view.innerHTML = '<div class="empty"><strong>資料尚未載入</strong>' +
        "找不到 data/anime-data-*.js，請確認資料檔存在於 data 資料夾。</div>";
      return;
    }
    document.getElementById("footer-count").textContent = "目前收錄 " + DATA.length + " 部動畫作品。";
    if (location.hash) {
      var st = parseHash();
      if (st.path === "/" && st.params.get("q")) $search.value = st.params.get("q");
    }
    route();
    setPicks(getPicks()); // 同步勾選狀態與底部列
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
