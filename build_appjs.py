#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建前端 app.js（源文件）。

JS 以 raw 字符串内嵌于此，运行后写入 transmed_web/app.js 与 docs/app.js 两份。
  python3 build_appjs.py

2026 重做 + 多语言：
  · 浅色 Claude 奶油风 + 苹果式滚动/动效
  · 接活死功能（登录/统计/用药/隐私/反馈/个人中心）
  · 导航：_AMapSecurityConfig 安全密钥 → 真实路线 + 转向步骤；修跨页目标丢失
  · 医院推荐：症状→分诊→匹配度排序 + 推荐理由 + 真实评价
  · 全局 i18n：首屏选语言→全站切换；EN/中文手写精翻，其余 10 种用本平台
    /api/translate 引擎实时翻译并缓存（失败回退英文）；导航转向步骤同理翻译。
"""
import os

JS = r'''/* TransMed frontend — light Claude theme + global i18n */
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

  /* ============================================================
     i18n — hand-authored en/zh; other langs via /api/translate (cached)
     ============================================================ */
  var LANGS = [
    { code: 'en', name: 'English', short: 'EN' }, { code: 'zh', name: '中文', short: '中文' },
    { code: 'ja', name: '日本語', short: '日本語' }, { code: 'ko', name: '한국어', short: '한국어' },
    { code: 'fr', name: 'Français', short: 'FR' }, { code: 'de', name: 'Deutsch', short: 'DE' },
    { code: 'es', name: 'Español', short: 'ES' }, { code: 'it', name: 'Italiano', short: 'IT' },
    { code: 'ru', name: 'Русский', short: 'RU' }, { code: 'ar', name: 'العربية', short: 'ع' },
    { code: 'pt', name: 'Português', short: 'PT' }, { code: 'hi', name: 'हिन्दी', short: 'हिं' }
  ];
  var LANG_KEY = 'transmed_lang', I18N_PREFIX = 'transmed_i18n_', STEP_PREFIX = 'transmed_steps_';

  var STR_EN = {
    tagline: 'AI medical companion · in-China care',
    nav_home: 'Home', nav_translate: 'Translate', nav_hospitals: 'Hospitals', nav_navigation: 'Navigation', nav_medication: 'Medication', nav_account: 'Account',
    login_register: 'Log in / Register', signout: 'Sign out',
    lang_pick_title: 'Choose your language', lang_pick_sub: 'The whole app will switch to it. You can change it anytime from the top bar.',
    login_tab: 'Log in', register_tab: 'Register', email: 'Email', password: 'Password', password_min: 'Password (min 6 chars)',
    do_login: 'Log in', create_account: 'Create my account', demo_hint: 'Demo: demo@transmed.io / demo123 · Admin: admin@transmed.io / admin123',
    fullname: 'Full name', pref_lang: 'Preferred language', country: 'Country',
    signing_in: 'Signing in…', creating: 'Creating account…', welcome_back: 'Welcome back, {name}', account_created: 'Account created — welcome!',
    signed_out: 'Signed out', login_failed: 'Login failed', reg_failed: 'Registration failed', please_name: 'Please enter your name',
    hero_eyebrow: 'AI medical companion for foreigners in China', hero_title_a: 'Get care in China', hero_title_b: 'without the language barrier.',
    hero_lead: 'Medical-grade multilingual translation with confidence scoring, symptom-based hospital matching, and real in-map navigation to the right department — all in one calm, trustworthy place.',
    hero_cta_translate: 'Start translating', hero_cta_hospital: 'Find the right hospital',
    trust_langs: '12 languages', trust_data: 'Real Beijing hospital data', trust_privacy: 'Privacy by design',
    feat_eyebrow: 'What TransMed does', feat_title: 'Four steps of a medical visit, handled.', feat_sub: 'From describing your symptoms to standing in the right department — each step is designed to remove friction and uncertainty.',
    feat1_t: 'AI medical translation', feat1_d: 'Vertical medical model with term alignment, a confidence score and 4-level risk alerts so nothing critical is lost in translation.',
    feat2_t: 'Smart hospital matching', feat2_d: 'Describe your symptoms; TransMed triages to a department and ranks real hospitals by specialty fit, rating and distance — with reasons.',
    feat3_t: 'In-map navigation', feat3_d: 'A drawn route and turn-by-turn directions on a live map, plus one tap to hand off to Apple, Google, AMap or Baidu Maps.',
    feat4_t: 'Medication & privacy', feat4_d: 'A bilingual drug library with reminders, and a privacy center to export or wipe your personal records anytime.',
    how_eyebrow: 'How it works', how_title: 'From symptom to seen.',
    how1_t: 'Describe it', how1_d: 'Type symptoms in your language. Get a clean medical translation with risk level.',
    how2_t: 'Get triaged', how2_d: 'TransMed identifies the right department and flags urgent cases.',
    how3_t: 'Pick a hospital', how3_d: 'Compare ranked hospitals with real ratings, reviews and travel distance.',
    how4_t: 'Navigate there', how4_d: 'Follow the drawn route, or hand off to your favourite maps app.',
    stats_eyebrow: 'Live platform', stats_title: 'Grounded in real data.',
    st_langs: 'Languages', st_terms: 'Medical terms', st_hosp: 'Hospitals', st_rules: 'Triage rules', st_trans: 'Translations served',
    tr_eyebrow: 'Translation', tr_title: 'AI medical translation', tr_lede: 'A vertical medical engine. Every translation is scored for confidence and risk, with the medical terms it recognised highlighted.',
    tr_from: 'From', tr_to: 'To', tr_src_ph: 'Describe symptoms, or paste what the doctor said…', tr_tip: 'Tip: be specific about duration, intensity and allergies.',
    tr_btn: 'Translate', tr_translating: 'Translating…', tr_result_ph: 'Translation will appear here.', tr_confidence: 'Confidence', tr_risk: 'Risk',
    tr_ack: 'I acknowledge the risk alert', tr_ack_done: 'Risk acknowledged', tr_templates: 'Quick symptom templates', tr_my_recent: 'My recent translations', tr_signin_save: '(sign in to save)',
    tr_terms_label: 'Recognised medical terms', tr_ref_label: 'Medical reference ({n})',
    tr_advice_low: 'High confidence. Still confirm critical details with your clinician.',
    tr_advice_med: 'Moderate confidence — double-check dosages, numbers and negations.',
    tr_advice_high: 'Low confidence. Please verify with a bilingual staff member before acting on this.',
    tr_online: 'Online', tr_offline: 'Offline',
    tr_hist_signin: 'Sign in to keep a history of your translations.', tr_hist_empty: 'No saved translations yet.', tr_hist_fail: 'Could not load history.',
    tr_conf_line: 'confidence {n}% · {risk}',
    hp_eyebrow: 'Triage & hospitals', hp_title: 'Find the right hospital', hp_lede: 'Describe your symptoms — TransMed triages you to a department and ranks real hospitals by how well they fit, telling you why.',
    hp_sym_label: 'Describe your symptoms', hp_sym_ph: 'e.g. persistent headache and high fever for 2 days', hp_dept_label: 'Department (optional)', hp_dept_auto: 'Auto-detect',
    hp_analyze: 'Analyze & recommend', hp_use_loc: '📍 Use my location for distance', hp_loc_set: '📍 Location set', hp_locating: '📍 Locating…',
    hp_sort_by: 'Sort by', hp_sort_match: 'Best match', hp_sort_rating: 'Rating', hp_sort_distance: 'Distance',
    hp_loading: 'Loading hospitals…', hp_matching: 'Matching hospitals…', hp_describe_first: 'Describe your symptoms first', hp_loc_first: 'Tap “Use my location” first',
    hp_loc_added: 'Location set — distances added',
    hp_urgent: '🚨 URGENT', hp_recommended: '✓ Recommended department', hp_call120: 'If this is an emergency, call 120 now.',
    hp_best_match: '#{n} best match', hp_match_cap: 'match', hp_strong_in: 'Strong in {sp}', hp_national_leader: 'National leader in {sp}', hp_grade_3a: 'Class III-A (top tier)', hp_rated: 'Rated {r}/5', hp_reviews: '{n} reviews', hp_reviews_paren: '({n} reviews)',
    hp_km_you: '{km} km from you', hp_km: '{km} km', hp_speaks: 'Speaks your language', hp_emergency: 'Strong emergency services', hp_navigate: 'Navigate →',
    hp_no_hosp: 'No hospitals found. Try a broader symptom or department.', hp_waking_t: 'Recommendation service is waking up', hp_waking_d: 'Showing all hospitals meanwhile. Try again in a moment.',
    nv_eyebrow: 'Navigation', nv_title: 'Navigate to care', nv_lede: "See the drawn route and turn-by-turn directions on a live map — or hand off to your phone's maps app in one tap.",
    nv_hospital: 'Hospital', nv_mode: 'Mode', nv_walking: '🚶 Walking', nv_driving: '🚗 Driving', nv_transit: '🚇 Transit', nv_use_loc: '📍 Use my location', nv_locating: '📍 Locating…',
    nv_map_loading: 'Loading map…', nv_origin_default: '📍 Origin: Beijing city center (default) · tap “Use my location”.', nv_origin_gps: '📍 Origin: your current location',
    nv_map_unavail: 'Live map unavailable.', nv_map_no_js: 'AMap JS key not configured.', nv_map_no_backend: 'Backend not configured.', nv_map_hint: 'Use the buttons below to open this place in a maps app.',
    nv_open_in: 'Open in maps:', nv_planning: 'Planning route…', nv_turn_by_turn: '🧭 Turn-by-turn', nv_arrive: 'Arrive at {name}', nv_you: 'You',
    nv_fallback: 'Turn-by-turn needs the AMap security key. Distance/time are straight-line estimates — use the buttons above to navigate in a maps app.',
    nv_dist: 'Distance', nv_straight: 'Straight-line', nv_duration: 'Duration', nv_est: 'Est. time', nv_mode_label: 'Mode', nv_walk: 'Walking', nv_drive: 'Driving', nv_transit_txt: 'Transit', nv_using_loc: 'Using your location',
    md_eyebrow: 'Medication', md_title: 'Medication & reminders', md_lede: 'Look up a drug in the bilingual library, then save it with reminder times to your personal list.',
    md_add: 'Add a medication', md_from_lib: 'From library', md_choose: '— choose —', md_custom: 'Or custom name', md_custom_ph: 'e.g. Vitamin D', md_dosage: 'Dosage / instructions', md_dosage_ph: 'e.g. 1 tablet each morning',
    md_times: 'Reminder times', md_notes: 'Notes', md_notes_ph: 'After meals, keep away from dairy…', md_save: 'Save to my list', md_login_req: 'Requires login. Stored against your account.',
    md_drug_info: 'Drug information', md_pick: 'Pick a medication from the library to see dosage, warnings and side effects.', md_rx: 'Rx', md_otc: 'OTC',
    md_dosage_h: 'Dosage', md_warnings_h: 'Warnings', md_side_h: 'Side effects', md_my_list: 'My medication list', md_list_signin: 'Sign in to save medications and reminders.', md_list_empty: 'No medications saved yet.',
    md_saved: 'Saved to your list', md_removed: 'Removed', md_remove: 'Remove', md_pick_first: 'Pick a medication from the library', md_login_first: 'Please log in first', md_load_fail: 'Could not load your list.',
    ac_eyebrow: 'Your account', ac_title: 'Account & privacy', ac_lede: 'Your identity is optional. Sensitive medical text is processed with minimal retention — and you can export or wipe everything anytime.',
    ac_signin_p: 'Log in to see your profile, saved translations and medication.', ac_signin_btn: 'Log in / Register', ac_member_since: 'Member since {date}',
    ac_your_data: 'Your data', ac_data_desc: 'Export a full JSON copy of everything tied to your account, or permanently delete your personal records (your login is kept).',
    ac_export: '⬇︎ Export all my data', ac_wipe: '🗑 Delete all personal records', ac_exported: 'Exported below', ac_wipe_confirm: 'Delete ALL your translations, medications, triage and feedback? Your login is kept. This cannot be undone.', ac_wiped: 'All personal records deleted',
    ac_feedback: 'Feedback', ac_category: 'Category', ac_cat_translation: 'translation', ac_cat_hospital: 'hospital', ac_cat_navigation: 'navigation', ac_cat_medication: 'medication', ac_cat_feature: 'feature request', ac_cat_other: 'other',
    ac_rating: 'Rating (1–5)', ac_your_msg: 'Your message', ac_msg_ph: 'Tell us how we can improve…', ac_submit: 'Submit feedback', ac_fb_thanks: 'Thank you! Your feedback was received.', ac_fb_write: 'Please write a message', ac_fb_sent: 'Feedback sent',
    footer_a: 'TransMed · AI for cross-cultural healthcare — for demonstration only. In an emergency call 120 or go to the nearest ER.', footer_b: 'Critical decisions must be confirmed with a licensed physician.',
    loc_prefix: 'Location: {msg}', ui_translating: 'Translating interface…', ui_ready: 'Language ready', please_login: 'Please log in first'
  };

  var STR_ZH = {
    tagline: 'AI 医疗陪护 · 在华就医',
    nav_home: '首页', nav_translate: '翻译', nav_hospitals: '医院', nav_navigation: '导航', nav_medication: '用药', nav_account: '我的',
    login_register: '登录 / 注册', signout: '退出',
    lang_pick_title: '选择你的语言', lang_pick_sub: '整个应用都会切换为该语言，随时可在顶栏更改。',
    login_tab: '登录', register_tab: '注册', email: '邮箱', password: '密码', password_min: '密码（至少 6 位）',
    do_login: '登录', create_account: '创建账户', demo_hint: '演示：demo@transmed.io / demo123 · 管理员：admin@transmed.io / admin123',
    fullname: '姓名', pref_lang: '首选语言', country: '国家 / 地区',
    signing_in: '登录中…', creating: '创建账户中…', welcome_back: '欢迎回来，{name}', account_created: '账户已创建，欢迎！',
    signed_out: '已退出', login_failed: '登录失败', reg_failed: '注册失败', please_name: '请填写姓名',
    hero_eyebrow: '为在华外籍人士打造的 AI 医疗陪护', hero_title_a: '在中国就医', hero_title_b: '不再受语言所困。',
    hero_lead: '医疗级多语言翻译（含置信度评分）、按症状智能匹配医院、地图内真实路线直达对应科室——一站式、从容又可信。',
    hero_cta_translate: '开始翻译', hero_cta_hospital: '找到合适的医院',
    trust_langs: '12 种语言', trust_data: '真实北京医院数据', trust_privacy: '隐私优先设计',
    feat_eyebrow: 'TransMed 能做什么', feat_title: '就医四步，一站搞定。', feat_sub: '从描述症状到站在正确的科室门口——每一步都为减少摩擦与不确定而设计。',
    feat1_t: 'AI 医疗翻译', feat1_d: '垂直医疗模型，术语对齐 + 置信度评分 + 4 级风险提示，关键信息绝不在翻译中丢失。',
    feat2_t: '智能医院匹配', feat2_d: '描述症状，TransMed 自动分诊到科室，并按专科匹配度、评分与距离对真实医院排序——并给出理由。',
    feat3_t: '地图内导航', feat3_d: '在实时地图上画出路线与转向步骤，并可一键跳转 Apple、Google、高德或百度地图。',
    feat4_t: '用药与隐私', feat4_d: '双语药品库 + 用药提醒；隐私中心支持随时导出或清除你的个人记录。',
    how_eyebrow: '使用流程', how_title: '从症状到就诊。',
    how1_t: '描述症状', how1_d: '用你的语言输入症状，得到干净的医疗翻译与风险等级。',
    how2_t: '智能分诊', how2_d: 'TransMed 识别对应科室，并标记紧急情况。',
    how3_t: '挑选医院', how3_d: '对比按匹配度排序的医院——含真实评分、评价与路程距离。',
    how4_t: '导航前往', how4_d: '沿画出的路线前往，或一键交给你常用的地图 App。',
    stats_eyebrow: '实时平台', stats_title: '基于真实数据。',
    st_langs: '语言', st_terms: '医学术语', st_hosp: '医院', st_rules: '分诊规则', st_trans: '累计翻译次数',
    tr_eyebrow: '翻译', tr_title: 'AI 医疗翻译', tr_lede: '垂直医疗引擎。每次翻译都给出置信度与风险评分，并高亮识别到的医学术语。',
    tr_from: '从', tr_to: '到', tr_src_ph: '描述症状，或粘贴医生说的话……', tr_tip: '提示：尽量写清持续时间、强度与过敏史。',
    tr_btn: '翻译', tr_translating: '翻译中…', tr_result_ph: '译文将显示在这里。', tr_confidence: '置信度', tr_risk: '风险',
    tr_ack: '我已知晓该风险提示', tr_ack_done: '已确认风险', tr_templates: '常用症状模板', tr_my_recent: '我的最近翻译', tr_signin_save: '（登录后保存）',
    tr_terms_label: '识别到的医学术语', tr_ref_label: '医学参考（{n}）',
    tr_advice_low: '置信度高。关键细节仍建议与医生确认。',
    tr_advice_med: '置信度中等——请仔细核对剂量、数字与否定表达。',
    tr_advice_high: '置信度偏低。采取行动前请让懂双语的工作人员核对。',
    tr_online: '在线', tr_offline: '离线',
    tr_hist_signin: '登录后即可保存翻译历史。', tr_hist_empty: '暂无已保存的翻译。', tr_hist_fail: '无法加载历史。',
    tr_conf_line: '置信度 {n}% · {risk}',
    hp_eyebrow: '分诊与医院', hp_title: '找到合适的医院', hp_lede: '描述症状——TransMed 会为你分诊到科室，并按匹配程度对真实医院排序，并告诉你“为什么”。',
    hp_sym_label: '描述你的症状', hp_sym_ph: '例如：持续头痛、高烧两天', hp_dept_label: '科室（可选）', hp_dept_auto: '自动识别',
    hp_analyze: '分析并推荐', hp_use_loc: '📍 用我的位置计算距离', hp_loc_set: '📍 位置已设置', hp_locating: '📍 定位中…',
    hp_sort_by: '排序', hp_sort_match: '最匹配', hp_sort_rating: '评分', hp_sort_distance: '距离',
    hp_loading: '加载医院中…', hp_matching: '匹配医院中…', hp_describe_first: '请先描述症状', hp_loc_first: '请先点“用我的位置”',
    hp_loc_added: '已定位——已加入距离',
    hp_urgent: '🚨 紧急', hp_recommended: '✓ 推荐科室', hp_call120: '若为紧急情况，请立即拨打 120。',
    hp_best_match: '#{n} 最匹配', hp_match_cap: '匹配', hp_strong_in: '{sp} 专科突出', hp_national_leader: '{sp} 全国领先', hp_grade_3a: '三级甲等', hp_rated: '评分 {r}/5', hp_reviews: '{n} 条评价', hp_reviews_paren: '（{n} 条评价）',
    hp_km_you: '距你 {km} 公里', hp_km: '{km} 公里', hp_speaks: '可用你的语言沟通', hp_emergency: '急诊能力强', hp_navigate: '导航 →',
    hp_no_hosp: '未找到医院。试试更宽泛的症状或科室。', hp_waking_t: '推荐服务正在唤醒', hp_waking_d: '同时先显示全部医院，请稍后重试。',
    nv_eyebrow: '导航', nv_title: '导航就医', nv_lede: '在实时地图上查看画出的路线与转向步骤——或一键交给手机地图 App。',
    nv_hospital: '医院', nv_mode: '出行方式', nv_walking: '🚶 步行', nv_driving: '🚗 驾车', nv_transit: '🚇 公交', nv_use_loc: '📍 用我的位置', nv_locating: '📍 定位中…',
    nv_map_loading: '地图加载中…', nv_origin_default: '📍 起点：北京市中心（默认）· 点“用我的位置”。', nv_origin_gps: '📍 起点：你的当前位置',
    nv_map_unavail: '实时地图不可用。', nv_map_no_js: '未配置高德 JS Key。', nv_map_no_backend: '未配置后端。', nv_map_hint: '用下方按钮在地图 App 中打开。',
    nv_open_in: '用地图App打开：', nv_planning: '规划路线中…', nv_turn_by_turn: '🧭 转向步骤', nv_arrive: '到达 {name}', nv_you: '我',
    nv_fallback: '页面内转向步骤需要高德安全密钥。当前距离/时间为直线估算——请用上方按钮在地图 App 中导航。',
    nv_dist: '距离', nv_straight: '直线距离', nv_duration: '用时', nv_est: '估算用时', nv_mode_label: '方式', nv_walk: '步行', nv_drive: '驾车', nv_transit_txt: '公交', nv_using_loc: '正在使用你的位置',
    md_eyebrow: '用药', md_title: '用药与提醒', md_lede: '在双语药品库中查询药物，再设置提醒时间保存到个人清单。',
    md_add: '添加用药', md_from_lib: '从药品库选择', md_choose: '— 选择 —', md_custom: '或自定义名称', md_custom_ph: '例如：维生素 D', md_dosage: '剂量 / 用法', md_dosage_ph: '例如：每天早上 1 片',
    md_times: '提醒时间', md_notes: '备注', md_notes_ph: '饭后服用，避免与乳制品同服……', md_save: '保存到我的清单', md_login_req: '需要登录。记录绑定到你的账户。',
    md_drug_info: '药品信息', md_pick: '从药品库选择一种药，查看剂量、警告与副作用。', md_rx: '处方', md_otc: '非处方',
    md_dosage_h: '用法用量', md_warnings_h: '警告', md_side_h: '副作用', md_my_list: '我的用药清单', md_list_signin: '登录后即可保存用药与提醒。', md_list_empty: '尚未保存任何用药。',
    md_saved: '已保存到清单', md_removed: '已删除', md_remove: '删除', md_pick_first: '请从药品库选择一种药', md_login_first: '请先登录', md_load_fail: '无法加载你的清单。',
    ac_eyebrow: '我的账户', ac_title: '账户与隐私', ac_lede: '身份信息可选。敏感医疗文本以最小化方式留存——你可随时导出或清除全部数据。',
    ac_signin_p: '登录后查看个人资料、已保存的翻译与用药。', ac_signin_btn: '登录 / 注册', ac_member_since: '注册于 {date}',
    ac_your_data: '你的数据', ac_data_desc: '导出与你账户关联的全部数据（JSON），或永久删除个人记录（保留登录账号）。',
    ac_export: '⬇︎ 导出我的全部数据', ac_wipe: '🗑 删除全部个人记录', ac_exported: '已导出（见下方）', ac_wipe_confirm: '删除你的全部翻译、用药、分诊与反馈记录？登录账号保留。此操作不可撤销。', ac_wiped: '已删除全部个人记录',
    ac_feedback: '反馈', ac_category: '类别', ac_cat_translation: '翻译', ac_cat_hospital: '医院', ac_cat_navigation: '导航', ac_cat_medication: '用药', ac_cat_feature: '功能建议', ac_cat_other: '其他',
    ac_rating: '评分（1–5）', ac_your_msg: '你的留言', ac_msg_ph: '告诉我们可以如何改进……', ac_submit: '提交反馈', ac_fb_thanks: '感谢！已收到你的反馈。', ac_fb_write: '请填写留言', ac_fb_sent: '反馈已发送',
    footer_a: 'TransMed · 跨文化医疗 AI——仅供演示。紧急情况请拨打 120 或前往最近急诊。', footer_b: '关键决策必须经执业医师确认。',
    loc_prefix: '定位：{msg}', ui_translating: '正在翻译界面…', ui_ready: '语言已就绪', please_login: '请先登录'
  };

  // 其余 10 种语言的预生成字典（构建期由 gen_i18n.py 写入 i18n_all.json 后注入；EN/ZH 见上 STR_EN/STR_ZH）
  var I18N_EXTRA = __I18N_EXTRA__;

  var curLang = '';
  try { curLang = localStorage.getItem(LANG_KEY) || ''; } catch (e) {}
  var DICT = {};

  function buildDict(lang) {
    var d = {}, k;
    for (k in STR_EN) d[k] = STR_EN[k];
    if (lang === 'zh') { for (k in STR_ZH) d[k] = STR_ZH[k]; }
    else if (lang !== 'en' && I18N_EXTRA[lang]) { var e = I18N_EXTRA[lang]; for (k in e) if (e[k]) d[k] = e[k]; }
    return d;
  }
  function t(key, vars) {
    var s = (DICT && DICT[key] != null) ? DICT[key] : (STR_EN[key] != null ? STR_EN[key] : key);
    if (vars) { for (var v in vars) s = s.replace(new RegExp('\\{' + v + '\\}', 'g'), vars[v]); }
    return s;
  }
  function applyStatic() {
    document.documentElement.lang = curLang || 'en';
    document.documentElement.dir = (curLang === 'ar') ? 'rtl' : 'ltr';
    qsa('[data-i18n]').forEach(function (el) { el.textContent = t(el.getAttribute('data-i18n')); });
    qsa('[data-i18n-ph]').forEach(function (el) { el.setAttribute('placeholder', t(el.getAttribute('data-i18n-ph'))); });
    var lbl = byId('btn-lang-label');
    if (lbl) { var L = LANGS.filter(function (x) { return x.code === (curLang || 'en'); })[0]; lbl.textContent = L ? L.short : 'EN'; }
  }
  function applyI18n() { applyStatic(); reRenderDynamic(); }

  function setLang(lang) {
    curLang = lang; try { localStorage.setItem(LANG_KEY, lang); } catch (e) {}
    DICT = buildDict(lang); applyI18n();   // 全部 12 种语言已预生成内嵌 → 即时切换，无需联网
  }

  // ---- 导航转向步骤：用高德结构化字段（方向 / 道路 / 主辅动作）即时本地化 ----
  // 高德 Driving/Walking 每个 step 提供 orientation(8 向) / road(路名) / action(主要动作) /
  // assistant_action(辅助动作)，皆为有限枚举；据此重建指令，绝不切分路名字符串，
  // 因此杜绝「海北路 → 海 north 路」这类污染。动作词查不到则省略（宁可少说，不乱拼）。
  var NAV_LEX = {
    en: { walk: 'Walk', drive: 'Drive', take: 'Take ', m: ' m', km: ' km', along: ' along ', arrive: 'Arrive at the destination',
      dir: { '东': 'east', '南': 'south', '西': 'west', '北': 'north', '东北': 'northeast', '东南': 'southeast', '西北': 'northwest', '西南': 'southwest' },
      act: { '左转': 'turn left', '右转': 'turn right', '直行': 'continue straight', '掉头': 'make a U-turn', '靠左': 'keep left', '靠右': 'keep right', '向左前方行驶': 'bear left', '向右前方行驶': 'bear right', '减速行驶': 'slow down', '到达目的地': 'arrive at the destination', '到达途经地': 'reach the waypoint', '进入主路': 'merge onto the main road', '进入辅路': 'take the side road', '进入匝道': 'take the ramp', '进入环岛': 'enter the roundabout', '驶出环岛': 'exit the roundabout' } },
    ja: { walk: '歩く', drive: '運転', take: '乗車 ', m: ' m', km: ' km', along: ' に沿って', arrive: '目的地に到着',
      dir: { '东': '東', '南': '南', '西': '西', '北': '北', '东北': '北東', '东南': '南東', '西北': '北西', '西南': '南西' },
      act: { '左转': '左折', '右转': '右折', '直行': '直進', '掉头': 'Uターン', '靠左': '左寄り', '靠右': '右寄り', '向左前方行驶': '斜め左前方へ', '向右前方行驶': '斜め右前方へ', '减速行驶': '減速', '到达目的地': '目的地に到着', '到达途经地': '経由地に到着', '进入主路': '本線に合流', '进入辅路': '側道に入る', '进入匝道': 'ランプに入る', '进入环岛': 'ロータリーに入る', '驶出环岛': 'ロータリーを出る' } },
    ko: { walk: '도보', drive: '운전', take: '탑승 ', m: ' m', km: ' km', along: ' 을 따라', arrive: '목적지 도착',
      dir: { '东': '동', '南': '남', '西': '서', '北': '북', '东北': '북동', '东南': '남동', '西北': '북서', '西南': '남서' },
      act: { '左转': '좌회전', '右转': '우회전', '直行': '직진', '掉头': '유턴', '靠左': '좌측 유지', '靠右': '우측 유지', '向左前方行驶': '좌측 전방으로', '向右前方行驶': '우측 전방으로', '减速行驶': '감속', '到达目的地': '목적지 도착', '到达途经地': '경유지 도착', '进入主路': '본선 합류', '进入辅路': '측도 진입', '进入匝道': '램프 진입', '进入环岛': '회전교차로 진입', '驶出环岛': '회전교차로 진출' } },
    fr: { walk: 'Marcher', drive: 'Conduire', take: 'Prendre ', m: ' m', km: ' km', along: ' le long de ', arrive: 'Arriver à destination',
      dir: { '东': 'est', '南': 'sud', '西': 'ouest', '北': 'nord', '东北': 'nord-est', '东南': 'sud-est', '西北': 'nord-ouest', '西南': 'sud-ouest' },
      act: { '左转': 'tourner à gauche', '右转': 'tourner à droite', '直行': 'continuer tout droit', '掉头': 'faire demi-tour', '靠左': 'rester à gauche', '靠右': 'rester à droite', '向左前方行驶': 'serrer à gauche', '向右前方行驶': 'serrer à droite', '减速行驶': 'ralentir', '到达目的地': 'arriver à destination', '到达途经地': 'atteindre le point de passage', '进入主路': "rejoindre l'axe principal", '进入辅路': 'prendre la contre-allée', '进入匝道': "prendre la bretelle", '进入环岛': 'entrer dans le rond-point', '驶出环岛': 'sortir du rond-point' } },
    de: { walk: 'Gehen', drive: 'Fahren', take: 'Nehmen ', m: ' m', km: ' km', along: ' entlang ', arrive: 'Ziel erreichen',
      dir: { '东': 'Osten', '南': 'Süden', '西': 'Westen', '北': 'Norden', '东北': 'Nordosten', '东南': 'Südosten', '西北': 'Nordwesten', '西南': 'Südwesten' },
      act: { '左转': 'links abbiegen', '右转': 'rechts abbiegen', '直行': 'geradeaus weiter', '掉头': 'wenden', '靠左': 'links halten', '靠右': 'rechts halten', '向左前方行驶': 'halb links', '向右前方行驶': 'halb rechts', '减速行驶': 'langsamer fahren', '到达目的地': 'Ziel erreichen', '到达途经地': 'Zwischenziel erreichen', '进入主路': 'auf die Hauptstraße auffahren', '进入辅路': 'auf die Nebenstraße', '进入匝道': 'auf die Auffahrt', '进入环岛': 'in den Kreisverkehr', '驶出环岛': 'Kreisverkehr verlassen' } },
    es: { walk: 'Caminar', drive: 'Conducir', take: 'Tomar ', m: ' m', km: ' km', along: ' por ', arrive: 'Llegar al destino',
      dir: { '东': 'este', '南': 'sur', '西': 'oeste', '北': 'norte', '东北': 'noreste', '东南': 'sureste', '西北': 'noroeste', '西南': 'suroeste' },
      act: { '左转': 'girar a la izquierda', '右转': 'girar a la derecha', '直行': 'seguir recto', '掉头': 'dar la vuelta', '靠左': 'mantenerse a la izquierda', '靠右': 'mantenerse a la derecha', '向左前方行驶': 'ligeramente a la izquierda', '向右前方行驶': 'ligeramente a la derecha', '减速行驶': 'reducir la velocidad', '到达目的地': 'llegar al destino', '到达途经地': 'llegar al punto de paso', '进入主路': 'incorporarse a la vía principal', '进入辅路': 'tomar la vía de servicio', '进入匝道': 'tomar la rampa', '进入环岛': 'entrar en la rotonda', '驶出环岛': 'salir de la rotonda' } },
    it: { walk: 'Camminare', drive: 'Guidare', take: 'Prendere ', m: ' m', km: ' km', along: ' lungo ', arrive: 'Arrivare a destinazione',
      dir: { '东': 'est', '南': 'sud', '西': 'ovest', '北': 'nord', '东北': 'nord-est', '东南': 'sud-est', '西北': 'nord-ovest', '西南': 'sud-ovest' },
      act: { '左转': 'svoltare a sinistra', '右转': 'svoltare a destra', '直行': 'proseguire dritto', '掉头': 'fare inversione', '靠左': 'tenere la sinistra', '靠右': 'tenere la destra', '向左前方行驶': 'leggermente a sinistra', '向右前方行驶': 'leggermente a destra', '减速行驶': 'rallentare', '到达目的地': 'arrivare a destinazione', '到达途经地': 'raggiungere la tappa', '进入主路': 'immettersi sulla strada principale', '进入辅路': 'prendere la complanare', '进入匝道': 'prendere la rampa', '进入环岛': 'entrare nella rotonda', '驶出环岛': 'uscire dalla rotonda' } },
    ru: { walk: 'Идти', drive: 'Ехать', take: 'Сесть на ', m: ' м', km: ' км', along: ' по ', arrive: 'Прибыть в пункт назначения',
      dir: { '东': 'на восток', '南': 'на юг', '西': 'на запад', '北': 'на север', '东北': 'на северо-восток', '东南': 'на юго-восток', '西北': 'на северо-запад', '西南': 'на юго-запад' },
      act: { '左转': 'повернуть налево', '右转': 'повернуть направо', '直行': 'прямо', '掉头': 'развернуться', '靠左': 'держаться левее', '靠右': 'держаться правее', '向左前方行驶': 'левее', '向右前方行驶': 'правее', '减速行驶': 'снизить скорость', '到达目的地': 'прибыть в пункт назначения', '到达途经地': 'прибыть в промежуточную точку', '进入主路': 'выехать на главную дорогу', '进入辅路': 'на дублёр', '进入匝道': 'на съезд', '进入环岛': 'на круговое движение', '驶出环岛': 'съехать с кольца' } },
    pt: { walk: 'Caminhar', drive: 'Conduzir', take: 'Apanhar ', m: ' m', km: ' km', along: ' ao longo de ', arrive: 'Chegar ao destino',
      dir: { '东': 'este', '南': 'sul', '西': 'oeste', '北': 'norte', '东北': 'nordeste', '东南': 'sudeste', '西北': 'noroeste', '西南': 'sudoeste' },
      act: { '左转': 'virar à esquerda', '右转': 'virar à direita', '直行': 'seguir em frente', '掉头': 'fazer inversão', '靠左': 'manter-se à esquerda', '靠右': 'manter-se à direita', '向左前方行驶': 'ligeiramente à esquerda', '向右前方行驶': 'ligeiramente à direita', '减速行驶': 'reduzir a velocidade', '到达目的地': 'chegar ao destino', '到达途经地': 'chegar ao ponto de passagem', '进入主路': 'entrar na via principal', '进入辅路': 'tomar a via secundária', '进入匝道': 'tomar a rampa', '进入环岛': 'entrar na rotunda', '驶出环岛': 'sair da rotunda' } },
    ar: { walk: 'سِر', drive: 'قُد', take: 'استقل ', m: ' م', km: ' كم', along: ' على طول ', arrive: 'الوصول إلى الوجهة',
      dir: { '东': 'شرقاً', '南': 'جنوباً', '西': 'غرباً', '北': 'شمالاً', '东北': 'شمال شرق', '东南': 'جنوب شرق', '西北': 'شمال غرب', '西南': 'جنوب غرب' },
      act: { '左转': 'انعطف يساراً', '右转': 'انعطف يميناً', '直行': 'استمر مستقيماً', '掉头': 'استدر', '靠左': 'الزم اليسار', '靠右': 'الزم اليمين', '向左前方行驶': 'يساراً قليلاً', '向右前方行驶': 'يميناً قليلاً', '减速行驶': 'خفّف السرعة', '到达目的地': 'الوصول إلى الوجهة', '到达途经地': 'الوصول إلى نقطة العبور', '进入主路': 'ادخل الطريق الرئيسي', '进入辅路': 'ادخل الطريق الجانبي', '进入匝道': 'ادخل المنحدر', '进入环岛': 'ادخل الدوار', '驶出环岛': 'اخرج من الدوار' } },
    hi: { walk: 'चलें', drive: 'ड्राइव करें', take: 'लें ', m: ' मी', km: ' किमी', along: ' के साथ ', arrive: 'गंतव्य पर पहुँचें',
      dir: { '东': 'पूर्व', '南': 'दक्षिण', '西': 'पश्चिम', '北': 'उत्तर', '东北': 'उत्तर-पूर्व', '东南': 'दक्षिण-पूर्व', '西北': 'उत्तर-पश्चिम', '西南': 'दक्षिण-पश्चिम' },
      act: { '左转': 'बाएँ मुड़ें', '右转': 'दाएँ मुड़ें', '直行': 'सीधे चलें', '掉头': 'यू-टर्न लें', '靠左': 'बाएँ रहें', '靠右': 'दाएँ रहें', '向左前方行驶': 'थोड़ा बाएँ', '向右前方行驶': 'थोड़ा दाएँ', '减速行驶': 'गति धीमी करें', '到达目的地': 'गंतव्य पर पहुँचें', '到达途经地': 'मार्गबिंदु पर पहुँचें', '进入主路': 'मुख्य मार्ग पर आएँ', '进入辅路': 'सर्विस रोड लें', '进入匝道': 'रैंप लें', '进入环岛': 'चक्र में प्रवेश करें', '驶出环岛': 'चक्र से बाहर निकलें' } }
  };
  // 把高德主/辅动作（如 "右转进入主路"）映射为目标语；优先整段匹配，否则逐枚举词替换。
  function localizeAction(L, phrase) {
    if (!phrase) return '';
    phrase = phrase.replace(/行走/g, '行驶').replace(/(右前方|左前方|正前方|前方)/g, ''); // 归一 + 去掉方位前缀
    if (!phrase) return '';
    if (L.act[phrase]) return L.act[phrase];
    var keys = Object.keys(L.act).sort(function (a, b) { return b.length - a.length; });
    var out = phrase, hit = false;
    keys.forEach(function (k) { if (out.indexOf(k) >= 0) { out = out.split(k).join(' ' + L.act[k] + ' '); hit = true; } });
    return hit ? out.replace(/\s+/g, ' ').trim() : '';
  }
  // 兜底：高德未给结构化字段时，安全解析中文指令（提取路名但绝不切分它）。
  function parseZhStep(L, s) {
    var zh = (s && s.zh) || '';
    if (!zh) return '';
    var m = zh.match(/^(?:沿(.+?))?(?:向([东南西北]{1,2})(?:方向)?)?(步行|行驶|骑行)([\d.]+)(公里|千米|米)(.*)$/);
    if (m) {
      var road = m[1], dir = m[2], verb = m[3], dist = m[4], unit = m[5], act = m[6];
      var out = (verb === '步行' ? L.walk : L.drive) + ' ' + dist + (unit === '米' ? L.m : L.km);
      if (L.dir[dir]) out += ' ' + L.dir[dir];
      if (road) out += L.along + road; // 路名保持中文
      var a = localizeAction(L, act);
      if (a) out += ', ' + a;
      return out.replace(/\s+/g, ' ').trim();
    }
    var a2 = localizeAction(L, zh); // 纯动作类（如"到达目的地""左转进入主路"）
    return a2 || zh;                // 实在解析不了，原样中文，不污染
  }
  // s: 结构化步骤 { walk, d(米), ori(中文方向), road(中文路名), act, ast, line, zh }
  function buildStepText(s, lang) {
    if (!s) return '';
    if (lang === 'zh') return s.zh || '';
    var L = NAV_LEX[lang] || NAV_LEX.en;
    if (s.line) { // 公交/地铁线路：线路名保持中文
      var seg = L.take + s.line;
      if (s.d) seg += ' (' + (s.d > 1000 ? (s.d / 1000).toFixed(1) + L.km : Math.round(s.d) + L.m) + ')';
      return seg.trim();
    }
    // 高德结构化字段（方向/路名/主辅动作）全缺时，回退到安全解析
    if (!s.ori && !s.road && !s.act && !s.ast) return parseZhStep(L, s);
    var distTxt = s.d ? (s.d > 1000 ? (s.d / 1000).toFixed(1) + L.km : Math.round(s.d) + L.m) : '';
    var head = (s.walk ? L.walk : L.drive) + (distTxt ? ' ' + distTxt : '');
    if (s.ori && L.dir[s.ori]) head += ' ' + L.dir[s.ori];
    if (s.road) head += L.along + s.road; // 路名始终保持中文
    var tail = [localizeAction(L, s.act), localizeAction(L, s.ast)].filter(Boolean).join(', ');
    if (tail) head += ', ' + tail;
    return head.replace(/\s+/g, ' ').trim();
  }

  // language picker (first visit) + switcher
  function buildLangGrid() {
    var g = byId('lang-grid'); if (!g) return;
    g.innerHTML = LANGS.map(function (L) {
      return '<button class="lang-btn' + (L.code === curLang ? ' active' : '') + '" data-lang="' + L.code + '"><span class="lang-native">' + esc(L.name) + '</span><span class="lang-code">' + L.code.toUpperCase() + '</span></button>';
    }).join('');
    qsa('.lang-btn', g).forEach(function (b) {
      on(b, 'click', function () { byId('lang-modal').classList.add('hidden'); setLang(b.getAttribute('data-lang')); });
    });
  }
  function showLangPicker() { buildLangGrid(); var m = byId('lang-modal'); if (m) m.classList.remove('hidden'); }

  /* ============================== shared geo ============================== */
  var _userLoc = null;
  function haversineKm(a, b) {
    if (!a || !b) return null;
    var R = 6371, toRad = function (d) { return d * Math.PI / 180; };
    var dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng);
    var s = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(s));
  }
  function getLocation(onOk, onErr) {
    if (!navigator.geolocation) { onErr && onErr('Geolocation unavailable'); return; }
    navigator.geolocation.getCurrentPosition(function (p) {
      _userLoc = { lng: p.coords.longitude, lat: p.coords.latitude };
      Nav.setOriginFromGps(_userLoc); onOk && onOk(_userLoc);
    }, function (err) { onErr && onErr(err.message || 'denied'); }, { timeout: 15000, enableHighAccuracy: true });
  }

  /* ============================== fallback hospital data ============================== */
  // 兜底医院名单（后端/高德不可用时用于医院页与导航下拉）。覆盖各大专科的北京三甲医院。
  // 高德可用时会被真实 POI 结果替换；坐标为 GCJ-02 近似值，仅用于离线兜底。
  var FALLBACK_HOSPITALS = [
    { id: 'pumch', name: 'Peking Union Medical College Hospital', name_zh: '北京协和医院', address_zh: '东城区帅府园1号', phone: '+86 10 6915 6114', rating: 4.9, grade: '三级甲等', specialties: ['General Medicine', 'Rheumatology', 'Endocrinology', 'OB/GYN'], lng: 116.41513, lat: 39.912815 },
    { id: 'fuwai', name: 'Fuwai Hospital', name_zh: '中国医学科学院阜外医院', address_zh: '西城区北礼士路167号', phone: '+86 10 8839 8866', rating: 4.8, grade: '三级甲等', specialties: ['Cardiology', 'Cardiovascular Surgery'], lng: 116.3668, lat: 39.9300 },
    { id: 'anzhen', name: 'Beijing Anzhen Hospital', name_zh: '首都医科大学附属北京安贞医院', address_zh: '朝阳区安贞路2号', phone: '+86 10 6445 6655', rating: 4.6, grade: '三级甲等', specialties: ['Cardiology', 'Cardiovascular Surgery'], lng: 116.3985, lat: 39.9740 },
    { id: 'tiantan', name: 'Beijing Tiantan Hospital', name_zh: '首都医科大学附属北京天坛医院', address_zh: '丰台区南四环西路119号', phone: '+86 10 5997 8001', rating: 4.7, grade: '三级甲等', specialties: ['Neurosurgery', 'Neurology'], lng: 116.3360, lat: 39.8350 },
    { id: 'xuanwu', name: 'Xuanwu Hospital', name_zh: '首都医科大学宣武医院', address_zh: '西城区长椿街45号', phone: '+86 10 8319 8277', rating: 4.6, grade: '三级甲等', specialties: ['Neurology', 'Neurosurgery', 'Geriatrics'], lng: 116.3570, lat: 39.8895 },
    { id: 'cancer', name: 'Cancer Hospital CAMS', name_zh: '中国医学科学院肿瘤医院', address_zh: '朝阳区潘家园南里17号', phone: '+86 10 8778 8800', rating: 4.7, grade: '三级甲等', specialties: ['Oncology', 'Surgical Oncology'], lng: 116.4610, lat: 39.8750 },
    { id: 'tongren', name: 'Beijing Tongren Hospital', name_zh: '首都医科大学附属北京同仁医院', address_zh: '东城区东交民巷1号', phone: '+86 10 5826 9988', rating: 4.6, grade: '三级甲等', specialties: ['Ophthalmology', 'ENT'], lng: 116.417224, lat: 39.902721 },
    { id: 'jst', name: 'Beijing Jishuitan Hospital', name_zh: '北京积水潭医院', address_zh: '西城区新街口东街31号', phone: '+86 10 5851 6688', rating: 4.6, grade: '三级甲等', specialties: ['Orthopedics', 'Sports Medicine'], lng: 116.3710, lat: 39.9430 },
    { id: 'children', name: "Beijing Children's Hospital", name_zh: '首都医科大学附属北京儿童医院', address_zh: '西城区南礼士路56号', phone: '+86 10 5961 6161', rating: 4.5, grade: '三级甲等', specialties: ['Pediatrics', 'Pediatric Surgery'], lng: 116.3530, lat: 39.9170 },
    { id: 'pku-people', name: "Peking University People's Hospital", name_zh: '北京大学人民医院', address_zh: '西城区西直门南大街11号', phone: '+86 10 8832 6666', rating: 4.6, grade: '三级甲等', specialties: ['Hematology', 'Trauma Surgery', 'Cardiology'], lng: 116.3530, lat: 39.9380 },
    { id: 'cyhospital', name: 'China-Japan Friendship Hospital', name_zh: '中日友好医院', address_zh: '朝阳区樱花园东街2号', phone: '+86 10 8420 5566', rating: 4.5, grade: '三级甲等', specialties: ['Respiratory', 'Pulmonary / Respiratory', 'Dermatology'], lng: 116.4260, lat: 39.9740 },
    { id: 'bjh', name: 'Beijing Hospital', name_zh: '北京医院', address_zh: '东城区东单大华路1号', phone: '+86 10 8513 2266', rating: 4.6, grade: '三级甲等', specialties: ['Geriatrics', 'Cardiology', 'Endocrinology'], lng: 116.415057, lat: 39.903772 },
    { id: '301', name: 'PLA General Hospital (301)', name_zh: '中国人民解放军总医院', address_zh: '海淀区复兴路28号', phone: '+86 10 6693 7329', rating: 4.7, grade: '三级甲等', specialties: ['Trauma Surgery', 'Oncology', 'Orthopedics', 'Nephrology'], lng: 116.2875, lat: 39.9067 },
    { id: 'ufh', name: 'Beijing United Family Hospital', name_zh: '北京和睦家医院', address_zh: '朝阳区将台路2号', phone: '+86 10 5927 7000', rating: 4.8, grade: '外资综合', specialties: ['Family Medicine', 'Pediatrics', 'Emergency', 'OB/GYN'], lng: 116.4677, lat: 39.9754 }
  ];

  /* ============================================================
     View switching + scroll reveal + topbar
     ============================================================ */
  var navLinks = qsa('.nav-link'), views = qsa('.view'), _viewInit = {};
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

  var _io = null;
  if ('IntersectionObserver' in window) {
    _io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-visible'); _io.unobserve(en.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
  }
  function revealScan() { qsa('.reveal:not(.is-visible)').forEach(function (el) { if (_io) _io.observe(el); else el.classList.add('is-visible'); }); }

  var topbar = byId('topbar');
  function onScroll() { if (topbar) topbar.classList.toggle('scrolled', window.scrollY > 8); }
  on(window, 'scroll', onScroll); onScroll();

  // re-render JS-built content after a language change
  function reRenderDynamic() {
    try { if (_lastStats) renderStats(_lastStats, false); } catch (e) {}
    try { if (_lastTranslation) showTranslation(_lastTranslation.translated, _lastTranslation.confidence, _lastTranslation.terms, _lastTranslation.engine, _lastTranslation.rag); } catch (e) {}
    try { loadMyTranslations(true); } catch (e) {}
    try { if (_lastHospitals && _lastHospitals.length && byId('hospital-list') && byId('hospital-list').children.length) { renderTriageBanner(); renderHospitals(_lastHospitals, _lastRanked, _lastMax); } } catch (e) {}
    try { Nav.relabel(); } catch (e) {}
    try { Med.relabel(); } catch (e) {}
    try { Account.render(); } catch (e) {}
  }

  /* ============================================================
     Translate
     ============================================================ */
  (function initLangSelectors() {
    [byId('src-lang'), byId('tgt-lang')].forEach(function (sel, i) {
      if (!sel) return; sel.innerHTML = '';
      LANGS.forEach(function (l) { var o = document.createElement('option'); o.value = l.code; o.textContent = l.name; sel.appendChild(o); });
      sel.value = i === 0 ? 'en' : 'zh';
    });
  })();
  on(byId('swap-lang'), 'click', function () { var s = byId('src-lang'), t2 = byId('tgt-lang'); if (s && t2) { var v = s.value; s.value = t2.value; t2.value = v; } });

  var _lastTranslation = null;
  function showTranslation(translated, confidence, terms, engine, ragCtx) {
    var out = byId('tgt-text'); if (!out) return;
    _lastTranslation = { translated: translated, confidence: confidence, terms: terms, engine: engine, rag: ragCtx };
    out.textContent = translated; out.classList.remove('placeholder');
    var conf = Math.max(0, Math.min(100, Math.round(confidence)));
    var cv = byId('conf-value'); if (cv) cv.textContent = String(conf);
    var cf = byId('conf-fill'); if (cf) cf.style.width = Math.max(8, conf) + '%';
    var riskKey = conf >= 85 ? 'low' : conf >= 65 ? 'medium' : conf >= 45 ? 'high' : 'critical';
    var rv = byId('risk-value'); if (rv) rv.textContent = riskKey;
    var el = byId('engine-label');
    if (el) {
      var online = engine && /groq|online|ai|api/i.test(engine) && engine !== 'offline';
      el.textContent = (online ? '● ' + t('tr_online') : '○ ' + t('tr_offline')) + ' · ' + engine;
      el.className = 'engine-label ' + (online ? 'online' : 'offline');
    }
    var adv = byId('conf-advice');
    if (adv) adv.textContent = conf >= 85 ? t('tr_advice_low') : conf >= 65 ? t('tr_advice_med') : t('tr_advice_high');
    var bc = byId('confidence-bar'); if (bc) bc.classList.remove('hidden');
    var tb = byId('matched-terms');
    if (tb) tb.innerHTML = (terms && terms.length) ? '<div class="muted small" style="margin-bottom:6px;">' + t('tr_terms_label') + '</div>' + terms.map(function (x) { return '<span class="chip static">' + esc(x) + '</span>'; }).join('') : '';
    var rb = byId('rag-reference');
    if (rb) rb.innerHTML = (ragCtx && ragCtx.length) ? '<details style="margin-top:12px;"><summary class="muted small" style="cursor:pointer;">📚 ' + t('tr_ref_label', { n: ragCtx.length }) + '</summary><ul class="muted small" style="margin:8px 0 0 18px;">' + ragCtx.slice(0, 5).map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul></details>' : '';
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
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> ' + t('tr_translating'); }
    var done = function () { if (btn) { btn.disabled = false; btn.textContent = t('tr_btn'); } };
    api('/api/translate', { method: 'POST', body: { text: txt, source: src, target: tgt }, auth: true, timeout: 18000 })
      .then(function (d) {
        var translated = d.translated || d.translated_text || '';
        var conf = num(d.confidence); if (conf == null) conf = 60; if (conf <= 1) conf *= 100;
        showTranslation(translated, conf, d.matched_terms || d.medical_terms || [], d.engine || 'api', d.rag_context || []);
        done(); loadMyTranslations();
      })
      .catch(function () { var f = offlineTranslate(txt, src, tgt); showTranslation(f.translated, f.confidence, f.matched, 'offline', []); done(); });
  });
  on(byId('btn-confirm-risk'), 'click', function () { this.classList.add('hidden'); toast(t('tr_ack_done'), 'ok'); });

  (function initSymptomChips() {
    var box = byId('symptom-chips'); if (!box) return;
    ['headache', 'chest pain', 'high fever', 'cough', 'stomach pain', 'shortness of breath', 'dizziness', 'rash', 'back pain', 'sore throat'].forEach(function (s) {
      var b = document.createElement('button'); b.className = 'chip'; b.type = 'button'; b.textContent = s;
      on(b, 'click', function () { var ta = byId('src-text'); if (ta) { ta.value = 'I have ' + s + ' for 2 days.'; ta.focus(); } });
      box.appendChild(b);
    });
  })();

  var _lastLogs = null;
  function loadMyTranslations(useCache) {
    var box = byId('my-translations'); if (!box) return;
    if (!token) { box.innerHTML = '<div class="empty-state">' + t('tr_hist_signin') + '</div>'; return; }
    var render = function (rows) {
      _lastLogs = rows;
      if (!rows || !rows.length) { box.innerHTML = '<div class="empty-state">' + t('tr_hist_empty') + '</div>'; return; }
      box.innerHTML = rows.slice(0, 8).map(function (r) {
        return '<div class="list-item"><div><strong>' + esc(trim(r.original, 60)) + '</strong><div class="meta">→ ' + esc(trim(r.translated, 70)) + '</div><div class="meta">' + esc(r.source) + '→' + esc(r.target) + ' · ' + t('tr_conf_line', { n: Math.round(r.confidence || 0), risk: esc(r.risk_level || '') }) + '</div></div></div>';
      }).join('');
    };
    if (useCache && _lastLogs) { render(_lastLogs); return; }
    api('/api/translate/logs', { auth: true }).then(render).catch(function () { box.innerHTML = '<div class="empty-state">' + t('tr_hist_fail') + '</div>'; });
  }

  /* ============================================================
     Home stats
     ============================================================ */
  var _lastStats = null;
  function animateCount(el, to) {
    var dur = 1100, start = null;
    function tick(ts) { if (start == null) start = ts; var p = Math.min(1, (ts - start) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))).toLocaleString(); if (p < 1) requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  }
  function renderStats(d, animate) {
    _lastStats = d; var box = byId('home-stats'); if (!box) return;
    var cards = [{ v: 12, k: 'st_langs' }, { v: d.medical_terms || 2428, k: 'st_terms' }, { v: d.hospitals || 6, k: 'st_hosp' }, { v: d.triage_rules || 55, k: 'st_rules' }, { v: d.translations || 0, k: 'st_trans' }];
    box.innerHTML = cards.map(function (c) { return '<div class="stat"><div class="stat-num" data-to="' + c.v + '">' + (animate === false ? c.v.toLocaleString() : '0') + '</div><div class="stat-label">' + t(c.k) + '</div></div>'; }).join('');
    if (animate === false) return;
    var run = function () { qsa('.stat-num', box).forEach(function (el) { animateCount(el, parseInt(el.getAttribute('data-to'), 10) || 0); }); };
    if ('IntersectionObserver' in window) { var ob = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { run(); ob.disconnect(); } }); }, { threshold: 0.3 }); ob.observe(box); } else run();
  }
  function loadStats() { renderStats({}); api('/api/stats').then(function (d) { renderStats(d); }).catch(function () {}); }

  /* ============================================================
     Hospitals: triage + recommendation
     ============================================================ */
  var _lastHospitals = [], _lastRanked = false, _lastMax = 0, _sortMode = 'match', _hospReq = 0, _lastTriage = null;

  function cleanReasons(rec, h, distKm) {
    var out = [], seen = {};
    function push(type, text) { if (text && !seen[text]) { seen[text] = 1; out.push({ type: type, text: text }); } }
    // 权威信号优先：全国专科领先 → 三甲等级 → 命中专科 → 评分 → 距离
    (rec && rec.leader_specialties || []).slice(0, 2).forEach(function (sp) { push('spec', t('hp_national_leader', { sp: sp })); });
    (rec && rec.matched_specialties || []).slice(0, 3).forEach(function (sp) { push('spec', t('hp_strong_in', { sp: sp })); });
    if (h.rating) push('ok', t('hp_rated', { r: num(h.rating).toFixed(1) }));
    if (distKm != null) push('ok', t('hp_km_you', { km: distKm.toFixed(1) }));
    (rec && rec.reasons || []).forEach(function (r) { if (/speaks your language/i.test(r)) push('ok', t('hp_speaks')); else if (/emergency/i.test(r)) push('ok', t('hp_emergency')); });
    return out.slice(0, 5);
  }
  function gradeLabel(g) { return (String(g).indexOf('三级甲等') >= 0 || String(g).indexOf('三甲') >= 0) ? t('hp_grade_3a') : esc(g); }
  function starStr(r) { var full = Math.floor(r), half = (r - full) >= 0.5 ? 1 : 0, empty = 5 - full - half; return '★'.repeat(full) + (half ? '⯨' : '') + '☆'.repeat(Math.max(0, empty)); }
  function hospitalCard(h, idx, ranked, maxScore) {
    var name = esc(h.name || h.name_zh || 'Hospital');
    var zh = (h.name_zh && h.name_zh !== h.name) ? '<span class="zh"> · ' + esc(h.name_zh) + '</span>' : '';
    var rating = num(h.rating), dist = (_userLoc && typeof h.lng === 'number') ? haversineKm(_userLoc, h) : null, ring = '';
    if (ranked && h.recommendation) {
      var pct = maxScore ? Math.max(10, Math.min(100, Math.round(h.recommendation.score / maxScore * 100))) : 60;
      ring = '<div class="score-ring" style="--p:' + pct + '"><div class="score-inner"><div class="score-val">' + pct + '</div><div class="score-cap">' + t('hp_match_cap') + '</div></div></div>';
    }
    var reasons = (ranked && h.recommendation) ? '<div class="match-reasons">' + cleanReasons(h.recommendation, h, dist).map(function (r) {
      return '<div class="reason ' + (r.type === 'spec' ? 'spec' : '') + '"><span class="tick">' + (r.type === 'spec' ? '◆' : '✓') + '</span><span>' + esc(r.text) + '</span></div>';
    }).join('') + '</div>' : '';
    var addr = (h.address_zh || h.address) ? '<div class="hospital-sub">📍 ' + esc(h.address_zh || h.address) + '</div>' : '';
    var phone = h.phone ? '<div class="hospital-sub">☎ ' + esc(h.phone) + '</div>' : '';
    var specs = (h.specialties || []).slice(0, 5).map(function (s) { return '<span class="chip static">' + esc(typeof s === 'string' ? s : (s.name || '')) + '</span>'; }).join('');
    var review = ''; // 列表不再展示模板化点评；真实点评见医院详情
    var hasLoc = typeof h.lng === 'number' && typeof h.lat === 'number';
    var nav = hasLoc ? '<button class="btn btn-primary btn-sm js-nav" data-lng="' + h.lng + '" data-lat="' + h.lat + '" data-name="' + esc(h.name_zh || h.name) + '">' + t('hp_navigate') + '</button>' : '';
    var gradeBadge = h.grade ? '<span class="grade-badge">🛡 ' + esc(gradeLabel(h.grade)) + '</span>' : '';
    var ratingLine = '<div class="rating-line">' + gradeBadge + (rating ? '<span class="stars">' + starStr(rating) + '</span><span class="rating-num">' + rating.toFixed(1) + '</span>' : '') + (dist != null ? '<span class="review-count">· ' + t('hp_km', { km: dist.toFixed(1) }) + '</span>' : '') + '</div>';
    return '<div class="hospital-card ' + (ranked && idx === 0 ? 'top' : '') + '">' + (ranked ? '<div class="rank-badge">' + t('hp_best_match', { n: idx + 1 }) + '</div>' : '') +
      '<div class="hospital-main"><div class="hospital-name">' + name + zh + '</div>' + ratingLine + addr + phone + (specs ? '<div class="chips" style="margin-top:8px;">' + specs + '</div>' : '') + reasons + review + '</div>' +
      '<div class="hospital-side">' + ring + nav + '</div></div>';
  }
  function renderHospitals(list, ranked, maxScore) {
    var box = byId('hospital-list'); if (!box) return;
    _lastHospitals = list || []; _lastRanked = !!ranked; _lastMax = maxScore || 0;
    if (!list || !list.length) { box.innerHTML = '<div class="empty-state">' + t('hp_no_hosp') + '</div>'; return; }
    var arr = list.slice();
    if (_sortMode === 'rating') arr.sort(function (a, b) { return (num(b.rating) || 0) - (num(a.rating) || 0); });
    else if (_sortMode === 'distance' && _userLoc) arr.sort(function (a, b) { return (haversineKm(_userLoc, a) || 9e9) - (haversineKm(_userLoc, b) || 9e9); });
    box.innerHTML = arr.map(function (h, i) { return hospitalCard(h, i, ranked, maxScore); }).join('');
    qsa('.js-nav', box).forEach(function (b) {
      on(b, 'click', function () {
        var lng = parseFloat(b.getAttribute('data-lng')), lat = parseFloat(b.getAttribute('data-lat'));
        setActive('navigation'); setTimeout(function () { Nav.setTarget(lng, lat, b.getAttribute('data-name')); }, 60);
      });
    });
  }
  function renderTriageBanner() {
    var banner = byId('triage-result'); if (!banner || !_lastTriage) return;
    var tr = _lastTriage;
    banner.className = 'triage-banner' + (tr.urgent ? ' urgent' : ''); banner.classList.remove('hidden');
    banner.innerHTML = '<span class="triage-tag">' + (tr.urgent ? t('hp_urgent') : t('hp_recommended')) + '</span>' +
      '<h4>' + esc(tr.department_en || 'General Medicine') + ' <span class="dept-zh">' + esc(tr.department_zh || '') + '</span></h4>' +
      (tr.urgent ? '<p style="margin:4px 0 0;color:var(--danger);font-weight:600;">' + t('hp_call120') + '</p>' : '') +
      ((tr.matched_symptoms && tr.matched_symptoms.length) ? '<div class="chips" style="margin-top:8px;">' + tr.matched_symptoms.slice(0, 6).map(function (s) { return '<span class="chip static">' + esc(s) + '</span>'; }).join('') + '</div>' : '');
  }
  function loadHospitals() {
    var box = byId('hospital-list'); if (!box) return;
    var myReq = ++_hospReq;
    box.innerHTML = '<div class="empty-state"><span class="spinner"></span> ' + t('hp_loading') + '</div>';
    renderHospitals(FALLBACK_HOSPITALS, false, 0);
    api('/api/hospitals?limit=12').then(function (d) { if (myReq !== _hospReq) return; if (d && d.hospitals && d.hospitals.length) renderHospitals(d.hospitals, false, 0); }).catch(function () {});
  }
  function runRecommend() {
    var sym = ((byId('triage-input') || {}).value || '').trim(), spec = (byId('specialty-filter') || {}).value || '';
    var banner = byId('triage-result'), box = byId('hospital-list');
    if (!sym && !spec) { toast(t('hp_describe_first'), 'warn'); return; }
    if (box) box.innerHTML = '<div class="empty-state"><span class="spinner"></span> ' + t('hp_matching') + '</div>';
    if (banner) banner.classList.add('hidden');
    _sortMode = 'match'; syncSortUI();
    var myReq = ++_hospReq, body = { symptoms: sym || spec, city: '北京', limit: 10 };
    if (spec) body.specialty_override = spec;
    if (currentUser && currentUser.language) body.language = currentUser.language;
    api('/api/recommendations', { method: 'POST', body: body, timeout: 18000 }).then(function (d) {
      if (myReq !== _hospReq) return;
      _lastTriage = d.triage || {}; renderTriageBanner();
      var list = d.hospitals || [], maxScore = list.reduce(function (m, h) { return Math.max(m, (h.recommendation && h.recommendation.score) || 0); }, 0);
      renderHospitals(list, true, maxScore);
    }).catch(function () {
      if (myReq !== _hospReq) return;
      if (banner) { banner.className = 'triage-banner'; banner.classList.remove('hidden'); banner.innerHTML = '<span class="triage-tag">•</span><h4 style="font-size:15px;">' + t('hp_waking_t') + '</h4><p class="muted small" style="margin:4px 0 0;">' + t('hp_waking_d') + '</p>'; }
      loadHospitals();
    });
  }
  on(byId('btn-triage'), 'click', runRecommend);
  on(byId('triage-input'), 'keydown', function (e) { if (e.key === 'Enter') runRecommend(); });
  on(byId('btn-use-location'), 'click', function () {
    var b = this; b.disabled = true; b.textContent = t('hp_locating');
    getLocation(function () { b.disabled = false; b.textContent = t('hp_loc_set'); toast(t('hp_loc_added'), 'ok'); renderHospitals(_lastHospitals, _lastRanked, _lastMax); },
      function (m) { b.disabled = false; b.textContent = t('hp_use_loc'); toast(t('loc_prefix', { msg: m }), 'err'); });
  });
  function syncSortUI() { qsa('#sort-seg button').forEach(function (b) { b.classList.toggle('active', b.dataset.sort === _sortMode); }); }
  qsa('#sort-seg button').forEach(function (b) {
    on(b, 'click', function () {
      if (b.dataset.sort === 'distance' && !_userLoc) { toast(t('hp_loc_first'), 'warn'); return; }
      _sortMode = b.dataset.sort; syncSortUI(); renderHospitals(_lastHospitals, _lastRanked, _lastMax);
    });
  });

  /* ============================================================
     Navigation
     ============================================================ */
  var Nav = (function () {
    var map = null, ready = false, inited = false, confFetched = false, jsKey = '', secCode = '';
    var origin = { lng: 116.4074, lat: 39.9042 }, originIsGps = false, target = null, mode = 'walking', list = [], city = '北京';
    var lastSummary = null, lastStepsRaw = null;

    function setOriginText() {
      var el = byId('nav-origin'); if (!el) return;
      el.textContent = originIsGps ? t('nv_origin_gps') : t('nv_origin_default');
    }
    function fillDropdown() {
      var sel = byId('nav-hospital'); if (!sel) return; sel.innerHTML = '';
      list.forEach(function (h, i) { if (typeof h.lng !== 'number' || typeof h.lat !== 'number') return; var o = document.createElement('option'); o.value = String(i); o.textContent = (h.name_zh || h.name || 'Hospital') + (h.name && h.name_zh && h.name !== h.name_zh ? ' / ' + h.name : ''); sel.appendChild(o); });
      syncDropdown();
    }
    function syncDropdown() {
      var sel = byId('nav-hospital'); if (!sel || !target) return; var best = -1, bestD = 9e9;
      list.forEach(function (h, i) { var d = Math.abs((h.lng || 0) - target.lng) + Math.abs((h.lat || 0) - target.lat); if (d < bestD) { bestD = d; best = i; } });
      if (best >= 0 && bestD < 0.01) sel.value = String(best);
    }
    function loadList() {
      list = FALLBACK_HOSPITALS.slice(); fillDropdown();
      if (!target && list[0]) target = { lng: list[0].lng, lat: list[0].lat, name: list[0].name_zh || list[0].name };
      api('/api/hospitals?limit=40').then(function (d) {
        var valid = (d && d.hospitals || []).filter(function (h) { return typeof h.lng === 'number' && typeof h.lat === 'number'; });
        if (valid.length) { list = valid; fillDropdown(); if (!target) target = { lng: list[0].lng, lat: list[0].lat, name: list[0].name_zh || list[0].name }; draw(); }
      }).catch(function () {});
    }
    function ensureAmap() {
      if (ready) { draw(); return; }
      if (confFetched) return; confFetched = true;
      if (!API) { mapUnavailable(t('nv_map_no_backend')); draw(); return; }
      api('/api/amap/config').then(function (cfg) {
        jsKey = cfg.js_key || ''; secCode = cfg.security_code || '';
        if (!jsKey) { mapUnavailable(t('nv_map_no_js')); draw(); return; }
        if (secCode) window._AMapSecurityConfig = { securityJsCode: secCode };
        var s = document.createElement('script');
        s.src = 'https://webapi.amap.com/maps?v=2.0&key=' + encodeURIComponent(jsKey) + '&plugin=AMap.Walking,AMap.Driving,AMap.Transfer,AMap.Geolocation,AMap.Scale,AMap.ToolBar';
        s.onload = function () { if (window.AMap) { ready = true; draw(); } else { mapUnavailable(); draw(); } };
        s.onerror = function () { mapUnavailable(); draw(); };
        document.head.appendChild(s);
      }).catch(function () { mapUnavailable(); draw(); });
    }
    function mapUnavailable(msg) { var m = byId('nav-map'); if (!m) return; m.innerHTML = '<div class="map-empty"><div class="big">🧭</div><div>' + esc(msg || t('nv_map_unavail')) + '</div><div class="small muted">' + t('nv_map_hint') + '</div></div>'; }
    function markerPin(color, label) { var d = document.createElement('div'); d.style.cssText = 'transform:translate(-50%,-100%);'; d.innerHTML = '<div style="background:' + color + ';color:#fff;padding:3px 9px;border-radius:11px;font:600 11px sans-serif;box-shadow:0 4px 10px rgba(0,0,0,.25);white-space:nowrap;">' + esc(label) + '</div><div style="width:2px;height:9px;background:' + color + ';margin:0 auto;"></div>'; return d; }
    function draw() {
      renderHandoff();
      if (!ready || !window.AMap) { textFallback(); return; }
      var m = byId('nav-map'); if (!m) return;
      if (m.querySelector('.map-empty')) m.innerHTML = '';
      if (!map) { map = new AMap.Map(m, { zoom: 12, center: [origin.lng, origin.lat], viewMode: '2D', mapStyle: 'amap://styles/whitesmoke' }); try { map.addControl(new AMap.Scale()); map.addControl(new AMap.ToolBar({ position: 'RB' })); } catch (e) {} }
      map.clearMap();
      new AMap.Marker({ position: [origin.lng, origin.lat], map: map, content: markerPin('#0E9488', t('nv_you')), offset: new AMap.Pixel(0, 0) });
      if (target) { new AMap.Marker({ position: [target.lng, target.lat], map: map, content: markerPin('#1A78C2', trim(target.name, 14)), offset: new AMap.Pixel(0, 0) }); plan(); try { map.setFitView(); } catch (e) {} }
      else map.setZoomAndCenter(12, [origin.lng, origin.lat]);
      setOriginText();
    }
    function plan() {
      if (!target || !window.AMap || !map) return;
      var rb = byId('nav-route'); if (rb) rb.innerHTML = '<div class="muted small"><span class="spinner"></span> ' + t('nv_planning') + '</div>';
      var ctor = mode === 'driving' ? 'Driving' : mode === 'transit' ? 'Transfer' : 'Walking';
      var go = function () {
        var planner;
        try { if (mode === 'transit') planner = new AMap.Transfer({ map: map, city: city, hideMarkers: true, autoFitView: true }); else planner = new AMap[ctor]({ map: map, hideMarkers: true, autoFitView: true }); }
        catch (e) { textFallback(); return; }
        planner.search([origin.lng, origin.lat], [target.lng, target.lat], function (status, result) { if (status !== 'complete') { textFallback(); return; } parseRoute(result); });
      };
      if (AMap[ctor]) go(); else AMap.plugin(['AMap.' + ctor], go);
    }
    function parseRoute(result) {
      var distance = 0, time = 0, steps = [];
      try {
        if (mode === 'transit' && result.plans && result.plans.length) {
          var pl = result.plans[0]; distance = pl.distance || 0; time = pl.time || 0;
          (pl.segments || []).forEach(function (seg) {
            if (seg.transit_mode === 'WALK' && seg.transit) steps.push({ walk: true, d: seg.transit.distance || 0, zh: '步行 ' + Math.round(seg.transit.distance || 0) + ' 米' });
            else if (seg.transit && seg.transit.lines && seg.transit.lines.length) steps.push({ line: seg.transit.lines[0].name, d: seg.transit.distance || 0, zh: '乘坐 ' + seg.transit.lines[0].name });
            else if (seg.instruction) steps.push({ zh: seg.instruction, d: 0 });
          });
        } else if (result.routes && result.routes.length) {
          var rt = result.routes[0]; distance = rt.distance || 0; time = rt.time || 0;
          var isWalk = mode !== 'driving';
          (rt.steps || []).forEach(function (s) {
            steps.push({
              walk: isWalk, d: s.distance || 0,
              ori: s.orientation || '', road: s.road || '',
              act: s.action || '', ast: s.assistant_action || '',
              zh: s.instruction || s.start_road || '继续前行'
            });
          });
        }
      } catch (e) {}
      lastSummary = { distM: distance, durSec: time, estimated: false }; lastStepsRaw = steps;
      renderSummary(); renderStepsLocalized();
    }
    function textFallback() {
      var km = haversineKm(origin, target), speed = mode === 'driving' ? 30 : mode === 'transit' ? 18 : 4.8, min = km != null ? Math.max(1, Math.round(km / speed * 60)) : 0;
      lastSummary = { distM: km != null ? km * 1000 : 0, durSec: min * 60, estimated: true }; lastStepsRaw = null;
      renderSummary();
      var box = byId('nav-route'); if (box) box.innerHTML = '<div class="empty-state">' + t('nv_fallback') + '</div>';
    }
    function renderSummary() {
      var box = byId('nav-summary'); if (!box || !lastSummary) return;
      var km = lastSummary.distM / 1000, min = Math.max(1, Math.round(lastSummary.durSec / 60));
      var modeTxt = mode === 'driving' ? t('nv_drive') : mode === 'transit' ? t('nv_transit_txt') : t('nv_walk');
      box.innerHTML = '<div class="nav-stat"><div class="k">' + (lastSummary.estimated ? t('nv_straight') : t('nv_dist')) + '</div><div class="v">' + km.toFixed(2) + '<span class="unit"> km</span></div></div>' +
        '<div class="nav-stat"><div class="k">' + (lastSummary.estimated ? t('nv_est') : t('nv_duration')) + '</div><div class="v">' + min + '<span class="unit"> min</span></div></div>' +
        '<div class="nav-stat"><div class="k">' + t('nv_mode_label') + '</div><div class="v" style="font-size:18px;">' + modeTxt + '</div></div>';
    }
    function renderStepsLocalized() {
      var box = byId('nav-route'); if (!box) return;
      if (!lastStepsRaw || !lastStepsRaw.length) { box.innerHTML = ''; return; }
      var rows = lastStepsRaw.slice(0, 24).map(function (s, i) {
        var dist = s.d ? (s.d > 1000 ? (s.d / 1000).toFixed(1) + ' km' : Math.round(s.d) + ' m') : '';
        return '<div class="step-item"><div class="step-pin">' + (i + 1) + '</div><div class="step-body"><div class="step-instruction">' + esc(buildStepText(s, curLang)) + '</div>' + (dist ? '<div class="step-dist">' + dist + '</div>' : '') + '</div></div>';
      }).join('');
      box.innerHTML = '<h4>' + t('nv_turn_by_turn') + '</h4>' + rows + '<div class="step-item is-endpoint"><div class="step-pin">★</div><div class="step-body"><div class="step-instruction">' + t('nv_arrive', { name: esc(target ? target.name : '') }) + '</div></div></div>';
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
      box.innerHTML = '<span class="label">' + t('nv_open_in') + '</span>' + links.map(function (l) { return '<a class="handoff" href="' + l.u + '" target="_blank" rel="noopener">🧭 ' + esc(l.t) + '</a>'; }).join('');
    }
    return {
      enter: function () {
        if (!inited) {
          inited = true;
          on(byId('nav-hospital'), 'change', function () { var h = list[parseInt(this.value, 10)]; if (h) { target = { lng: h.lng, lat: h.lat, name: h.name_zh || h.name }; draw(); } });
          on(byId('nav-mode'), 'change', function () { mode = this.value; draw(); });
          on(byId('nav-locate'), 'click', function () { var b = this; b.disabled = true; b.textContent = t('nv_locating'); getLocation(function () { b.disabled = false; b.textContent = t('nv_use_loc'); toast(t('nv_using_loc'), 'ok'); }, function (m) { b.disabled = false; b.textContent = t('nv_use_loc'); toast(t('loc_prefix', { msg: m }), 'err'); }); });
          loadList(); ensureAmap(); setOriginText();
        } else draw();
      },
      setTarget: function (lng, lat, name) { target = { lng: +lng, lat: +lat, name: name || 'Hospital' }; if (!inited) this.enter(); else { syncDropdown(); ensureAmap(); draw(); } },
      setOriginFromGps: function (gps) {
        var apply = function (lng, lat) { origin = { lng: lng, lat: lat }; originIsGps = true; setOriginText(); draw(); };
        if (window.AMap && AMap.convertFrom) { try { AMap.convertFrom([gps.lng, gps.lat], 'gps', function (st, res) { if (st === 'complete' && res.locations && res.locations.length) { var p = res.locations[0]; apply(p.lng, p.lat); } else apply(gps.lng, gps.lat); }); return; } catch (e) {} }
        apply(gps.lng, gps.lat);
      },
      relabel: function () { if (!inited) return; setOriginText(); fillDropdown(); renderSummary(); renderHandoff(); renderStepsLocalized(); }
    };
  })();

  /* ============================================================
     Medication
     ============================================================ */
  var Med = (function () {
    var lib = [], lastInfo = null, inited = false;
    function tagFor(m) { return m.rx_required ? '<span class="pill-tag pill-rx">' + t('md_rx') + '</span>' : '<span class="pill-tag pill-otc">' + t('md_otc') + '</span>'; }
    function showInfo(m) {
      lastInfo = m; var box = byId('med-info'); if (!box) return;
      if (!m) { box.innerHTML = '<div class="empty-state">' + t('md_pick') + '</div>'; return; }
      var ul = function (arr) { return (arr && arr.length) ? '<ul>' + arr.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>' : '<p class="muted small">—</p>'; };
      box.innerHTML = '<div class="drug-info"><div class="drug-name">' + esc(m.name) + tagFor(m) + '</div><div class="muted small">' + esc(m.name_zh || '') + ' · ' + esc(m.category || '') + (m.price_cny ? ' · ¥' + m.price_cny : '') + '</div>' +
        '<h5>' + t('md_dosage_h') + '</h5><p>' + esc(m.dosage || m.dosage_zh || '—') + '</p><h5>' + t('md_warnings_h') + '</h5>' + ul(m.warnings && m.warnings.length ? m.warnings : m.warnings_zh) + '<h5>' + t('md_side_h') + '</h5>' + ul(m.side_effects) + '</div>';
    }
    function loadRecords() {
      var box = byId('med-list'); if (!box) return;
      if (!token) { box.innerHTML = '<div class="empty-state">' + t('md_list_signin') + '</div>'; return; }
      api('/api/medications/record', { auth: true }).then(function (rows) {
        if (!rows || !rows.length) { box.innerHTML = '<div class="empty-state">' + t('md_list_empty') + '</div>'; return; }
        box.innerHTML = rows.map(function (r) {
          var times = (r.reminder_times || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
          return '<div class="list-item"><div><strong>' + esc(r.custom_name || r.medication_key) + '</strong>' + (r.dosage ? '<div class="meta">' + esc(r.dosage) + '</div>' : '') + (r.notes ? '<div class="meta">' + esc(r.notes) + '</div>' : '') + (times.length ? '<div class="when">' + times.map(function (x) { return '<span class="time-pill">⏰ ' + esc(x) + '</span>'; }).join('') + '</div>' : '') + '</div><button class="btn btn-danger btn-sm js-del" data-id="' + r.id + '">' + t('md_remove') + '</button></div>';
        }).join('');
        qsa('.js-del', box).forEach(function (b) { on(b, 'click', function () { api('/api/medications/record/' + b.getAttribute('data-id'), { method: 'DELETE', auth: true }).then(function () { toast(t('md_removed'), 'ok'); loadRecords(); }).catch(function (e) { toast(e.message, 'err'); }); }); });
      }).catch(function () { box.innerHTML = '<div class="empty-state">' + t('md_load_fail') + '</div>'; });
    }
    return {
      init: function () {
        inited = true; var sel = byId('med-picker');
        api('/api/medications').then(function (d) {
          lib = (d && d.medications) || [];
          if (sel) { sel.innerHTML = '<option value="">' + t('md_choose') + '</option>' + lib.map(function (m) { return '<option value="' + esc(m.key) + '">' + esc(m.name) + ' / ' + esc(m.name_zh || '') + '</option>'; }).join(''); on(sel, 'change', function () { showInfo(lib.filter(function (m) { return m.key === sel.value; })[0]); }); }
          showInfo(null);
        }).catch(function () {});
        on(byId('btn-add-med'), 'click', function () {
          if (!token) { openAuth('login'); toast(t('md_login_first'), 'warn'); return; }
          var key = (byId('med-picker') || {}).value || ''; if (!key) { toast(t('md_pick_first'), 'warn'); return; }
          var body = { medication_key: key, custom_name: (byId('med-custom') || {}).value || '', dosage: (byId('med-dosage') || {}).value || '', reminder_times: (byId('med-times') || {}).value || '', notes: (byId('med-notes') || {}).value || '' };
          api('/api/medications/record', { method: 'POST', body: body, auth: true }).then(function () { toast(t('md_saved'), 'ok'); ['med-custom', 'med-dosage', 'med-times', 'med-notes'].forEach(function (id) { var el = byId(id); if (el) el.value = ''; }); loadRecords(); }).catch(function (e) { toast(e.message, 'err'); });
        });
        loadRecords();
      },
      relabel: function () { if (!inited) return; var sel = byId('med-picker'); if (sel && sel.options.length) sel.options[0].textContent = t('md_choose'); showInfo(lastInfo); loadRecords(); },
      reload: loadRecords
    };
  })();

  /* ============================================================
     Account
     ============================================================ */
  var Account = {
    render: function () {
      var box = byId('profile-body'); if (!box) return;
      if (!currentUser) { box.innerHTML = '<p class="muted">' + t('ac_signin_p') + '</p><button class="btn btn-primary" id="btn-profile-login">' + t('ac_signin_btn') + '</button>'; on(byId('btn-profile-login'), 'click', function () { openAuth('login'); }); return; }
      var u = currentUser, since = u.created_at ? new Date(u.created_at).toLocaleDateString() : '—';
      box.innerHTML = '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;"><div class="logo" style="width:54px;height:54px;font-size:20px;border-radius:16px;">' + esc((u.full_name || u.email || '?').slice(0, 1).toUpperCase()) + '</div><div><div style="font-family:var(--font-serif);font-size:22px;">' + esc(u.full_name || u.email) + '</div><div class="muted small">' + esc(u.email) + ' · ' + esc(u.role || 'patient') + '</div></div></div>' +
        '<div class="chips" style="margin-top:16px;"><span class="chip static">🌐 ' + esc(u.language || 'en') + '</span>' + (u.country ? '<span class="chip static">📍 ' + esc(u.country) + '</span>' : '') + '<span class="chip static">' + t('ac_member_since', { date: esc(since) }) + '</span></div>' +
        '<div class="row mt"><button class="btn btn-ghost btn-sm" id="btn-acc-logout">' + t('signout') + '</button></div>';
      on(byId('btn-acc-logout'), 'click', doLogout);
    }
  };
  on(byId('btn-export'), 'click', function () { if (!token) { openAuth('login'); return; } var box = byId('export-box'); api('/api/privacy/export', { auth: true }).then(function (d) { if (box) { box.classList.remove('hidden'); box.textContent = JSON.stringify(d, null, 2); } toast(t('ac_exported'), 'ok'); }).catch(function (e) { toast(e.message, 'err'); }); });
  on(byId('btn-wipe'), 'click', function () { if (!token) { openAuth('login'); return; } if (!confirm(t('ac_wipe_confirm'))) return; api('/api/privacy/wipe', { method: 'POST', auth: true }).then(function () { toast(t('ac_wiped'), 'ok'); var box = byId('export-box'); if (box) { box.classList.add('hidden'); box.textContent = ''; } loadMyTranslations(); Med.reload(); }).catch(function (e) { toast(e.message, 'err'); }); });
  on(byId('btn-send-feedback'), 'click', function () {
    var content = (byId('fb-content') || {}).value || ''; if (content.trim().length < 2) { toast(t('ac_fb_write'), 'warn'); return; }
    var body = { category: (byId('fb-category') || {}).value || 'other', rating: parseInt((byId('fb-rating') || {}).value, 10) || 5, comment: content.trim() };
    api('/api/feedback', { method: 'POST', body: body, auth: !!token }).then(function () { var st = byId('fb-status'); if (st) st.textContent = t('ac_fb_thanks'); if (byId('fb-content')) byId('fb-content').value = ''; toast(t('ac_fb_sent'), 'ok'); }).catch(function (e) { toast(e.message, 'err'); });
  });

  /* ============================================================
     Auth modal
     ============================================================ */
  function openAuth(tab) { var m = byId('auth-modal'); if (!m) return; m.classList.remove('hidden'); switchTab(tab || 'login'); }
  function closeAuth() { var m = byId('auth-modal'); if (m) m.classList.add('hidden'); var am = byId('auth-message'); if (am) am.textContent = ''; }
  function switchTab(tab) { qsa('.modal-tabs .tab').forEach(function (b) { b.classList.toggle('active', b.dataset.tab === tab); }); var lp = byId('tab-login'), rp = byId('tab-register'); if (lp) lp.classList.toggle('hidden', tab !== 'login'); if (rp) rp.classList.toggle('hidden', tab !== 'register'); }
  qsa('.modal-tabs .tab').forEach(function (b) { on(b, 'click', function () { switchTab(b.dataset.tab); }); });
  on(byId('auth-modal'), 'click', function (e) { if (e.target === this) closeAuth(); });
  on(byId('btn-login'), 'click', function () { openAuth('login'); });
  on(byId('btn-logout'), 'click', doLogout);
  on(byId('btn-lang'), 'click', showLangPicker);
  function doLogout() { clearSession(); toast(t('signed_out'), 'ok'); setActive('home'); }
  on(byId('btn-do-login'), 'click', function () {
    var email = (byId('login-email') || {}).value || '', pw = (byId('login-password') || {}).value || '', msg = byId('auth-message'); if (msg) msg.textContent = t('signing_in');
    api('/api/auth/login', { method: 'POST', body: { email: email.trim(), password: pw } }).then(function (d) { setSession(d.access_token, d.user); closeAuth(); toast(t('welcome_back', { name: (d.user && d.user.full_name) || '' }), 'ok'); afterAuth(); }).catch(function (e) { if (msg) msg.textContent = e.message || t('login_failed'); });
  });
  on(byId('btn-do-register'), 'click', function () {
    var body = { full_name: (byId('reg-name') || {}).value || '', email: ((byId('reg-email') || {}).value || '').trim(), password: (byId('reg-password') || {}).value || '', language: (byId('reg-language') || {}).value || 'en', country: (byId('reg-country') || {}).value || '' };
    var msg = byId('auth-message'); if (msg) msg.textContent = t('creating'); if (!body.full_name) { if (msg) msg.textContent = t('please_name'); return; }
    api('/api/auth/register', { method: 'POST', body: body }).then(function (d) { setSession(d.access_token, d.user); closeAuth(); toast(t('account_created'), 'ok'); afterAuth(); }).catch(function (e) { if (msg) msg.textContent = e.message || t('reg_failed'); });
  });
  function afterAuth() { loadMyTranslations(); Med.reload(); Account.render(); }
  function refreshAuthUI() {
    var loginBtn = byId('btn-login'), chip = byId('user-chip'), email = byId('user-email');
    if (currentUser) { if (loginBtn) loginBtn.classList.add('hidden'); if (chip) chip.classList.remove('hidden'); if (email) email.textContent = currentUser.full_name || currentUser.email; }
    else { if (loginBtn) loginBtn.classList.remove('hidden'); if (chip) chip.classList.add('hidden'); }
  }

  /* ============================================================
     Boot
     ============================================================ */
  if (!curLang) { DICT = buildDict('en'); applyStatic(); refreshAuthUI(); setActive('home'); loadStats(); revealScan(); showLangPicker(); }
  else { setLang(curLang); refreshAuthUI(); setActive('home'); loadStats(); revealScan(); }
  console.log('TransMed UI ready · API:', API || '(same origin)', '· lang:', curLang || '(pick)');
})();
'''

# ---------------------------------------------------------------------------
# 注入预生成的多语言字典（其余 10 种语言；EN/ZH 已手写在 STR_EN/STR_ZH）
# ---------------------------------------------------------------------------
import json
import re as _re
_root = os.path.dirname(os.path.abspath(__file__))
_i18n_path = os.path.join(_root, 'i18n_all.json')
_extra = {}
if os.path.exists(_i18n_path):
    _all = json.load(open(_i18n_path, encoding='utf-8'))
    for _lang, _d in _all.items():
        if _lang in ('en', 'zh'):
            continue  # EN/ZH 来自 JS 中手写的 STR_EN/STR_ZH
        # 去掉导航起点里残留的经纬度括注（用户要求不显示坐标）
        if 'nv_origin_gps' in _d:
            _d['nv_origin_gps'] = _re.sub(r'\s*[（(][^（）()]*\{lng\}[^（）()]*[）)]', '', _d['nv_origin_gps'])
        _extra[_lang] = _d
    print('embedded i18n: %d extra languages' % len(_extra))
else:
    print('⚠️  i18n_all.json not found — only EN/ZH available. Run: python3 gen_i18n.py')
JS = JS.replace('__I18N_EXTRA__', json.dumps(_extra, ensure_ascii=False))

# ---------------------------------------------------------------------------
# 写出到两份前端目录：transmed_web/（后端服务）与 docs/（GitHub Pages）
# ---------------------------------------------------------------------------
_targets = [
    os.path.join(_root, 'transmed_web', 'app.js'),
    os.path.join(_root, 'docs', 'app.js'),
]
for _path in _targets:
    os.makedirs(os.path.dirname(_path), exist_ok=True)
    with open(_path, 'w', encoding='utf-8') as f:
        f.write(JS)
    print('wrote', os.path.relpath(_path, _root), '(%d bytes)' % len(JS.encode('utf-8')))
