/* TransMed frontend logic - simple and clean */
(function() {
  'use strict';

  // --- DOM helpers ---
  var byId = function(id) { return document.getElementById(id); };
  var qs = function(sel) { return document.querySelector(sel); };
  var qsa = function(sel) { return Array.from(document.querySelectorAll(sel)); };
  var bindClick = function(el, handler) { if (el) el.addEventListener('click', handler); };
  var bindChange = function(el, handler) { if (el) el.addEventListener('change', handler); };

  // --- API base detection ---
  // CSS selector: meta[name='api-base']
  var metaApi = qs("meta[name='api-base']");
  var isPages = location.hostname.indexOf('github.io') !== -1;
  var API = '';
  if (metaApi) API = metaApi.getAttribute('content') || '';
  else if (location.protocol === 'file:' || location.hostname === '127.0.0.1' || location.hostname === 'localhost') API = 'http://127.0.0.1:8000';

  // --- Auth helpers ---
  var TOKEN_KEY = 'transmed_token';
  var USER_KEY = 'transmed_user';
  var getToken = function() { return localStorage.getItem(TOKEN_KEY); };
  var setToken = function(t) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); };
  var getUser = function() { try { var raw = localStorage.getItem(USER_KEY); return raw ? JSON.parse(raw) : null; } catch(e) { return null; } };
  var setUser = function(u) { u ? localStorage.setItem(USER_KEY, JSON.stringify(u)) : localStorage.removeItem(USER_KEY); };

  // --- View switching ---
  var navLinks = qsa('.nav-link');
  var views = qsa('.view');
  var setActive = function(view) {
    views.forEach(function(v) { v.classList.toggle('active', v.dataset.view === view); });
    navLinks.forEach(function(a) { a.classList.toggle('active', a.dataset.view === view); });
    try {
      if (view === 'hospitals') loadHospitals();
      if (view === 'medication') loadMedications();
      if (view === 'navigation') initNavigation();
    } catch(e) { console.warn('setActive error:', e); }
  };
  navLinks.forEach(function(a) { bindClick(a, function() { setActive(a.dataset.view); }); });
  qsa('[data-go]').forEach(function(btn) { bindClick(btn, function() { setActive(btn.dataset.go); }); });

  // --- Login/Register modal ---
  var authModal = byId('auth-modal');
  var refreshAuthUI = function() {
    var user = getUser();
    if (byId('btn-login')) byId('btn-login').classList.toggle('hidden', !!user);
    if (byId('user-chip')) byId('user-chip').classList.toggle('hidden', !user);
    if (byId('user-email') && user) byId('user-email').textContent = user.email;
  };
  if (authModal) bindClick(authModal, function(e) { if (e.target === authModal) authModal.classList.add('hidden'); });
  bindClick(byId('btn-login'), function() { if (authModal) authModal.classList.remove('hidden'); });
  bindClick(byId('btn-logout'), function() { setToken(null); setUser(null); refreshAuthUI(); setActive('home'); });

  var switchAuthTab = function(tab) {
    qsa('.modal-tabs .tab').forEach(function(b) { b.classList.toggle('active', b.dataset.tab === tab); });
    var l = byId('tab-login'); if (l) l.classList.toggle('hidden', tab !== 'login');
    var r = byId('tab-register'); if (r) r.classList.toggle('hidden', tab !== 'register');
    var msg = byId('auth-message'); if (msg) msg.textContent = '';
  };
  qsa('.modal-tabs .tab').forEach(function(btn) { bindClick(btn, function() { switchAuthTab(btn.dataset.tab); }); });

  bindClick(byId('btn-do-login'), function() {
    var email = byId('login-email') ? byId('login-email').value.trim() : '';
    var pw = byId('login-password') ? byId('login-password').value : '';
    var msg = byId('auth-message');
    if (!email || !pw) { if (msg) msg.textContent = 'Please enter email and password'; return; }
    fetch(API + '/api/auth/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: email, password: pw}) })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data && data.access_token) { setToken(data.access_token); setUser(data.user); refreshAuthUI(); if (authModal) authModal.classList.add('hidden'); setActive('home'); }
        else { if (msg) msg.textContent = (data && data.detail) || 'Login failed'; }
      }).catch(function(e) { if (msg) msg.textContent = 'Error: ' + e.message; });
  });

  bindClick(byId('btn-do-register'), function() {
    var name = byId('reg-name') ? byId('reg-name').value.trim() : '';
    var email = byId('reg-email') ? byId('reg-email').value.trim() : '';
    var pw = byId('reg-password') ? byId('reg-password').value : '';
    var lang = byId('reg-language') ? byId('reg-language').value : 'en';
    var country = byId('reg-country') ? byId('reg-country').value.trim() : '';
    var msg = byId('auth-message');
    if (!name || !email || pw.length < 6) { if (msg) msg.textContent = 'Please fill all fields (min 6 char password)'; return; }
    fetch(API + '/api/auth/register', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({full_name: name, email: email, password: pw, language: lang, country: country}) })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data && data.access_token) { setToken(data.access_token); setUser(data.user); refreshAuthUI(); if (authModal) authModal.classList.add('hidden'); setActive('home'); }
        else { if (msg) msg.textContent = (data && data.detail) || 'Registration failed'; }
      }).catch(function(e) { if (msg) msg.textContent = 'Error: ' + e.message; });
  });

  // --- Translate ---
  bindClick(byId('btn-translate'), function() {
    var txt = byId('src-text') ? byId('src-text').value.trim() : '';
    var srcLang = byId('src-lang') ? byId('src-lang').value : 'en';
    var tgtLang = byId('tgt-lang') ? byId('tgt-lang').value : 'zh';
    var btn = byId('btn-translate');
    var out = byId('tgt-text');
    if (!txt || !out) return;
    if (btn) { btn.disabled = true; btn.textContent = 'Translating...'; }
    fetch(API + '/api/translate', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: txt, source_lang: srcLang, target_lang: tgtLang, medical_context: true}) })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        out.textContent = data.translated_text || '(no translation)';
        var c = typeof data.confidence === 'number' ? Math.round(data.confidence * 100) : 80;
        var conf = byId('confidence-bar'); if (conf) conf.classList.remove('hidden');
        var cv = byId('conf-value'); if (cv) cv.textContent = c;
        var cf = byId('conf-fill'); if (cf) cf.style.width = c + '%';
        var rv = byId('risk-value'); if (rv) rv.textContent = data.risk_level || 'low';
        var rb = byId('btn-confirm-risk'); if (rb) rb.classList.toggle('hidden', data.risk_level !== 'high');
        var ca = byId('conf-advice'); if (ca) ca.textContent = data.safety_advice || '';
        var matched = byId('matched-terms');
        if (matched) {
          var items = (data.medical_terms || []).map(function(t) {
            var def = t.definition ? ' ' + '·' + ' ' + t.definition : '';
            return '<span class="chip">' + t.term + def + '</span>';
          }).join('');
          matched.innerHTML = items ? '<div class="muted small" style="margin-bottom:6px;">Medical terms:</div>' + items : '';
        }
      }).catch(function(e) { out.textContent = 'Error: ' + e.message; })
      .finally(function() { if (btn) { btn.disabled = false; btn.textContent = 'Translate'; } });
  });

  bindClick(byId('swap-lang'), function() {
    var src = byId('src-lang'); var tgt = byId('tgt-lang');
    if (src && tgt) { var v = src.value; src.value = tgt.value; tgt.value = v; }
  });

  // --- Symptom chips ---
  var symptomBox = byId('symptom-chips');
  if (symptomBox) {
    ['headache', 'chest pain', 'cough', 'fever', 'stomach pain', 'back pain', 'skin rash', 'dizziness', 'fatigue', 'sore throat', 'shortness of breath', 'nausea', 'joint pain', 'anxiety'].forEach(function(txt) {
      var el = document.createElement('button');
      el.className = 'chip'; el.textContent = txt; el.type = 'button';
      bindClick(el, function() { var t = byId('src-text'); if (t) t.value = txt; });
      symptomBox.appendChild(el);
    });
  }

  // --- Triage & hospitals ---
  var lastHospitals = [];
  bindClick(byId('btn-triage'), function() {
    var symptom = byId('triage-input') ? byId('triage-input').value.trim() : '';
    var el = byId('triage-result');
    if (!symptom) return;
    fetch(API + '/api/triage', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({symptoms: symptom, language: 'en'}) })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!el) return;
        el.classList.remove('hidden');
        var dept = data.department_en || 'General Medicine';
        var deptZh = data.department_zh || '';
        var urgent = !!data.urgent;
        if (urgent) el.classList.add('urgent');
        var label = urgent ? 'URGENT - please see a doctor ASAP' : 'Recommended';
        var matched = '';
        if (data.matched_symptoms && data.matched_symptoms.length) {
          matched = '<div class="muted small" style="margin-top:6px;">Matched: ' + data.matched_symptoms.map(function(s){return '<span class="chip">' + s + '</span>';}).join('') + '</div>';
        }
        var zhPart = deptZh ? ' ' + '·' + ' ' + deptZh : '';
        el.innerHTML = '<div><span class="triage-label">' + label + '</span></div>' +
          '<strong>Department:</strong> ' + dept + zhPart + '<br>' +
          (data.recommendation_en || 'Please consult a doctor.') + matched;
      }).catch(function(e) { if (el) el.textContent = 'Triage service unavailable.'; });
    loadHospitals();
  });

  function loadHospitals() {
    var container = byId('hospital-list');
    if (!container) return;
    fetch(API + '/api/hospitals?limit=20')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var list = (data && data.hospitals) ? data.hospitals : [];
        lastHospitals = list;
        renderHospitals(list);
      }).catch(function(e) { container.innerHTML = '<p class="muted">Hospital list unavailable.</p>'; });
  }

  function renderHospitals(list) {
    var container = byId('hospital-list');
    if (!container) return;
    if (!Array.isArray(list) || !list.length) { container.innerHTML = '<p class="muted">No hospitals found.</p>'; return; }
    container.innerHTML = list.map(function(h) {
      var name = h.name || '';
      var nameZh = h.name_zh && h.name_zh !== h.name ? ' ' + '·' + ' ' + h.name_zh : '';
      var address = h.address || '';
      var rating = typeof h.rating === 'number' ? h.rating.toFixed(1) : '-';
      var wait = typeof h.wait_minutes === 'number' ? h.wait_minutes + ' min' : '-';
      var dist = typeof h.distance_km === 'number' ? h.distance_km.toFixed(1) + ' km' : '-';
      var specialties = (h.specialties || []).slice(0, 5).map(function(s) { return '<span class="chip">' + (typeof s === 'string' ? s : (s.name || s)) + '</span>'; }).join('');
      var insurances = (h.insurance || []).slice(0, 4).map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('');
      var languages = (h.languages || []).map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('');
      var parts = [];
      parts.push('<div class="hospital">');
      parts.push('<div class="hospital-main">');
      parts.push('<div class="hospital-head"><h4>' + name + nameZh + '</h4></div>');
      parts.push('<div class="sub">Address: ' + address + '</div>');
      if (h.phone) parts.push('<div class="sub">Phone: ' + h.phone + '</div>');
      parts.push('<div class="hospital-meta-row"><span class="meta-item">Wait: <strong>' + wait + '</strong></span><span class="meta-item">Distance: <strong>' + dist + '</strong></span></div>');
      if (specialties) parts.push('<div class="chips"><span class="muted small">Specialties: </span>' + specialties + '</div>');
      if (insurances) parts.push('<div class="chips"><span class="muted small">Insurance: </span>' + insurances + '</div>');
      if (languages) parts.push('<div class="chips"><span class="muted small">Languages: </span>' + languages + '</div>');
      parts.push('</div>');
      parts.push('<div class="hospital-side">');
      parts.push('<div class="rating-badge"><span class="rating-num">' + rating + '</span></div>');
      parts.push('<button class="btn btn-light btn-nav">Navigate here</button>');
      parts.push('</div></div>');
      return parts.join('');
    }).join('');
    qsa('#hospital-list .btn-nav').forEach(function(btn) { bindClick(btn, function() { setActive('navigation'); }); });
  }

  // --- Navigation ---
  function initNavigation() {
    var out = byId('nav-output');
    if (!out) return;
    out.innerHTML = '<div class="card"><h4 style="margin-top:0;">Outdoor Hospital Navigation</h4><p class="muted small">Select a hospital from the Hospitals page, then use external map services (Google Maps, AMap, Apple Maps, Baidu Maps) to get directions.</p><p>Click the Use my location button to enable geolocation-based routing from your current position.</p></div>';
  }

  bindClick(byId('nav-locate'), function() {
    if (!navigator.geolocation) { alert('Geolocation not available in this browser'); return; }
    navigator.geolocation.getCurrentPosition(function(pos) {
      alert('Your location: ' + pos.coords.latitude.toFixed(4) + ', ' + pos.coords.longitude.toFixed(4));
    }, function(err) { alert('Location error: ' + err.message); });
  });

  // --- Medications ---
  function loadMedications() {
    var listEl = byId('med-list');
    if (!listEl) return;
    fetch(API + '/api/medications?limit=30')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var meds = data.medications || [];
        var picker = byId('med-picker');
        if (picker) {
          picker.innerHTML = '';
          meds.forEach(function(m) { var opt = document.createElement('option'); opt.value = m.id || m.name; opt.textContent = m.name; picker.appendChild(opt); });
        }
        listEl.innerHTML = '<p class="muted small">' + meds.length + ' medications available. Log in to save your personal list.</p>';
      }).catch(function(e) { listEl.innerHTML = '<p class="muted">Medication list unavailable.</p>'; });
  }

  bindClick(byId('btn-add-med'), function() {
    if (!getUser()) { alert('Please log in to save medications'); return; }
    alert('Medication saved (demo feature)');
  });

  // --- Insurance ---
  bindClick(byId('btn-insurance'), function() {
    var sel = byId('ins-provider');
    var out = byId('ins-result');
    if (!sel || !out) return;
    var name = sel.value;
    var parts = [];
    parts.push('<div class="card">');
    parts.push('<h4 style="margin-top:0;">Checklist for ' + name + '</h4>');
    parts.push('<ul style="line-height:1.8;"><li>Passport / ID</li><li>Insurance card</li><li>Previous medical records</li><li>Referral letter (if required)</li><li>Invoice for reimbursement</li></ul>');
    parts.push('</div>');
    out.innerHTML = parts.join('');
  });

  bindClick(byId('btn-add-claim'), function() {
    if (!getUser()) { alert('Please log in first'); return; }
    alert('Claim submitted (demo feature)');
  });

  // --- Privacy ---
  bindClick(byId('btn-export'), function() { alert('Export ready (demo)'); });
  bindClick(byId('btn-wipe'), function() { if (confirm('Delete all your saved records?')) alert('Records wiped (demo)'); });

  // --- Feedback ---
  bindClick(byId('btn-send-feedback'), function() {
    var content = byId('fb-content') ? byId('fb-content').value.trim() : '';
    var statusEl = byId('fb-status');
    if (!content) return;
    if (statusEl) statusEl.textContent = 'Thank you for your feedback!';
    if (byId('fb-content')) byId('fb-content').value = '';
  });

  // --- Quick symptom chips on hospital page ---
  var hospitalChips = byId('symptom-chips');
  // already handled above

  // --- Init ---
  refreshAuthUI();
  setActive('home');
  console.log('TransMed UI initialized, API:', API);
})();