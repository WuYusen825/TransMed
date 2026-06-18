#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建前端 app.js（源文件）。

JS 以 raw 字符串内嵌于此，运行后写入 transmed_web/app.js 与 docs/app.js 两份。
  python3 build_appjs.py

设计目标（2026 重做）：
  · 浅色 Claude 奶油风 + 苹果式滚动/动效（配合 style.css）
  · 接活此前的死功能：登录注册 / 首页统计 / 用药库与提醒 / 隐私导出清除 / 反馈 / 个人中心
  · 修复导航：设置 _AMapSecurityConfig 安全密钥 → 真正画出路线折线 + 转向步骤；跨页"导航到这里"不再丢目标
  · 升级医院推荐：症状→分诊→按匹配度排序，给出推荐理由 + 真实评价 + 距离 + 一键导航
"""
import os

JS = r'''/* TransMed frontend — light Claude theme build */
(function () {
  'use strict';

  /* ============================== tiny utils ============================== */
  var byId = function (id) { return document.getElementById(id); };
  var qs   = function (s, r) { return (r || document).querySelector(s); };
  var qsa  = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var on   = function (el, ev, fn) { if (el) el.addEventListener(ev, fn); };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }
  function trim(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n).trim() + '…' : s; }
  function num(v) { var n = typeof v === 'number' ? v : parseFloat(v); return isFinite(n) ? n : null; }

  /* ============================== API base ============================== */
  var metaApi = qs("meta[name='api-base']");
  var API = metaApi ? (metaApi.getAttribute('content') || '') : '';
  if (!API && (location.protocol === 'file:' || /localhost|127\.0\.0\.1/.test(location.hostname))) {
    API = 'http://127.0.0.1:8000';
  }

  /* ============================== session ============================== */
  var TOKEN_KEY = 'transmed_token', USER_KEY = 'transmed_user';
  var token = '', currentUser = null;
  try { token = localStorage.getItem(TOKEN_KEY) || ''; } catch (e) {}
  try { currentUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch (e) {}

  function setSession(tok, user) {
    token = tok || ''; currentUser = user || null;
    try { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(currentUser)); } catch (e) {}
    refreshAuthUI();
  }
  function clearSession() {
    token = ''; currentUser = null;
    try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); } catch (e) {}
    refreshAuthUI();
  }

  /* ============================== fetch helper ============================== */
  // api(path, {method, body, auth, timeout}) -> Promise<data>; rejects with Error(.status,.data)
  function api(path, opts) {
    opts = opts || {};
    var headers = {};
    if (opts.body != null) headers['Content-Type'] = 'application/json';
    if (opts.auth && token) headers['Authorization'] = 'Bearer ' + token;
    var ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    var tid = ctrl ? setTimeout(function () { ctrl.abort(); }, opts.timeout || 15000) : null;
    var init = { method: opts.method || 'GET', headers: headers };
    if (opts.body != null) init.body = JSON.stringify(opts.body);
    if (ctrl) init.signal = ctrl.signal;
    return fetch((API || '') + path, init).then(function (r) {
      return r.text().then(function (t) {
        var data; try { data = t ? JSON.parse(t) : {}; } catch (e) { data = { _raw: t }; }
        if (!r.ok) {
          var msg = (data && (data.detail || data.message)) || ('HTTP ' + r.status);
          var err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
          err.status = r.status; err.data = data; throw err;
        }
        return data;
      });
    }).then(function (d) { if (tid) clearTimeout(tid); return d; }, function (e) { if (tid) clearTimeout(tid); throw e; });
  }

  /* ============================== toast ============================== */
  function toast(msg, kind) {
    var host = byId('toast-host'); if (!host) { return; }
    var icon = kind === 'ok' ? '✓' : kind === 'err' ? '⚠' : kind === 'warn' ? '!' : '•';
    var el = document.createElement('div');
    el.className = 'toast ' + (kind || '');
    el.innerHTML = '<span class="ti">' + icon + '</span><span>' + esc(msg) + '</span>';
    host.appendChild(el);
    setTimeout(function () {
      el.style.transition = 'opacity .35s, transform .35s'; el.style.opacity = '0'; el.style.transform = 'translateY(10px)';
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 380);
    }, 3200);
  }

  /* ============================== shared geo ============================== */
  var _userLoc = null;          // {lng, lat} (WGS84 from browser)
  function haversineKm(a, b) {
    if (!a || !b) return null;
    var R = 6371, toRad = function (d) { return d * Math.PI / 180; };
    var dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
    var s = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(s));
  }
  function getLocation(onOk, onErr) {
    if (!navigator.geolocation) { onErr && onErr('Geolocation unavailable'); return; }
    navigator.geolocation.getCurrentPosition(function (p) {
      _userLoc = { lng: p.coords.longitude, lat: p.coords.latitude };
      Nav.setOriginFromGps(_userLoc);
      onOk && onOk(_userLoc);
    }, function (err) { onErr && onErr(err.message || 'denied'); },
       { timeout: 15000, enableHighAccuracy: true });
  }

  /* ============================== fallback hospital data ============================== */
  var FALLBACK_HOSPITALS = [
    { id: 'pumch', name: 'Peking Union Medical College Hospital', name_zh: '北京协和医院', address_zh: '东城区帅府园1号', phone: '+86 10 6915 6114', rating: 4.9, review_count: 8600, specialties: ['General Medicine', 'Cardiology', 'Neurology', 'Endocrinology'], lng: 116.41513, lat: 39.912815 },
    { id: 'bjh', name: 'Beijing Hospital', name_zh: '北京医院', address_zh: '东城区东单大华路1号', phone: '+86 10 8513 2266', rating: 4.6, review_count: 2100, specialties: ['Geriatrics', 'Cardiology', 'Endocrinology'], lng: 116.415057, lat: 39.903772 },
    { id: 'tongren', name: 'Beijing Tongren Hospital', name_zh: '北京同仁医院', address_zh: '东城区东交民巷1号', phone: '+86 10 5826 9988', rating: 4.6, review_count: 4200, specialties: ['Ophthalmology', 'ENT'], lng: 116.417224, lat: 39.902721 },
    { id: 'ufh', name: 'Beijing United Family Hospital', name_zh: '北京和睦家医院', address_zh: '朝阳区将台路2号', phone: '+86 10 5927 7000', rating: 4.8, review_count: 1500, specialties: ['Family Medicine', 'Pediatrics', 'Emergency', 'OB/GYN'], lng: 116.4677, lat: 39.9754 },
    { id: '301', name: 'PLA General Hospital (301)', name_zh: '解放军总医院', address_zh: '海淀区复兴路28号', phone: '+86 10 6693 7329', rating: 4.7, review_count: 5300, specialties: ['Trauma Surgery', 'Oncology', 'Cardiology', 'Orthopedics'], lng: 116.2875, lat: 39.9067 }
  ];

  /* ============================== languages ============================== */
  var LANGS = [
    { code: 'en', name: 'English' }, { code: 'zh', name: '中文' }, { code: 'ja', name: '日本語' },
    { code: 'ko', name: '한국어' }, { code: 'fr', name: 'Français' }, { code: 'de', name: 'Deutsch' },
    { code: 'es', name: 'Español' }, { code: 'it', name: 'Italiano' }, { code: 'ru', name: 'Русский' },
    { code: 'ar', name: 'العربية' }, { code: 'pt', name: 'Português' }, { code: 'hi', name: 'हिन्दी' }
  ];

  /* ============================================================
     1) View switching + scroll reveal + topbar
     ============================================================ */
  var navLinks = qsa('.nav-link'), views = qsa('.view');
  var _viewInit = {};
  function setActive(view) {
    views.forEach(function (v) { v.classList.toggle('active', v.dataset.view === view); });
    navLinks.forEach(function (a) { a.classList.toggle('active', a.dataset.view === view); });
    if (view !== 'home') window.scrollTo({ top: 0, behavior: 'smooth' });
    try {
      if (view === 'hospitals' && !_viewInit.hospitals) { _viewInit.hospitals = 1; loadHospitals(); }
      if (view === 'navigation') Nav.enter();
      if (view === 'medication' && !_viewInit.medication) { _viewInit.medication = 1; Med.init(); }
      if (view === 'account') Account.render();
      if (view === 'translate') loadMyTranslations();
    } catch (e) { console.warn('view init error', view, e); }
    revealScan();
  }
  navLinks.forEach(function (a) { on(a, 'click', function () { setActive(a.dataset.view); }); });
  qsa('[data-go]').forEach(function (b) { on(b, 'click', function () { setActive(b.dataset.go); }); });

  // scroll reveal
  var _io = null;
  if ('IntersectionObserver' in window) {
    _io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-visible'); _io.unobserve(en.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
  }
  function revealScan() {
    qsa('.reveal:not(.is-visible)').forEach(function (el) {
      if (_io) _io.observe(el); else el.classList.add('is-visible');
    });
  }

  // topbar shadow on scroll
  var topbar = byId('topbar');
  function onScroll() { if (topbar) topbar.classList.toggle('scrolled', window.scrollY > 8); }
  on(window, 'scroll', onScroll); onScroll();

  /* ============================================================
     2) Translate
     ============================================================ */
  (function initLangSelectors() {
    [byId('src-lang'), byId('tgt-lang')].forEach(function (sel, i) {
      if (!sel) return; sel.innerHTML = '';
      LANGS.forEach(function (l) {
        var o = document.createElement('option'); o.value = l.code; o.textContent = l.name; sel.appendChild(o);
      });
      sel.value = i === 0 ? 'en' : 'zh';
    });
  })();
  on(byId('swap-lang'), 'click', function () {
    var s = byId('src-lang'), t = byId('tgt-lang');
    if (s && t) { var v = s.value; s.value = t.value; t.value = v; }
  });

  function showTranslation(translated, confidence, terms, engine, ragCtx) {
    var out = byId('tgt-text'); if (!out) return;
    out.textContent = translated; out.classList.remove('placeholder');
    var conf = Math.max(0, Math.min(100, Math.round(confidence)));
    var cv = byId('conf-value'); if (cv) cv.textContent = String(conf);
    var cf = byId('conf-fill'); if (cf) cf.style.width = Math.max(8, conf) + '%';
    var risk = conf >= 85 ? 'low' : conf >= 65 ? 'medium' : conf >= 45 ? 'high' : 'critical';
    var rv = byId('risk-value'); if (rv) rv.textContent = risk;
    var el = byId('engine-label');
    if (el) {
      var online = engine && /groq|online|ai|api/i.test(engine) && engine !== 'offline';
      el.textContent = (online ? '● Online · ' : '○ Offline · ') + engine;
      el.className = 'engine-label ' + (online ? 'online' : 'offline');
    }
    var adv = byId('conf-advice');
    if (adv) adv.textContent = risk === 'low' ? 'High confidence. Still confirm critical details with your clinician.'
      : risk === 'medium' ? 'Moderate confidence — double-check dosages, numbers and negations.'
      : 'Low confidence. Please verify with a bilingual staff member before acting on this.';
    var bc = byId('confidence-bar'); if (bc) bc.classList.remove('hidden');
    var tb = byId('matched-terms');
    if (tb) tb.innerHTML = (terms && terms.length)
      ? '<div class="muted small" style="margin-bottom:6px;">Recognised medical terms</div>' +
        terms.map(function (t) { return '<span class="chip static">' + esc(t) + '</span>'; }).join('')
      : '';
    var rb = byId('rag-reference');
    if (rb) rb.innerHTML = (ragCtx && ragCtx.length)
      ? '<details style="margin-top:12px;"><summary class="muted small" style="cursor:pointer;">📚 Medical reference (' + ragCtx.length + ')</summary><ul class="muted small" style="margin:8px 0 0 18px;">' +
        ragCtx.slice(0, 5).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul></details>'
      : '';
  }

  var OFFLINE = { 'headache': '头痛', 'fever': '发热', 'cough': '咳嗽', 'chest pain': '胸痛', 'dizziness': '头晕', 'nausea': '恶心', 'vomiting': '呕吐', 'sore throat': '咽痛', 'shortness of breath': '呼吸困难', 'back pain': '背痛', 'rash': '皮疹', 'fatigue': '乏力' };
  function offlineTranslate(txt, src, tgt) {
    var res = txt, matched = [];
    if (/zh/.test(tgt)) {
      Object.keys(OFFLINE).sort(function (a, b) { return b.length - a.length; }).forEach(function (k) {
        var re = new RegExp('\\b' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
        if (re.test(res)) { res = res.replace(re, OFFLINE[k]); matched.push(k); }
      });
    }
    return { translated: res, confidence: matched.length ? Math.min(70, 35 + matched.length * 9) : 28, matched: matched };
  }

  on(byId('btn-translate'), 'click', function () {
    var txt = (byId('src-text') || {}).value; txt = (txt || '').trim();
    var src = (byId('src-lang') || {}).value || 'en', tgt = (byId('tgt-lang') || {}).value || 'zh';
    var btn = byId('btn-translate'), out = byId('tgt-text');
    if (!txt || !out) return;
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Translating…'; }
    var done = function () { if (btn) { btn.disabled = false; btn.textContent = 'Translate'; } };

    api('/api/translate', { method: 'POST', body: { text: txt, source: src, target: tgt }, auth: true, timeout: 18000 })
      .then(function (d) {
        var translated = d.translated || d.translated_text || '';
        var conf = num(d.confidence); if (conf == null) conf = 60; if (conf <= 1) conf *= 100;
        showTranslation(translated, conf, d.matched_terms || d.medical_terms || [], d.engine || 'api', d.rag_context || []);
        done(); loadMyTranslations();
      })
      .catch(function (e) {
        var f = offlineTranslate(txt, src, tgt);
        showTranslation(f.translated, f.confidence, f.matched, 'offline', []);
        done();
      });
  });

  on(byId('btn-confirm-risk'), 'click', function () { this.classList.add('hidden'); toast('Risk acknowledged', 'ok'); });

  (function initSymptomChips() {
    var box = byId('symptom-chips'); if (!box) return;
    ['headache', 'chest pain', 'high fever', 'cough', 'stomach pain', 'shortness of breath', 'dizziness', 'rash', 'back pain', 'sore throat'].forEach(function (t) {
      var b = document.createElement('button'); b.className = 'chip'; b.type = 'button'; b.textContent = t;
      on(b, 'click', function () { var ta = byId('src-text'); if (ta) { ta.value = 'I have ' + t + ' for 2 days.'; ta.focus(); } });
      box.appendChild(b);
    });
  })();

  function loadMyTranslations() {
    var box = byId('my-translations'); if (!box) return;
    if (!token) { box.innerHTML = '<div class="empty-state">Sign in to keep a history of your translations.</div>'; return; }
    api('/api/translate/logs', { auth: true }).then(function (rows) {
      if (!rows || !rows.length) { box.innerHTML = '<div class="empty-state">No saved translations yet.</div>'; return; }
      box.innerHTML = rows.slice(0, 8).map(function (r) {
        return '<div class="list-item"><div><strong>' + esc(trim(r.original, 60)) + '</strong>' +
          '<div class="meta">→ ' + esc(trim(r.translated, 70)) + '</div>' +
          '<div class="meta">' + esc(r.source) + '→' + esc(r.target) + ' · confidence ' + Math.round(r.confidence || 0) + '% · ' + esc((r.risk_level || '')) + '</div></div></div>';
      }).join('');
    }).catch(function () { box.innerHTML = '<div class="empty-state">Could not load history.</div>'; });
  }

  /* ============================================================
     3) Home stats (animated)
     ============================================================ */
  function animateCount(el, to) {
    var dur = 1100, start = null, from = 0;
    function tick(ts) {
      if (start == null) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(from + (to - from) * eased).toLocaleString();
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  function renderStats(d) {
    var box = byId('home-stats'); if (!box) return;
    var cards = [
      { v: 12, label: 'Languages' },
      { v: d.medical_terms || 349, label: 'Medical terms' },
      { v: d.hospitals || 6, label: 'Hospitals' },
      { v: d.triage_rules || 55, label: 'Triage rules' },
      { v: d.translations || 0, label: 'Translations served' }
    ];
    box.innerHTML = cards.map(function (c) {
      return '<div class="stat"><div class="stat-num" data-to="' + c.v + '">0</div><div class="stat-label">' + esc(c.label) + '</div></div>';
    }).join('');
    var started = false;
    var run = function () { if (started) return; started = true; qsa('.stat-num', box).forEach(function (el) { animateCount(el, parseInt(el.getAttribute('data-to'), 10) || 0); }); };
    if ('IntersectionObserver' in window) {
      var ob = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { run(); ob.disconnect(); } }); }, { threshold: 0.3 });
      ob.observe(box);
    } else run();
  }
  function loadStats() {
    renderStats({});
    api('/api/stats').then(renderStats).catch(function () {});
  }

  /* ============================================================
     4) Hospitals: triage + recommendation
     ============================================================ */
  var _lastHospitals = [], _lastRanked = false, _lastMax = 0, _sortMode = 'match', _hospReq = 0;

  function cleanReasons(rec, h, distKm) {
    var out = [], seen = {};
    function push(type, text) { if (text && !seen[text]) { seen[text] = 1; out.push({ type: type, text: text }); } }
    (rec && rec.matched_specialties || []).slice(0, 3).forEach(function (sp) { push('spec', 'Strong in ' + sp); });
    if (h.rating) push('ok', 'Rated ' + num(h.rating).toFixed(1) + '/5' + (h.review_count ? ' (' + Number(h.review_count).toLocaleString() + ' reviews)' : ''));
    if (distKm != null) push('ok', distKm.toFixed(1) + ' km from you');
    (rec && rec.reasons || []).forEach(function (r) {
      if (/speaks your language/i.test(r)) push('ok', 'Speaks your language');
      else if (/emergency/i.test(r)) push('ok', 'Strong emergency services');
    });
    return out.slice(0, 4);
  }
  function starStr(r) {
    var full = Math.floor(r), half = (r - full) >= 0.5 ? 1 : 0, empty = 5 - full - half;
    return '★'.repeat(full) + (half ? '⯨' : '') + '☆'.repeat(Math.max(0, empty));
  }
  function hospitalCard(h, idx, ranked, maxScore) {
    var name = esc(h.name || h.name_zh || 'Hospital');
    var zh = (h.name_zh && h.name_zh !== h.name) ? '<span class="zh"> · ' + esc(h.name_zh) + '</span>' : '';
    var rating = num(h.rating);
    var dist = (_userLoc && typeof h.lng === 'number') ? haversineKm(_userLoc, h) : null;
    var ring = '';
    if (ranked && h.recommendation) {
      var pct = maxScore ? Math.max(10, Math.min(100, Math.round(h.recommendation.score / maxScore * 100))) : 60;
      ring = '<div class="score-ring" style="--p:' + pct + '"><div class="score-inner"><div class="score-val">' + pct + '</div><div class="score-cap">match</div></div></div>';
    }
    var reasons = (ranked && h.recommendation) ? '<div class="match-reasons">' +
      cleanReasons(h.recommendation, h, dist).map(function (r) {
        return '<div class="reason ' + (r.type === 'spec' ? 'spec' : '') + '"><span class="tick">' + (r.type === 'spec' ? '◆' : '✓') + '</span><span>' + esc(r.text) + '</span></div>';
      }).join('') + '</div>' : '';
    var addr = (h.address_zh || h.address) ? '<div class="hospital-sub">📍 ' + esc(h.address_zh || h.address) + '</div>' : '';
    var phone = h.phone ? '<div class="hospital-sub">☎ ' + esc(h.phone) + '</div>' : '';
    var specs = (h.specialties || []).slice(0, 5).map(function (s) { return '<span class="chip static">' + esc(typeof s === 'string' ? s : (s.name || '')) + '</span>'; }).join('');
    var review = (h.reviews && h.reviews.length) ? '<div class="review-quote">“' + esc(trim(h.reviews[0], 96)) + '”</div>' : '';
    var hasLoc = typeof h.lng === 'number' && typeof h.lat === 'number';
    var nav = hasLoc ? '<button class="btn btn-primary btn-sm js-nav" data-lng="' + h.lng + '" data-lat="' + h.lat + '" data-name="' + esc(h.name_zh || h.name) + '">Navigate →</button>' : '';
    var ratingLine = '<div class="rating-line">' +
      (rating ? '<span class="stars">' + starStr(rating) + '</span><span class="rating-num">' + rating.toFixed(1) + '</span>' : '') +
      (h.review_count ? '<span class="review-count">' + Number(h.review_count).toLocaleString() + ' reviews</span>' : '') +
      (dist != null ? '<span class="review-count">· ' + dist.toFixed(1) + ' km</span>' : '') + '</div>';
    return '<div class="hospital-card ' + (ranked && idx === 0 ? 'top' : '') + '">' +
      (ranked ? '<div class="rank-badge">#' + (idx + 1) + ' best match</div>' : '') +
      '<div class="hospital-main"><div class="hospital-name">' + name + zh + '</div>' + ratingLine + addr + phone +
      (specs ? '<div class="chips" style="margin-top:8px;">' + specs + '</div>' : '') + reasons + review + '</div>' +
      '<div class="hospital-side">' + ring + nav + '</div></div>';
  }
  function renderHospitals(list, ranked, maxScore) {
    var box = byId('hospital-list'); if (!box) return;
    _lastHospitals = list || []; _lastRanked = !!ranked; _lastMax = maxScore || 0;
    if (!list || !list.length) { box.innerHTML = '<div class="empty-state">No hospitals found. Try a broader symptom or department.</div>'; return; }
    var arr = list.slice();
    if (_sortMode === 'rating') arr.sort(function (a, b) { return (num(b.rating) || 0) - (num(a.rating) || 0); });
    else if (_sortMode === 'distance' && _userLoc) arr.sort(function (a, b) { return (haversineKm(_userLoc, a) || 9e9) - (haversineKm(_userLoc, b) || 9e9); });
    box.innerHTML = arr.map(function (h, i) { return hospitalCard(h, i, ranked, maxScore); }).join('');
    qsa('.js-nav', box).forEach(function (b) {
      on(b, 'click', function () {
        var lng = parseFloat(b.getAttribute('data-lng')), lat = parseFloat(b.getAttribute('data-lat'));
        setActive('navigation');
        setTimeout(function () { Nav.setTarget(lng, lat, b.getAttribute('data-name')); }, 60);
      });
    });
  }

  function loadHospitals() {
    var box = byId('hospital-list'); if (!box) return;
    var myReq = ++_hospReq;
    box.innerHTML = '<div class="empty-state"><span class="spinner"></span> Loading hospitals…</div>';
    renderHospitals(FALLBACK_HOSPITALS, false, 0);
    api('/api/hospitals?limit=12').then(function (d) {
      if (myReq !== _hospReq) return; // a newer request superseded this one
      if (d && d.hospitals && d.hospitals.length) renderHospitals(d.hospitals, false, 0);
    }).catch(function () {});
  }

  function runRecommend() {
    var sym = (byId('triage-input') || {}).value; sym = (sym || '').trim();
    var spec = (byId('specialty-filter') || {}).value || '';
    var banner = byId('triage-result'), box = byId('hospital-list');
    if (!sym && !spec) { toast('Describe your symptoms first', 'warn'); return; }
    if (box) box.innerHTML = '<div class="empty-state"><span class="spinner"></span> Matching hospitals…</div>';
    if (banner) banner.classList.add('hidden');
    _sortMode = 'match'; syncSortUI();
    var myReq = ++_hospReq;
    var body = { symptoms: sym || spec, city: '北京', limit: 10 };
    if (spec) body.specialty_override = spec;
    if (currentUser && currentUser.language) body.language = currentUser.language;
    api('/api/recommendations', { method: 'POST', body: body, timeout: 18000 }).then(function (d) {
      if (myReq !== _hospReq) return; // superseded by a newer query
      var tr = d.triage || {};
      if (banner) {
        banner.className = 'triage-banner' + (tr.urgent ? ' urgent' : '');
        banner.classList.remove('hidden');
        banner.innerHTML = '<span class="triage-tag">' + (tr.urgent ? '🚨 URGENT' : '✓ Recommended department') + '</span>' +
          '<h4>' + esc(tr.department_en || 'General Medicine') + ' <span class="dept-zh">' + esc(tr.department_zh || '') + '</span></h4>' +
          (tr.urgent ? '<p style="margin:4px 0 0;color:var(--danger);font-weight:600;">If this is an emergency, call 120 now.</p>' : '') +
          ((tr.matched_symptoms && tr.matched_symptoms.length) ? '<div class="chips" style="margin-top:8px;">' + tr.matched_symptoms.slice(0, 6).map(function (s) { return '<span class="chip static">' + esc(s) + '</span>'; }).join('') + '</div>' : '');
      }
      var list = d.hospitals || [];
      var maxScore = list.reduce(function (m, h) { return Math.max(m, (h.recommendation && h.recommendation.score) || 0); }, 0);
      renderHospitals(list, true, maxScore);
    }).catch(function (e) {
      if (myReq !== _hospReq) return; // superseded — don't clobber a newer result
      if (banner) { banner.className = 'triage-banner'; banner.classList.remove('hidden'); banner.innerHTML = '<span class="triage-tag">Heads up</span><h4 style="font-size:15px;">Recommendation service is waking up</h4><p class="muted small" style="margin:4px 0 0;">Showing all hospitals meanwhile. Try again in a moment.</p>'; }
      loadHospitals();
    });
  }
  on(byId('btn-triage'), 'click', runRecommend);
  on(byId('triage-input'), 'keydown', function (e) { if (e.key === 'Enter') runRecommend(); });
  on(byId('btn-use-location'), 'click', function () {
    var b = this; b.disabled = true; b.textContent = '📍 Locating…';
    getLocation(function () { b.disabled = false; b.textContent = '📍 Location set'; toast('Location set — distances added', 'ok'); renderHospitals(_lastHospitals, _lastRanked, _lastMax); },
      function (m) { b.disabled = false; b.textContent = '📍 Use my location for distance'; toast('Location: ' + m, 'err'); });
  });
  function syncSortUI() { qsa('#sort-seg button').forEach(function (b) { b.classList.toggle('active', b.dataset.sort === _sortMode); }); }
  qsa('#sort-seg button').forEach(function (b) {
    on(b, 'click', function () {
      if (b.dataset.sort === 'distance' && !_userLoc) { toast('Tap “Use my location” first', 'warn'); return; }
      _sortMode = b.dataset.sort; syncSortUI(); renderHospitals(_lastHospitals, _lastRanked, _lastMax);
    });
  });

  /* ============================================================
     5) Navigation — AMap with security code, drawn route + steps
     ============================================================ */
  var Nav = (function () {
    var DEFAULT_ORIGIN = { lng: 116.4074, lat: 39.9042 };
    var map = null, ready = false, inited = false, confFetched = false;
    var jsKey = '', secCode = '', hasSec = false;
    var origin = { lng: DEFAULT_ORIGIN.lng, lat: DEFAULT_ORIGIN.lat }, originIsGps = false;
    var target = null, mode = 'walking', list = [], city = '北京';

    function setOriginText() {
      var el = byId('nav-origin'); if (!el) return;
      el.innerHTML = originIsGps
        ? '📍 Origin / 起点：your current location (' + origin.lng.toFixed(4) + ', ' + origin.lat.toFixed(4) + ')'
        : '📍 Origin / 起点：Beijing city center (default) · tap “Use my location”.';
    }

    function fillDropdown() {
      var sel = byId('nav-hospital'); if (!sel) return;
      sel.innerHTML = '';
      list.forEach(function (h, i) {
        if (typeof h.lng !== 'number' || typeof h.lat !== 'number') return;
        var o = document.createElement('option'); o.value = String(i);
        o.textContent = (h.name_zh || h.name || 'Hospital') + (h.name && h.name_zh && h.name !== h.name_zh ? ' / ' + h.name : '');
        sel.appendChild(o);
      });
      syncDropdown();
    }
    function syncDropdown() {
      var sel = byId('nav-hospital'); if (!sel || !target) return;
      var best = -1, bestD = 9e9;
      list.forEach(function (h, i) {
        var d = Math.abs((h.lng || 0) - target.lng) + Math.abs((h.lat || 0) - target.lat);
        if (d < bestD) { bestD = d; best = i; }
      });
      if (best >= 0 && bestD < 0.01) sel.value = String(best);
    }

    function loadList() {
      list = FALLBACK_HOSPITALS.slice(); fillDropdown();
      if (!target && list[0]) target = { lng: list[0].lng, lat: list[0].lat, name: list[0].name_zh || list[0].name };
      api('/api/hospitals?limit=20').then(function (d) {
        var valid = (d && d.hospitals || []).filter(function (h) { return typeof h.lng === 'number' && typeof h.lat === 'number'; });
        if (valid.length) { list = valid; fillDropdown(); if (!target) { target = { lng: list[0].lng, lat: list[0].lat, name: list[0].name_zh || list[0].name }; } draw(); }
      }).catch(function () {});
    }

    function ensureAmap() {
      if (ready) { draw(); return; }
      if (confFetched) { return; }
      confFetched = true;
      if (!API) { mapUnavailable('Backend not configured.'); draw(); return; }
      api('/api/amap/config').then(function (cfg) {
        jsKey = cfg.js_key || ''; secCode = cfg.security_code || ''; hasSec = !!cfg.has_security_code;
        if (!jsKey) { mapUnavailable('AMap JS key not configured.'); draw(); return; }
        if (secCode) { window._AMapSecurityConfig = { securityJsCode: secCode }; }
        var s = document.createElement('script');
        s.src = 'https://webapi.amap.com/maps?v=2.0&key=' + encodeURIComponent(jsKey) +
                '&plugin=AMap.Walking,AMap.Driving,AMap.Transfer,AMap.Geolocation,AMap.Scale,AMap.ToolBar';
        s.onload = function () { if (window.AMap) { ready = true; draw(); } else { mapUnavailable(); draw(); } };
        s.onerror = function () { mapUnavailable('Failed to load AMap.'); draw(); };
        document.head.appendChild(s);
      }).catch(function () { mapUnavailable(); draw(); });
    }

    function mapUnavailable(msg) {
      var m = byId('nav-map'); if (!m) return;
      m.innerHTML = '<div class="map-empty"><div class="big">🧭</div><div>' + esc(msg || 'Live map unavailable.') +
        '</div><div class="small muted">Use the buttons below to open this place in a maps app. 用下方按钮在地图 App 中打开。</div></div>';
    }

    function markerPin(color, label) {
      var d = document.createElement('div');
      d.style.cssText = 'transform:translate(-50%,-100%);font:600 11px var(--font-sans,sans-serif);';
      d.innerHTML = '<div style="background:' + color + ';color:#fff;padding:3px 9px;border-radius:11px;box-shadow:0 4px 10px rgba(0,0,0,.25);white-space:nowrap;">' + esc(label) + '</div>' +
        '<div style="width:2px;height:9px;background:' + color + ';margin:0 auto;"></div>';
      return d;
    }

    function draw() {
      renderHandoff();
      if (!ready || !window.AMap) { textFallback(); return; }
      var m = byId('nav-map'); if (!m) return;
      if (m.querySelector('.map-empty')) m.innerHTML = '';
      if (!map) {
        map = new AMap.Map(m, { zoom: 12, center: [origin.lng, origin.lat], viewMode: '2D', mapStyle: 'amap://styles/whitesmoke' });
        try { map.addControl(new AMap.Scale()); map.addControl(new AMap.ToolBar({ position: 'RB' })); } catch (e) {}
      }
      map.clearMap();
      new AMap.Marker({ position: [origin.lng, origin.lat], map: map, content: markerPin('#2F7D6E', 'You'), offset: new AMap.Pixel(0, 0) });
      if (target) {
        new AMap.Marker({ position: [target.lng, target.lat], map: map, content: markerPin('#D97757', trim(target.name, 14)), offset: new AMap.Pixel(0, 0) });
        plan();
        try { map.setFitView(); } catch (e) {}
      } else {
        map.setZoomAndCenter(12, [origin.lng, origin.lat]);
      }
      setOriginText();
    }

    function plan() {
      if (!target || !window.AMap || !map) return;
      var routeBox = byId('nav-route'); if (routeBox) routeBox.innerHTML = '<div class="muted small"><span class="spinner"></span> Planning route…</div>';
      var ctor = mode === 'driving' ? 'Driving' : mode === 'transit' ? 'Transfer' : 'Walking';
      var go = function () {
        var planner;
        try {
          var opts = { map: map, hideMarkers: true, autoFitView: true };
          if (mode === 'transit') planner = new AMap.Transfer({ map: map, city: city, hideMarkers: true, autoFitView: true });
          else planner = new AMap[ctor](opts);
        } catch (e) { textFallback('Route plugin unavailable.'); return; }
        planner.search([origin.lng, origin.lat], [target.lng, target.lat], function (status, result) {
          if (status !== 'complete') { textFallback(); return; }
          parseRoute(result);
        });
      };
      if (AMap[ctor]) go(); else AMap.plugin(['AMap.' + ctor], go);
    }

    function parseRoute(result) {
      var distance = 0, time = 0, steps = [];
      try {
        if (mode === 'transit' && result.plans && result.plans.length) {
          var pl = result.plans[0]; distance = pl.distance || 0; time = pl.time || 0;
          (pl.segments || []).forEach(function (seg) {
            if (seg.transit_mode === 'WALK' && seg.transit) { steps.push({ t: 'Walk ' + Math.round((seg.transit.distance || 0)) + ' m', d: seg.transit.distance || 0 }); }
            else if (seg.transit && seg.transit.lines && seg.transit.lines.length) { steps.push({ t: seg.transit.lines[0].name, d: seg.transit.distance || 0 }); }
            else if (seg.instruction) steps.push({ t: seg.instruction, d: 0 });
          });
        } else if (result.routes && result.routes.length) {
          var rt = result.routes[0]; distance = rt.distance || 0; time = rt.time || 0;
          (rt.steps || []).forEach(function (s) { steps.push({ t: s.instruction || s.start_road || 'Continue', d: s.distance || 0 }); });
        }
      } catch (e) {}
      renderSummary(distance, time, false);
      renderSteps(steps);
    }

    function textFallback(note) {
      var km = haversineKm(origin, target);
      var speed = mode === 'driving' ? 30 : mode === 'transit' ? 18 : 4.8;
      var min = km != null ? Math.max(1, Math.round(km / speed * 60)) : 0;
      renderSummary(km != null ? km * 1000 : 0, min * 60, true);
      var box = byId('nav-route');
      if (box) box.innerHTML = '<div class="empty-state">' + (note ? esc(note) + '<br>' : '') +
        'Turn-by-turn needs the AMap security key. Distance/time are straight-line estimates — use the buttons above to navigate in a maps app.<br><span class="muted small">配置高德安全密钥后即可在页面内显示真实路线与转向步骤。</span></div>';
    }

    function renderSummary(distM, durSec, estimated) {
      var box = byId('nav-summary'); if (!box) return;
      var km = (distM / 1000), min = Math.max(1, Math.round(durSec / 60));
      var modeTxt = mode === 'driving' ? 'Driving 驾车' : mode === 'transit' ? 'Transit 公交' : 'Walking 步行';
      box.innerHTML =
        '<div class="nav-stat"><div class="k">' + (estimated ? 'Straight-line 直线' : 'Distance 距离') + '</div><div class="v">' + km.toFixed(2) + '<span class="unit"> km</span></div></div>' +
        '<div class="nav-stat"><div class="k">' + (estimated ? 'Est. time 估算' : 'Duration 用时') + '</div><div class="v">' + min + '<span class="unit"> min</span></div></div>' +
        '<div class="nav-stat"><div class="k">Mode 方式</div><div class="v" style="font-size:18px;">' + modeTxt + '</div></div>';
    }

    function renderSteps(steps) {
      var box = byId('nav-route'); if (!box) return;
      if (!steps || !steps.length) { box.innerHTML = ''; return; }
      var rows = steps.slice(0, 24).map(function (s, i) {
        var dist = s.d ? (s.d > 1000 ? (s.d / 1000).toFixed(1) + ' km' : Math.round(s.d) + ' m') : '';
        return '<div class="step-item"><div class="step-pin">' + (i + 1) + '</div><div class="step-body"><div class="step-instruction">' + esc(s.t) + '</div>' + (dist ? '<div class="step-dist">' + dist + '</div>' : '') + '</div></div>';
      }).join('');
      box.innerHTML = '<h4>🧭 Turn-by-turn / 转向步骤</h4>' + rows +
        '<div class="step-item is-endpoint"><div class="step-pin">★</div><div class="step-body"><div class="step-instruction">Arrive at ' + esc(target ? target.name : 'destination') + '</div></div></div>';
    }

    function renderHandoff() {
      var box = byId('nav-handoff'); if (!box || !target) { if (box) box.innerHTML = ''; return; }
      var lng = target.lng, lat = target.lat, name = encodeURIComponent(target.name || 'Hospital');
      var links = [
        { t: 'Apple', u: 'https://maps.apple.com/?daddr=' + lat + ',' + lng + '&q=' + name },
        { t: 'Google', u: 'https://www.google.com/maps/dir/?api=1&destination=' + lat + ',' + lng },
        { t: '高德 AMap', u: 'https://uri.amap.com/navigation?to=' + lng + ',' + lat + ',' + name + '&mode=' + (mode === 'driving' ? 'car' : mode === 'transit' ? 'bus' : 'walk') + '&coordinate=gaode' },
        { t: '百度 Baidu', u: 'https://api.map.baidu.com/direction?destination=' + lat + ',' + lng + '&mode=' + (mode === 'driving' ? 'driving' : mode === 'transit' ? 'transit' : 'walking') + '&output=html' }
      ];
      box.innerHTML = '<span class="label">Open in 用地图App打开：</span>' + links.map(function (l) {
        return '<a class="handoff" href="' + l.u + '" target="_blank" rel="noopener">🧭 ' + esc(l.t) + '</a>';
      }).join('');
    }

    // public
    return {
      enter: function () {
        if (!inited) {
          inited = true;
          on(byId('nav-hospital'), 'change', function () { var h = list[parseInt(this.value, 10)]; if (h) { target = { lng: h.lng, lat: h.lat, name: h.name_zh || h.name }; draw(); } });
          on(byId('nav-mode'), 'change', function () { mode = this.value; draw(); });
          on(byId('nav-locate'), 'click', function () {
            var b = this; b.disabled = true; b.textContent = '📍 Locating…';
            getLocation(function () { b.disabled = false; b.textContent = '📍 Location set'; toast('Using your location', 'ok'); },
              function (m) { b.disabled = false; b.textContent = '📍 Use my location'; toast('Location: ' + m, 'err'); });
          });
          loadList(); ensureAmap(); setOriginText();
        } else { draw(); }
      },
      setTarget: function (lng, lat, name) {
        target = { lng: +lng, lat: +lat, name: name || 'Hospital' };
        if (!inited) { this.enter(); } else { syncDropdown(); ensureAmap(); draw(); }
      },
      setOriginFromGps: function (gps) {
        var apply = function (lng, lat) { origin = { lng: lng, lat: lat }; originIsGps = true; setOriginText(); draw(); };
        if (window.AMap && AMap.convertFrom) {
          try { AMap.convertFrom([gps.lng, gps.lat], 'gps', function (st, res) {
            if (st === 'complete' && res.locations && res.locations.length) { var p = res.locations[0]; apply(p.lng, p.lat); }
            else apply(gps.lng, gps.lat);
          }); return; } catch (e) {}
        }
        apply(gps.lng, gps.lat);
      }
    };
  })();

  /* ============================================================
     6) Medication
     ============================================================ */
  var Med = (function () {
    var lib = [];
    function tagFor(m) { return m.rx_required ? '<span class="pill-tag pill-rx">Rx 处方</span>' : '<span class="pill-tag pill-otc">OTC 非处方</span>'; }
    function showInfo(m) {
      var box = byId('med-info'); if (!box) return;
      if (!m) { box.innerHTML = '<div class="empty-state">Pick a medication to see details.</div>'; return; }
      var ul = function (arr) { return (arr && arr.length) ? '<ul>' + arr.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>' : '<p class="muted small">—</p>'; };
      box.innerHTML = '<div class="drug-info"><div class="drug-name">' + esc(m.name) + tagFor(m) + '</div>' +
        '<div class="muted small">' + esc(m.name_zh || '') + ' · ' + esc(m.category || '') + (m.price_cny ? ' · ¥' + m.price_cny : '') + '</div>' +
        '<h5>Dosage 用法用量</h5><p>' + esc(m.dosage || m.dosage_zh || '—') + '</p>' +
        '<h5>Warnings 警告</h5>' + ul(m.warnings && m.warnings.length ? m.warnings : m.warnings_zh) +
        '<h5>Side effects 副作用</h5>' + ul(m.side_effects) + '</div>';
    }
    function loadRecords() {
      var box = byId('med-list'); if (!box) return;
      if (!token) { box.innerHTML = '<div class="empty-state">Sign in to save medications and reminders.</div>'; return; }
      api('/api/medications/record', { auth: true }).then(function (rows) {
        if (!rows || !rows.length) { box.innerHTML = '<div class="empty-state">No medications saved yet.</div>'; return; }
        box.innerHTML = rows.map(function (r) {
          var times = (r.reminder_times || '').split(',').map(function (t) { return t.trim(); }).filter(Boolean);
          return '<div class="list-item"><div><strong>' + esc(r.custom_name || r.medication_key) + '</strong>' +
            (r.dosage ? '<div class="meta">' + esc(r.dosage) + '</div>' : '') +
            (r.notes ? '<div class="meta">' + esc(r.notes) + '</div>' : '') +
            (times.length ? '<div class="when">' + times.map(function (t) { return '<span class="time-pill">⏰ ' + esc(t) + '</span>'; }).join('') + '</div>' : '') +
            '</div><button class="btn btn-danger btn-sm js-del" data-id="' + r.id + '">Remove</button></div>';
        }).join('');
        qsa('.js-del', box).forEach(function (b) {
          on(b, 'click', function () {
            api('/api/medications/record/' + b.getAttribute('data-id'), { method: 'DELETE', auth: true })
              .then(function () { toast('Removed', 'ok'); loadRecords(); }).catch(function (e) { toast(e.message, 'err'); });
          });
        });
      }).catch(function () { box.innerHTML = '<div class="empty-state">Could not load your list.</div>'; });
    }
    return {
      init: function () {
        var sel = byId('med-picker');
        api('/api/medications').then(function (d) {
          lib = (d && d.medications) || [];
          if (sel) {
            sel.innerHTML = '<option value="">— choose —</option>' + lib.map(function (m) { return '<option value="' + esc(m.key) + '">' + esc(m.name) + ' / ' + esc(m.name_zh || '') + '</option>'; }).join('');
            on(sel, 'change', function () { showInfo(lib.filter(function (m) { return m.key === sel.value; })[0]); });
          }
        }).catch(function () {});
        on(byId('btn-add-med'), 'click', function () {
          if (!token) { openAuth('login'); toast('Please log in first', 'warn'); return; }
          var key = (byId('med-picker') || {}).value || '';
          if (!key) { toast('Pick a medication from the library', 'warn'); return; }
          var body = {
            medication_key: key, custom_name: (byId('med-custom') || {}).value || '',
            dosage: (byId('med-dosage') || {}).value || '', reminder_times: (byId('med-times') || {}).value || '',
            notes: (byId('med-notes') || {}).value || ''
          };
          api('/api/medications/record', { method: 'POST', body: body, auth: true }).then(function () {
            toast('Saved to your list', 'ok');
            ['med-custom', 'med-dosage', 'med-times', 'med-notes'].forEach(function (id) { var el = byId(id); if (el) el.value = ''; });
            loadRecords();
          }).catch(function (e) { toast(e.message, 'err'); });
        });
        loadRecords();
      },
      reload: loadRecords
    };
  })();

  /* ============================================================
     7) Account — profile, privacy, feedback
     ============================================================ */
  var Account = {
    render: function () {
      var box = byId('profile-body'); if (!box) return;
      if (!currentUser) {
        box.innerHTML = '<p class="muted">Log in to see your profile, saved translations and medication.</p><button class="btn btn-primary" id="btn-profile-login">Log in / Register</button>';
        on(byId('btn-profile-login'), 'click', function () { openAuth('login'); });
        return;
      }
      var u = currentUser;
      var since = u.created_at ? new Date(u.created_at).toLocaleDateString() : '—';
      box.innerHTML =
        '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">' +
        '<div class="logo" style="width:54px;height:54px;font-size:20px;border-radius:16px;">' + esc((u.full_name || u.email || '?').slice(0, 1).toUpperCase()) + '</div>' +
        '<div><div style="font-family:var(--font-serif);font-size:22px;">' + esc(u.full_name || u.email) + '</div>' +
        '<div class="muted small">' + esc(u.email) + ' · ' + esc(u.role || 'patient') + '</div></div></div>' +
        '<div class="chips" style="margin-top:16px;">' +
        '<span class="chip static">🌐 ' + esc(u.language || 'en') + '</span>' +
        (u.country ? '<span class="chip static">📍 ' + esc(u.country) + '</span>' : '') +
        '<span class="chip static">Member since ' + esc(since) + '</span></div>' +
        '<div class="row mt"><button class="btn btn-ghost btn-sm" id="btn-acc-logout">Sign out</button></div>';
      on(byId('btn-acc-logout'), 'click', doLogout);
    }
  };

  on(byId('btn-export'), 'click', function () {
    if (!token) { openAuth('login'); return; }
    var box = byId('export-box');
    api('/api/privacy/export', { auth: true }).then(function (d) {
      if (box) { box.classList.remove('hidden'); box.textContent = JSON.stringify(d, null, 2); }
      toast('Exported below', 'ok');
    }).catch(function (e) { toast(e.message, 'err'); });
  });
  on(byId('btn-wipe'), 'click', function () {
    if (!token) { openAuth('login'); return; }
    if (!confirm('Delete ALL your translations, medications, triage and feedback? Your login is kept. This cannot be undone.')) return;
    api('/api/privacy/wipe', { method: 'POST', auth: true }).then(function () {
      toast('All personal records deleted', 'ok');
      var box = byId('export-box'); if (box) { box.classList.add('hidden'); box.textContent = ''; }
      loadMyTranslations(); Med.reload();
    }).catch(function (e) { toast(e.message, 'err'); });
  });
  on(byId('btn-send-feedback'), 'click', function () {
    var content = (byId('fb-content') || {}).value || '';
    if (content.trim().length < 2) { toast('Please write a message', 'warn'); return; }
    var body = { category: (byId('fb-category') || {}).value || 'other', rating: parseInt((byId('fb-rating') || {}).value, 10) || 5, comment: content.trim() };
    api('/api/feedback', { method: 'POST', body: body, auth: !!token }).then(function () {
      var st = byId('fb-status'); if (st) st.textContent = 'Thank you! Your feedback was received.';
      if (byId('fb-content')) byId('fb-content').value = ''; toast('Feedback sent', 'ok');
    }).catch(function (e) { toast(e.message, 'err'); });
  });

  /* ============================================================
     8) Auth modal
     ============================================================ */
  function openAuth(tab) {
    var m = byId('auth-modal'); if (!m) return; m.classList.remove('hidden');
    switchTab(tab || 'login');
  }
  function closeAuth() { var m = byId('auth-modal'); if (m) m.classList.add('hidden'); var am = byId('auth-message'); if (am) am.textContent = ''; }
  function switchTab(tab) {
    qsa('.modal-tabs .tab').forEach(function (b) { b.classList.toggle('active', b.dataset.tab === tab); });
    var lp = byId('tab-login'), rp = byId('tab-register');
    if (lp) lp.classList.toggle('hidden', tab !== 'login');
    if (rp) rp.classList.toggle('hidden', tab !== 'register');
  }
  qsa('.modal-tabs .tab').forEach(function (b) { on(b, 'click', function () { switchTab(b.dataset.tab); }); });
  on(byId('auth-modal'), 'click', function (e) { if (e.target === this) closeAuth(); });
  on(byId('btn-login'), 'click', function () { openAuth('login'); });
  on(byId('btn-logout'), 'click', doLogout);

  function doLogout() { clearSession(); toast('Signed out', 'ok'); setActive('home'); }

  on(byId('btn-do-login'), 'click', function () {
    var email = (byId('login-email') || {}).value || '', pw = (byId('login-password') || {}).value || '';
    var msg = byId('auth-message'); if (msg) msg.textContent = 'Signing in…';
    api('/api/auth/login', { method: 'POST', body: { email: email.trim(), password: pw } }).then(function (d) {
      setSession(d.access_token, d.user); closeAuth(); toast('Welcome back, ' + ((d.user && d.user.full_name) || 'friend'), 'ok'); afterAuth();
    }).catch(function (e) { if (msg) msg.textContent = e.message || 'Login failed'; });
  });
  on(byId('btn-do-register'), 'click', function () {
    var body = {
      full_name: (byId('reg-name') || {}).value || '', email: ((byId('reg-email') || {}).value || '').trim(),
      password: (byId('reg-password') || {}).value || '', language: (byId('reg-language') || {}).value || 'en',
      country: (byId('reg-country') || {}).value || ''
    };
    var msg = byId('auth-message'); if (msg) msg.textContent = 'Creating account…';
    if (!body.full_name) { if (msg) msg.textContent = 'Please enter your name'; return; }
    api('/api/auth/register', { method: 'POST', body: body }).then(function (d) {
      setSession(d.access_token, d.user); closeAuth(); toast('Account created — welcome!', 'ok'); afterAuth();
    }).catch(function (e) { if (msg) msg.textContent = e.message || 'Registration failed'; });
  });

  function afterAuth() { loadMyTranslations(); Med.reload(); Account.render(); }

  function refreshAuthUI() {
    var loginBtn = byId('btn-login'), chip = byId('user-chip'), email = byId('user-email');
    if (currentUser) {
      if (loginBtn) loginBtn.classList.add('hidden');
      if (chip) chip.classList.remove('hidden');
      if (email) email.textContent = currentUser.full_name || currentUser.email;
    } else {
      if (loginBtn) loginBtn.classList.remove('hidden');
      if (chip) chip.classList.add('hidden');
    }
  }

  /* ============================================================
     9) Boot
     ============================================================ */
  refreshAuthUI();
  setActive('home');
  loadStats();
  revealScan();
  console.log('TransMed UI ready · API:', API || '(same origin)');
})();
'''

# ---------------------------------------------------------------------------
# 写出到两份前端目录：transmed_web/（后端服务）与 docs/（GitHub Pages）
# ---------------------------------------------------------------------------
_root = os.path.dirname(os.path.abspath(__file__))
_targets = [
    os.path.join(_root, 'transmed_web', 'app.js'),
    os.path.join(_root, 'docs', 'app.js'),
]
for _path in _targets:
    os.makedirs(os.path.dirname(_path), exist_ok=True)
    with open(_path, 'w', encoding='utf-8') as f:
        f.write(JS)
    print('wrote', os.path.relpath(_path, _root), '(%d bytes)' % len(JS.encode('utf-8')))
