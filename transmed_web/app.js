/* TransMed 前端主逻辑 — 室外导航版本 */
(function () {
  // --- DOM helpers -------------------------------------------------
  const byId = (id) => document.getElementById(id);
  const qs = (sel) => document.querySelector(sel);
  const qsa = (sel) => Array.from(document.querySelectorAll(sel));
  const onClick = (el, handler) => {
    if (el) el.addEventListener("click", handler);
  };
  const onChange = (el, handler) => {
    if (el) el.addEventListener("change", handler);
  };

  // --- API base 检测 ------------------------------------------------
  const META_API = qs('meta[name="api-base"]');
  const IS_PAGES = location.hostname.includes("github.io")
    || location.hostname.includes("pages");
  let API = "";
  if (META_API) API = META_API.getAttribute("content") || "";
  else if (location.protocol === "file:" || location.hostname === "127.0.0.1" || location.hostname === "localhost") API = "http://127.0.0.1:8000";
  else API = "";

  const TOKEN_KEY = "transmed_token";
  const USER_KEY = "transmed_user";
  const getToken = () => localStorage.getItem(TOKEN_KEY);
  const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));
  const getUser = () => { try { const raw = localStorage.getItem(USER_KEY); return raw ? JSON.parse(raw) : null; } catch (e) { return null; } };
  const setUser = (u) => (u ? localStorage.setItem(USER_KEY, JSON.stringify(u)) : localStorage.removeItem(USER_KEY));

  async function api(url, opts) {
    opts = opts || {};
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    const fullUrl = API + url;
    let res;
    try {
      res = await fetch(fullUrl, Object.assign({}, opts, { headers, mode: "cors" }));
    } catch (e) {
      const hint = IS_PAGES
        ? " (GitHub Pages serves only the frontend — back-end features need a local or Render instance.)"
        : " (Please start your local back-end first.)";
      throw new Error("Unable to reach back-end " + (API || "") + " — " + e.message + hint);
    }
    if (res.status === 204) return null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  // --- 视图切换 ----------------------------------------------------
  const navLinks = qsa(".nav-link");
  const views = qsa(".view");
  function setActive(view) {
    views.forEach((v) => v.classList.toggle("active", v.dataset.view === view));
    navLinks.forEach((a) => a.classList.toggle("active", a.dataset.view === view));
    try {
      if (view === "hospitals") loadHospitals();
      if (view === "medication") loadMedications();
      if (view === "navigation") initNavigationPage();
      if (view === "insurance") { loadInsuranceProviders(); loadMyClaims(); }
      if (view === "translate") doTranslateReset();
      if (view === "home") loadStats();
      if (view === "profile") loadProfile();
    } catch (e) {
      console.warn("setActive(" + view + ") error:", e);
    }
  }
  navLinks.forEach((a) => onClick(a, () => setActive(a.dataset.view)));
  qsa("[data-go]").forEach((btn) => onClick(btn, () => setActive(btn.dataset.go)));

  // --- 认证 UI -----------------------------------------------------
  const authModal = byId("auth-modal");
  function switchAuthTab(tab) {
    qsa(".modal-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    const panelLogin = byId("tab-login");
    const panelRegister = byId("tab-register");
    if (panelLogin) panelLogin.classList.toggle("hidden", tab !== "login");
    if (panelRegister) panelRegister.classList.toggle("hidden", tab !== "register");
    const msg = byId("auth-message");
    if (msg) msg.textContent = "";
  }
  if (authModal) {
    onClick(authModal, (e) => {
      if (e.target === authModal) authModal.classList.add("hidden");
    });
  }
  onClick(byId("btn-login"), () => { if (authModal) { authModal.classList.remove("hidden"); switchAuthTab("login"); } });
  onClick(byId("btn-logout"), () => { setToken(null); setUser(null); refreshAuthUI(); setActive("home"); });
  qsa(".modal-tabs .tab").forEach((btn) => onClick(btn, () => switchAuthTab(btn.dataset.tab)));

  function refreshAuthUI() {
    const user = getUser();
    if (byId("btn-login")) byId("btn-login").classList.toggle("hidden", !!user);
    if (byId("user-chip")) byId("user-chip").classList.toggle("hidden", !user);
    if (byId("user-email") && user) byId("user-email").textContent = user.email;
  }

  onClick(byId("btn-do-login"), async () => {
    const email = byId("login-email") ? byId("login-email").value.trim() : "";
    const password = byId("login-password") ? byId("login-password").value : "";
    const msg = byId("auth-message");
    if (!email || !password) { if (msg) msg.textContent = "Please enter email and password"; return; }
    try {
      const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      if (data && data.access_token) {
        setToken(data.access_token); setUser(data.user); refreshAuthUI();
        if (authModal) authModal.classList.add("hidden"); setActive("home");
      } else {
        if (msg) msg.textContent = (data && data.detail) || "Login failed";
      }
    } catch (e) { if (msg) msg.textContent = "Error: " + e.message; }
  });

  onClick(byId("btn-do-register"), async () => {
    const payload = {
      full_name: byId("reg-name") ? byId("reg-name").value.trim() : "",
      email: byId("reg-email") ? byId("reg-email").value.trim() : "",
      password: byId("reg-password") ? byId("reg-password").value : "",
      language: byId("reg-language") ? byId("reg-language").value : "en",
      country: byId("reg-country") ? byId("reg-country").value.trim() : "",
    };
    const msg = byId("auth-message");
    if (!payload.full_name || !payload.email || payload.password.length < 6) {
      if (msg) msg.textContent = "Full name, valid email and password >= 6 chars required"; return;
    }
    try {
      const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify(payload) });
      if (data && data.access_token) {
        setToken(data.access_token); setUser(data.user); refreshAuthUI();
        if (authModal) authModal.classList.add("hidden"); setActive("home");
      } else {
        if (msg) msg.textContent = (data && data.detail) || "Registration failed";
      }
    } catch (e) { if (msg) msg.textContent = "Error: " + e.message; }
  });

  // --- 语言选择 ---------------------------------------------------
  (async () => {
    try {
      const langs = await api("/api/languages");
      const srcSel = byId("src-lang");
      const tgtSel = byId("tgt-lang");
      if (!langs || typeof langs !== "object") return;
      if (srcSel) for (const c in langs) { const opt = document.createElement("option"); opt.value = c; opt.textContent = langs[c] + " \u00B7 " + c; srcSel.add(opt); }
      if (tgtSel) for (const c in langs) { const opt = document.createElement("option"); opt.value = c; opt.textContent = langs[c] + " \u00B7 " + c; tgtSel.add(opt); }
      if (srcSel) srcSel.value = "en";
      if (tgtSel) tgtSel.value = "zh";
    } catch (e) { console.warn("languages:", e); }
  })();

  onClick(byId("swap-lang"), () => {
    const src = byId("src-lang"), tgt = byId("tgt-lang");
    if (!src || !tgt) return;
    const sv = src.value; src.value = tgt.value; tgt.value = sv;
  });

  // --- 症状快捷 chips ---------------------------------------------
  (function buildSymptomChips() {
    const symptoms = [
      "headache", "chest pain", "cough", "fever", "stomach pain",
      "back pain", "skin rash", "dizziness", "fatigue", "sore throat",
      "shortness of breath", "nausea", "joint pain", "anxiety",
    ];
    const box = byId("symptom-chips");
    if (!box) return;
    symptoms.forEach((txt) => {
      const el = document.createElement("button");
      el.className = "chip"; el.textContent = txt;
      el.type = "button";
      onClick(el, () => {
        const t = byId("src-text");
        if (t) t.value = txt;
        doTranslate();
      });
      box.appendChild(el);
    });
  })();

  // --- 翻译 -------------------------------------------------------
  let lastLogId = null;
  const btnTranslate = byId("btn-translate");
  onClick(btnTranslate, doTranslate);
  const srcText = byId("src-text");
  if (srcText) srcText.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") doTranslate();
  });

  async function doTranslate() {
    const txt = srcText ? srcText.value.trim() : "";
    const srcLang = byId("src-lang") ? byId("src-lang").value : "en";
    const tgtLang = byId("tgt-lang") ? byId("tgt-lang").value : "zh";
    const tgt = byId("tgt-text");
    const conf = byId("confidence-bar");
    const confVal = byId("conf-value");
    const confFill = byId("conf-fill");
    const advice = byId("conf-advice");
    const matched = byId("matched-terms");
    const riskBtn = byId("btn-confirm-risk");
    const engineLabel = byId("engine-label");
    if (!txt || !tgt) return;
    if (btnTranslate) { btnTranslate.disabled = true; btnTranslate.textContent = "Translating..."; }
    try {
      const res = await api("/api/translate", {
        method: "POST",
        body: JSON.stringify({
          text: txt, source_lang: srcLang, target_lang: tgtLang,
          medical_context: true,
        }),
      });
      tgt.textContent = res.translated_text || "(no translation)";
      const c = typeof res.confidence === "number" ? Math.round(res.confidence * 100) : 80;
      if (conf) conf.classList.remove("hidden");
      if (confVal) confVal.textContent = c;
      if (confFill) confFill.style.width = c + "%";
      const risk = res.risk_level || "low";
      const riskEl = byId("risk-value");
      if (riskEl) riskEl.textContent = risk;
      if (riskBtn) riskBtn.classList.toggle("hidden", risk !== "high");
      if (advice) advice.textContent = res.safety_advice || "";
      if (matched) {
        const items = (res.medical_terms || []).map((t) =>
          '<span class="chip">' + t.term + (t.definition ? (" \u00B7 " + t.definition) : "") + '</span>');
        matched.innerHTML = items.length ? '<div class="muted small" style="margin-bottom:6px;">Medical terms:</div>' + items.join("") : "";
      }
      if (engineLabel) { engineLabel.classList.remove("hidden"); engineLabel.textContent = "Engine: " + (res.engine || "server"); }
      lastLogId = typeof res.log_id === "number" ? res.log_id : res.log_id;
    } catch (e) { tgt.textContent = "Error: " + e.message; }
    finally { if (btnTranslate) { btnTranslate.disabled = false; btnTranslate.textContent = "Translate"; } }
  }

  onClick(byId("btn-confirm-risk"), async () => {
    if (!lastLogId) return;
    try { await api("/api/translate/" + lastLogId + "/confirm", { method: "POST" }); alert("Acknowledged."); }
    catch (e) { alert("Confirmation failed: " + e.message); }
  });

  function doTranslateReset() {}

  // --- 分诊 + 医院推荐 -------------------------------------------
  let lastHospitalsRaw = [];
  onClick(byId("btn-triage"), async () => {
    const symptom = byId("triage-input") ? byId("triage-input").value.trim() : "";
    const insurance = byId("insurance-filter") ? byId("insurance-filter").value : "";
    const specialty = byId("specialty-filter") ? byId("specialty-filter").value : "";
    const el = byId("triage-result");
    if (el) el.classList.remove("hidden", "urgent");
    let recRes = null;
    if (symptom) {
      try {
        recRes = await api("/api/recommendations", {
          method: "POST",
          body: JSON.stringify({
            symptoms: symptom, city: "Beijing",
            insurance: insurance || null, language: null,
            specialty_override: specialty || null, limit: 10,
          }),
        });
      } catch (e) { console.warn("recommendations fallback", e); }
    }
    if (symptom) {
      let triage = (recRes && recRes.triage) ? recRes.triage : null;
      if (!triage) {
        try { triage = await api("/api/triage", { method: "POST", body: JSON.stringify({ symptoms: symptom, language: "en" }) }); }
        catch (e) { triage = null; }
      }
      if (el) {
        if (!triage) el.textContent = "Triage service unavailable.";
        else {
          const dept = triage.department_en || "General Medicine";
          const deptZh = triage.department_zh || "";
          const urgent = !!triage.urgent;
          const label = urgent ? "\uD83D\uDEA8 URGENT \u2014 please see a doctor ASAP" : "Recommended";
          if (urgent) el.classList.add("urgent");
          const matched = triage.matched_symptoms && triage.matched_symptoms.length
            ? '<div class="muted small" style="margin-top:6px;">Matched keywords: ' + triage.matched_symptoms.map((s) => '<span class="chip">' + s + '</span>').join("") + "</div>" : "";
          el.innerHTML = '<div><span class="triage-label">' + label + '</span></div>' +
            '<strong>Department:</strong> ' + dept + (deptZh ? (" \u00B7 " + deptZh) : "") + '<br>' +
            (triage.recommendation_en || "Please consult a doctor.") +
            matched;
        }
      }
    } else if (el) el.classList.add("hidden");

    if (recRes && Array.isArray(recRes.hospitals)) { lastHospitalsRaw = recRes.hospitals; renderHospitals(lastHospitalsRaw, { symptom }); }
    else loadHospitals();
  });

  qsa('input[name="sort"]').forEach((r) => onChange(r, () => {
    const v = qs('.view[data-view="hospitals"]');
    if (v && v.classList.contains("active")) renderHospitals(lastHospitalsRaw);
  }));

  async function loadHospitals() {
    const container = byId("hospital-list");
    if (!container) return;
    try {
      const res = await api("/api/hospitals?limit=20");
      const list = (res && res.hospitals) ? res.hospitals : [];
      lastHospitalsRaw = list;
      renderHospitals(list);
    } catch (e) { container.innerHTML = "<p class='muted'>Hospital list unavailable.</p>"; }
  }

  function renderHospitals(list, ctx) {
    ctx = ctx || {};
    const container = byId("hospital-list");
    if (!container) return;
    if (!Array.isArray(list) || !list.length) {
      container.innerHTML = "<p class='muted'>No hospitals found.</p>";
      return;
    }
    container.innerHTML = list.map((h) => {
      const name = h.name || "";
      const nameZh = h.name_zh && h.name_zh !== h.name ? (" \u00B7 " + h.name_zh) : "";
      const address = h.address || "";
      const phone = h.phone || "";
      const hours = h.hours || "";
      const rating = typeof h.rating === "number" ? h.rating.toFixed(1) : "\u2014";
      const wait = (typeof h.wait_minutes === "number") ? (h.wait_minutes + " min") : "\u2014";
      const dist = (typeof h.distance_km === "number") ? h.distance_km.toFixed(1) + " km" : "\u2014";
      const specialties = (h.specialties || []).slice(0, 5).map((s) => '<span class="chip">' + (typeof s === "string" ? s : (s.name || s)) + "</span>").join("");
      const insurances = (h.insurance || []).slice(0, 4).map((s) => '<span class="chip">' + s + "</span>").join("");
      const languages = (h.languages || []).map((s) => '<span class="chip">' + s + "</span>").join("");
      const rec = h.recommendation;
      let recHtml = "";
      if (rec) {
        const score = typeof rec.score === "number" ? Math.round(rec.score) : 0;
        const badgeColor = score >= 80 ? "#059669" : score >= 60 ? "#2563eb" : "#6b7280";
        const reasonsHtml = (Array.isArray(rec.reasons) && rec.reasons.length)
          ? '<div class="chips"><span class="muted small">Why it is a good match:</span> ' + rec.reasons.map((r) => '<span class="chip">' + r + "</span>").join("") + "</div>" : "";
        const matchedHtml = (Array.isArray(rec.matched_specialties) && rec.matched_specialties.length)
          ? '<div class="chips"><span class="muted small">Matched specialties:</span> ' + rec.matched_specialties.map((r) => '<span class="chip">' + r + "</span>").join("") + "</div>" : "";
        recHtml = '<div class="hospital-recommendation">' +
          '<div class="rec-head"><span class="rec-badge" style="color:' + badgeColor + ';">' + (score > 0 ? score : "\u2014") + '</span>' +
          '<span class="rec-score">' +
          ((rec.matched_specialties && rec.matched_specialties.length) ? '<span class="muted small">\u00B7 ' + rec.matched_specialties.length + ' matched</span>' : "") +
          "</span></div>" +
          reasonsHtml + matchedHtml +
          "</div>";
      }
      return '<div class="hospital">' +
        '<div class="hospital-main">' +
        '<div class="hospital-head"><h4>' + name + nameZh + "</h4></div>" +
        '<div class="sub">\uD83D\uDCCD ' + address + "</div>" +
        (phone ? '<div class="sub">\uD83D\uDCDE ' + phone + "</div>" : "") +
        (hours ? '<div class="sub">\uD83D\uDD52 ' + hours + "</div>" : "") +
        '<div class="hospital-meta-row"><span class="meta-item">\u23F3 Wait: <strong>' + wait + "</strong></span>" +
        '<span class="meta-item">\uD83D\uDE97 Distance: <strong>' + dist + "</strong></span></div>" +
        (specialties ? '<div class="chips"><span class="muted small">Specialties:</span> ' + specialties + "</div>" : "") +
        (insurances ? '<div class="chips"><span class="muted small">Insurance:</span> ' + insurances + "</div>" : "") +
        (languages ? '<div class="chips"><span class="muted small">Languages:</span> ' + languages + "</div>" : "") +
        recHtml +
        "</div>" +
        '<div class="hospital-side">' +
        '<div class="rating-badge" title="Rating from public reviews">' +
        '<span class="rating-num">' + rating + '</span><span class="rating-label muted small">from public reviews</span></div>' +
        '<button class="btn btn-light btn-nav" data-hospital-idx="' + list.indexOf(h) + '">\uD83D\uDCCD Navigate here</button>' +
        "</div></div>";
    }).join("");

    qsa("#hospital-list .btn-nav").forEach((btn) => {
      onClick(btn, () => {
        const idx = btn.getAttribute("data-hospital-idx");
        if (idx !== null && idx !== undefined) {
          const h = lastHospitalsRaw[parseInt(idx, 10)];
          if (h) _navSelectedHospital = h;
        }
        setActive("navigation");
      });
    });
  }

  // --- 室外导航 --------------------------------------------------
  let _navHospitals = [];
  let _navOrigin = { lat: null, lng: null, provided: false, label: "" };
  let _navSelectedHospital = null;

  async function initNavigationPage() {
    const sel = byId("nav-hospital");
    if (!sel) return;

    if (_navSelectedHospital) {
      _navHospitals = [_navSelectedHospital];
      _navSelectedHospital = null;
    } else if (!_navHospitals.length) {
      try {
        const res = await api("/api/hospitals?limit=20");
        _navHospitals = (res && res.hospitals) ? res.hospitals : [];
      } catch (e) {
        _navHospitals = [
          { id: "pumch", name: "Peking Union Medical College Hospital", name_zh: "Beijing Xiehe Hospital", lng: 116.4165, lat: 39.9094 },
          { id: "ufh", name: "United Family Hospital Beijing", name_zh: "Hemu Jia Hospital", lng: 116.4677, lat: 39.9754 },
          { id: "bjh", name: "Beijing Hospital", name_zh: "Beijing Hospital", lng: 116.4151, lat: 39.9038 },
          { id: "tongren", name: "Beijing Tongren Hospital", name_zh: "Beijing Tongren Hospital", lng: 116.4172, lat: 39.9027 },
        ];
      }
    }

    sel.innerHTML = "";
    _navHospitals.forEach((h, idx) => {
      const opt = document.createElement("option");
      opt.value = String(idx);
      opt.textContent = h.name + ((h.name_zh && h.name_zh !== h.name) ? (" \u00B7 " + h.name_zh) : "");
      sel.appendChild(opt);
    });
    if (_navHospitals.length) sel.selectedIndex = 0;
    updateOriginLabel();
    refreshNavigation();

    onChange(sel, refreshNavigation);
    onChange(byId("nav-mode"), refreshNavigation);
    onClick(byId("nav-locate"), useMyLocation);
  }

  function updateOriginLabel() {
    const el = byId("nav-origin");
    if (!el) return;
    if (_navOrigin.provided && _navOrigin.lat !== null) {
      el.textContent = "\uD83D\uDCCD " + _navOrigin.label + " (" +
        Number(_navOrigin.lat).toFixed(4) + ", " +
        Number(_navOrigin.lng).toFixed(4) + ")";
    } else {
      el.textContent = "\uD83D\uDCCD Using default reference point (Beijing) \u2014 click 'Use my location' for accurate routing";
    }
  }

  async function refreshNavigation() {
    const sel = byId("nav-hospital");
    const modeEl = byId("nav-mode");
    const mode = (modeEl && modeEl.value) || "walking";
    if (!sel || sel.value === "" || !_navHospitals.length) return;
    const h = _navHospitals[parseInt(sel.value, 10)];
    if (!h) return;

    const lng = (h.lng !== undefined && h.lng !== null) ? h.lng : h.longitude;
    const lat = (h.lat !== undefined && h.lat !== null) ? h.lat : h.latitude;
    let url;
    if (typeof lng === "number" && typeof lat === "number") {
      url = "/api/navigation?to_lng=" + lng + "&to_lat=" + lat +
        "&name=" + encodeURIComponent(h.name || h.name_zh || "hospital") +
        "&mode=" + encodeURIComponent(mode);
    } else {
      url = "/api/navigation?hospital_id=" + encodeURIComponent(h.id || "") + "&mode=" + encodeURIComponent(mode);
    }
    if (_navOrigin.provided && _navOrigin.lat !== null) {
      url += "&from_lat=" + _navOrigin.lat + "&from_lng=" + _navOrigin.lng;
    }
    try {
      const data = await api(url);
      renderNavigationResult(data);
    } catch (e) {
      const out = byId("nav-output");
      if (out) out.innerHTML = "<p class='muted'>Navigation unavailable: " + e.message + "</p>";
    }
  }

  function renderNavigationResult(data) {
    const out = byId("nav-output");
    if (!out) return;
    if (!data || !data.hospital) {
      out.innerHTML = "<p class='muted'>Hospital not found. Try another selection.</p>";
      return;
    }
    const h = data.hospital;
    const dir = data.direction || {};
    const maps = data.maps || {};
    const distKm = (typeof data.straight_line_km === "number") ? data.straight_line_km.toFixed(1) : "\u2014";
    const routeDistM = (typeof dir.distance_m === "number") ? dir.distance_m : null;
    const routeMin = (typeof dir.duration_min === "number") ? dir.duration_min : null;
    const statusStr = (dir.status === "estimated") ? "Estimated" : ((dir.status && String(dir.status).replace(/_/g, " ")) || "\u2014");

    const nameZh = (h.name_zh && h.name_zh !== h.name) ? (" \u00B7 " + h.name_zh) : "";
    const addrZh = (h.address_zh && h.address_zh !== h.address) ? ('<br><span class="muted small">' + h.address_zh + "</span>") : "";

    let deptHtml = "";
    if (Array.isArray(data.departments) && data.departments.length) {
      const chips = data.departments.slice(0, 12).map((d) => {
        const en = (d.name || "").trim();
        const zh = (d.name_zh || "").trim();
        const text = zh ? (en + (en && en !== zh ? " / " + zh : "")) : (en || zh);
        return text ? '<span class="chip">' + text + "</span>" : "";
      }).filter(Boolean).join("");
      if (chips) deptHtml = '<div class="chips"><span class="muted small">Key departments:</span> ' + chips + "</div>";
    } else if (Array.isArray(data.specialties) && data.specialties.length) {
      const chips = data.specialties.map((s) => '<span class="chip">' + String(s) + "</span>").join("");
      deptHtml = '<div class="chips"><span class="muted small">Specialties:</span> ' + chips + "</div>";
    }

    let stepsHtml = "";
    if (Array.isArray(dir.steps) && dir.steps.length) {
      stepsHtml = '<div style="margin-top:14px;"><h4 style="margin-bottom:10px;">\uD83D\uDEB6 Directions</h4>' + dir.steps.map((s) => {
        const instruction = (typeof s === "string") ? s : (s.instruction || s.text || "");
        return '<div class="nav-step"><span class="nav-step-pill">\u2022</span><div class="nav-step-body"><div class="nav-step-title">' + instruction + "</div>" +
          ((s.distance || s.duration) ? '<div class="nav-step-meta muted small">' + (s.distance || "") + (s.duration ? (" \u00B7 " + s.duration) : "") + "</div>" : "") +
          "</div></div>";
      }).join("") + "</div>";
    }

    out.innerHTML = '<div class="card">' +
      '<h3 style="margin-top:0;">\uD83C\uDFE5 ' + (h.name || "") + nameZh + '</h3>' +
      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 18px;margin-top:10px;">' +
      (h.address ? '<div><span class="muted small">Address</span><div>' + h.address + addrZh + "</div></div>" : "") +
      (h.phone ? '<div><span class="muted small">Phone</span><div>' + h.phone + "</div></div>" : "") +
      "</div>" +
      (h.hours ? '<div class="muted small" style="margin-top:8px;">Hours: ' + h.hours + "</div>" : "") +
      ((h.rating !== null && h.rating !== undefined) ? '<div class="muted small">Rating: ' + Number(h.rating).toFixed(1) + " \u2605</div>" : "") +
      "</div>" +

      '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;">' +
      '<a class="btn btn-primary" href="' + (maps.google || "#") + '" target="_blank" rel="noopener noreferrer">\uD83C\uDF0D Google Maps</a>' +
      '<a class="btn btn-primary" href="' + (maps.amap || "#") + '" target="_blank" rel="noopener noreferrer">\uD83D\uDDFA\uFE0F AMap</a>' +
      '<a class="btn btn-primary" href="' + (maps.apple || "#") + '" target="_blank" rel="noopener noreferrer">\uD83C\uDF4E Apple Maps</a>' +
      '<a class="btn btn-primary" href="' + (maps.baidu || "#") + '" target="_blank" rel="noopener noreferrer">\uD83D\uDDFA\uFE0F Baidu Maps</a>' +
      "</div>" +

      '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:16px;">' +
      '<div class="nav-stat"><div class="muted small">Straight line</div><div class="nav-stat-value">' + distKm + " km</div></div>" +
      (routeDistM !== null ? '<div class="nav-stat"><div class="muted small">Route distance</div><div class="nav-stat-value">' + (routeDistM / 1000).toFixed(1) + " km</div></div>" : "") +
      (routeMin !== null ? '<div class="nav-stat"><div class="muted small">Travel time</div><div class="nav-stat-value">' + routeMin + " min</div></div>" : "") +
      "</div>" +
      '<div class="muted small" style="margin-top:6px;">Mode: ' + (data.mode || "walking") + " \u00B7 " + statusStr + "</div>" +

      ((h.lat && h.lng) ? '<div class="muted small" style="margin-top:12px;">Coordinates: ' + Number(h.lat).toFixed(5) + ", " + Number(h.lng).toFixed(5) + "</div>" : "") +

      deptHtml + stepsHtml;
  }

  async function useMyLocation() {
    const btn = byId("nav-locate");
    if (!btn) return;
    btn.textContent = "Locating..."; btn.disabled = true;
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
      alert("Unable to get your location: " + e.message);
    } finally {
      btn.textContent = "Use my location"; btn.disabled = false;
    }
    updateOriginLabel();
    refreshNavigation();
  }

  // --- 药品 ------------------------------------------------------
  async function loadMedications() {
    const picker = byId("med-picker");
    const listEl = byId("med-list");
    const info = byId("med-info");
    try {
      const res = await api("/api/medications?limit=30");
      const meds = res && res.medications ? res.medications : [];
      if (picker) {
        picker.innerHTML = "";
        meds.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id || m.name;
          opt.textContent = m.name;
          picker.appendChild(opt);
        });
        if (meds[0]) {
          const m = meds[0];
          if (info) info.innerHTML = "<strong>" + m.name + "</strong>" + (m.generic_name ? (" \u00B7 " + m.generic_name) : "") + '<br><span class="muted small">' + (m.category || "") + "</span><br>" + (m.description || "");
        }
      }
      onChange(picker, () => {
        const v = picker.value;
        const m = meds.find((x) => (x.id || x.name) === v);
        if (info && m) info.innerHTML = "<strong>" + m.name + "</strong>" + (m.generic_name ? (" \u00B7 " + m.generic_name) : "") + '<br><span class="muted small">' + (m.category || "") + "</span><br>" + (m.description || "");
      });
    } catch (e) { if (listEl) listEl.innerHTML = "<p class='muted'>Medication list unavailable.</p>"; }

    try {
      const user = getUser();
      if (user && listEl) {
        const list = await api("/api/medications/mine");
        const items = Array.isArray(list) ? list : (list && list.medications) || [];
        if (items.length) {
          listEl.innerHTML = items.map((m) => '<div class="card" style="margin-bottom:10px;">' +
            "<div><strong>" + m.name + "</strong></div>" +
            '<div class="muted small">Dosage: ' + (m.dosage || "\u2014") + " \u00B7 Notes: " + (m.notes || "\u2014") + "</div>" +
            (m.scheduled_times ? '<div class="muted small">Schedule: ' + m.scheduled_times + "</div>" : "") +
            "</div>").join("");
        } else {
          listEl.innerHTML = "<p class='muted small'>No saved medications yet.</p>";
        }
      } else if (listEl) {
        listEl.innerHTML = "<p class='muted small'>Log in to save medications for future visits.</p>";
      }
    } catch (e) { /* ignore */ }
  }

  onClick(byId("btn-add-med"), async () => {
    const picker = byId("med-picker");
    const custom = byId("med-custom");
    const dosage = byId("med-dosage");
    const times = byId("med-times");
    const notes = byId("med-notes");
    const listEl = byId("med-list");
    if (!getUser()) { alert("Please log in to save medications."); return; }
    const name = (picker && picker.value) || (custom && custom.value.trim());
    if (!name) return;
    try {
      await api("/api/medications", {
        method: "POST",
        body: JSON.stringify({
          name, dosage: dosage ? dosage.value.trim() : "",
          scheduled_times: times ? times.value.trim() : "",
          notes: notes ? notes.value.trim() : "",
        }),
      });
      loadMedications();
    } catch (e) { alert("Save failed: " + e.message); }
  });

  // --- 保险 ------------------------------------------------------
  async function loadInsuranceProviders() {
    try {
      const res = await api("/api/insurance/providers");
      const list = (res && res.providers) ? res.providers : (Array.isArray(res) ? res : []);
      const sel = byId("ins-provider");
      if (sel) {
        sel.innerHTML = "";
        list.forEach((p) => {
          const opt = document.createElement("option");
          const name = typeof p === "string" ? p : (p.name || p.id || "Provider");
          opt.value = name; opt.textContent = name;
          sel.appendChild(opt);
        });
      }
    } catch (e) { /* ignore */ }
  }

  onClick(byId("btn-insurance"), () => {
    const sel = byId("ins-provider");
    const out = byId("ins-result");
    if (!sel || !out) return;
    const name = sel.value;
    out.innerHTML = '<div class="card"><h4 style="margin-top:0;">\uD83D\uDCCB Checklist: ' + name + "</h4>" +
      '<ul style="line-height:1.8;">' +
      "<li>\u2705 Passport / ID</li>" +
      "<li>\u2705 Insurance card (or policy number)</li>" +
      "<li>\u2705 Previous medical records</li>" +
      "<li>\u2705 Referral letter (if required by policy)</li>" +
      "<li>\u2705 Invoice for reimbursement</li>" +
      "</ul>" +
      '<p class="muted small">This is a demonstration checklist \u2014 please consult your provider for the complete, up-to-date workflow.</p>' +
      "</div>";
  });

  async function loadMyClaims() {
    const claimsEl = byId("my-claims");
    if (!claimsEl) return;
    if (!getUser()) { claimsEl.innerHTML = "<p class='muted small'>Log in to manage your insurance claims.</p>"; return; }
    try {
      const list = await api("/api/insurance/claims");
      const items = Array.isArray(list) ? list : [];
      if (items.length) {
        claimsEl.innerHTML = items.map((c) => '<div class="card" style="margin-bottom:10px;">' +
          "<div><strong>" + (c.provider || "Claim") + "</strong> \u2014 " + (c.status || "draft") + "</div>" +
          (c.amount ? '<div class="muted small">Amount: \u00A5' + c.amount + "</div>" : "") +
          (c.notes ? '<div class="muted small">Notes: ' + c.notes + "</div>" : "") +
          "</div>").join("");
      } else {
        claimsEl.innerHTML = "<p class='muted small'>No saved claims yet.</p>";
      }
    } catch (e) { /* ignore */ }
  }

  onClick(byId("btn-add-claim"), async () => {
    if (!getUser()) { alert("Please log in to submit claims."); return; }
    const provider = byId("claim-provider") ? byId("claim-provider").value.trim() : "";
    const amount = byId("claim-amount") ? parseFloat(byId("claim-amount").value) : 0;
    const notes = byId("claim-notes") ? byId("claim-notes").value.trim() : "";
    if (!provider) return;
    try {
      await api("/api/insurance/claims", {
        method: "POST",
        body: JSON.stringify({ provider, status: "draft", amount: amount || 0, notes }),
      });
      loadMyClaims();
    } catch (e) { alert("Claim submission failed: " + e.message); }
  });

  // --- 隐私 & 数据导出 ------------------------------------------
  onClick(byId("btn-export"), async () => {
    try {
      const data = await api("/api/privacy/export");
      if (byId("export-box")) byId("export-box").textContent = JSON.stringify(data, null, 2);
      alert("Export ready.");
    } catch (e) { alert("Export failed: " + e.message); }
  });

  onClick(byId("btn-wipe"), async () => {
    if (!confirm("This will delete all your saved records. Continue?")) return;
    try {
      await api("/api/privacy/wipe", { method: "POST" });
      alert("Records wiped.");
    } catch (e) { alert("Wipe failed: " + e.message); }
  });

  // --- 反馈 ------------------------------------------------------
  onClick(byId("btn-send-feedback"), async () => {
    const cat = byId("fb-category") ? byId("fb-category").value : "other";
    const rating = byId("fb-rating") ? parseInt(byId("fb-rating").value, 10) : 0;
    const content = byId("fb-content") ? byId("fb-content").value.trim() : "";
    const statusEl = byId("fb-status");
    if (!content) return;
    try {
      await api("/api/feedback", {
        method: "POST",
        body: JSON.stringify({ category: cat, rating: rating || 5, content }),
      });
      if (statusEl) statusEl.textContent = "\u2705 Thank you!";
      if (byId("fb-content")) byId("fb-content").value = "";
    } catch (e) { if (statusEl) statusEl.textContent = "Failed: " + e.message; }
  });

  // --- 个人资料 -------------------------------------------------
  function loadProfile() {
    const body = byId("profile-body");
    if (!body) return;
    const user = getUser();
    if (!user) {
      body.innerHTML = '<div class="card"><h4>Log in / Register</h4>' +
        '<p class="muted small">Create a free account to save medications, insurance claims and translations.</p>' +
        '<button class="btn btn-primary" id="btn-profile-login-2">Log in / Register</button></div>';
      onClick(byId("btn-profile-login-2"), () => { if (authModal) { authModal.classList.remove("hidden"); switchAuthTab("login"); } });
      return;
    }
    body.innerHTML = '<div class="card">' +
      '<h4 style="margin-top:0;">\uD83D\uDC64 ' + (user.full_name || user.email) + "</h4>" +
      '<div><span class="muted small">Email:</span> ' + user.email + "</div>" +
      '<div><span class="muted small">Language:</span> ' + (user.language || "en") + "</div>" +
      '<div><span class="muted small">Country:</span> ' + (user.country || "\u2014") + "</div>" +
      '<div style="margin-top:12px;">' +
      '<label>Preferred language</label>' +
      '<select id="pf-lang"><option value="en">English</option><option value="zh">Chinese</option><option value="ja">Japanese</option><option value="ko">Korean</option><option value="fr">French</option><option value="de">German</option></select>' +
      '<label>Country</label>' +
      '<input id="pf-country" type="text" placeholder="e.g. China" value="' + (user.country || "") + '" />' +
      '<label>New password (optional)</label>' +
      '<input id="pf-new" type="password" placeholder="Leave blank to keep current" />' +
      '<button class="btn btn-primary" id="pf-save" style="margin-top:10px;">Save profile</button>' +
      '<button class="btn btn-light" id="pf-change-password" style="margin-top:10px;margin-left:8px;">Update password</button>' +
      "</div></div>";
    if (byId("pf-lang") && user.language) byId("pf-lang").value = user.language;
    onClick(byId("pf-save"), async () => {
      try {
        await api("/api/auth/profile", {
          method: "PUT",
          body: JSON.stringify({
            language: byId("pf-lang") ? byId("pf-lang").value : user.language,
            country: byId("pf-country") ? byId("pf-country").value : user.country,
          }),
        });
        const updated = Object.assign({}, user, {
          language: byId("pf-lang") ? byId("pf-lang").value : user.language,
          country: byId("pf-country") ? byId("pf-country").value : user.country,
        });
        setUser(updated); refreshAuthUI(); alert("Saved.");
      } catch (e) { alert("Error: " + e.message); }
    });
    onClick(byId("pf-change-password"), async () => {
      const newPw = byId("pf-new") ? byId("pf-new").value : "";
      if (!newPw || newPw.length < 6) { alert("Please enter a new password (min 6 chars)."); return; }
      try { await api("/api/auth/profile", { method: "PUT", body: JSON.stringify({ password: newPw }) }); alert("Password updated."); if (byId("pf-new")) byId("pf-new").value = ""; }
      catch (e) { alert("Error: " + e.message); }
    });
  }

  // --- 首页统计 -------------------------------------------------
  async function loadStats() {
    try {
      const res = await api("/api/stats");
      const el = byId("home-stats");
      if (!res || !el) return;
      const items = [
        ["Hospitals", res.hospitals],
        ["Departments", res.departments],
        ["Translations", res.translations],
        ["Users", res.users],
        ["Medications", res.medications],
        ["Claims", res.insurance_claims],
      ];
      el.innerHTML = items.map(([l, n]) => '<div class="stat"><div class="stat-num">' + (n || 0) + '</div><div class="stat-label">' + l + "</div></div>").join("");
    } catch (e) { /* ignore */ }
  }

  // --- 启动 ------------------------------------------------------
  refreshAuthUI();
  loadStats();
  setActive("home");
})();
