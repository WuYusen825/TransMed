/* TransMed 前端主逻辑 — 2025 重写：
   - 登录/注册 (JWT)
   - AI 翻译 (deep-translator 真实引擎 + 置信度评估
   - 症状分诊
   - 医院推荐 + 室内导航 (SVG)
   - 药品库 / 保险 / 隐私
   ============================================================ */
(() => {
  // API 基址检测（优先级从高到低）：
  // 1) meta[name="api-base"] content="http://x.x.x.x:8000"（部署时显式配置）
  // 2) file:// 协议：必须指向 http://127.0.0.1:8000
  // 3) 127.0.0.1 / localhost 域名：也指向 http://127.0.0.1:8000（前后端分端口）
  // 4) 其他：使用相对路径（同源部署 / 生产环境 nginx 反代）
  const META_API = document.querySelector('meta[name="api-base"]');
  const IS_PAGES = location.hostname.includes("github.io") || location.hostname.includes("pages");
  let API = "";
  if (META_API) {
    API = META_API.getAttribute("content") || "";
  } else if (location.protocol === "file:" || location.hostname === "127.0.0.1" || location.hostname === "localhost" || location.hostname === "") {
    API = "http://127.0.0.1:8000";
  } else if (IS_PAGES) {
    API = ""; // 在 GitHub Pages 上，后端地址由部署者配置（meta api-base 或同源部署）
  } else {
    API = "";
  }
  if (API && !API.endsWith("/")) API = API + ""; // 保持不变：url 以 / 开头
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
      const hint = IS_PAGES
        ? "（GitHub Pages 仅托管静态前端。后端需要你自己的服务器运行：在项目中运行 python run.py 启动服务后，将 API 基址配置到 <meta name=\"api-base\"> 或通过同源部署。）"
        : (location.protocol === "file:"
            ? "（file:// 打开 HTML 时请确认 Python 后端已启动：在项目目录运行 python run.py）"
            : "（请确认后端服务正在运行）");
      throw new Error("无法连接后端 " + (API || location.origin) + " — " + e.message + hint);
    }
        if (res.status === 204) return null;
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) return res.json();
        return res.text();
      }

  /* ----------------------------- 视图切换 ----------------------------- */
  const links = document.querySelectorAll(".nav-link");
  const views = document.querySelectorAll(".view");
  function setActive(view) {
    views.forEach(v => v.classList.toggle("active", v.dataset.view === view));
    links.forEach(a => a.classList.toggle("active", a.dataset.view === view));
    if (view === "hospitals") loadHospitals();
    if (view === "medication") loadMedications();
    if (view === "navigation") initNavigationPage();
    if (view === "insurance") { loadInsuranceProviders(); loadMyClaims(); }
    if (view === "translate") doTranslateReset();
    if (view === "home") loadStats();
    if (view === "profile") loadProfile();
  }
  links.forEach(a => a.addEventListener("click", () => setActive(a.dataset.view)));
  document.querySelectorAll("[data-go]").forEach(btn =>
    btn.addEventListener("click", () => setActive(btn.dataset.go))
  );

  /* ----------------------------- 认证 UI ----------------------------- */
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

  /* ----------------------------- 语言选择 ----------------------------- */
  (async () => {
    const langs = await api("/api/languages");
    const srcSel = document.getElementById("src-lang");
    const tgtSel = document.getElementById("tgt-lang");
    if (langs && typeof langs === "object" && !Array.isArray(langs)) {
      for (const code in langs) {
        srcSel.add(new Option(langs[code] + " · " + code, code));
        tgtSel.add(new Option(langs[code] + " · " + code, code));
      }
      srcSel.value = "en"; tgtSel.value = "zh";
    }
  })();

  /* ----------------------------- 后端连通性状态 ----------------------------- */
  (async () => {
    // 在页面顶部（可选）显示后端状态 —— 静默写入 console，供开发者排查
    try {
      const health = await api("/health");
      console.log("[TransMed] Backend healthy →", JSON.stringify(health));
    } catch (e) {
      console.warn("[TransMed] Backend unreachable —", e.message);
      alert("提示：未能连接 TransMed 后端。请在终端运行：\n\n  cd /Users/johnwoo/Documents/TransMed && python3 -m uvicorn transmed_app.backend:app --host 127.0.0.1 --port 8000\n\n然后刷新本页面。");
    }
  })();

  document.getElementById("swap-lang").addEventListener("click", () => {
    const s = document.getElementById("src-lang"), t = document.getElementById("tgt-lang");
    const sv = s.value; s.value = t.value; t.value = sv;
    const st = document.getElementById("src-text");
    const tt = document.getElementById("tgt-text");
    const tv = st.value;
    st.value = tt.dataset.translated || tt.textContent;
    tt.textContent = tv;
  });

  /* ----------------------------- 症状模板 chips ----------------------------- */
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

  /* ----------------------------- 翻译主逻辑 ----------------------------- */
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
  function doTranslateReset() {
    // 切换到翻译页时重置状态
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

  /* ----------------------------- 分诊 ----------------------------- */
  document.getElementById("btn-triage").addEventListener("click", async () => {
    const symptom = document.getElementById("triage-input").value.trim();
    const insurance = document.getElementById("insurance-filter").value;
    const specialty = document.getElementById("specialty-filter").value;

    // 使用 POST /api/recommendations 一步完成：分诊 + 医院推荐排序
    let recRes = null;
    if (symptom) {
      try {
        recRes = await api("/api/recommendations", {
          method: "POST",
          body: JSON.stringify({
            symptoms: symptom,
            city: "北京",
            insurance: insurance || null,
            language: null,
            specialty_override: specialty || null,
            limit: 10,
          }),
        });
      } catch (e) {
        console.warn("recommendations endpoint failed, fallback to triage + list", e);
      }
    }

    const el = document.getElementById("triage-result");
    el.classList.remove("hidden", "urgent");
    if (symptom) {
      let triage = null;
      if (recRes && recRes.triage) triage = recRes.triage;
      else {
        triage = await api("/api/triage", {
          method: "POST", body: JSON.stringify({ symptoms: symptom, language: "en" })
        });
      }
      if (!triage) {
        el.textContent = "Triage service temporarily unavailable.";
      } else {
        const dept = triage.department_en || "General Medicine";
        const deptZh = triage.department_zh || "";
        const urgent = !!triage.urgent;
        const label = urgent ? "🚨 URGENT — please see a doctor ASAP" : "Recommended";
        if (urgent) el.classList.add("urgent");
        const matched = triage.matched_symptoms && triage.matched_symptoms.length
          ? `<div class="muted small" style="margin-top:6px;">Matched keywords: ${triage.matched_symptoms.map(s => `<span class="chip">${s}</span>`).join("")}</div>`
          : "";
        el.innerHTML = `
          <div><span class="triage-label">${label}</span></div>
          <strong>Department:</strong> ${dept}${deptZh ? " · " + deptZh : ""}<br>
          ${triage.recommendation_en || "Please consult a doctor."}
          ${matched}
        `;
      }
    } else {
      el.classList.add("hidden");
    }

    if (recRes && Array.isArray(recRes.hospitals)) {
      lastHospitalsRaw = recRes.hospitals;
      renderHospitals(lastHospitalsRaw, { symptom });
    } else {
      loadHospitals();
    }
  });

  /* 排序单选按钮触发重新排序 */
  document.querySelectorAll('input[name="sort"]').forEach(r => {
    r.addEventListener("change", () => {
      if (document.querySelector('.view[data-view="hospitals"]').classList.contains("active")) {
        renderHospitals(lastHospitalsRaw);
      }
    });
  });

  let lastHospitalsRaw = null;

  async function loadHospitals() {
    const symptom = document.getElementById("triage-input").value.trim();
    const insurance = document.getElementById("insurance-filter").value;
    const specialty = document.getElementById("specialty-filter").value;
    const q = new URLSearchParams();
    if (symptom) q.set("symptom", symptom);
    if (insurance) q.set("insurance", insurance);
    if (specialty) q.set("specialty", specialty);
    const res = await api("/api/hospitals" + (q.toString() ? "?" + q.toString() : ""));
    if (res && Array.isArray(res.hospitals)) {
      lastHospitalsRaw = res.hospitals;
    } else if (res && Array.isArray(res)) {
      lastHospitalsRaw = res;
    } else {
      lastHospitalsRaw = [];
    }
    renderHospitals(lastHospitalsRaw, { symptom });
  }

  function currentSortKey() {
    if (document.getElementById("sort-wait").checked) return "wait_minutes";
    if (document.getElementById("sort-distance").checked) return "distance_km";
    return "rating";
  }

  function renderHospitals(list, options) {
    options = options || {};
    const container = document.getElementById("hospital-list");
    if (!list || list.length === 0) {
      container.innerHTML = "<p class='muted'>No hospitals match your filters.</p>";
      return;
    }
    const sortKey = currentSortKey();
    const hasScores = list.some(h => h && h.recommendation && typeof h.recommendation.score === "number");
    let sorted;
    if (hasScores && sortKey === "rating") {
      // 症状模式下：按推荐分排序
      sorted = [...list].sort((a, b) => (b.recommendation && b.recommendation.score || 0) - (a.recommendation && a.recommendation.score || 0));
    } else {
      sorted = [...list].sort((a, b) => {
        const va = a[sortKey]; const vb = b[sortKey];
        if (va == null) return 1;
        if (vb == null) return -1;
        if (sortKey === "rating") return vb - va;
        return va - vb;
      });
    }

    container.innerHTML = sorted.map((h, idx) => {
      const specialties = (h.specialties || h.departments || []).slice(0, 5).map(s => {
        const name = typeof s === "string" ? s : (s.name || "");
        return `<span class="chip">${name}</span>`;
      }).join("");
      const insurances = (h.insurance || []).map(i => `<span class="chip">${i}</span>`).join("");
      const languages = (h.languages || []).map(l => `<span class="chip">${l}</span>`).join("");
      const rating = h.rating != null ? Number(h.rating).toFixed(2) : "-";
      const wait = h.wait_minutes != null ? `${h.wait_minutes} min` : "-";
      const dist = h.distance_km != null ? `${h.distance_km} km` : "-";
      const address = [h.address, h.address_zh].filter(Boolean).join(" · ");
      const phone = h.phone || "";
      const hours = h.hours || "";

      const rec = h.recommendation;
      let recHtml = "";
      if (rec) {
        const badgeColor = hasScores && idx === 0 ? "#d97706" : "#0891b2";
        const badgeText = hasScores && idx === 0 ? "★ TOP PICK" : "Recommended";
        const scoreColor = rec.score >= 250 ? "#16a34a" : rec.score >= 150 ? "#f59e0b" : "#64748b";
        const reasonsHtml = (rec.reasons && rec.reasons.length)
          ? `<div class="chips"><span class="muted small">Why it's a good match:</span> ${rec.reasons.map(r => `<span class="chip">${r}</span>`).join("")}</div>`
          : "";
        const deptsHtml = (rec.matched_specialties && rec.matched_specialties.length)
          ? `<div class="chips"><span class="muted small">Matched specialties:</span> ${rec.matched_specialties.map(r => `<span class="chip">${r}</span>`).join("")}</div>`
          : "";
        recHtml = `
          <div class="hospital-recommendation">
            <div class="rec-head">
              <span class="rec-badge" style="color:${badgeColor};">${badgeText}</span>
              <span class="rec-score" title="Composite score">
                Score <strong style="color:${scoreColor}">${Number(rec.score).toFixed(0)}</strong>
              </span>
              ${typeof rec.specialty_score === "number" ? `<span class="muted small">· specialty ${Number(rec.specialty_score).toFixed(0)}</span>` : ""}
              ${typeof rec.rating_score === "number" ? `<span class="muted small">· rating ${Number(rec.rating_score).toFixed(0)}</span>` : ""}
              ${typeof rec.wait_score === "number" ? `<span class="muted small">· wait-time ${Number(rec.wait_score).toFixed(0)}</span>` : ""}
              ${typeof rec.distance_score === "number" ? `<span class="muted small">· distance ${Number(rec.distance_score).toFixed(0)}</span>` : ""}
            </div>
            ${deptsHtml}
            ${reasonsHtml}
          </div>
        `;
      }

      return `
        <div class="hospital">
          <div class="hospital-main">
            <div class="hospital-head">
              <h4>${h.name || ""}${h.name_zh ? ` <span class="muted small">· ${h.name_zh}</span>` : ""}</h4>
            </div>
            <div class="sub">📍 ${address}</div>
            ${phone ? `<div class="sub">📞 ${phone}</div>` : ""}
            ${hours ? `<div class="sub">🕒 ${hours}</div>` : ""}
            <div class="hospital-meta-row">
              <span class="meta-item">⏳ Wait: <strong>${wait}</strong></span>
              <span class="meta-item">🚗 Distance: <strong>${dist}</strong></span>
            </div>
            ${specialties ? `<div class="chips"><span class="muted small">Specialties:</span> ${specialties}</div>` : ""}
            ${insurances ? `<div class="chips"><span class="muted small">Insurance:</span> ${insurances}</div>` : ""}
            ${languages ? `<div class="chips"><span class="muted small">Languages:</span> ${languages}</div>` : ""}
            ${recHtml}
          </div>
          <div class="hospital-side">
            <div class="rating-badge" title="Rating from public reviews">
              <span class="rating-num">${rating}</span>
              <span class="rating-label muted small">from public reviews</span>
            </div>
            <button class="btn btn-light btn-nav" data-goto="navigation">
              📍 View indoor map
            </button>
          </div>
        </div>
      `;
    }).join("");

    container.querySelectorAll('.btn-nav').forEach(btn => {
      btn.addEventListener("click", () => setActive(btn.dataset.goto));
    });
  }

  /* ----------------------------- 室外导航 ----------------------------- */
  let _navHospitals = [];
  let _navOrigin = { lat: null, lng: null, provided: false, label: "" };

  async function initNavigationPage() {
    const sel = document.getElementById("nav-hospital");
    if (!sel) return;
    if (!_navHospitals.length) {
      const res = await api("/api/hospitals?limit=20");
      _navHospitals = (res && res.hospitals) ? res.hospitals : [];
    }
    sel.innerHTML = "";
    _navHospitals.forEach(h => {
      const opt = document.createElement("option");
      opt.value = h.id;
      opt.textContent = h.name + (h.name_zh && h.name_zh !== h.name ? (" · " + h.name_zh) : "");
      sel.appendChild(opt);
    });
    if (_navHospitals.length) sel.selectedIndex = 0;
    updateOriginLabel();
    refreshNavigation();
  }

  function updateOriginLabel() {
    const el = document.getElementById("nav-origin");
    if (el) {
      if (_navOrigin.provided && _navOrigin.lat !== null) {
        el.textContent = "📍 " + _navOrigin.label + " (" +
          Number(_navOrigin.lat).toFixed(4) + ", " +
          Number(_navOrigin.lng).toFixed(4) + ")";
      } else {
        el.textContent = "📍 Using default reference point (Beijing) — click 'Use my location' for accurate routing";
      }
    }
  }

  async function refreshNavigation() {
    const sel = document.getElementById("nav-hospital");
    const mode = (document.getElementById("nav-mode") || {}).value || "walking";
    if (!sel || !sel.value) return;
    const hid = sel.value;

    let url = "/api/navigation?hospital_id=" + encodeURIComponent(hid) + "&mode=" + encodeURIComponent(mode);
    if (_navOrigin.provided && _navOrigin.lat !== null) {
      url += "&from_lat=" + _navOrigin.lat + "&from_lng=" + _navOrigin.lng;
    }
    const data = await api(url);
    renderNavigationResult(data);
  }

  function renderNavigationResult(data) {
    const out = document.getElementById("nav-output");
    if (!out) return;
    if (!data || !data.hospital) {
      out.innerHTML = `<p class="muted">Hospital not found. Try another selection.</p>`;
      return;
    }
    const h = data.hospital;
    const dir = data.direction || {};
    const maps = data.maps || {};
    const distKm = (typeof data.straight_line_km === "number") ? data.straight_line_km.toFixed(1) : "--";
    const routeDistM = (typeof dir.distance_m === "number") ? dir.distance_m : null;
    const routeMin = (typeof dir.duration_min === "number") ? dir.duration_min : null;
    const statusStr = (dir.status === "estimated") ? "Estimated" : ((dir.status && dir.status.replace(/_/g, " ")) || "--");

    const nameZh = h.name_zh && h.name_zh !== h.name ? (" · " + h.name_zh) : "";
    const addrZh = (h.address_zh && h.address_zh !== h.address) ? ("<br><span class="muted small">" + h.address_zh + "</span>") : "";

    let deptHtml = "";
    if (Array.isArray(data.departments) && data.departments.length) {
      const chips = data.departments.slice(0, 12).map(d => {
        const en = (d.name || "").trim();
        const zh = (d.name_zh || "").trim();
        const text = zh ? (en + (en && en !== zh ? " / " + zh : "")) : (en || zh);
        return text ? `<span class="chip">${text}</span>` : "";
      }).filter(Boolean).join("");
      if (chips) deptHtml = `<div class="chips"><span class="muted small">Key departments:</span> ${chips}</div>`;
    } else if (Array.isArray(data.specialties) && data.specialties.length) {
      const chips = data.specialties.map(s => `<span class="chip">${String(s)}</span>`).join("");
      deptHtml = `<div class="chips"><span class="muted small">Specialties:</span> ${chips}</div>`;
    }

    let stepsHtml = "";
    if (Array.isArray(dir.steps) && dir.steps.length) {
      const steps = dir.steps.map((s, i) => {
        const instruction = (typeof s === "string") ? s : (s.instruction || s.text || JSON.stringify(s));
        return `<div class="nav-step ${i === 0 ? "nav-step-current" : ""}">
          <span class="nav-step-pill">${i + 1}</span>
          <div class="nav-step-body">
            <div class="nav-step-title">${instruction}</div>
            ${(s.distance || s.duration) ? `<div class="nav-step-meta muted small">${s.distance || ""}${s.duration ? (" · " + s.duration) : ""}</div>` : ""}
          </div>
        </div>`;
      }).join("");
      stepsHtml = `<div style="margin-top:14px;"><h4 style="margin-bottom:10px;">🚶 Directions</h4>${steps}</div>`;
    }

    out.innerHTML = `
      <div class="card">
        <h3 style="margin-top:0;">🏥 ${h.name || ""}${nameZh}</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 18px;margin-top:10px;">
          ${h.address ? `<div><span class="muted small">Address</span><div>${h.address}${addrZh}</div></div>` : ""}
          ${h.phone ? `<div><span class="muted small">Phone</span><div>${h.phone}</div></div>` : ""}
        </div>
        ${h.hours ? `<div class="muted small" style="margin-top:8px;">Hours: ${h.hours}</div>` : ""}
        ${(h.rating !== null && h.rating !== undefined) ? `<div class="muted small">Rating: ${Number(h.rating).toFixed(1)} ★</div>` : ""}
      </div>

      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;">
        <a class="btn btn-primary" href="${maps.google || "#"}" target="_blank" rel="noopener noreferrer">🌍 Google Maps</a>
        <a class="btn btn-primary" href="${maps.amap || "#"}" target="_blank" rel="noopener noreferrer">🗺️ 高德 AMap</a>
        <a class="btn btn-primary" href="${maps.apple || "#"}" target="_blank" rel="noopener noreferrer">🍎 Apple Maps</a>
        <a class="btn btn-primary" href="${maps.baidu || "#"}" target="_blank" rel="noopener noreferrer">🗺️ 百度地图</a>
      </div>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:16px;">
        <div class="nav-stat"><div class="muted small">Straight line</div><div class="nav-stat-value">${distKm} km</div></div>
        ${routeDistM !== null ? `<div class="nav-stat"><div class="muted small">Route distance</div><div class="nav-stat-value">${(routeDistM / 1000).toFixed(1)} km</div></div>` : ""}
        ${routeMin !== null ? `<div class="nav-stat"><div class="muted small">Travel time</div><div class="nav-stat-value">${routeMin} min</div></div>` : ""}
      </div>
      <div class="muted small" style="margin-top:6px;">Mode: ${data.mode || "walking"} · ${statusStr}</div>

      ${h.lat && h.lng ? `<div class="muted small" style="margin-top:12px;">Coordinates: ${Number(h.lat).toFixed(5)}, ${Number(h.lng).toFixed(5)}</div>` : ""}

      ${deptHtml}

      ${stepsHtml}
    `;
  }

  async function useMyLocation() {
    const btn = document.getElementById("nav-locate");
    if (!btn) return;
    btn.textContent = "Locating…";
    btn.disabled = true;
    try {
      const pos = await new Promise((resolve, reject) => {
        if (!navigator.geolocation) reject(new Error("geolocation not available"));
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000 });
      });
      _navOrigin = {
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        provided: true,
        label: "Your location",
      };
    } catch (e) {
      _navOrigin = { lat: null, lng: null, provided: false, label: "" };
      alert("Unable to get your location: " + (e.message || e));
    } finally {
      btn.textContent = "Use my location";
      btn.disabled = false;
    }
    updateOriginLabel();
    refreshNavigation();
  }

  function wireNavigationPage() {
    const sel = document.getElementById("nav-hospital");
    const mode = document.getElementById("nav-mode");
    const locate = document.getElementById("nav-locate");
    if (sel) sel.addEventListener("change", refreshNavigation);
    if (mode) mode.addEventListener("change", refreshNavigation);
    if (locate) locate.addEventListener("click", useMyLocation);
  }
  wireNavigationPage();

  /* ----------------------------- 用药 ----------------------------- */
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
    // 支持两种格式: 数组 或 { records: [...] }
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

  /* ----------------------------- 保险 ----------------------------- */
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
    el.innerHTML = "<p class='muted'>Loading...</p>";
    // 提示信息
    const checklist = `
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
        <li>Always ask hospital for "fapiao" (official invoice) — this is required for all claims in China</li>
        <li>Take photos of every document before submitting</li>
        <li>Ask the hospital to stamp all diagnostic reports</li>
      </ul></div>
    `;
    el.innerHTML = checklist;
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

  /* ----------------------------- 隐私 ----------------------------- */
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

  /* ----------------------------- 反馈 ----------------------------- */
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

  /* ----------------------------- 个人中心 ----------------------------- */
  function loadProfile() {
    const body = document.getElementById("profile-body");
    const user = getUser();
    if (!user) {
      body.innerHTML = `
        <p class="muted">Log in or create an account to access your saved medications, translations and claims.</p>
        <button class="btn btn-primary" id="btn-profile-login-2">Log in / Register</button>`;
      document.getElementById("btn-profile-login-2").addEventListener("click", () => {
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

  /* ----------------------------- 首页统计 ----------------------------- */
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

  /* ----------------------------- 启动 ----------------------------- */
  refreshAuthUI();
  loadStats();
  setActive("home");
})();
