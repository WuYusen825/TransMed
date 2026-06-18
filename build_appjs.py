#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build app.js - simple approach: write directly"""
import os

JS = r'''/* TransMed frontend logic */
(function() {
  'use strict';

  // --- DOM helpers ---
  var byId = function(id) { return document.getElementById(id); };
  var qs = function(sel) { return document.querySelector(sel); };
  var qsa = function(sel) { return Array.from(document.querySelectorAll(sel)); };
  var bindClick = function(el, handler) { if (el) el.addEventListener('click', handler); };
  var bindChange = function(el, handler) { if (el) el.addEventListener('change', handler); };

  // --- Fallback data for offline / GitHub Pages ---
  var FALLBACK_HOSPITALS = [
    { id: 'pumch', name: 'Peking Union Medical College Hospital', name_zh: '北京协和医院', address: '1 Shuaifuyuan, Dongcheng District, Beijing', phone: '+86 10 6915 6114', hours: '24/7 Emergency · Outpatient 8:00-17:00', rating: 4.8, wait_minutes: 45, distance_km: 2.3, lng: 116.4165, lat: 39.9094, specialties: ['General Medicine', 'Cardiology', 'Neurology', 'Endocrinology', 'Rheumatology'], insurance: ['Self-pay', 'Social insurance', 'Bupa', 'Ping An'], languages: ['English', 'Japanese', 'Mandarin'] },
    { id: 'bjh', name: 'Beijing Hospital', name_zh: '北京医院', address: '1 Dongdan Dahua Road, Dongcheng District, Beijing', phone: '+86 10 8513 2266', hours: '24/7 Emergency', rating: 4.6, wait_minutes: 30, distance_km: 3.1, lng: 116.4151, lat: 39.9038, specialties: ['Geriatrics', 'Cardiology', 'Neurology', 'Oncology'], insurance: ['Self-pay', 'Social insurance'], languages: ['Mandarin', 'English'] },
    { id: 'tongren', name: 'Beijing Tongren Hospital', name_zh: '北京同仁医院', address: '1 Dongjiaominxiang, Dongcheng District, Beijing', phone: '+86 10 5826 9988', hours: '24/7 Emergency · OPD 8:00-17:00', rating: 4.7, wait_minutes: 35, distance_km: 2.8, lng: 116.4172, lat: 39.9027, specialties: ['ENT', 'Ophthalmology', 'General Medicine'], insurance: ['Self-pay', 'Social insurance', 'Cigna'], languages: ['Mandarin', 'English'] },
    { id: 'ufh', name: 'United Family Hospital', name_zh: '和睦家医院', address: '2 Jiangtai Road, Chaoyang District, Beijing', phone: '+86 10 5927 7000', hours: '24/7 Emergency and outpatient', rating: 4.9, wait_minutes: 15, distance_km: 7.2, lng: 116.4677, lat: 39.9754, specialties: ['Family Medicine', 'Pediatrics', 'Emergency', 'OB/GYN', 'Dental'], insurance: ['Bupa', 'Cigna', 'Allianz', 'Self-pay', 'International insurance'], languages: ['English', 'Mandarin', 'Japanese', 'Korean', 'French', 'German'] },
    { id: 'cmuh', name: 'China-Japan Friendship Hospital', name_zh: '中日友好医院', address: '2 Yinghua East Street, Chaoyang District, Beijing', phone: '+86 10 8420 5566', hours: '24/7 Emergency', rating: 4.5, wait_minutes: 40, distance_km: 6.8, lng: 116.4294, lat: 39.9783, specialties: ['Respiratory', 'Cardiology', 'Orthopedics', 'Traditional Chinese Medicine'], insurance: ['Self-pay', 'Social insurance'], languages: ['Mandarin', 'Japanese', 'English'] },
    { id: '301', name: '301 Hospital (PLA General Hospital)', name_zh: '解放军总医院', address: '28 Fuxing Road, Haidian District, Beijing', phone: '+86 10 6693 7329', hours: '24/7 Emergency · OPD 8:00-17:00', rating: 4.7, wait_minutes: 50, distance_km: 8.5, lng: 116.2875, lat: 39.9067, specialties: ['Trauma Surgery', 'Oncology', 'Cardiology', 'Neurology', 'Orthopedics'], insurance: ['Self-pay', 'Social insurance'], languages: ['Mandarin', 'English'] },
    { id: 'bch', name: 'Beijing Children\'s Hospital', name_zh: '北京儿童医院', address: '56 Nanlishi Road, Xicheng District, Beijing', phone: '+86 10 5961 6161', hours: '24/7 Emergency', rating: 4.6, wait_minutes: 60, distance_km: 5.4, lng: 116.3488, lat: 39.9167, specialties: ['Pediatrics', 'Pediatric Surgery', 'Pediatric Neurology'], insurance: ['Self-pay', 'Social insurance'], languages: ['Mandarin', 'English'] },
    { id: 'hk', name: 'Hong Kong International Medical Clinic', name_zh: '香港国际医疗中心', address: 'Central, Hong Kong', phone: '+852 2523 8000', hours: 'Mon-Sun 9:00-21:00', rating: 4.8, wait_minutes: 20, distance_km: 1960.0, lng: 114.1586, lat: 22.2793, specialties: ['Family Medicine', 'Emergency', 'Travel Medicine'], insurance: ['International insurance', 'Self-pay'], languages: ['English', 'Cantonese', 'Mandarin'] }
  ];

  var SYMPTOM_CHIPS = ['headache', 'chest pain', 'cough', 'fever', 'stomach pain', 'back pain', 'skin rash', 'dizziness', 'fatigue', 'sore throat', 'shortness of breath', 'nausea', 'joint pain', 'anxiety'];

  // --- API base detection ---
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
  function resetTranslateUI() {
    var cv = byId('conf-value'); if (cv) cv.textContent = '\u2014';
    var rv = byId('risk-value'); if (rv) rv.textContent = '\u2014';
    var cf = byId('conf-fill'); if (cf) cf.style.width = '0%';
    var cb = byId('confidence-bar'); if (cb) cb.classList.add('hidden');
    var rb = byId('btn-confirm-risk'); if (rb) rb.classList.add('hidden');
    var matched = byId('matched-terms'); if (matched) matched.innerHTML = '';
  }
  resetTranslateUI();

  bindClick(byId('btn-translate'), function() {
    var txt = byId('src-text') ? byId('src-text').value.trim() : '';
    var srcLang = byId('src-lang') ? byId('src-lang').value : 'en';
    var tgtLang = byId('tgt-lang') ? byId('tgt-lang').value : 'zh';
    var btn = byId('btn-translate');
    var out = byId('tgt-text');
    if (!txt || !out) return;
    if (btn) { btn.disabled = true; btn.textContent = 'Translating...'; }
    resetTranslateUI();

    var done = function() { if (btn) { btn.disabled = false; btn.textContent = 'Translate'; } };

    var url = API + '/api/translate';
    var timeoutMs = 8000;
    var timedOut = false;
    var controller = null;
    if (window.AbortController) { controller = new AbortController(); }
    var timer = setTimeout(function() { timedOut = true; if (controller) controller.abort(); }, timeoutMs);

    var doTranslate = function() {
      var opts = { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text: txt, source_lang: srcLang, target_lang: tgtLang, medical_context: true}) };
      if (controller) opts.signal = controller.signal;
      return fetch(url, opts).then(function(r) { return r.json(); });
    };

    var onSuccess = function(data) {
      if (out) out.textContent = data.translated_text || '(no translation)';
      var c = typeof data.confidence === 'number' ? Math.round(data.confidence * 100) : 80;
      if (c < 0) c = 0; if (c > 100) c = 100;
      var conf = byId('confidence-bar'); if (conf) conf.classList.remove('hidden');
      var cv = byId('conf-value'); if (cv) cv.textContent = c;
      var cf = byId('conf-fill'); if (cf) cf.style.width = c + '%';
      var rv = byId('risk-value'); if (rv) rv.textContent = data.risk_level || 'low';
      var rb = byId('btn-confirm-risk'); if (rb) rb.classList.toggle('hidden', data.risk_level !== 'high');
      var ca = byId('conf-advice'); if (ca) ca.textContent = data.safety_advice || '';
      var matched = byId('matched-terms');
      if (matched) {
        var items = (data.medical_terms || []).map(function(t) {
          var def = t.definition ? ' \u00b7 ' + t.definition : '';
          return '<span class="chip">' + t.term + def + '</span>';
        }).join('');
        matched.innerHTML = items ? '<div class="muted small" style="margin-bottom:6px;">Medical terms:</div>' + items : '';
      }
    };

    var onError = function(msg) {
      if (out) out.textContent = 'Error: ' + msg;
      // Also show a fallback offline translation (simple keyword translation)
      if (tgtLang === 'zh') {
        var simpleMap = {
          'headache': '\u5934\u75db',
          'fever': '\u53d1\u70ed',
          'cough': '\u54b3\u55fd',
          'stomach': '\u80c3\u75db',
          'nausea': '\u6076\u5fc3',
          'chest pain': '\u80f8\u75db',
          'back pain': '\u80cc\u75db',
          'dizziness': '\u7729\u6655',
          'skin rash': '\u76ae\u75b9',
          'fatigue': '\u6d88\u75e5',
          'sore throat': '\u7163\u55d3',
          'shortness of breath': '\u547c\u5438\u56f0\u96be',
          'joint pain': '\u5173\u8282\u75db',
          'anxiety': '\u7126\u8651'
        };
        var lowerTxt = txt.toLowerCase();
        var translated = txt;
        var matched = false;
        for (var key in simpleMap) {
          if (lowerTxt.indexOf(key) !== -1) {
            translated = translated.replace(new RegExp(key, 'gi'), simpleMap[key]);
            matched = true;
          }
        }
        if (matched && out) out.textContent = translated + ' (offline demo translation)';
      }
      // Show confidence info even on error
      var conf = byId('confidence-bar'); if (conf) conf.classList.remove('hidden');
      var cv = byId('conf-value'); if (cv) cv.textContent = '50';
      var cf = byId('conf-fill'); if (cf) cf.style.width = '50%';
      var rv = byId('risk-value'); if (rv) rv.textContent = 'low';
    };

    doTranslate().then(function(data) {
      clearTimeout(timer);
      onSuccess(data);
      done();
    }).catch(function(err) {
      clearTimeout(timer);
      if (timedOut) onError('Request timed out');
      else onError(err.message || 'Network error');
      done();
    });
  });

  bindClick(byId('swap-lang'), function() {
    var src = byId('src-lang'); var tgt = byId('tgt-lang');
    if (src && tgt) { var v = src.value; src.value = tgt.value; tgt.value = v; }
  });

  // --- Language selectors ---
  (function initLangSelectors() {
    var srcSel = byId('src-lang');
    var tgtSel = byId('tgt-lang');
    var langs = [
      { code: 'en', name: 'English' },
      { code: 'zh', name: '\u4e2d\u6587' },
      { code: 'ja', name: '\u65e5\u672c\u8a9e' },
      { code: 'ko', name: '\ud55c\uad6d\uc5b4' },
      { code: 'fr', name: 'Fran\u00e7ais' },
      { code: 'de', name: 'Deutsch' },
      { code: 'es', name: 'Espa\u00f1ol' },
      { code: 'it', name: 'Italiano' },
      { code: 'ru', name: '\u0420\u0443\u0441\u0441\u043a\u0438\u0439' },
      { code: 'ar', name: '\u0627\u0644\u0639\u0631\u0628\u064a\u0629' },
      { code: 'hi', name: '\u0939\u093f\u0928\u094d\u0926\u0940' },
      { code: 'pt', name: 'Portugu\u00eas' }
    ];
    [srcSel, tgtSel].forEach(function(sel, idx) {
      if (!sel) return;
      sel.innerHTML = '';
      langs.forEach(function(l) {
        var opt = document.createElement('option');
        opt.value = l.code;
        opt.textContent = l.name + ' \u00b7 ' + l.code;
        sel.appendChild(opt);
      });
      sel.value = idx === 0 ? 'en' : 'zh';
    });
  })();

  // --- Symptom chips ---
  (function buildSymptomChips() {
    var symptomBox = byId('symptom-chips');
    if (!symptomBox) return;
    SYMPTOM_CHIPS.forEach(function(txt) {
      var el = document.createElement('button');
      el.className = 'chip';
      el.textContent = txt;
      el.type = 'button';
      bindClick(el, function() {
        var t = byId('src-text');
        if (t) t.value = 'I have ' + txt + '.';
      });
      symptomBox.appendChild(el);
    });
  })();

  // --- Triage & hospitals ---
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
        var zhPart = deptZh ? ' \u00b7 ' + deptZh : '';
        el.innerHTML = '<div><span class="triage-label">' + label + '</span></div>' +
          '<strong>Department:</strong> ' + dept + zhPart + '<br>' +
          (data.recommendation_en || 'Please consult a doctor.') + matched;
      }).catch(function(e) {
        if (el) {
          el.classList.remove('hidden');
          el.textContent = 'Triage service unavailable (back-end not reachable). Please visit your nearest hospital.';
        }
      });
    loadHospitals();
  });

  function loadHospitals() {
    var container = byId('hospital-list');
    if (!container) return;
    fetch(API + '/api/hospitals?limit=20')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var list = (data && data.hospitals) ? data.hospitals : [];
        renderHospitals(list);
      }).catch(function(e) {
        // Fallback to local data
        renderHospitals(FALLBACK_HOSPITALS);
      });
  }

  function renderHospitals(list) {
    var container = byId('hospital-list');
    if (!container) return;
    if (!Array.isArray(list) || !list.length) { container.innerHTML = '<p class="muted">No hospitals found.</p>'; return; }
    container.innerHTML = list.map(function(h) {
      var name = h.name || '';
      var nameZh = h.name_zh && h.name_zh !== h.name ? ' \u00b7 ' + h.name_zh : '';
      var address = h.address || '';
      var rating = typeof h.rating === 'number' ? h.rating.toFixed(1) : '\u2014';
      var wait = typeof h.wait_minutes === 'number' ? h.wait_minutes + ' min' : '\u2014';
      var dist = typeof h.distance_km === 'number' ? h.distance_km.toFixed(1) + ' km' : '\u2014';
      var specialties = (h.specialties || []).slice(0, 5).map(function(s) { return '<span class="chip">' + (typeof s === 'string' ? s : (s.name || s)) + '</span>'; }).join('');
      var insurances = (h.insurance || []).slice(0, 4).map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('');
      var languages = (h.languages || []).map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('');
      var parts = [];
      parts.push('<div class="hospital">');
      parts.push('<div class="hospital-main">');
      parts.push('<div class="hospital-head"><h4>' + name + nameZh + '</h4></div>');
      parts.push('<div class="sub">Address: ' + address + '</div>');
      if (h.phone) parts.push('<div class="sub">Phone: ' + h.phone + '</div>');
      if (h.hours) parts.push('<div class="sub">Hours: ' + h.hours + '</div>');
      parts.push('<div class="hospital-meta-row"><span class="meta-item">Wait: <strong>' + wait + '</strong></span><span class="meta-item">Distance: <strong>' + dist + '</strong></span></div>');
      if (specialties) parts.push('<div class="chips"><span class="muted small">Specialties: </span>' + specialties + '</div>');
      if (insurances) parts.push('<div class="chips"><span class="muted small">Insurance: </span>' + insurances + '</div>');
      if (languages) parts.push('<div class="chips"><span class="muted small">Languages: </span>' + languages + '</div>');
      parts.push('</div>');
      parts.push('<div class="hospital-side">');
      parts.push('<div class="rating-badge"><span class="rating-num">' + rating + '</span></div>');
      var gurl = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(h.name || 'hospital');
      if (typeof h.lat === 'number' && typeof h.lng === 'number') {
        gurl = 'https://www.google.com/maps/search/?api=1&query=' + h.lat + ',' + h.lng;
      }
      parts.push('<a class="btn btn-light btn-nav" href="' + gurl + '" target="_blank" rel="noopener noreferrer">Navigate here</a>');
      parts.push('</div></div>');
      return parts.join('');
    }).join('');
  }

  // --- Navigation (outdoor) ---
  var _navOrigin = { lat: 39.9042, lng: 116.4074, label: 'Beijing (default)' };
  var _navHospitals = FALLBACK_HOSPITALS;

  function initNavigation() {
    // Try to load from API, fall back to local data
    fetch(API + '/api/hospitals?limit=20')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data && data.hospitals && data.hospitals.length) _navHospitals = data.hospitals;
        _buildNavigationUI();
      }).catch(function(e) {
        _navHospitals = FALLBACK_HOSPITALS;
        _buildNavigationUI();
      });
  }

  function _buildNavigationUI() {
    var sel = byId('nav-hospital');
    var out = byId('nav-output');
    var origin = byId('nav-origin');
    if (!sel || !out) return;

    // Populate hospital selector
    sel.innerHTML = '';
    _navHospitals.forEach(function(h, idx) {
      var opt = document.createElement('option');
      opt.value = String(idx);
      opt.textContent = h.name + (h.name_zh ? ' \u00b7 ' + h.name_zh : '');
      sel.appendChild(opt);
    });

    // Render first hospital
    _renderNavOutput(0);

    // Bind events
    bindChange(sel, function() { _renderNavOutput(parseInt(sel.value, 10)); });
    bindChange(byId('nav-mode'), function() { _renderNavOutput(parseInt(sel.value, 10)); });
    bindClick(byId('nav-locate'), function() {
      if (!navigator.geolocation) { alert('Geolocation is not available in this browser.'); return; }
      var btn = byId('nav-locate');
      if (btn) btn.textContent = 'Locating...';
      navigator.geolocation.getCurrentPosition(function(pos) {
        _navOrigin = { lat: pos.coords.latitude, lng: pos.coords.longitude, label: 'Your location' };
        if (origin) origin.textContent = '\uD83D\uDCCD ' + _navOrigin.label + ' (' + pos.coords.latitude.toFixed(4) + ', ' + pos.coords.longitude.toFixed(4) + ')';
        _renderNavOutput(parseInt(sel.value, 10));
        if (btn) btn.textContent = 'Use my location';
      }, function(err) {
        alert('Location access denied or unavailable: ' + err.message);
        if (btn) btn.textContent = 'Use my location';
      }, { timeout: 10000 });
    });
  }

  function _renderNavOutput(idx) {
    var out = byId('nav-output');
    if (!out) return;
    var h = _navHospitals[idx];
    if (!h) return;
    var modeEl = byId('nav-mode');
    var mode = modeEl ? modeEl.value : 'walking';

    var lat = typeof h.lat === 'number' ? h.lat : 39.9042;
    var lng = typeof h.lng === 'number' ? h.lng : 116.4074;

    // Build map URLs
    var gmaps = 'https://www.google.com/maps/dir/?api=1&origin=' + _navOrigin.lat + ',' + _navOrigin.lng + '&destination=' + lat + ',' + lng + '&travelmode=' + mode;
    var amap = 'https://uri.amap.com/navigation?from=' + _navOrigin.lng + ',' + _navOrigin.lat + ',Origin&to=' + lng + ',' + lat + ',' + (h.name || 'Hospital') + '&mode=' + (mode === 'transit' ? 'transit' : (mode === 'driving' ? 'car' : 'walk')) + '&src=transmed&coordinate=gaode&callnative=1';
    var apple = 'https://maps.apple.com/?daddr=' + lat + ',' + lng + '&dirflg=' + (mode === 'driving' ? 'd' : (mode === 'transit' ? 'r' : 'w'));
    var baidu = 'https://api.map.baidu.com/direction?origin=' + _navOrigin.lat + ',' + _navOrigin.lng + '&destination=' + lat + ',' + lng + '&mode=' + (mode === 'transit' ? 'transit' : (mode === 'driving' ? 'driving' : 'walking')) + '&region=Beijing&output=html&src=transmed';

    var nameZh = h.name_zh && h.name_zh !== h.name ? ' \u00b7 ' + h.name_zh : '';

    // Estimate travel time (very rough)
    var dx = (lng - _navOrigin.lng) * 111 * Math.cos((lat + _navOrigin.lat) / 2 * Math.PI / 180);
    var dy = (lat - _navOrigin.lat) * 111;
    var straightKm = Math.sqrt(dx*dx + dy*dy);
    var speed = mode === 'driving' ? 40 : (mode === 'transit' ? 25 : 5); // km/h
    var estMin = Math.max(1, Math.round(straightKm / speed * 60));

    var specialties = (h.specialties || []).slice(0, 6).map(function(s) { return '<span class="chip">' + (typeof s === 'string' ? s : (s.name || s)) + '</span>'; }).join('');
    var languages = (h.languages || []).map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('');

    out.innerHTML = '<div class="card" style="margin-bottom:14px;">' +
      '<h4 style="margin-top:0;">' + (h.name || 'Hospital') + nameZh + '</h4>' +
      (h.address ? '<div class="muted small" style="margin:4px 0;">\uD83D\uDCCD ' + h.address + '</div>' : '') +
      (h.phone ? '<div class="muted small" style="margin:4px 0;">\u260E ' + h.phone + '</div>' : '') +
      (h.hours ? '<div class="muted small" style="margin:4px 0;">\uD83D\uDD52 ' + h.hours + '</div>' : '') +
      (specialties ? '<div class="chips" style="margin-top:10px;"><span class="muted small">Specialties: </span>' + specialties + '</div>' : '') +
      (languages ? '<div class="chips" style="margin-top:8px;"><span class="muted small">Languages: </span>' + languages + '</div>' : '') +
      '<div style="margin-top:12px;"><span class="muted small">Straight-line distance: <strong>' + straightKm.toFixed(1) + ' km</strong> \u00b7 Estimated ' + mode + ' time: <strong>' + estMin + ' min</strong></span></div>' +
      '</div>' +
      '<div style="display:flex; gap:10px; flex-wrap:wrap;">' +
      '<a class="btn btn-primary" href="' + gmaps + '" target="_blank" rel="noopener noreferrer">\uD83C\uDF0D Google Maps</a>' +
      '<a class="btn btn-primary" href="' + amap + '" target="_blank" rel="noopener noreferrer">\uD83D\uDDFA\uFE0F AMap / GaoDe</a>' +
      '<a class="btn btn-primary" href="' + apple + '" target="_blank" rel="noopener noreferrer">\uD83C\uDF4E Apple Maps</a>' +
      '<a class="btn btn-primary" href="' + baidu + '" target="_blank" rel="noopener noreferrer">\uD83D\uDDFA\uFE0F Baidu Maps</a>' +
      '</div>';
  }

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
  (function initInsurance() {
    var sel = byId('ins-provider');
    if (!sel) return;
    sel.innerHTML = '';
    ['Ping An Health', 'China Life', 'AIA', 'Cigna', 'Bupa', 'Self-pay'].forEach(function(p) {
      var opt = document.createElement('option');
      opt.value = p; opt.textContent = p;
      sel.appendChild(opt);
    });
  })();

  bindClick(byId('btn-insurance'), function() {
    var sel = byId('ins-provider');
    var out = byId('ins-result');
    if (!sel || !out) return;
    var name = sel.value;
    out.innerHTML = '<div class="card"><h4 style="margin-top:0;">Checklist for ' + name + '</h4><ul style="line-height:1.8;"><li>Passport / ID</li><li>Insurance card (or policy number)</li><li>Previous medical records</li><li>Referral letter (if required by policy)</li><li>Invoice for reimbursement</li></ul></div>';
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

  // --- Init ---
  refreshAuthUI();
  setActive('home');
  console.log('TransMed UI initialized, API:', API);
})();
'''

outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transmed_web', 'app.js')
with open(outpath, 'w', encoding='utf-8') as f:
    f.write(JS)
print('Written to', outpath, '(' + str(len(JS)) + ' chars)')
