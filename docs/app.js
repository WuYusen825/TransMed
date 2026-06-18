/* TransMed 前端主逻辑 — 2025 重构版：
   - 登录/注册 (JWT)
   - AI 翻译 (语言选择立即可用，无需先点击按钮)
   - 症状分诊 + 医院推荐 (高德地图 POI 真实数据，带数据来源标注)
   - 医院外导航 (高德地图 JS API：步行/驾车)
   - 药品库 / 保险 / 隐私
   ================================================================= */
(() => {
  // ========== API 基址检测 ==========
  const META_API = document.querySelector('meta[name="api-base"]');
  let API = "";
  if (META_API) {
    API = META_API.getAttribute("content") || "";
  } else if (location.protocol === "file:" ||
             location.hostname === "127.0.0.1" ||
             location.hostname === "localhost" ||
             location.hostname === "") {
    API = "http://127.0.0.1:8000";
  }
  if (API && !API.endsWith("/")) API = API + "";
  const TOKEN_KEY = "transmed_token";
  const USER_KEY = "transmed_user";

  const getToken = () => localStorage.getItem(TOKEN_KEY);
  const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));
  const getUser = () => {
    try { const raw = localStorage.getItem(USER_KEY); return raw ? JSON.parse(raw) : null; }
    catch { return null; }
  };
  const setUser = (u) => (u ? localStorage.setItem(USER_KEY, JSON.stringify(u)) : localStorage.removeItem(USER_KEY));
  const logout = () => { setToken(null); setUser(null); refreshAuthUI(); setActive("home"); };

  async function api(url, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    const fullUrl = API + url;
    let res;
    try {
      res = await fetch(fullUrl, Object.assign({}, opts, { headers, mode: "cors" }));
    } catch (e) {
      const hint = (location.protocol === "file:")
        ? "（在本地目录中打开 HTML 时，请确认后端已启动：在项目目录运行 python run.py）"
        : "（请确认后端服务正在运行）";
      throw new Error("无法连接后端 " + (API || location.origin) + " — " + e.message + hint);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  // ========== 语言：内置静态映射，立即可用 ==========
  const LANGUAGES = {
    en: "English", zh: "中文", ja: "日本語", ko: "한국어",
    fr: "Français", de: "Deutsch", es: "Español", it: "Italiano",
    ru: "Русский", ar: "العربية", hi: "हिन्दी", pt: "Português",
    nl: "Nederlands", tr: "Türkçe", vi: "Tiếng Việt", th: "ไทย",
  };

  function initLanguageSelectors() {
    const srcSel = document.getElementById("src-lang");
    const tgtSel = document.getElementById("tgt-lang");
    if (!srcSel || !tgtSel) return;
    // 先用内置静态映射填充，确保立即可用
    srcSel.innerHTML = "";
    tgtSel.innerHTML = "";
    for (const code in LANGUAGES) {
      srcSel.add(new Option(LANGUAGES[code] + " · " + code, code));
      tgtSel.add(new Option(LANGUAGES[code] + " · " + code, code));
    }
    srcSel.value = "en";
    tgtSel.value = "zh";
    // 可选：异步用后端语言列表覆盖（如后端语言更多）
    api("/api/languages").then(serverLangs => {
      if (serverLangs && typeof serverLangs === "object" && !Array.isArray(serverLangs)) {
        const curSrc = srcSel.value, curTgt = tgtSel.value;
        srcSel.innerHTML = "";
        tgtSel.innerHTML = "";
        for (const code in serverLangs) {
          srcSel.add(new Option(serverLangs[code] + " · " + code, code));
          tgtSel.add(new Option(serverLangs[code] + " · " + code, code));
        }
        if (serverLangs[curSrc]) srcSel.value = curSrc;
        if (serverLangs[curTgt]) tgtSel.value = curTgt;
      }
    }).catch(() => { /* 静默失败——静态映射已经足够 */ });
  }

  // ========== 视图切换 ==========
  const links = document.querySelectorAll(".nav-link");
  const views = document.querySelectorAll(".view");
  function setActive(view) {
    views.forEach(v => v.classList.toggle("active", v.dataset.view === view));
    links.forEach(a => a.classList.toggle("active", a.dataset.view === view));
    if (view === "hospitals") loadHospitals();
    if (view === "medication") loadMedications();
    if (view === "insurance") { loadInsuranceProviders(); loadMyClaims(); }
    if (view === "translate") { /* 语言选择立即可用，无需额外重置 */ }
    if (view === "home") loadStats();
    if (view === "profile") loadProfile();
  }
  links.forEach(a => a.addEventListener("click", () => setActive(a.dataset.view)));
  document.querySelectorAll("[data-go]").forEach(btn =>
    btn.addEventListener("click", () => setActive(btn.dataset.go))
  );

  // ========== 认证 UI ==========
  const authModal = document.getElementById("auth-modal");
  document.getElementById("btn-login").addEventListener("click", () => { authModal.classList.remove("hidden"); switchAuthTab("login"); });
  document.getElementById("btn-logout").addEventListener("click", logout);
  authModal.addEventListener("click", e => { if (e.target === authModal) authModal.classList.add("hidden"); });
  document.querySelectorAll(".modal-tabs .tab").forEach(btn =>
    btn.addEventListener("click", () => switchAuthTab(btn.dataset.tab))
  );
  function switchAuthTab(tab) {
    document.querySelectorAll(".modal-tabs .tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.toggle("hidden", p.id !== "tab-" + tab));
    document.getElementById("auth-message").textContent = "";
  }
  function setAuthMessage(msg, isError = false) {
    const el = document.getElementById("auth-message");
    el.textContent = msg; el.style.color = isError ? "#dc2626" : "#059669";
  }

  document.getElementById("btn-do-login").addEventListener("click", async () => {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    if (!email || !password) { setAuthMessage("Please enter email and password", true); return; }
    try {
      const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      if (data && data.access_token) {
        setToken(data.access_token); setUser(data.user); refreshAuthUI();
        authModal.classList.add("hidden"); setActive("home");
      } else {
        setAuthMessage((data && data.detail) || "Login failed", true);
      }
    } catch (e) { setAuthMessage("Network error: " + e.message, true); }
  });

  document.getElementById("btn-do-register").addEventListener("click", async () => {
    const payload = {
      full_name: document.getElementById("reg-name").value.trim(),
      email: document.getElementById("reg-email").value.trim(),
      password: document.getElementById("reg-password").value,
      language: document.getElementById("reg-language").value,
      country: document.getElementById("reg-country").value.trim(),
    };
    if (!payload.full_name || !payload.email || payload.password.length < 6) {
      setAuthMessage("Full name, valid email and password >= 6 chars required", true); return;
    }
    try {
      const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify(payload) });
      if (data && data.access_token) {
        setToken(data.access_token); setUser(data.user); refreshAuthUI();
        authModal.classList.add("hidden"); setActive("home");
      } else {
        setAuthMessage((data && data.detail) || "Registration failed", true);
      }
    } catch (e) { setAuthMessage("Network error: " + e.message, true); }
  });

  function refreshAuthUI() {
    const user = getUser();
    document.getElementById("btn-login").classList.toggle("hidden", !!user);
    document.getElementById("user-chip").classList.toggle("hidden", !user);
    if (user) document.getElementById("user-email").textContent = user.email;
  }

  // ========== 翻译：语言互换 & 翻译主逻辑 ==========
  document.getElementById("swap-lang").addEventListener("click", () => {
    const s = document.getElementById("src-lang"), t = document.getElementById("tgt-lang");
    const sv = s.value; s.value = t.value; t.value = sv;
    const st = document.getElementById("src-text");
    const tt = document.getElementById("tgt-text");
    const tv = st.value;
    st.value = tt.dataset.translated || "";
    tt.textContent = tv;
    tt.dataset.translated = "";
  });

  // 快捷症状模板 chips
  const TEMPLATES = [
    "I have a headache and fever since yesterday",
    "My stomach hurts after eating spicy food",
    "Chest pain when breathing, with cough",
    "I need to see a cardiologist",
    "Back pain after exercise, muscle soreness",
    "Tooth pain since morning, sensitivity to cold",
    "I feel dizzy when standing up",
    "Sore throat and runny nose for 3 days",
  ];
  const chipsBox = document.getElementById("symptom-chips");
  TEMPLATES.forEach(txt => {
    const el = document.createElement("button");
    el.className = "chip"; el.textContent = txt;
    el.addEventListener("click", () => {
      document.getElementById("src-text").value = txt;
      doTranslate();
    });
    chipsBox.appendChild(el);
  });

  const btnTranslate = document.getElementById("btn-translate");
  btnTranslate.addEventListener("click", doTranslate);
  document.getElementById("src-text").addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") doTranslate();
  });

  let lastLogId = null;
  async function doTranslate() {
    const text = document.getElementById("src-text").value.trim();
    if (!text) return;
    btnTranslate.disabled = true;
    const originalText = btnTranslate.textContent;
    btnTranslate.textContent = "Translating...";
    try {
      const res = await api("/api/translate", {
        method: "POST",
        body: JSON.stringify({
          text,
          source: document.getElementById("src-lang").value,
          target: document.getElementById("tgt-lang").value,
        }),
      });
      const tt = document.getElementById("tgt-text");
      tt.textContent = (res && res.translated) || "(Translation not available)";
      tt.dataset.translated = (res && res.translated) || "";
      const conf = document.getElementById("confidence-bar");
      conf.classList.remove("hidden");
      const confVal = (res && res.confidence) || 0;
      document.getElementById("conf-value").textContent = confVal + "%";
      document.getElementById("risk-value").textContent = (res && res.risk_level) || "unknown";
      const engine = (res && res.engine) || "unknown";
      const engineEl = document.getElementById("engine-label");
      if (engineEl) {
        engineEl.textContent = engine === "groq" ? "🎯 Groq AI (llama-3.3-70b) + 医学语料库 RAG"
                              : engine === "offline" ? "⚠️ 离线术语匹配（Groq 服务不可用，检查你的 API key）"
                              : engine === "same-language" ? "✓ same-language"
                              : "unknown";
        engineEl.classList.remove("online", "offline", "hidden");
        engineEl.classList.add(engine === "groq" ? "online" : "offline");
      }
      const fill = document.getElementById("conf-fill");
      fill.style.width = Math.max(5, confVal) + "%";
      if (confVal < 60) fill.style.background = "#dc2626";
      else if (confVal < 80) fill.style.background = "#f59e0b";
      else fill.style.background = "#16a34a";

      let advice = "";
      if (confVal >= 85) advice = "High confidence — reliable for casual reference";
      else if (confVal >= 70) advice = "Medium confidence — verify medical terms aligned";
      else advice = "Low confidence — double-check with a professional translator";
      document.getElementById("conf-advice").textContent = "⚠ " + advice;

      const matched = (res && res.matched_terms) || [];
      document.getElementById("matched-terms").textContent =
        matched.length ? "Medical terms: " + matched.join(" · ") : "";
      document.getElementById("btn-confirm-risk").classList.toggle("hidden", confVal >= 80);
      lastLogId = res && res.id || null;
      if (getToken()) loadTranslationLogs();
    } catch (e) {
      document.getElementById("tgt-text").textContent = "Translation failed: " + e.message;
    } finally {
      btnTranslate.disabled = false;
      btnTranslate.textContent = originalText;
    }
  }

  document.getElementById("btn-confirm-risk").addEventListener("click", async () => {
    if (!lastLogId) return;
    try {
      await api("/api/translate/" + lastLogId + "/confirm", { method: "POST" });
      alert("Acknowledged. This confirmation is stored as part of the safety workflow.");
    } catch (e) { alert("Confirmation failed: " + e.message); }
  });

  async function loadTranslationLogs() {
    const box = document.getElementById("my-translations");
    if (!getToken()) { box.innerHTML = "<p class='muted'>Log in to see your translation history.</p>"; return; }
    const items = await api("/api/translate/logs");
    if (!Array.isArray(items) || items.length === 0) {
      box.innerHTML = "<p class='muted'>No translations yet.</p>"; return;
    }
    box.innerHTML = items.slice(0, 10).map(i => {
      const src = i.source_text || "";
      return `
      <div class="med-item">
        <div>
          <strong>${i.source_lang} → ${i.target_lang}</strong>
          <div style="font-size:13px;">${src.slice(0, 120)}${src.length > 120 ? "..." : ""}</div>
          <div class="times">Confidence ${i.confidence} · Risk ${i.risk_level}${i.user_confirmed ? " · ✓ Acknowledged" : ""} · ${i.created_at}</div>
        </div>
      </div>`;
    }).join("");
  }

  // ========== 分诊 ==========
  document.getElementById("btn-triage").addEventListener("click", async () => {
    const symptom = document.getElementById("triage-input").value.trim();
    const res = symptom ? await api("/api/triage", {
      method: "POST", body: JSON.stringify({ symptoms: symptom, language: "en" })
    }) : null;
    const el = document.getElementById("triage-result");
    el.classList.remove("hidden", "urgent");
    if (symptom) {
      if (!res) {
        el.textContent = "Triage service temporarily unavailable.";
      } else {
        const dept = res.department_en || "General Medicine";
        const deptZh = res.department_zh || "";
        const urgent = !!res.urgent;
        const label = urgent ? "URGENT" : "Recommended";
        if (urgent) el.classList.add("urgent");
        el.innerHTML = `
          <div><span class="triage-label">${label}</span></div>
          <strong>Department:</strong> ${dept}${deptZh ? " · " + deptZh : ""}<br>
          ${res.recommendation_en || "Please consult a doctor."}
        `;
        // 自动把分诊得到的科室关键词预填入医院搜索框
        const kw = document.getElementById("hospital-keyword");
        if (kw && dept) kw.value = dept;
      }
    } else {
      el.classList.add("hidden");
    }
    loadHospitals();
  });

  // 排序单选按钮
  document.querySelectorAll('input[name="sort"]').forEach(r => {
    r.addEventListener("change", () => {
      if (document.querySelector('.view[data-view="hospitals"]').classList.contains("active")) {
        renderHospitals(lastHospitalsRaw, lastDataSource);
      }
    });
  });

  let lastHospitalsRaw = null;
  let lastDataSource = "demo";

  // 新增搜索按钮绑定
  const searchBtn = document.getElementById("btn-hospital-search");
  if (searchBtn) searchBtn.addEventListener("click", () => loadHospitals());

  async function loadHospitals() {
    const kwEl = document.getElementById("hospital-keyword");
    const cityEl = document.getElementById("hospital-city");
    const keyword = (kwEl && kwEl.value || "").trim();
    const city = (cityEl && cityEl.value || "").trim();
    const symptom = document.getElementById("triage-input").value.trim();
    const q = new URLSearchParams();
    if (keyword) q.set("keyword", keyword);
    else if (symptom) q.set("keyword", symptom);
    if (city) q.set("city", city);
    q.set("limit", "20");
    let res = null;
    try { res = await api("/api/hospitals" + (q.toString() ? "?" + q.toString() : "")); } catch (e) { console.warn(e); }
    let errorMsg = null;
    if (res && Array.isArray(res.hospitals)) {
      lastHospitalsRaw = res.hospitals;
      lastDataSource = res.data_source || "demo";
      if (res.amap_error) errorMsg = res.amap_error;
    } else if (res && Array.isArray(res)) {
      lastHospitalsRaw = res;
      lastDataSource = "demo";
    } else {
      lastHospitalsRaw = [];
      lastDataSource = "demo";
    }
    renderHospitals(lastHospitalsRaw, lastDataSource, errorMsg);
  }

  function currentSortKey() {
    if (document.getElementById("sort-wait").checked) return "wait_minutes";
    if (document.getElementById("sort-distance").checked) return "distance_km";
    return "rating";
  }

  function renderHospitals(list, dataSource, amapError) {
    const container = document.getElementById("hospital-list");
    const note = document.getElementById("hospital-note");
    if (note) {
      if (dataSource === "amap") {
        note.innerHTML = '<div style="margin-bottom:4px;">📍 <b>真实数据来源：高德地图 POI search</b> — rating, address, phone, coordinates 均为真实值。</div>';
      } else {
        let errHtml = "";
        if (amapError) {
          errHtml = `<div style="margin-top:8px;padding:8px 12px;background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.35);border-radius:6px;color:#fef3c7;line-height:1.6;"><b>⚠️ 高德 API 诊断：</b><pre style="margin:6px 0 0;padding:0;white-space:pre-wrap;word-break:break-all;white-space:-moz-pre-wrap;white-space:pre-line;">` + String(amapError).replace(/</g, "&lt;") + "</pre></div>";
        }
        note.innerHTML = '<div style="margin-bottom:4px;">💡 <b>演示数据（不是真实数据）</b> — 后端未配置或 Web 服务 Key，显示内置样例。配置高德 Web 服务 API Key 后即可启用真实搜索。</div>' + errHtml;
      }
    }
    if (!list || list.length === 0) {
      container.innerHTML = "<p class='muted'>No hospitals match your filters. Try different city or keyword.</p>";
      return;
    }
    const sortKey = currentSortKey();
    const sorted = [...list].sort((a, b) => {
      const va = a[sortKey]; const vb = b[sortKey];
      if (va == null) return 1;
      if (vb == null) return -1;
      if (sortKey === "rating") return (vb || 0) - (va || 0);
      return (va || 0) - (vb || 0);
    });

    container.innerHTML = sorted.map((h, idx) => {
      const specialties = (h.specialties || h.departments || []).slice(0, 5).map(s => {
        const name = typeof s === "string" ? s : (s.name || "");
        return `<span class="chip">${name}</span>`;
      }).join("");
      const insurances = (h.insurance || []).map(i => `<span class="chip">${i}</span>`).join("");
      const languages = (h.languages || []).map(l => `<span class="chip">${l}</span>`).join("");
      const rating = h.rating != null ? Number(h.rating).toFixed(2) : "—";
      const wait = h.wait_minutes != null ? `${h.wait_minutes} min` : "—";
      const dist = h.distance_km != null && h.distance_km > 0 ? `${Number(h.distance_km).toFixed(2)} km` : "—";
      const address = [h.address, h.address_zh].filter(Boolean).join(" · ");
      const phone = h.phone || "";
      const hours = h.hours || "";
      const hasCoords = h.lat && h.lng;
      const hid = h.id || ("h-" + idx);

      const sourceBadge = dataSource === "amap"
        ? '<span class="chip chip-real">AMap · real</span>'
        : '<span class="chip chip-demo">demo</span>';

      return `
        <div class="hospital" data-lat="${h.lat || ""}" data-lng="${h.lng || ""}" data-name="${h.name || ""}">
          <div class="hospital-main">
            <div class="hospital-head">
              <h4>${h.name || ""}${h.name_zh && h.name_zh !== h.name ? ` <span class="muted small">· ${h.name_zh}</span>` : ""} ${sourceBadge}</h4>
            </div>
            <div class="sub">📍 ${address || "—"}</div>
            ${phone ? `<div class="sub">📞 ${phone}</div>` : ""}
            ${hours ? `<div class="sub">🕒 ${hours}</div>` : ""}
            <div class="hospital-meta-row">
              <span class="meta-item">⏳ Wait: <strong>${wait}</strong></span>
              <span class="meta-item">🚗 Distance: <strong>${dist}</strong></span>
            </div>
            ${specialties ? `<div class="chips"><span class="muted small">Specialties:</span> ${specialties}</div>` : ""}
            ${insurances ? `<div class="chips"><span class="muted small">Insurance:</span> ${insurances}</div>` : ""}
            ${languages ? `<div class="chips"><span class="muted small">Languages:</span> ${languages}</div>` : ""}
          </div>
          <div class="hospital-side">
            <div class="rating-badge" title="Rating from public reviews">
              <span class="rating-num">${rating}</span>
              <span class="rating-label muted small">/ 5.00</span>
            </div>
            <button class="btn btn-light btn-navigate"
                    data-id="${hid}" data-lat="${h.lat || ""}" data-lng="${h.lng || ""}"
                    data-name="${(h.name || "").replace(/"/g, "&quot;")}"
                    data-address="${address.replace(/"/g, "&quot;")}"
                    ${hasCoords ? "" : "disabled"}>
              🗺️ Navigate there
            </button>
          </div>
        </div>
      `;
    }).join("");

    // 绑定导航跳转（使用全局导航状态）
    container.querySelectorAll(".btn-navigate").forEach(btn => {
      btn.addEventListener("click", () => {
        const lng = btn.getAttribute("data-lng");
        const lat = btn.getAttribute("data-lat");
        const name = btn.getAttribute("data-name");
        const address = btn.getAttribute("data-address");
        setActive("navigation");
        setTimeout(() => {
          // 更新目标显示区
          const destText = document.getElementById("nav-destination-text");
          if (destText) {
            destText.innerHTML = `<div><b>${name}</b></div><div class="muted small" style="margin-top:4px;">${address || "—"} · 经度 ${lng}, 纬度 ${lat}</div>`;
          }
          // 保存到全局状态
          window.__navDest = { lng: parseFloat(lng), lat: parseFloat(lat), name: name, address: address };
          const summary = document.getElementById("nav-summary");
          if (summary) summary.textContent = "— 点击 “Show route on map” 绘制路线，或输入出发点后查询。";
          // 清空旧地图内容
          const mapC = document.getElementById("amap-container");
          if (mapC) mapC.innerHTML = "";
          // 若已配置 JS key，先显示目标位置标记
          renderAmapMap(parseFloat(lng), parseFloat(lat), name, null, null, null);
        }, 200);
      });
    });
  }

  // ========== 导航：高德地图 JS API ==========
  let amapScriptLoaded = false;
  let amapConfigCache = null;

  async function ensureAmapConfig() {
    if (amapConfigCache) return amapConfigCache;
    try {
      amapConfigCache = await api("/api/amap/config");
    } catch (e) {
      amapConfigCache = { has_js_key: false, has_web_key: false };
    }
    return amapConfigCache;
  }

  function loadAmapScript(jsKey) {
    return new Promise((resolve, reject) => {
      if (window.AMap) return resolve();
      if (document.getElementById("amap-loader")) {
        const existing = document.getElementById("amap-loader");
        existing.addEventListener("load", () => resolve());
        existing.addEventListener("error", () => reject(new Error("AMap SDK failed to load")));
        return;
      }
      const s = document.createElement("script");
      s.id = "amap-loader";
      s.src = `https://webapi.amap.com/maps?v=2.0&key=${encodeURIComponent(jsKey)}&plugin=AMap.Driving,AMap.Walking,AMap.Geocoder,AMap.Geolocation,AMap.Scale,AMap.ToolBar`;
      s.async = true;
      s.onload = () => { amapScriptLoaded = true; resolve(); };
      s.onerror = () => reject(new Error("AMap SDK failed to load — check your JS API key"));
      document.head.appendChild(s);
    });
  }

  async function renderAmapMap(destLng, destLat, destName, fromLng, fromLat, mode) {
    const container = document.getElementById("amap-container");
    if (!container) return;
    const summary = document.getElementById("nav-summary");
    if (!Number.isFinite(destLng) || !Number.isFinite(destLat)) {
      container.innerHTML = '<p class="muted" style="padding:16px;">No destination selected. Go to the Hospitals page and click "Navigate there" on a hospital with coordinates.</p>';
      if (summary) summary.textContent = "—";
      return;
    }
    const cfg = await ensureAmapConfig();
    if (!cfg || !cfg.has_js_key) {
      container.innerHTML = `<p class="muted" style="padding:16px;line-height:1.8;">
        🗺️ 高德地图 JS API 未配置 <code>TRANSMED_AMAP_JS_KEY</code>，无法绘制地图。
        <br>目标医院：<b>${destName || "—"}</b>（经度 ${destLng.toFixed(6)}，纬度 ${destLat.toFixed(6)}）。
        <br>作为替代方案，你可以：
        <ul style="margin-top:8px;">
          <li>在 <a href="https://uri.amap.com/marker?position=${destLng},${destLat}&name=${encodeURIComponent(destName || "hospital")}" target="_blank" rel="noopener">高德网页版 →</a> 直接查看位置并启动导航</li>
          <li>在后端配置 <code>TRANSMED_AMAP_JS_KEY</code> 后刷新本页，这里会自动显示可交互地图</li>
        </ul>
      </p>`;
      if (summary) summary.textContent = "（未配置 JS key — 使用高德网页链接作为替代）";
      return;
    }
    try {
      await loadAmapScript(cfg.js_key);
    } catch (e) {
      container.innerHTML = `<p class="muted" style="padding:16px;color:#dc2626;">${e.message}</p>`;
      return;
    }
    container.innerHTML = "";
    const modeLabel = (mode === "driving") ? "驾车" : "步行";
    const center = (Number.isFinite(fromLng) && Number.isFinite(fromLat))
      ? [(fromLng + destLng) / 2, (fromLat + destLat) / 2]
      : [destLng, destLat];
    const map = new window.AMap.Map(container, {
      zoom: (Number.isFinite(fromLng) && Number.isFinite(fromLat)) ? 13 : 15,
      center: center,
      resizeEnable: true,
    });
    map.addControl(new window.AMap.Scale());
    map.addControl(new window.AMap.ToolBar({ position: "RB" }));

    // 目标医院标记
    new window.AMap.Marker({
      position: [destLng, destLat],
      map: map,
      title: destName || "Hospital",
      label: {
        content: `<div style="padding:4px 8px;background:#1e40af;color:#fff;border-radius:4px;font-size:12px;">🏥 ${destName || "Destination"}</div>`,
        direction: "top",
      },
    });

    if (Number.isFinite(fromLng) && Number.isFinite(fromLat)) {
      // 出发点标记
      new window.AMap.Marker({
        position: [fromLng, fromLat],
        map: map,
        title: "Origin",
        label: { content: `<div style="padding:4px 8px;background:#16a34a;color:#fff;border-radius:4px;font-size:12px;">📍 Origin</div>`, direction: "top" },
      });
      // 路线规划（调用高德 JS API 内置插件）
      const RoutePlugin = (mode === "driving") ? window.AMap.Driving : window.AMap.Walking;
      const routeService = new RoutePlugin({
        map: map,
        hideMarkers: false,
        autoFitView: true,
      });
      routeService.search(
        [fromLng, fromLat],
        [destLng, destLat],
        (status, result) => {
          if (status === "complete" && result.routes && result.routes.length) {
            const r = result.routes[0];
            const km = (r.distance / 1000).toFixed(2);
            const min = Math.max(1, Math.round((r.time || 0) / 60));
            if (summary) {
              summary.innerHTML = `🚩 ${modeLabel}路线：<b>${km} km</b>，预计 <b>${min} 分钟</b>。数据来源：高德地图 ${mode === "driving" ? "Driving" : "Walking"} API。`;
            }
          } else {
            if (summary) summary.textContent = `⚠️ 未查询到${modeLabel}路线，请确认出发点地址在中国大陆境内。`;
          }
        }
      );
    } else {
      if (summary) summary.textContent = `🏥 已标记目标医院位置（${modeLabel}模式）。输入出发点后点击 "Show route on map" 可绘制完整路线，或点击 "Use my location" 使用浏览器定位。`;
    }
  }

  // "使用我的位置" 按钮：调用浏览器定位
  document.getElementById("btn-use-mylocation").addEventListener("click", () => {
    const fromInput = document.getElementById("nav-from");
    if (!navigator.geolocation) {
      alert("浏览器不支持地理定位，请手动输入地址。");
      return;
    }
    fromInput.value = "⏳ 正在定位...";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        fromInput.value = `${pos.coords.longitude.toFixed(6)}, ${pos.coords.latitude.toFixed(6)}`;
      },
      (err) => {
        fromInput.value = "";
        alert("定位失败：" + (err.message || "请检查浏览器权限"));
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  });

  // 主要导航按钮：解析出发点 + 调用 renderAmapMap
  document.getElementById("btn-navigate").addEventListener("click", async () => {
    const dest = window.__navDest || null;
    if (!dest || !Number.isFinite(dest.lng) || !Number.isFinite(dest.lat)) {
      alert('请先在 Hospitals 页选择一所医院并点击 "Navigate there"。');
      return;
    }
    const destLng = dest.lng, destLat = dest.lat, destName = dest.name;
    const fromText = document.getElementById("nav-from").value.trim();
    const mode = document.getElementById("nav-mode-drive").checked ? "driving" : "walking";
    const cfg = await ensureAmapConfig();

    let fromLng = null, fromLat = null;
    if (fromText) {
      // 如果输入是 "数字,数字"（坐标格式），直接解析
      if (/^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$/.test(fromText)) {
        const parts = fromText.split(",").map(s => parseFloat(s.trim()));
        fromLng = parts[0]; fromLat = parts[1];
      } else {
        // 否则用 JS 端 Geocoder（需要 JS key）
        if (cfg && cfg.has_js_key) {
          try {
            await loadAmapScript(cfg.js_key);
            const geocoder = new window.AMap.Geocoder({ city: "全国" });
            const result = await new Promise((resolve, reject) => {
              geocoder.getLocation(fromText, (status, r) => {
                if (status === "complete" && r.geocodes && r.geocodes.length) resolve(r.geocodes[0]);
                else reject(new Error("address not found by AMap"));
              });
            });
            fromLng = result.location.lng;
            fromLat = result.location.lat;
          } catch (e) {
            alert('无法解析出发点地址。请尝试：\n1) 使用 "Use my location" 按钮自动定位\n2) 直接输入坐标（格式：经度,纬度，例如 116.397428,39.90923）');
            return;
          }
        } else {
          alert('需要配置 TRANSMED_AMAP_JS_KEY 来解析地址。请改用 "Use my location" 或直接输入坐标（经度,纬度）。');
          return;
        }
      }
    }
    renderAmapMap(destLng, destLat, destName, fromLng, fromLat, mode);
  });

  // ========== 用药 ==========
  (async () => {
    const picker = document.getElementById("med-picker");
    const res = await api("/api/medications");
    if (res && res.medications) {
      res.medications.forEach(m => {
        const label = m.name + (m.name_zh ? " · " + m.name_zh : "");
        picker.add(new Option(label, m.name));
      });
      if (res.medications[0]) renderDrugInfo(res.medications[0]);
      picker.addEventListener("change", () => {
        const name = picker.value.toLowerCase();
        const found = res.medications.find(m => m.name.toLowerCase() === name);
        renderDrugInfo(found || res.medications[0]);
      });
    }
  })();

  function renderDrugInfo(m) {
    const box = document.getElementById("med-info");
    if (!m) { box.innerHTML = "<p class='muted'>Select a medication to see details.</p>"; return; }
    const warningsHtml = (m.warnings && m.warnings.length) ? `<p><strong>Warnings:</strong><ul>${m.warnings.slice(0, 5).map(w => `<li>${w}</li>`).join("")}</ul></p>` : "";
    const sideHtml = (m.side_effects && m.side_effects.length) ? `<p><strong>Side effects:</strong><ul>${m.side_effects.slice(0, 5).map(w => `<li>${w}</li>`).join("")}</ul></p>` : "";
    box.innerHTML = `
      <div class="drug-info">
        <strong>${m.name}</strong> ${m.name_zh ? "<span class='muted'>" + m.name_zh + "</span>" : ""}
        ${m.category ? `<p><strong>Category:</strong> ${m.category}${m.category_zh ? " · " + m.category_zh : ""}</p>` : ""}
        ${m.dosage ? `<p><strong>Dosage:</strong> ${m.dosage}${m.dosage_zh ? " · " + m.dosage_zh : ""}</p>` : ""}
        ${warningsHtml}
        ${sideHtml}
      </div>`;
  }

  document.getElementById("btn-add-med").addEventListener("click", async () => {
    const key = document.getElementById("med-picker").value;
    const custom = document.getElementById("med-custom").value.trim();
    const dosage = document.getElementById("med-dosage").value.trim();
    const times = document.getElementById("med-times").value.trim();
    const notes = document.getElementById("med-notes").value.trim();
    if (!key && !custom) { alert("Select or enter a medication name"); return; }
    await api("/api/medications/record", {
      method: "POST",
      body: JSON.stringify({ medication_key: key, custom_name: custom, dosage, reminder_times: times, notes })
    });
    ["med-custom", "med-dosage", "med-times", "med-notes"].forEach(id => document.getElementById(id).value = "");
    loadMedications();
  });

  async function loadMedications() {
    const list = document.getElementById("med-list");
    if (!getToken()) {
      list.innerHTML = "<p class='muted'>Log in to save your medications and reminders.</p>"; return;
    }
    const res = await api("/api/medications/record");
    const records = Array.isArray(res) ? res : (res && res.records) || [];
    if (!records.length) {
      list.innerHTML = "<p class='muted'>No medications saved yet.</p>"; return;
    }
    list.innerHTML = records.map(m => `
      <div class="med-item">
        <div>
          <strong>${m.medication_key || m.custom_name || "Medication"}</strong>
          <div>${m.dosage || ""}</div>
          <div class="times">Reminders: ${m.reminder_times || "—"} · ${m.notes || ""}</div>
        </div>
        <button class="btn btn-danger" data-id="${m.id}">Delete</button>
      </div>
    `).join("");
    list.querySelectorAll("button[data-id]").forEach(btn => {
      btn.addEventListener("click", async () => {
        await api("/api/medications/record/" + btn.dataset.id, { method: "DELETE" });
        loadMedications();
      });
    });
  }

  // ========== 保险 ==========
  async function loadInsuranceProviders() {
    const res = await api("/api/insurance");
    const sel = document.getElementById("ins-provider");
    if (res && res.providers) {
      const first = sel.value;
      sel.innerHTML = '<option value="">- Select provider -</option>';
      res.providers.forEach(p => {
        sel.add(new Option(p.name + (p.name_zh ? " · " + p.name_zh : ""), p.name));
      });
      if (first) sel.value = first;
    }
  }

  document.getElementById("btn-insurance").addEventListener("click", async () => {
    const prov = document.getElementById("ins-provider").value;
    if (!prov) return;
    const el = document.getElementById("ins-result");
    el.innerHTML = `
      <div class="checklist"><h4>📄 Required documents</h4>
      <ul>
        <li>Valid passport / ID card</li>
        <li>Original medical invoice (发票原件)</li>
        <li>Detailed medical report (诊断书)</li>
        <li>Prescription (处方)</li>
        <li>Completed claim form (理赔申请表)</li>
        <li>Bank account details for reimbursement</li>
      </ul></div>
      <div class="checklist"><h4>🛠 Claim process</h4>
      <ul>
        <li>Step 1: Collect all original documents from your visit</li>
        <li>Step 2: Submit online claim form via provider portal or email</li>
        <li>Step 3: Provider reviews (3-10 business days)</li>
        <li>Step 4: Reimbursement transferred to your account</li>
      </ul></div>
      <div class="checklist"><h4>💡 Tips</h4>
      <ul>
        <li>Always ask hospital for "fapiao" (official invoice) — required for all claims in China</li>
        <li>Take photos of every document before submitting</li>
        <li>Ask the hospital to stamp all diagnostic reports</li>
      </ul></div>
    `;
  });

  const addClaimBtn = document.getElementById("btn-add-claim");
  if (addClaimBtn) {
    addClaimBtn.addEventListener("click", async () => {
      if (!getToken()) { alert("Log in to save claims"); return; }
      const provider = document.getElementById("claim-provider").value.trim();
      const amount = parseFloat(document.getElementById("claim-amount").value || "0");
      const notes = document.getElementById("claim-notes").value.trim();
      if (!provider) { alert("Enter the insurance provider"); return; }
      const res = await api("/api/insurance/claims", {
        method: "POST", body: JSON.stringify({ provider, status: "draft", estimated_amount: amount, notes })
      });
      if (res && res.ok) {
        document.getElementById("claim-provider").value = "";
        document.getElementById("claim-amount").value = "";
        document.getElementById("claim-notes").value = "";
        loadMyClaims();
      } else {
        alert("Failed to save claim: " + ((res && res.detail) || "unknown error"));
      }
    });
  }

  async function loadMyClaims() {
    const box = document.getElementById("my-claims");
    if (!getToken()) { box.innerHTML = "<p class='muted'>Log in to see your claims.</p>"; return; }
    const items = await api("/api/insurance/claims");
    if (!Array.isArray(items) || items.length === 0) {
      box.innerHTML = "<p class='muted'>No claims saved yet.</p>"; return;
    }
    box.innerHTML = items.map(c => `
      <div class="med-item">
        <div>
          <strong>${c.provider}</strong>
          <div>¥ ${(c.amount || c.estimated_amount || 0).toFixed ? (c.amount || c.estimated_amount || 0).toFixed(2) : (c.amount || c.estimated_amount || 0)} · ${c.status || "draft"}</div>
          <div class="times">${c.notes || ""} · ${c.created_at || ""}</div>
        </div>
      </div>`).join("");
  }
  loadMyClaims();

  // ========== 隐私 ==========
  document.getElementById("btn-export").addEventListener("click", async () => {
    const box = document.getElementById("export-box");
    if (!getToken()) { alert("Log in to export your data."); return; }
    const res = await api("/api/privacy/export");
    box.classList.remove("hidden");
    box.textContent = JSON.stringify(res, null, 2);
  });

  document.getElementById("btn-wipe").addEventListener("click", async () => {
    if (!getToken()) { alert("Log in to wipe your records."); return; }
    if (!confirm("Delete ALL your personal records (translations, medications, triage, claims)? This cannot be undone.")) return;
    const res = await api("/api/privacy/wipe", { method: "DELETE" });
    alert(res && res.message || "Your records have been wiped.");
  });

  // ========== 反馈 ==========
  document.getElementById("btn-send-feedback").addEventListener("click", async () => {
    const category = document.getElementById("fb-category").value;
    const rating = parseInt(document.getElementById("fb-rating").value, 10);
    const content = document.getElementById("fb-content").value.trim();
    if (!content) { alert("Please enter a message."); return; }
    await api("/api/feedback", { method: "POST", body: JSON.stringify({ category, content, rating }) });
    document.getElementById("fb-content").value = "";
    const status = document.getElementById("fb-status");
    status.textContent = "✅ Feedback submitted. Thank you!";
    setTimeout(() => { status.textContent = ""; }, 4000);
  });

  // ========== 个人中心 ==========
  function loadProfile() {
    const body = document.getElementById("profile-body");
    const user = getUser();
    if (!user) {
      body.innerHTML = `
        <p class="muted">Log in or create an account to access your saved medications, translations and claims.</p>
        <button class="btn btn-primary" id="btn-profile-login">Log in / Register</button>`;
      document.getElementById("btn-profile-login").addEventListener("click", () => {
        authModal.classList.remove("hidden"); switchAuthTab("login");
      });
      return;
    }
    body.innerHTML = `
      <div class="card">
        <h3>Profile</h3>
        <p><strong>Email:</strong> ${user.email}</p>
        <p><strong>Name:</strong> <input id="pf-name" type="text" value="${user.full_name || ""}" /></p>
        <p><strong>Preferred language:</strong> <input id="pf-lang" type="text" value="${user.language || ""}" /></p>
        <p><strong>Country:</strong> <input id="pf-country" type="text" value="${user.country || ""}" /></p>
        <p><strong>Role:</strong> ${user.role || "patient"}</p>
        <button class="btn btn-primary" id="pf-save">Save changes</button>
      </div>
      <div class="card">
        <h3>Change password</h3>
        <label>Current password</label><input type="password" id="pf-old" />
        <label>New password (min 6 chars)</label><input type="password" id="pf-new" />
        <button class="btn btn-primary" id="pf-change-password">Update password</button>
      </div>
    `;
    document.getElementById("pf-save").addEventListener("click", async () => {
      const updated = {
        full_name: document.getElementById("pf-name").value.trim(),
        language: document.getElementById("pf-lang").value.trim(),
        country: document.getElementById("pf-country").value.trim(),
      };
      const res = await api("/api/auth/profile", { method: "PUT", body: JSON.stringify(updated) });
      if (res && res.user) { setUser(res.user); alert("Profile updated."); }
    });
    document.getElementById("pf-change-password").addEventListener("click", async () => {
      const oldPw = document.getElementById("pf-old").value;
      const newPw = document.getElementById("pf-new").value;
      if (!oldPw || newPw.length < 6) { alert("Please provide current password and a new password (min 6 chars)."); return; }
      const res = await api("/api/auth/change-password", { method: "POST", body: JSON.stringify({ old_password: oldPw, new_password: newPw }) });
      if (res && res.message) { alert("✓ " + res.message); document.getElementById("pf-old").value = ""; document.getElementById("pf-new").value = ""; }
    });
  }

  // ========== 首页统计 ==========
  async function loadStats() {
    const res = await api("/api/stats");
    const el = document.getElementById("home-stats");
    if (!res) return;
    const items = [
      ["Hospitals", res.hospitals],
      ["Departments", res.departments],
      ["Translations", res.translations],
      ["Users", res.users],
      ["Medications", res.medications],
      ["Claims", res.insurance_claims],
    ];
    el.innerHTML = items.map(([l, n]) => `<div class="stat"><div class="stat-num">${n || 0}</div><div class="stat-label">${l}</div></div>`).join("");
  }

  // ========== 启动 ==========
  initLanguageSelectors();  // 语言选择立即填充
  refreshAuthUI();
  loadStats();
  setActive("home");
})();
