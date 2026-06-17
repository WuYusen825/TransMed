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
    if (view === "navigation") buildNavigationOptions();
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
        engineEl.textContent = engine === "deepseek" ? "🎯 DeepSeek AI + 医学语料库 RAG"
                              : engine === "offline" ? "⚠️ 离线术语匹配（DeepSeek 服务不可用，检查你的 API key）"
                              : engine === "same-language" ? "✓ same-language"
                              : "unknown";
        engineEl.classList.remove("online", "offline", "hidden");
        engineEl.classList.add(engine === "deepseek" ? "online" : "offline");
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
      }
    } else {
      el.classList.add("hidden");
    }
    loadHospitals();
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
    renderHospitals(lastHospitalsRaw);
  }

  function currentSortKey() {
    if (document.getElementById("sort-wait").checked) return "wait_minutes";
    if (document.getElementById("sort-distance").checked) return "distance_km";
    return "rating";
  }

  function renderHospitals(list) {
    const container = document.getElementById("hospital-list");
    if (!list || list.length === 0) {
      container.innerHTML = "<p class='muted'>No hospitals match your filters.</p>";
      return;
    }
    const sortKey = currentSortKey();
    const sorted = [...list].sort((a, b) => {
      const va = a[sortKey]; const vb = b[sortKey];
      if (va == null) return 1;
      if (vb == null) return -1;
      if (sortKey === "rating") return vb - va;
      return va - vb;
    });

    container.innerHTML = sorted.map(h => {
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

  /* ----------------------------- 室内导航 ----------------------------- */
  let lastNavHospitalName = "";
  async function buildNavigationOptions() {
    const hospitalSel = document.getElementById("nav-hospital");
    if (!hospitalSel.options.length) {
      const res = await api("/api/hospitals");
      hospitalSel.innerHTML = "";
      if (res && res.hospitals) {
        res.hospitals.forEach(h => hospitalSel.add(new Option(h.name, h.id)));
      }
    }
    const hid = hospitalSel.value;
    const selectedOpt = hospitalSel.options[hospitalSel.selectedIndex];
    lastNavHospitalName = selectedOpt ? selectedOpt.textContent : (hid || "");
    const destSel = document.getElementById("nav-dest");
    destSel.innerHTML = "";
    const mapRes = await api("/api/navigation/map?hospital_id=" + encodeURIComponent(hid || ""));
    if (mapRes && mapRes.nodes) {
      mapRes.nodes.forEach(n => destSel.add(new Option(n.label, n.id)));
    }
    document.getElementById("nav-info-hospital").textContent = "🏥 " + lastNavHospitalName;
    document.getElementById("nav-info-distance").textContent = "";
    renderMapBase(mapRes);
  }
  hospitalSelHandler();
  function hospitalSelHandler() {
    const hospitalSel = document.getElementById("nav-hospital");
    if (!hospitalSel) return;
    hospitalSel.addEventListener("change", () => buildNavigationOptions());
  }

  document.getElementById("btn-navigate").addEventListener("click", async () => {
    const hospitalSel = document.getElementById("nav-hospital");
    const dest = document.getElementById("nav-dest").value;
    const hid = hospitalSel.value;
    if (!hid || !dest) return;
    const nav = await api("/api/navigation?hospital_id=" + encodeURIComponent(hid)
      + "&from_node=entrance&to=" + encodeURIComponent(dest));
    const mapRes = await api("/api/navigation/map?hospital_id=" + encodeURIComponent(hid));
    renderMapBase(mapRes, nav && nav.route || null, true);
    renderRoute(nav, dest);
  });

  function computeLayoutCoords(nodes) {
    // Original backend coords range roughly 80..880 (x) and 200..800 (y)
    // Scale/translate to fit within the 1000x600 viewBox while keeping room
    // rectangles readable and leaving outer-wall padding.
    const padLeft = 60, padRight = 60;
    const padTop = 60, padBottom = 60;
    const innerW = 1000 - padLeft - padRight;
    const innerH = 600 - padTop - padBottom;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.forEach(n => {
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    });
    const dataW = Math.max(1, maxX - minX);
    const dataH = Math.max(1, maxY - minY);
    const scale = Math.min(innerW / dataW, innerH / dataH);
    const offX = padLeft + (innerW - dataW * scale) / 2 - minX * scale;
    const offY = padTop + (innerH - dataH * scale) / 2 - minY * scale;
    return { scale, offX, offY, padLeft, padTop, padRight, padBottom };
  }

  function splitLabel(label) {
    // Labels from backend look like "Name / 名称"
    if (!label) return { en: "", zh: "" };
    const idx = label.indexOf("/");
    if (idx === -1) return { en: label.trim(), zh: "" };
    return { en: label.slice(0, idx).trim(), zh: label.slice(idx + 1).trim() };
  }

  function renderMapBase(mapRes, route, animate) {
    const svg = document.getElementById("nav-svg");
    svg.innerHTML = "";
    const ns = "http://www.w3.org/2000/svg";
    svg.setAttribute("viewBox", "0 0 1000 600");

    // ---- Outer building border (with subtle drop shadow) ----
    const outer = document.createElementNS(ns, "rect");
    outer.setAttribute("x", 20);
    outer.setAttribute("y", 20);
    outer.setAttribute("width", 960);
    outer.setAttribute("height", 560);
    outer.setAttribute("rx", 8);
    outer.setAttribute("fill", "#0f1218");
    outer.setAttribute("stroke", "#2a2f3a");
    outer.setAttribute("stroke-width", 2);
    svg.appendChild(outer);

    // Ground fill (corridors will render on top)
    const ground = document.createElementNS(ns, "rect");
    ground.setAttribute("x", 30);
    ground.setAttribute("y", 30);
    ground.setAttribute("width", 940);
    ground.setAttribute("height", 540);
    ground.setAttribute("rx", 6);
    ground.setAttribute("fill", "#15181f");
    svg.appendChild(ground);

    if (!mapRes || !mapRes.nodes || mapRes.nodes.length === 0) {
      const empty = document.createElementNS(ns, "text");
      empty.setAttribute("x", 500);
      empty.setAttribute("y", 300);
      empty.setAttribute("text-anchor", "middle");
      empty.setAttribute("fill", "#94a3b8");
      empty.setAttribute("font-size", "14");
      empty.textContent = "No floor plan data available for this hospital.";
      svg.appendChild(empty);
      return;
    }

    const layout = computeLayoutCoords(mapRes.nodes);
    const nodeById = {};
    mapRes.nodes.forEach(n => {
      nodeById[n.id] = {
        ...n,
        _x: n.x * layout.scale + layout.offX,
        _y: n.y * layout.scale + layout.offY,
      };
    });

    const ROOM_W = 120;
    const ROOM_H = 80;

    // ---- Determine corridor geometry from node positions ----
    // Group nodes by similar y to find horizontal corridor rows.
    const yBuckets = {};
    const yTol = 25; // tolerance for "same row" in data coords
    mapRes.nodes.forEach(n => {
      const key = Math.round(n.y / yTol) * yTol;
      if (!yBuckets[key]) yBuckets[key] = [];
      yBuckets[key].push(n);
    });
    const rowYs = Object.keys(yBuckets).map(Number).sort((a, b) => a - b);

    // Horizontal corridors at each row (drawn as darker grey bands)
    rowYs.forEach(rawY => {
      const y = rawY * layout.scale + layout.offY;
      const band = document.createElementNS(ns, "rect");
      band.setAttribute("x", 40);
      band.setAttribute("y", y - ROOM_H / 2 - 4);
      band.setAttribute("width", 920);
      band.setAttribute("height", ROOM_H + 8);
      band.setAttribute("fill", "#1a1f29");
      band.setAttribute("rx", 3);
      svg.appendChild(band);
    });

    // Vertical corridor connecting the rows (through the central hall area)
    // Pick a center-x based on where nodes cluster horizontally.
    let centerX = 500;
    if (mapRes.nodes.length) {
      const mid = mapRes.nodes.reduce((s, n) => s + n.x, 0) / mapRes.nodes.length;
      centerX = mid * layout.scale + layout.offX;
    }
    const vCorridor = document.createElementNS(ns, "rect");
    vCorridor.setAttribute("x", centerX - ROOM_W / 2 - 4);
    vCorridor.setAttribute("y", 35);
    vCorridor.setAttribute("width", ROOM_W + 8);
    vCorridor.setAttribute("height", 530);
    vCorridor.setAttribute("fill", "#1a1f29");
    svg.appendChild(vCorridor);

    // ---- Grey path lines between rooms (walking graph) ----
    if (mapRes.paths && mapRes.paths.length) {
      mapRes.paths.forEach(p => {
        const from = nodeById[p.from], to = nodeById[p.to];
        if (!from || !to) return;
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", from._x);
        line.setAttribute("y1", from._y);
        line.setAttribute("x2", to._x);
        line.setAttribute("y2", to._y);
        line.setAttribute("stroke", "#2a2f3a");
        line.setAttribute("stroke-width", 2);
        line.setAttribute("stroke-dasharray", "4 3");
        line.setAttribute("opacity", "0.75");
        svg.appendChild(line);
      });
    }

    // ---- Rooms ----
    mapRes.nodes.forEach((n, idx) => {
      const g = document.createElementNS(ns, "g");
      const x = nodeById[n.id]._x;
      const y = nodeById[n.id]._y;

      const rect = document.createElementNS(ns, "rect");
      rect.setAttribute("x", x - ROOM_W / 2);
      rect.setAttribute("y", y - ROOM_H / 2);
      rect.setAttribute("width", ROOM_W);
      rect.setAttribute("height", ROOM_H);
      rect.setAttribute("rx", 4);
      rect.setAttribute("fill", "#15181f");
      rect.setAttribute("stroke", "#2a2f3a");
      rect.setAttribute("stroke-width", 1.5);
      g.appendChild(rect);

      // Room code in top-left corner (e.g. R101, R205)
      const roomCode = document.createElementNS(ns, "text");
      roomCode.setAttribute("x", x - ROOM_W / 2 + 8);
      roomCode.setAttribute("y", y - ROOM_H / 2 + 16);
      roomCode.setAttribute("fill", "#64748b");
      roomCode.setAttribute("font-size", "10");
      roomCode.setAttribute("font-family", "ui-monospace, SFMono-Regular, Menlo, monospace");
      roomCode.textContent = "R" + (n.floor || 1) * 100 + (idx + 1);
      g.appendChild(roomCode);

      // Floor badge in top-right
      const floorBadge = document.createElementNS(ns, "text");
      floorBadge.setAttribute("x", x + ROOM_W / 2 - 8);
      floorBadge.setAttribute("y", y - ROOM_H / 2 + 16);
      floorBadge.setAttribute("text-anchor", "end");
      floorBadge.setAttribute("fill", "#64748b");
      floorBadge.setAttribute("font-size", "10");
      floorBadge.textContent = "F" + (n.floor || 1);
      g.appendChild(floorBadge);

      // Two-line label inside room (English + Chinese)
      const { en, zh } = splitLabel(n.label);
      const enText = document.createElementNS(ns, "text");
      enText.setAttribute("x", x);
      enText.setAttribute("y", y - 2);
      enText.setAttribute("text-anchor", "middle");
      enText.setAttribute("fill", "#e2e8f0");
      enText.setAttribute("font-size", "12");
      enText.setAttribute("font-weight", "600");
      enText.textContent = truncateCenter(en, 18);
      g.appendChild(enText);

      if (zh) {
        const zhText = document.createElementNS(ns, "text");
        zhText.setAttribute("x", x);
        zhText.setAttribute("y", y + 16);
        zhText.setAttribute("text-anchor", "middle");
        zhText.setAttribute("fill", "#94a3b8");
        zhText.setAttribute("font-size", "11");
        zhText.textContent = truncateCenter(zh, 10);
        g.appendChild(zhText);
      }

      // Center anchor dot (will be overlaid by bigger circles for start/end/route)
      const dot = document.createElementNS(ns, "circle");
      dot.setAttribute("cx", x);
      dot.setAttribute("cy", y + ROOM_H / 2 - 10);
      dot.setAttribute("r", 2.5);
      dot.setAttribute("fill", "#475569");
      g.appendChild(dot);

      svg.appendChild(g);
    });

    // ---- Highlighted route path (orange) ----
    const routeIds = new Set();
    const routeNodes = [];
    if (route && route.length) {
      route.forEach(s => {
        routeIds.add(s.node_id);
        if (nodeById[s.node_id]) routeNodes.push(nodeById[s.node_id]);
      });
      for (let i = 0; i < route.length - 1; i++) {
        const from = nodeById[route[i].node_id];
        const to = nodeById[route[i + 1].node_id];
        if (!from || !to) continue;
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", from._x);
        line.setAttribute("y1", from._y);
        line.setAttribute("x2", to._x);
        line.setAttribute("y2", to._y);
        line.setAttribute("stroke", "#f97316");
        line.setAttribute("stroke-width", 4);
        line.setAttribute("stroke-linecap", "round");
        line.setAttribute("stroke-linejoin", "round");
        if (animate) {
          line.setAttribute("opacity", "0");
          setTimeout(() => {
            line.style.transition = "opacity 0.6s ease";
            line.setAttribute("opacity", "1");
          }, 120 * i);
        }
        svg.appendChild(line);
      }
    }

    // ---- Markers: START / DESTINATION / route-node dots ----
    mapRes.nodes.forEach((n, i) => {
      const x = nodeById[n.id]._x;
      const y = nodeById[n.id]._y;
      const inRoute = routeIds.has(n.id);
      const isStart = n.id === "entrance";
      const isDest = route && route.length && route[route.length - 1].node_id === n.id;

      let fill = "transparent";
      let stroke = "#2a2f3a";
      let r = 5;
      let labelText = "";
      let labelColor = "#94a3b8";

      if (inRoute) {
        fill = "#f97316";
        stroke = "#f97316";
        r = 6;
      }
      if (isStart) {
        fill = "#22c55e";
        stroke = "#22c55e";
        r = 7;
        labelText = "START";
        labelColor = "#22c55e";
      }
      if (isDest) {
        fill = "#f97316";
        stroke = "#f97316";
        r = 8;
        labelText = "DESTINATION";
        labelColor = "#f97316";
      }

      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", x);
      c.setAttribute("cy", y - ROOM_H / 2 - 12);
      c.setAttribute("r", r);
      c.setAttribute("fill", fill);
      c.setAttribute("stroke", stroke);
      c.setAttribute("stroke-width", 2);
      if (animate && inRoute) {
        c.setAttribute("opacity", "0");
        setTimeout(() => {
          c.style.transition = "opacity 0.5s ease";
          c.setAttribute("opacity", "1");
        }, 100 * i);
      }
      svg.appendChild(c);

      if (labelText) {
        const t = document.createElementNS(ns, "text");
        t.setAttribute("x", x);
        t.setAttribute("y", y - ROOM_H / 2 - 22);
        t.setAttribute("text-anchor", "middle");
        t.setAttribute("fill", labelColor);
        t.setAttribute("font-size", "11");
        t.setAttribute("font-weight", "700");
        t.setAttribute("letter-spacing", "1");
        t.textContent = labelText;
        svg.appendChild(t);
      }
    });

    // ---- Compass / floor label in a corner ----
    const corner = document.createElementNS(ns, "g");
    const cornerBox = document.createElementNS(ns, "rect");
    cornerBox.setAttribute("x", 30);
    cornerBox.setAttribute("y", 30);
    cornerBox.setAttribute("width", 120);
    cornerBox.setAttribute("height", 28);
    cornerBox.setAttribute("rx", 4);
    cornerBox.setAttribute("fill", "#0f1218");
    cornerBox.setAttribute("stroke", "#2a2f3a");
    corner.appendChild(cornerBox);
    const cornerText = document.createElementNS(ns, "text");
    cornerText.setAttribute("x", 90);
    cornerText.setAttribute("y", 49);
    cornerText.setAttribute("text-anchor", "middle");
    cornerText.setAttribute("fill", "#94a3b8");
    cornerText.setAttribute("font-size", "11");
    cornerText.textContent = "HOSPITAL FLOOR PLAN";
    corner.appendChild(cornerText);
    svg.appendChild(corner);
  }

  function truncateCenter(s, n) {
    if (!s) return "";
    if (s.length <= n) return s;
    if (n <= 3) return s.slice(0, n);
    const half = Math.floor((n - 1) / 2);
    return s.slice(0, half) + "…" + s.slice(s.length - half);
  }

  function renderRoute(nav, dest) {
    const routeEl = document.getElementById("nav-route");
    const distEl = document.getElementById("nav-info-distance");
    if (!nav || !nav.route || nav.route.length === 0) {
      routeEl.innerHTML = `<p class="muted">No route available. Try a different destination.</p>`;
      if (distEl) distEl.textContent = "";
      return;
    }
    const total = nav.total_distance;
    const distStr = (typeof total === "number") ? total.toFixed(0) : (total || "—");
    if (distEl) {
      distEl.textContent = "🚶 Total distance: " + distStr + " units · " + nav.route.length + " steps";
    }

    const first = nav.route[0];
    const last = nav.route[nav.route.length - 1];
    const firstNode = typeof first === "object" ? (first.label || first.node_id || "") : "";
    const lastNode = typeof last === "object" ? (last.label || last.node_id || dest) : dest;

    const steps = nav.route.map((s, i) => {
      const label = (typeof s === "object" && s.label) ? s.label : (s.node_id || "");
      const parts = splitLabel(label);
      const en = parts.en || label || "Step " + (i + 1);
      const zh = parts.zh ? `<span class="muted small"> · ${parts.zh}</span>` : "";
      const instruction = (typeof s === "object" && s.instruction) ? s.instruction : "";
      const floor = (typeof s === "object" && s.floor) ? `Floor ${s.floor}` : "";
      return `
        <div class="nav-step ${i === 0 ? "nav-step-current" : ""}">
          <span class="nav-step-pill">${i + 1}</span>
          <div class="nav-step-body">
            <div class="nav-step-title">${en}${zh}</div>
            ${floor ? `<div class="nav-step-meta muted small">${floor}</div>` : ""}
            ${instruction ? `<div class="nav-step-instr muted small">${instruction}</div>` : ""}
          </div>
        </div>
      `;
    }).join("");

    routeEl.innerHTML = `
      <div class="card" style="padding:12px 14px;margin-bottom:12px;border-color:var(--border-strong);">
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <h4 style="margin:0;">📍 Route to ${splitLabel(lastNode).en || lastNode}</h4>
          <span class="chip" style="color:var(--accent-soft);">${distStr} units</span>
        </div>
        <p class="muted small" style="margin-top:6px;margin-bottom:0;">From: ${splitLabel(firstNode).en || firstNode}</p>
      </div>
      ${steps}
    `;
  }

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
