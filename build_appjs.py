#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建前端 app.js
 - 翻译：修复字段名 (source/target, translated, matched_terms)
 - 导航：内置高德 JS API 地图 + 路线（不跳外部）
"""
import os

JS = r'''/* TransMed frontend logic */
(function() {
  'use strict';

  // ===== 全局配置 =====
  var byId = function(id) { return document.getElementById(id); };
  var qs = function(sel) { return document.querySelector(sel); };
  var qsa = function(sel) { return Array.from(document.querySelectorAll(sel)); };
  var bindClick = function(el, handler) { if (el) el.addEventListener('click', handler); };
  var bindChange = function(el, handler) { if (el) el.addEventListener('change', handler); };

  // ---- 语言代码表 ----
  var LANGS = [
    { code: 'en', name: 'English' },
    { code: 'zh', name: '中文' },
    { code: 'ja', name: '日文' },
    { code: 'ko', name: '韩文' },
    { code: 'fr', name: 'Français' },
    { code: 'de', name: 'Deutsch' },
    { code: 'es', name: 'Español' },
    { code: 'it', name: 'Italiano' },
    { code: 'ru', name: 'Русский' },
    { code: 'ar', name: 'العربية' },
    { code: 'hi', name: 'हिन्दी' },
    { code: 'pt', name: 'Português' }
  ];

  // ---- API base 检测 ----
  var metaApi = qs("meta[name='api-base']");
  var API = '';
  if (metaApi) API = metaApi.getAttribute('content') || '';
  else if (location.protocol === 'file:' || location.hostname === '127.0.0.1' || location.hostname === 'localhost') {
    API = 'http://127.0.0.1:8000';
  }

  // ---- 简易离线医学词库（兜底，当 API 不可用时使用） ----
  var OFFLINE_EN2ZH = {
    'headache': '头痛', 'dizziness': '头晕', 'fever': '发热', 'cough': '咳嗽',
    'stomach pain': '胃痛', 'back pain': '背痛', 'skin rash': '皮疹',
    'fatigue': '乏力', 'sore throat': '咽痛', 'shortness of breath': '呼吸困难',
    'nausea': '恶心', 'vomiting': '呕吐', 'diarrhea': '腹泻',
    'joint pain': '关节痛', 'anxiety': '焦虑', 'chest pain': '胸痛',
    'high blood pressure': '高血压', 'palpitations': '心悸',
    'insomnia': '失眠', 'loss of appetite': '食欲减退',
    'runny nose': '流鼻涕', 'sneezing': '打喷嚏', 'itching': '瘙痒'
  };

  // ================================================================
  // 1) 视图切换
  // ================================================================
  var navLinks = qsa('.nav-link');
  var views = qsa('.view');
  var setActive = function(view) {
    views.forEach(function(v) { v.classList.toggle('active', v.dataset.view === view); });
    navLinks.forEach(function(a) { a.classList.toggle('active', a.dataset.view === view); });
    try {
      if (view === 'hospitals') loadHospitals();
      if (view === 'navigation') initNavigation();
    } catch(e) { console.warn('setActive error:', e); }
  };
  navLinks.forEach(function(a) { bindClick(a, function() { setActive(a.dataset.view); }); });
  qsa('[data-go]').forEach(function(btn) { bindClick(btn, function() { setActive(btn.dataset.go); }); });

  // ================================================================
  // 2) 翻译
  // ================================================================
  (function initLangSelectors() {
    var src = byId('src-lang');
    var tgt = byId('tgt-lang');
    [src, tgt].forEach(function(sel, idx) {
      if (!sel) return;
      sel.innerHTML = '';
      LANGS.forEach(function(l) {
        var o = document.createElement('option');
        o.value = l.code;
        o.textContent = l.name;
        sel.appendChild(o);
      });
      sel.value = idx === 0 ? 'en' : 'zh';
    });
  })();

  bindClick(byId('swap-lang'), function() {
    var src = byId('src-lang'); var tgt = byId('tgt-lang');
    if (src && tgt) { var v = src.value; src.value = tgt.value; tgt.value = v; }
  });

  bindClick(byId('btn-translate'), function() {
    var txt = byId('src-text') ? byId('src-text').value.trim() : '';
    var srcLang = byId('src-lang') ? byId('src-lang').value : 'en';
    var tgtLang = byId('tgt-lang') ? byId('tgt-lang').value : 'zh';
    var btn = byId('btn-translate');
    var out = byId('tgt-text');
    var confBox = byId('confidence-bar');
    if (!txt || !out) return;

    if (btn) { btn.disabled = true; btn.textContent = '翻译中 / Translating…'; }
    out.textContent = '';
    if (confBox) confBox.classList.add('hidden');

    var done = function() { if (btn) { btn.disabled = false; btn.textContent = '翻译 / Translate'; } };

    // ---- 1) 优先：后端真实翻译 API ----
    var tryApi = function(onOk, onErr) {
      if (!API) { onErr && onErr('no API configured'); return; }
      var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      var tid = null;
      if (controller) tid = setTimeout(function() { controller.abort(); }, 15000);
      var opts = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: txt, source: srcLang, target: tgtLang })
      };
      if (controller) opts.signal = controller.signal;
      fetch(API + '/api/translate', opts)
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (tid) clearTimeout(tid);
          if (data && (data.translated || data.translated_text)) { onOk(data); }
          else { onErr && onErr('empty response'); }
        })
        .catch(function(e) {
          if (tid) clearTimeout(tid);
          onErr && onErr(e.message || 'network');
        });
    };

    // ---- 2) 离线兜底（仅 en↔zh 的简单替换）----
    var offlineFallback = function() {
      var translated = txt;
      var matched = 0;
      var src = srcLang.toLowerCase();
      var tgt = tgtLang.toLowerCase();
      if (tgt.indexOf('zh') !== -1) {
        // en → zh
        var sortedKeys = Object.keys(OFFLINE_EN2ZH).sort(function(a, b) { return b.length - a.length; });
        sortedKeys.forEach(function(k) {
          var re = new RegExp('\\b' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
          if (re.test(translated)) { translated = translated.replace(re, OFFLINE_EN2ZH[k]); matched++; }
        });
      } else if (src.indexOf('zh') !== -1 && tgt.indexOf('en') !== -1) {
        // zh → en：简单翻转
        for (var k in OFFLINE_EN2ZH) {
          var zh = OFFLINE_EN2ZH[k];
          if (translated.indexOf(zh) !== -1) {
            translated = translated.split(zh).join(k);
            matched++;
          }
        }
      }
      var conf = matched > 0 ? Math.min(75, 35 + matched * 8) : 30;
      showResult(translated, conf, [], 'offline');
      done();
    };

    var showResult = function(translated, confidence, terms, engine, ragCtx) {
      if (!out) return;
      // ---- 关键：译文框只显示纯净译文（RAG 上下文放下方医学参考区）----
      out.textContent = translated;
      // ---- 置信度条 ----
      var cv = byId('conf-value'); if (cv) cv.textContent = String(Math.round(confidence));
      var cf = byId('conf-fill'); if (cf) cf.style.width = String(Math.min(99, Math.max(10, confidence))) + '%';
      var risk = 'low';
      if (confidence < 85 && confidence >= 65) risk = 'medium';
      else if (confidence < 65 && confidence >= 45) risk = 'high';
      else if (confidence < 45) risk = 'critical';
      var rv = byId('risk-value'); if (rv) rv.textContent = risk;
      var engineLabel = byId('engine-label');
      if (engineLabel) {
        engineLabel.textContent = 'Engine: ' + engine;
        engineLabel.classList.remove('hidden');
      }
      if (confBox) confBox.classList.remove('hidden');
      // ---- 匹配术语 ----
      var termsBox = byId('matched-terms');
      if (termsBox) {
        if (terms && terms.length) {
          termsBox.innerHTML = '<div class="muted small" style="margin-bottom:6px;">Matched medical terms:</div>' +
            terms.map(function(t) { return '<span class="chip">' + t + '</span>'; }).join('');
        } else {
          termsBox.innerHTML = '';
        }
      }
      // ---- RAG 医学参考（独立区域，不混入译文）----
      var ragBox = byId('rag-reference');
      if (ragBox) {
        if (ragCtx && ragCtx.length) {
          var items = ragCtx.slice(0, 5).map(function(item, i) {
            var safe = String(item).replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return '<li style="margin:4px 0; line-height:1.45;">' + safe + '</li>';
          }).join('');
          ragBox.innerHTML =
            '<details open style="margin-top:10px;">' +
            '<summary class="muted small" style="cursor:pointer;">📚 医学参考 / Medical reference (' + ragCtx.length + ')</summary>' +
            '<ul class="muted small" style="margin:8px 0 0 18px; padding-left:4px;">' + items + '</ul>' +
            '</details>';
        } else {
          ragBox.innerHTML = '';
        }
      }
    };

    tryApi(function(data) {
      // 后端字段：translated 是纯净译文（不再混 RAG 原文）；confidence 0-100；matched_terms 关键词；rag_context 参考
      var translated = data.translated || data.translated_text || '';
      var confidence = typeof data.confidence === 'number' ? data.confidence : 60;
      if (confidence < 1) confidence = confidence * 100;
      var terms = data.matched_terms || data.medical_terms || [];
      var engine = data.engine || 'api';
      var ragCtx = (data.rag_context && data.rag_context.length) ? data.rag_context : [];
      showResult(translated, confidence, terms, engine, ragCtx);
      done();
    }, function(err) {
      console.warn('translate API failed:', err, '- using offline fallback');
      offlineFallback();
    });
  });

  // 快速症状填充
  (function initSymptomChips() {
    var box = byId('symptom-chips');
    if (!box) return;
    var items = ['headache', 'chest pain', 'cough', 'fever', 'stomach pain', 'back pain', 'skin rash',
                 'dizziness', 'fatigue', 'sore throat', 'shortness of breath', 'nausea', 'joint pain', 'anxiety'];
    items.forEach(function(t) {
      var el = document.createElement('button');
      el.className = 'chip';
      el.textContent = t;
      el.type = 'button';
      bindClick(el, function() {
        var textarea = byId('src-text');
        if (textarea) textarea.value = 'I have ' + t + ' for 2 days.';
      });
      box.appendChild(el);
    });
  })();

  // ================================================================
  // 3) 医院列表
  // ================================================================
  function loadHospitals() {
    var container = byId('hospital-list');
    if (!container) return;
    container.innerHTML = '<p class="muted">加载医院 / Loading…</p>';

    var renderList = function(list, srcTag) {
      if (!list || !list.length) {
        container.innerHTML = '<p class="muted">未找到医院。</p>'; return;
      }
      container.innerHTML = list.map(function(h) {
        var name = h.name || '';
        var nameZh = (h.name_zh && h.name_zh !== name) ? (' / ' + h.name_zh) : '';
        var addr = h.address || h.address_zh || '';
        var phone = h.phone || '';
        var hours = h.hours || '';
        var rating = typeof h.rating === 'number' ? h.rating.toFixed(1) : '—';
        var specials = (h.specialties || []).slice(0, 5).map(function(s) {
          return '<span class="chip">' + (typeof s === 'string' ? s : (s.name || s)) + '</span>';
        }).join('');
        var insurances = (h.insurance || []).slice(0, 4).map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('');
        var lngLat = '';
        var hasLoc = (typeof h.lng === 'number' && typeof h.lat === 'number');
        if (hasLoc) lngLat = h.lng + ',' + h.lat;
        var btnAction = hasLoc
          ? '<button class="btn btn-light btn-navigate-here" data-lng="' + h.lng + '" data-lat="' + h.lat + '" data-name="' + (h.name_zh || name).replace(/"/g, '&quot;') + '">📍 导航到这里 / Navigate</button>'
          : '';
        return '<div class="hospital">' +
          '<div class="hospital-main">' +
          '<div class="hospital-head"><h4>' + name + nameZh + '</h4></div>' +
          (addr ? '<div class="sub">Address / 地址：' + addr + '</div>' : '') +
          (phone ? '<div class="sub">Phone / 电话：' + phone + '</div>' : '') +
          (hours ? '<div class="sub">Hours / 营业：' + hours + '</div>' : '') +
          (specials ? '<div class="chips"><span class="muted small">Specialties / 专科：</span>' + specials + '</div>' : '') +
          (insurances ? '<div class="chips"><span class="muted small">Insurance / 保险：</span>' + insurances + '</div>' : '') +
          '</div>' +
          '<div class="hospital-side">' +
          '<div class="rating-badge"><span class="rating-num">' + rating + '</span></div>' +
          btnAction +
          '</div>' +
          '</div>';
      }).join('');

      // 为每个导航按钮绑定点击
      container.querySelectorAll('.btn-navigate-here').forEach(function(b) {
        bindClick(b, function() {
          var lng = parseFloat(b.getAttribute('data-lng'));
          var lat = parseFloat(b.getAttribute('data-lat'));
          var nm = b.getAttribute('data-name');
          setActive('navigation');
          setTimeout(function() { navToTarget(lng, lat, nm); }, 80);
        });
      });
    };

    // ---- 先显示本地回退数据，若 API 可用则更新 ----
    var fallback = [
      { id: 'pumch', name: 'Peking Union Medical College Hospital', name_zh: '北京协和医院',
        address: '1 Shuaifuyuan, Dongcheng District, Beijing', address_zh: '东城区帅府园1号',
        phone: '+86 10 6915 6114', hours: '24h Emergency · Outpatient 8:00-17:00', rating: 4.8,
        specialties: ['General Medicine', 'Cardiology', 'Neurology', 'Endocrinology', 'Rheumatology'],
        insurance: ['Self-pay', 'Social Insurance', 'Ping An', 'Bupa'], languages: ['English', 'Japanese', 'Mandarin'],
        lng: 116.4165, lat: 39.9094 },
      { id: 'bjh', name: 'Beijing Hospital', name_zh: '北京医院',
        address: '1 Dongdan Dahua Road, Dongcheng', address_zh: '东城区东单大华路1号',
        phone: '+86 10 8513 2266', hours: '24h Emergency', rating: 4.6,
        specialties: ['Geriatrics', 'Cardiology', 'Neurology', 'Oncology'],
        insurance: ['Self-pay', 'Social Insurance'], languages: ['Mandarin', 'English'],
        lng: 116.4151, lat: 39.9038 },
      { id: 'tongren', name: 'Beijing Tongren Hospital', name_zh: '北京同仁医院',
        address: '1 Dongjiaominxiang, Dongcheng', address_zh: '东城区东交民巷1号',
        phone: '+86 10 5826 9988', hours: '24h Emergency', rating: 4.7,
        specialties: ['ENT', 'Ophthalmology', 'General Medicine'],
        insurance: ['Self-pay', 'Social Insurance', 'Cigna'], languages: ['Mandarin', 'English'],
        lng: 116.4172, lat: 39.9027 },
      { id: 'ufh', name: 'United Family Hospital', name_zh: '和睦家医院',
        address: '2 Jiangtai Road, Chaoyang', address_zh: '朝阳区将台路2号',
        phone: '+86 10 5927 7000', hours: '24h Emergency & Outpatient', rating: 4.9,
        specialties: ['Family Medicine', 'Pediatrics', 'Emergency', 'OB/GYN', 'Dental'],
        insurance: ['Bupa', 'Cigna', 'Allianz', 'Self-pay', 'International Insurance'],
        languages: ['English', 'Mandarin', 'Japanese', 'Korean', 'French', 'German'],
        lng: 116.4677, lat: 39.9754 },
      { id: '301', name: '301 Hospital (PLA General Hospital)', name_zh: '解放军总医院',
        address: '28 Fuxing Road, Haidian', address_zh: '海淀区复兴路28号',
        phone: '+86 10 6693 7329', hours: '24h Emergency', rating: 4.7,
        specialties: ['Trauma Surgery', 'Oncology', 'Cardiology', 'Neurology', 'Orthopedics'],
        insurance: ['Self-pay', 'Social Insurance'], languages: ['Mandarin', 'English'],
        lng: 116.2875, lat: 39.9067 }
    ];

    renderList(fallback, 'fallback');

    if (!API) return;
    var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    var tid = null;
    if (controller) tid = setTimeout(function() { controller.abort(); }, 12000);
    var opts = controller ? { signal: controller.signal } : {};
    fetch(API + '/api/hospitals?limit=20', opts)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (tid) clearTimeout(tid);
        var list = (data && data.hospitals) ? data.hospitals : [];
        if (list.length) renderList(list, 'api');
      }).catch(function() { if (tid) clearTimeout(tid); });
  }

  // ================================================================
  // 4) 分诊（症状 → 推荐科室）
  // ================================================================
  bindClick(byId('btn-triage'), function() {
    var symInput = byId('triage-input');
    var sym = symInput ? symInput.value.trim() : '';
    var box = byId('triage-result');
    if (!sym) return;
    if (box) { box.classList.remove('hidden'); box.textContent = '分析中 / Analyzing…'; }

    var renderTriage = function(depEn, depZh, urgent, matched) {
      if (!box) return;
      var tag = urgent ? 'URGENT · 紧急' : 'Recommended · 建议';
      var matchedHtml = (matched && matched.length)
        ? '<div class="muted small" style="margin-top:6px;">Matched / 匹配：' +
          matched.map(function(s) { return '<span class="chip">' + s + '</span>'; }).join('') + '</div>'
        : '';
      box.innerHTML =
        '<div><span class="triage-label">' + tag + '</span></div>' +
        '<strong>Department / 科室：</strong> ' + depEn + ' / ' + depZh +
        matchedHtml;
    };

    // ---- 离线规则（即时显示） ----
    var rules = {
      'headache': { en: 'Neurology', zh: '神经内科', urgent: false },
      'chest pain': { en: 'Cardiology', zh: '心内科', urgent: true },
      'cough': { en: 'Pulmonology / General Medicine', zh: '呼吸内科 / 全科', urgent: false },
      'fever': { en: 'Infectious Diseases / ER', zh: '感染科 / 急诊', urgent: false },
      'stomach': { en: 'Gastroenterology', zh: '消化内科', urgent: false },
      'back pain': { en: 'Orthopedics', zh: '骨科', urgent: false },
      'skin': { en: 'Dermatology', zh: '皮肤科', urgent: false },
      'rash': { en: 'Dermatology', zh: '皮肤科', urgent: false },
      'dizziness': { en: 'Neurology / Cardiology', zh: '神经内科 / 心内科', urgent: false },
      'sore throat': { en: 'ENT', zh: '耳鼻喉科', urgent: false },
      'shortness of breath': { en: 'Pulmonology / ER', zh: '呼吸内科 / 急诊', urgent: true },
      'nausea': { en: 'Gastroenterology', zh: '消化内科', urgent: false },
      'vomit': { en: 'Gastroenterology', zh: '消化内科', urgent: false },
      'joint pain': { en: 'Rheumatology / Orthopedics', zh: '风湿免疫 / 骨科', urgent: false },
      'anxiety': { en: 'Psychiatry', zh: '精神心理科', urgent: false },
      'bleeding': { en: 'ER', zh: '急诊', urgent: true },
      'child': { en: 'Pediatrics', zh: '儿科', urgent: false },
      'pregnancy': { en: 'Obstetrics', zh: '产科', urgent: false },
      'dental': { en: 'Dentistry', zh: '口腔科', urgent: false }
    };
    var lower = sym.toLowerCase();
    var matchedTerms = [];
    var chosen = { en: 'General Medicine / 全科', zh: '全科', urgent: false };
    var keys = Object.keys(rules).sort(function(a, b) { return b.length - a.length; });
    keys.forEach(function(k) {
      if (lower.indexOf(k) !== -1) {
        matchedTerms.push(k);
        chosen = rules[k];
      }
    });
    renderTriage(chosen.en, chosen.zh, chosen.urgent, matchedTerms);

    // ---- 若有后端，则用更精确结果异步覆盖 ----
    if (!API) return;
    var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    var tid = null;
    if (controller) tid = setTimeout(function() { controller.abort(); }, 10000);
    var opts = controller ? { signal: controller.signal } : {};
    fetch(API + '/api/triage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symptoms: sym, language: 'en' }),
      ...(Object.keys(opts).length ? opts : {})
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (tid) clearTimeout(tid);
        if (data && (data.department_en || data.department_zh)) {
          renderTriage(data.department_en || chosen.en, data.department_zh || chosen.zh,
            !!data.urgent, data.matched_symptoms || matchedTerms);
        }
      }).catch(function() { if (tid) clearTimeout(tid); });

    loadHospitals();
  });

  // ================================================================
  // 5) 导航（内置高德地图 JS API，不跳外部）
  // ================================================================
  var _navMap = null;       // AMap 实例
  var _navKey = null;       // 高德 JS key（从 /api/amap/config 获取）
  var _navOrigin = null;    // {lng, lat}
  var _navTarget = null;    // {lng, lat, name}
  var _navMode = 'walking'; // walking | driving | transit

  function initNavigation() {
    var sel = byId('nav-hospital');
    var modeSel = byId('nav-mode');
    var locateBtn = byId('nav-locate');
    var originBox = byId('nav-origin');
    var mapDiv = byId('nav-map');
    var routeBox = byId('nav-route');

    if (!sel || !mapDiv) return;

    // ---- 1) 获取 AMap JS Key ----
    var fetchAmapConfig = function(onGot) {
      if (_navKey) { onGot(_navKey); return; }
      if (!API) { onGot(null); return; }
      fetch(API + '/api/amap/config').then(function(r) { return r.json(); })
        .then(function(data) {
          var k = data && (data.js_key || data.jsKey || data.key);
          _navKey = k || null;
          onGot(_navKey);
        }).catch(function() { onGot(null); });
    };

    // ---- 2) 加载高德 JS API ----
    var loadAmapJs = function(key, onReady) {
      if (window.AMap) { onReady(); return; }
      var script = document.createElement('script');
      script.src = 'https://webapi.amap.com/maps?v=2.0&key=' +
        encodeURIComponent(key || '') +
        '&plugin=AMap.Driving,AMap.Walking,AMap.Transfer,AMap.Geolocation,AMap.Scale,AMap.ToolBar';
      script.onerror = function() { onReady(new Error('AMap load failed')); };
      script.onload = function() {
        if (!window.AMap) { onReady(new Error('AMap not loaded')); return; }
        window.AMap._securityCode = key;
        onReady();
      };
      document.head.appendChild(script);
    };

    // ---- 3) 填充医院下拉 ----
    var fillHospitalDropdown = function(list) {
      if (!sel) return;
      sel.innerHTML = '';
      list.forEach(function(h, idx) {
        if (typeof h.lng !== 'number' || typeof h.lat !== 'number') return;
        var o = document.createElement('option');
        o.value = String(idx);
        o.textContent = (h.name_zh || h.name || '医院') + ' / ' + (h.name || '');
        sel.appendChild(o);
      });
    };

    // ---- 4) 渲染：医院卡片 + 地图 + 路线 ----
    var renderNavOutput = function(hospital, mode) {
      var cardBox = byId('nav-output-cards');
      if (cardBox && hospital) {
        var name = hospital.name || '';
        var nameZh = hospital.name_zh || '';
        var addr = hospital.address_zh || hospital.address || '';
        var phone = hospital.phone || '';
        var hours = hospital.hours || '';
        var rating = typeof hospital.rating === 'number' ? hospital.rating.toFixed(1) : '—';
        cardBox.innerHTML =
          '<div class="card" style="margin-bottom:14px;">' +
          '<h4 style="margin-top:0;">' + name + (nameZh ? ' / ' + nameZh : '') + '</h4>' +
          (addr ? '<div class="muted small" style="margin:4px 0;">📍 ' + addr + '</div>' : '') +
          (phone ? '<div class="muted small" style="margin:4px 0;">☎ ' + phone + '</div>' : '') +
          (hours ? '<div class="muted small" style="margin:4px 0;">🕒 ' + hours + '</div>' : '') +
          '<div class="muted small" style="margin-top:6px;">Rating / 评分：<strong>' + rating + '</strong></div>' +
          '</div>';
      }

      if (hospital && typeof hospital.lng === 'number' && typeof hospital.lat === 'number') {
        _navTarget = { lng: hospital.lng, lat: hospital.lat, name: hospital.name_zh || hospital.name };
      }
      if (mode) _navMode = mode;
      drawMap();
    };

    // ---- 5) 绘制地图 + 路线 ----
    var drawMap = function() {
      if (!window.AMap || !byId('nav-map')) return;
      var origin = _navOrigin || { lng: 116.4074, lat: 39.9042 };  // 默认：北京天安门
      var target = _navTarget;

      if (!_navMap) {
        _navMap = new window.AMap.Map(byId('nav-map'), {
          zoom: 12,
          center: [origin.lng, origin.lat],
          viewMode: '2D'
        });
        try {
          _navMap.addControl(new window.AMap.Scale());
          _navMap.addControl(new window.AMap.ToolBar({ position: 'RB' }));
        } catch(e) {}
      }

      // 清空旧覆盖物
      _navMap.clearMap();

      // 起点 / 终点 标记
      new window.AMap.Marker({ position: [origin.lng, origin.lat], title: '起点 / Origin', map: _navMap });
      if (target) {
        new window.AMap.Marker({ position: [target.lng, target.lat], title: target.name || '医院', map: _navMap });
        // 路线规划
        planRoute(origin, target, _navMode);
        // 自适应视野
        try {
          _navMap.setFitView();
        } catch(e) {
          _navMap.setZoomAndCenter(13, [(origin.lng + target.lng)/2, (origin.lat + target.lat)/2]);
        }
      } else {
        _navMap.setZoomAndCenter(12, [origin.lng, origin.lat]);
      }

      if (byId('nav-origin') && origin) {
        byId('nav-origin').textContent = '📍 Origin / 起点：(' + origin.lng.toFixed(4) + ', ' + origin.lat.toFixed(4) + ')';
      }
    };

    var planRoute = function(origin, target, mode) {
      var box = byId('nav-route');
      if (!box || !window.AMap) return;
      box.innerHTML = '<p class="muted small">规划路线中 / Planning route…</p>';

      var modeText = mode === 'driving' ? '驾车 / Driving' :
                     mode === 'transit' ? '公交 / Transit' : '步行 / Walking';

      var showRouteInfo = function(distanceMeters, durationSec, steps) {
        var km = (distanceMeters / 1000).toFixed(2);
        var min = Math.max(1, Math.round(durationSec / 60));
        var stepHtml = '';
        if (steps && steps.length) {
          stepHtml = '<ol style="line-height:1.8; padding-left:20px; margin:10px 0 0;">' +
            steps.slice(0, 20).map(function(s, i) {
              var instruction = s.instruction || s.text || s.name || ('Step ' + (i+1));
              var dist = s.distance ? ' (' + (s.distance > 1000 ? (s.distance/1000).toFixed(2) + ' km' : s.distance + ' m') + ')' : '';
              return '<li>' + instruction + dist + '</li>';
            }).join('') +
            '</ol>';
        }
        box.innerHTML =
          '<div class="card">' +
          '<h4 style="margin-top:0;">Route / 路线 · ' + modeText + '</h4>' +
          '<div class="muted small" style="margin:4px 0;">' +
          '<strong>Distance / 距离：</strong>' + km + ' km &nbsp;&nbsp;|&nbsp;&nbsp;' +
          '<strong>Duration / 用时：</strong>约 ' + min + ' 分钟' +
          '</div>' + stepHtml +
          '</div>';
      };

      var showFallback = function() {
        // 高德插件不可用（如无 key 或 配额不足）→ 返回直线路线估算
        var dx = (target.lng - origin.lng) * 111 * Math.cos((target.lat + origin.lat) / 2 * Math.PI / 180);
        var dy = (target.lat - origin.lat) * 111;
        var km = Math.sqrt(dx*dx + dy*dy);
        var speed = mode === 'driving' ? 35 : (mode === 'transit' ? 20 : 5);
        var min = Math.max(1, Math.round(km / speed * 60));
        box.innerHTML =
          '<div class="card">' +
          '<h4 style="margin-top:0;">Estimated route / 估算路线 · ' + modeText + '</h4>' +
          '<div class="muted small" style="margin:6px 0;">Straight-line / 直线距离：' + km.toFixed(2) + ' km · 估算用时 ~ ' + min + ' 分钟</div>' +
          '<div class="muted small">提示：配置高德 JS API key 可启用真正路线规划 / Configure AMap JS key to enable real routing.</div>' +
          '</div>';
      };

      try {
        var pluginName = mode === 'driving' ? 'AMap.Driving' :
                         mode === 'transit' ? 'AMap.Transfer' : 'AMap.Walking';
        if (!window.AMap[pluginName]) {
          // 尝试动态加载插件
          window.AMap.plugin([pluginName], function() {
            if (!window.AMap[pluginName]) { showFallback(); return; }
            runPlugin();
          });
        } else {
          runPlugin();
        }
        function runPlugin() {
          var opts = { map: _navMap, hideMarkers: true, autoFitView: true };
          var planner;
          try {
            if (mode === 'driving') planner = new window.AMap.Driving(opts);
            else if (mode === 'transit') planner = new window.AMap.Transfer({
              city: '北京', map: _navMap, panel: null
            });
            else planner = new window.AMap.Walking(opts);
          } catch(e) { showFallback(); return; }

          planner.search(
            new window.AMap.LngLat(origin.lng, origin.lat),
            new window.AMap.LngLat(target.lng, target.lat),
            function(status, result) {
              if (status !== 'complete') { showFallback(); return; }
              var distance = 0, duration = 0, steps = [];
              try {
                if (result.routes && result.routes.length) {
                  var route = result.routes[0];
                  distance = route.distance || 0;
                  duration = route.time || 0;
                  var rawSteps = route.steps || (route.via_stops ? route.via_stops : []);
                  if (mode === 'transit' && result.plans && result.plans.length) {
                    var plan = result.plans[0];
                    distance = plan.distance || 0;
                    duration = plan.time || 0;
                    steps = (plan.segments || []).map(function(seg, i) {
                      var line = seg.transit_line || {};
                      var name = line.name || ('步行段 ' + (i+1));
                      var walkDist = seg.walk_distance || 0;
                      var lineDist = (line.distance || 0);
                      return { instruction: name + '（步行 ' + (walkDist>0?Math.round(walkDist/1000*10)/10+' km':'') + '）', distance: walkDist + lineDist };
                    });
                  } else {
                    steps = rawSteps.map(function(s, i) {
                      return { instruction: (i+1) + '. ' + (s.instruction || s.name || '继续前行'), distance: s.distance || 0 };
                    });
                  }
                }
              } catch(e) {}
              showRouteInfo(distance, duration, steps);
            }
          );
        }
      } catch(e) {
        showFallback();
      }
    };

    // ---- 6) 事件绑定（只绑一次）----
    if (sel.dataset.bound !== '1') {
      sel.dataset.bound = '1';
      bindChange(sel, function() {
        var list = JSON.parse(sel.getAttribute('data-list') || '[]');
        var h = list[parseInt(sel.value, 10)];
        if (h) renderNavOutput(h, _navMode);
      });
    }
    if (modeSel && modeSel.dataset.bound !== '1') {
      modeSel.dataset.bound = '1';
      bindChange(modeSel, function() {
        _navMode = modeSel.value;
        var list = JSON.parse(sel.getAttribute('data-list') || '[]');
        var h = list[parseInt(sel.value, 10)];
        if (h) renderNavOutput(h, _navMode);
      });
    }
    if (locateBtn && locateBtn.dataset.bound !== '1') {
      locateBtn.dataset.bound = '1';
      bindClick(locateBtn, function() {
        // 先尝试浏览器 Geolocation
        if (!navigator.geolocation) {
          alert('Geolocation is not available in this browser.');
          return;
        }
        locateBtn.textContent = '定位中 / Locating…';
        navigator.geolocation.getCurrentPosition(function(pos) {
          _navOrigin = { lng: pos.coords.longitude, lat: pos.coords.latitude };
          locateBtn.textContent = '使用我的位置 / Use my location';
          var list = JSON.parse(sel.getAttribute('data-list') || '[]');
          var h = list[parseInt(sel.value, 10)];
          if (h) renderNavOutput(h, _navMode);
        }, function(err) {
          locateBtn.textContent = '使用我的位置 / Use my location';
          alert('Location access denied or unavailable: ' + err.message);
        }, { timeout: 15000, enableHighAccuracy: true });
      });
    }

    // ---- 7) 填充数据 ----
    var fallbackList = [
      { name: 'Peking Union Medical College Hospital', name_zh: '北京协和医院',
        address: '1 Shuaifuyuan, Dongcheng District', address_zh: '东城区帅府园1号',
        phone: '+86 10 6915 6114', hours: '24h Emergency · 8:00-17:00', rating: 4.8,
        lng: 116.4165, lat: 39.9094 },
      { name: 'Beijing Hospital', name_zh: '北京医院',
        address: '1 Dongdan Dahua Road, Dongcheng', address_zh: '东城区东单大华路1号',
        phone: '+86 10 8513 2266', hours: '24h Emergency', rating: 4.6,
        lng: 116.4151, lat: 39.9038 },
      { name: 'Beijing Tongren Hospital', name_zh: '北京同仁医院',
        address: '1 Dongjiaominxiang, Dongcheng', address_zh: '东城区东交民巷1号',
        phone: '+86 10 5826 9988', hours: '24h Emergency', rating: 4.7,
        lng: 116.4172, lat: 39.9027 },
      { name: 'United Family Hospital', name_zh: '和睦家医院',
        address: '2 Jiangtai Road, Chaoyang', address_zh: '朝阳区将台路2号',
        phone: '+86 10 5927 7000', hours: '24h', rating: 4.9,
        lng: 116.4677, lat: 39.9754 },
      { name: '301 Hospital', name_zh: '解放军总医院',
        address: '28 Fuxing Road, Haidian', address_zh: '海淀区复兴路28号',
        phone: '+86 10 6693 7329', hours: '24h Emergency', rating: 4.7,
        lng: 116.2875, lat: 39.9067 }
    ];

    sel.setAttribute('data-list', JSON.stringify(fallbackList));
    fillHospitalDropdown(fallbackList);
    renderNavOutput(fallbackList[0], _navMode);

    // 尝试从后端 API 更新列表（带更多真实数据 + 坐标）
    if (!API) return;
    fetch(API + '/api/hospitals?limit=20').then(function(r) { return r.json(); })
      .then(function(data) {
        var list = (data && data.hospitals && data.hospitals.length) ? data.hospitals : null;
        if (list) {
          var valid = list.filter(function(h) { return typeof h.lng === 'number' && typeof h.lat === 'number'; });
          if (valid.length) {
            sel.setAttribute('data-list', JSON.stringify(valid));
            fillHospitalDropdown(valid);
            renderNavOutput(valid[0], _navMode);
          }
        }
      }).catch(function() {});

    // ---- 异步获取 AMap JS key + 加载地图 ----
    fetchAmapConfig(function(key) {
      loadAmapJs(key, function(err) {
        if (err) {
          console.warn('AMap JS unavailable:', err.message || err);
          // 仍然可以显示路线估算（无地图），但尝试让 mapDiv 显示友好提示
          if (mapDiv) {
            mapDiv.innerHTML = '<div style="padding:40px; text-align:center; color:#888;">' +
              '🗺 Map preview unavailable (AMap JS key not configured).<br>' +
              '<span class="small muted">未配置高德 JS key，使用文本路线预览。</span></div>';
          }
        } else {
          drawMap();
        }
      });
    });
  }

  // ---- 医院列表页点击"导航到这里"跳转到导航页并设置目标 ----
  function navToTarget(lng, lat, name) {
    if (!lng || !lat) return;
    _navTarget = { lng: lng, lat: lat, name: name || '医院' };
    // 确保地图已经初始化（触发视图切换会调 initNavigation）
    if (byId('nav-hospital') && byId('nav-map') && window.AMap && _navMap) {
      drawMap();
    }
  }
  // 暴露 drawMap 引用
  var drawMap = function() {};

  // ================================================================
  // 6) 初始
  // ================================================================
  setActive('home');
  console.log('TransMed UI initialized · API:', API);
})();
'''

import os
_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transmed_web')
os.makedirs(_dir, exist_ok=True)
_path = os.path.join(_dir, 'app.js')
with open(_path, 'w', encoding='utf-8') as f:
    f.write(JS)
print('Written to', _path, '(' + str(len(JS)) + ' chars)')
