/* TransMed frontend — light Claude theme + global i18n */
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
  if (/localhost|127\.0\.0\.1/.test(location.hostname)) {
    API = location.protocol === 'file:' ? 'http://127.0.0.1:8000' : location.origin;
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
    st_langs: 'Languages', st_terms: 'Term banks', st_hosp: 'Hospitals', st_rules: 'Triage rules', st_trans: 'Translations served',
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
    hp_urgent: '🚨 URGENT', hp_recommended: '✓ Preliminary department', hp_call120: 'Call 120 or go to the nearest emergency department now. Do not delay care for a ranking.',
    hp_best_match: '#{n} best match', hp_match_cap: 'fit', hp_strong_in: 'Verified in {sp}', hp_name_indicates: 'Map listing indicates {sp}; call to confirm', hp_national_leader: 'National leader in {sp}', hp_grade_3a: 'Class III-A (top tier)', hp_rated: 'Rated {r}/5', hp_reviews: '{n} reviews', hp_reviews_paren: '({n} reviews)',
    hp_triage_conf: 'Triage confidence {n}%', hp_need_more: 'More detail is needed before choosing a hospital.', hp_follow_up: 'Please add:', hp_preliminary: 'Preliminary guidance, not a diagnosis.',
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
    st_langs: '语言', st_terms: '权威术语库', st_hosp: '医院', st_rules: '分诊规则', st_trans: '累计翻译次数',
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
    hp_urgent: '🚨 紧急', hp_recommended: '✓ 初步建议科室', hp_call120: '请立即拨打 120 或前往最近急诊，不要因医院排名延误就医。',
    hp_best_match: '#{n} 最匹配', hp_match_cap: '可信匹配', hp_strong_in: '已核验 {sp} 能力', hp_name_indicates: '地图名称显示设有 {sp}，建议电话确认', hp_national_leader: '{sp} 全国领先', hp_grade_3a: '三级甲等', hp_rated: '评分 {r}/5', hp_reviews: '{n} 条评价', hp_reviews_paren: '（{n} 条评价）',
    hp_triage_conf: '分诊置信度 {n}%', hp_need_more: '当前信息不足，建议补充后再选择医院。', hp_follow_up: '请补充：', hp_preliminary: '仅为就医分流建议，不构成诊断。',
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
  var I18N_EXTRA = {"ja": {"tagline": "AI医療コンパニオン · 中国でのケア", "nav_home": "ホーム", "nav_translate": "翻訳", "nav_hospitals": "病院", "nav_navigation": "ナビゲーション", "nav_medication": "薬剤", "nav_account": "アカウント", "login_register": "ログイン / 登録", "signout": "ログアウト", "lang_pick_title": "言語を選択", "lang_pick_sub": "全アプリが切り替わります。いつでも上部バーから変更できます。", "login_tab": "ログイン", "register_tab": "登録", "email": "メール", "password": "パスワード", "password_min": "パスワード（6文字以上）", "do_login": "ログイン", "create_account": "アカウントを作成", "demo_hint": "デモ: demo@transmed.io / demo123 · 管理者: admin@transmed.io / admin123", "fullname": "フルネーム", "feat_title": "医療訪問の4つのステップを処理します。", "feat_sub": "症状の説明から適切な科への受付まで — 各ステップは摩擦と不確実性を除去するように設計されています。", "feat1_t": "AI医療翻訳", "feat1_d": "用語の整列、信頼性スコア、4レベルのリスクアラートを備えた垂直型医療モデルにより、重要な情報が翻訳で失われることはありません。", "feat2_t": "スマート病院マッチング", "feat2_d": "症状を説明してください。TransMedは科を特定し、専門性、評価、距離に基づいて実際の病院をランク付けします — 理由も付けて。", "feat3_t": "マップ内ナビゲーション", "feat3_d": "ライブマップ上のルートとターンバイターンドィレクション、さらにApple、Google、AMap、またはBaidu Mapsへのハンドオフが1タップで可能です。", "feat4_t": "服用とプライバシー", "feat4_d": "リマインダー付きのバイリンガル薬剤庫と、いつでも個人記録をエクスポートまたは消去できるプライバシーセンター。", "how_eyebrow": "どうやって機能するのか", "how_title": "症状から診察まで。", "how1_t": "説明してください", "how1_d": "ご自身の言語で症状を入力してください。クリーンな医療翻訳とリスクレベルを取得します。", "how2_t": "トライアージュを受けます", "how2_d": "TransMedは適切な科を特定し、緊急事態をフラグ付けします。", "how3_t": "病院を選択してください", "how3_d": "実際の評価、レビュー、移動距離に基づいてランク付けされた病院を比較してください。", "how4_t": "そこへナビゲート", "how4_d": "描かれたルートに従ってください、またはお好みのマップアプリにハンドオフします。", "stats_eyebrow": "ライブプラットフォーム", "stats_title": "実際のデータに基づいています。", "st_langs": "言語", "st_terms": "用語バンク", "st_hosp": "病院", "st_rules": "トライアージュルール", "st_trans": "翻訳サービス", "tr_eyebrow": "翻訳", "tr_title": "AI医療翻訳", "tr_lede": "垂直統合型医療エンジン。翻訳は信頼性とリスクに基づいてスコア付けされ、認識された医療用語が強調表示されます。", "tr_from": "元の言語", "tr_to": "翻訳言語", "tr_src_ph": "症状を説明する、または医師の発言を貼り付けてください…", "tr_tip": "ヒント：期間、強度、そしてアレルギーについて具体的に記述してください。", "tr_btn": "翻訳", "tr_translating": "翻訳中…", "tr_result_ph": "翻訳結果がここに表示されます。", "tr_confidence": "信頼性", "tr_risk": "リスク", "tr_ack": "リスク警告を了承します", "tr_ack_done": "リスクを認識", "tr_templates": "クイック症状テンプレート", "tr_my_recent": "私の最近の翻訳", "tr_signin_save": "(サインインして保存)", "tr_terms_label": "認識された医療用語", "tr_ref_label": "医療参考 ({n})", "tr_advice_low": "高い信頼性。ただし、クリニシャンと確認して重要な詳細を確認してください。", "tr_advice_med": "中程度の信頼性 — 用量、数字、否定を二重に確認してください。", "tr_advice_high": "低い信頼性。行動を起こす前に、バイリンガルスタッフと確認してください。", "tr_online": "オンライン", "tr_offline": "オフライン", "tr_hist_signin": "サインインして翻訳の履歴を保持します。", "tr_hist_empty": "まだ保存された翻訳はありません。", "tr_hist_fail": "履歴を読み込むことができませんでした。", "hp_eyebrow": "トリアージ＆病院", "hp_title": "適切な病院を見つける", "hp_lede": "症状を説明してください — TransMedはあなたを部門にトリアージし、病院をランク付けし、理由を説明します。", "hp_sym_label": "症状を説明してください", "hp_sym_ph": "例： 2日間の持続的な頭痛と高熱", "hp_dept_label": "部門（任意）", "hp_dept_auto": "自動検出", "hp_analyze": "分析＆推奨", "hp_use_loc": "📍 私の位置を距離に使用", "hp_loc_set": "📍 場所を設定", "hp_locating": "📍 場所を検出中…", "hp_sort_by": "並べ替え", "hp_sort_match": "一致度", "hp_sort_rating": "評価", "hp_sort_distance": "距離", "hp_loading": "病院を読み込んでいます…", "hp_matching": "一致する病院を検索中…", "hp_describe_first": "最初に症状を説明してください", "hp_loc_first": "「私の位置を使用」をタップしてください", "hp_loc_added": "場所を設定しました — 距離を追加しました", "hp_urgent": "🚨 急いでください", "hp_recommended": "✓ 推奨部門", "hp_call120": "緊急の場合は、120に今すぐ電話してください。", "hp_best_match": "#{n} 一致度が高い", "hp_match_cap": "一致度", "nv_use_loc": "📍 現在地を使用", "nv_locating": "📍 検索中…", "nv_map_loading": "マップを読み込んでいます…", "nv_origin_default": "📍 出発地：北京市中心（デフォルト） · 「現在の位置を使用」をタップ。", "nv_origin_gps": "📍 出発地：現在の位置", "nv_map_unavail": "ライブマップは利用できない。", "nv_map_no_js": "AMap JS キーが設定されていません。", "nv_map_no_backend": "バックエンドが設定されていません。", "nv_map_hint": "以下のボタンを使用して、地図アプリでこの場所を開きます。", "nv_open_in": "地図で開く：", "nv_planning": "ルートを計画中…", "nv_turn_by_turn": "🧭 ターンバイターン", "nv_arrive": "{name} に到着", "nv_you": "あなた", "nv_fallback": "ターンバイターンには、AMap セキュリティ キーが必要です。距離/時間は、直線距離の見積もりです - 上部のボタンを使用して、地図アプリでナビゲートします。", "nv_dist": "距離", "nv_straight": "直線", "nv_duration": "時間", "nv_est": "見積もり時間", "nv_mode_label": "モード", "nv_walk": "歩行", "nv_drive": "運転", "nv_transit_txt": "交通機関", "nv_using_loc": "あなたの場所の使用", "md_eyebrow": "薬", "md_title": "薬およびリマインダー", "md_lede": "二言語ライブラリで薬を検索して、リマインダーの時間とともにあなたの個人リストに保存します。", "md_add": "薬の追加", "md_from_lib": "ライブラリから", "md_choose": "— 選択 —", "md_custom": "またはカスタム名", "md_custom_ph": "例：ビタミンD", "md_dosage": "用量/指示", "md_dosage_ph": "例：毎朝1錠", "md_times": "リマインダーの時間", "md_notes": "ノート", "md_notes_ph": "食後、乳製品から遠ざけ…", "md_save": "リストに保存", "md_login_req": "ログインが必要です。アカウントに保存されます。", "md_drug_info": "薬の情報", "md_pick": "薬のライブラリから薬を選択して用量、警告、副作用を確認します。", "md_rx": "処方箋", "md_otc": "無処方", "md_dosage_h": "用量", "md_warnings_h": "警告", "md_side_h": "副作用", "md_my_list": "私の薬のリスト", "md_list_signin": "薬やリマインダーの保存にはサインインしてください。", "md_list_empty": "まだ薬は保存されていません。", "md_saved": "リストに保存されました", "md_removed": "削除", "md_remove": "削除", "md_pick_first": "ライブラリから薬を選択してください", "md_login_first": "まずログインしてください", "md_load_fail": "リストを読み込むことができませんでした。", "ac_eyebrow": "あなたのアカウント", "ac_title": "アカウントとプライバシー", "ac_lede": "あなたの身分は任意です。機密性の高い医療テキストは最小限の保持で処理されます — あなたはいつでもエクスポートまたはすべてを消去することができます。", "ac_signin_p": "プロフィール、保存された翻訳、薬を見たい場合はログインしてください。", "ac_signin_btn": "ログイン / 登録", "ac_member_since": "{date}以来メンバー", "ac_your_data": "あなたのデータ", "ac_data_desc": "アカウントに関連付けられたすべてのデータの完全なJSONコピーをエクスポートする、またはあなたの個人レコードを永久に削除する（ログインは保持される）。", "ac_export": "⬇︎ 全てのデータをエクスポート", "ac_wipe": "🗑 個人レコードをすべて削除", "ac_exported": "以下にエクスポート", "ac_wipe_confirm": "翻訳、薬、トリアージ、フィードバックをすべて削除します。ログインは保持されます。これは取り消しできません。", "ac_wiped": "全ての個人レコードが削除されました", "ac_feedback": "フィードバック", "ac_category": "カテゴリ", "ac_cat_translation": "翻訳", "ac_cat_hospital": "病院", "ac_cat_navigation": "ナビゲーション", "ac_cat_medication": "薬", "ac_cat_feature": "機能リクエスト", "ac_cat_other": "その他", "ac_rating": "評価（1〜5）", "ac_your_msg": "あなたのメッセージ", "ac_msg_ph": "私たちをどう改善できるか教えてください…", "ac_submit": "フィードバックを送信", "ac_fb_thanks": "ありがとうございます！ご意見をいただきました。", "ac_fb_write": "メッセージを書いてください", "ac_fb_sent": "フィードバックを送信しました", "footer_a": "TransMed · 医療における異文化コミュニケーションを支援するAI — デモ用です。緊急の場合には120に電話するか、最も近い救急室に行ってください。", "footer_b": "重要な決定は、医師のライセンスを確認してください。", "loc_prefix": "場所：{msg}", "ui_translating": "翻訳インターフェース…", "ui_ready": "言語が準備できました", "please_login": "まずログインしてください", "pref_lang": "優先言語", "country": "国", "signing_in": "サインイン中…", "creating": "アカウントを作成中…", "welcome_back": "{name}、お帰りなさい", "account_created": "アカウントを作成しました — ようこそ！", "signed_out": "サインアウトしました", "login_failed": "ログインに失敗しました", "reg_failed": "登録に失敗しました", "please_name": "名前を入力してください", "hero_eyebrow": "中国の外国人向けAI医療コンパニオン", "hero_title_a": "中国で治療を受けます", "hero_title_b": "言語の壁がないで。", "hero_lead": "医療グレードの多言語翻訳に信頼スコアリング、症状に基づいた病院マッチング、そして実際の地図内ナビゲーションで正しい部門へ — すべてがひとつの落ち着いた、信頼できる場所にまとまっています。", "hero_cta_translate": "翻訳を開始する", "hero_cta_hospital": "適切な病院を見つける", "trust_langs": "12言語", "trust_data": "北京の実際の病院データ", "trust_privacy": "デザインによるプライバシー保護", "feat_eyebrow": "トランスメッドが行うこと", "tr_conf_line": "信頼度{n}% · {risk}", "hp_strong_in": "強い::{sp}に", "hp_rated": "評価 {r}/5", "hp_reviews": "{n} 件のレビュー", "hp_reviews_paren": "({n} 件のレビュー)", "hp_km_you": "あなたから{km}キロメートルです", "hp_km": "キロメートル{km}キロメートル", "hp_speaks": "あなたの言語を話す", "hp_emergency": "強力な緊急医療サービス", "hp_navigate": "ナビゲート →", "hp_no_hosp": "病院が見つかりませんでした。より広範な症状または科を試してください。", "hp_waking_t": "レコメンデーションサービスが起動しています", "hp_waking_d": "現在すべての病院を表示しています。しばらくして再度お試しください。", "nv_eyebrow": "ナビゲーション", "nv_title": "ケアに移動する", "nv_lede": "実際の地図上で描かれたルートとターンバイターンドィレクションを確認する — または1タップで携帯電話のマップアプリに引き渡す。", "nv_hospital": "病院", "nv_mode": "モード", "nv_walking": "🚶 歩行", "nv_driving": "運転中🚗", "nv_transit": "🚇 移行", "hp_national_leader": "{sp} 全国トップクラス", "hp_grade_3a": "三級甲等（最上位）"}, "ko": {"tagline": "AI 의료 동반자 · 중국 내 치료", "nav_home": "홈", "nav_translate": "번역", "nav_hospitals": "병원", "nav_navigation": "내비게이션", "nav_medication": "약물", "nav_account": "계정", "login_register": "로그인 / 등록", "signout": "로그아웃", "lang_pick_title": "언어 선택", "lang_pick_sub": "전체 앱이 선택한 언어로 전환됩니다. 언제든지 상단 바에서 변경할 수 있습니다.", "login_tab": "로그인", "register_tab": "등록", "email": "이메일", "password": "비밀번호", "password_min": "비밀번호 (최소 6자)", "do_login": "로그인", "create_account": "계정 생성", "demo_hint": "데모: demo@transmed.io / demo123 · 관리자: admin@transmed.io / admin123", "fullname": "전체 이름", "feat_title": "의료 방문 4단계, 처리 완료.", "feat_sub": "증상을 설명하는 것에서부터 올바른 부서에 서 있는 것까지 — 각 단계는 마찰과 불확실성을 제거하도록 설계되었습니다.", "feat1_t": "AI 의료 번역", "feat1_d": "용어 정렬, 신뢰도 점수, 4단계 위험 경보와 함께 하는 수직 의료 모델로 번역에서 중요한 내용이 손실되지 않습니다.", "feat2_t": "스마트 병원 매칭", "feat2_d": "증상을 설명하세요; TransMed는 부서로 분류하고 전문 분야 적합성, 평점, 거리에 따라 실제 병원을 순위대로 매깁니다 — 이유와 함께.", "feat3_t": "지도 내비게이션", "feat3_d": "실시간 지도에서 그린 경로와 단계별 방향, Apple, Google, AMap 또는 Baidu Maps로 한 번의 탭으로 전환합니다.", "feat4_t": "약물 및 개인 정보 보호", "feat4_d": "약물 라이브러리와 개인 기록을 언제든지 내보내기 또는 삭제할 수 있는 개인 정보 보호 센터가 포함된 다국어 약물 라이브러리.", "how_eyebrow": "작동 원리", "how_title": "증상에서 진찰까지.", "how1_t": "설명하기", "how1_d": "언어로 증상을 입력하세요. 위험 수준이 포함된 깨끗한 의료 번역을 얻으세요.", "how2_t": "분류 받기", "how2_d": "TransMed는 올바른 부서를 식별하고 긴급한 경우를 표시합니다.", "how3_t": "병원 선택", "how3_d": "실제 평점, 리뷰, 여행 거리와 함께 순위가 매겨진 병원을 비교하세요.", "how4_t": "그곳으로 이동", "how4_d": "그린 경로를 따라가거나 좋아하는 지도 앱으로 전환하세요.", "stats_eyebrow": "라이브 플랫폼", "stats_title": "실제 데이터에 기반을 두고 있습니다.", "st_langs": "언어", "st_terms": "용어 데이터베이스", "st_hosp": "병원", "st_rules": "트라이어지 규칙", "st_trans": "제공 번역", "tr_eyebrow": "번역", "tr_title": "AI 의료 번역", "tr_lede": "수직 의료 엔진입니다. 번역의 신뢰도와 위험도를 평가하며, 인식된 의학 용어를 강조 표시합니다.", "tr_from": "원본", "tr_to": "대상", "tr_src_ph": "증상을 설명하거나 의사가 말한 것을 붙여 넣으십시오…", "tr_tip": "팁: 기간, 강도 및 알레르기에 대해 구체적으로 설명하십시오.", "tr_btn": "번역", "tr_translating": "번역 중...", "tr_result_ph": "번역 결과가 여기 나타날 것입니다.", "tr_confidence": "신뢰도", "tr_risk": "위험도", "tr_ack": "위험 경고를 인정합니다", "tr_ack_done": "위험 확인", "tr_templates": "빠른 증상 템플릿", "tr_my_recent": "최근 번역", "tr_signin_save": "(로그인하여 저장)", "tr_terms_label": "인식된 의료 용어", "tr_ref_label": "의료 참고문헌({n})", "tr_advice_low": "높은 신뢰도. 그래도 중요한 세부 사항을 의사와 확인하십시오.", "tr_advice_med": "중간 신뢰도 — 용량, 숫자 및 부정을 다시 확인하십시오.", "tr_advice_high": "낮은 신뢰도. 행동을 취하기 전에 이중 언어 스태프와 확인하십시오.", "tr_online": "온라인", "tr_offline": "오프라인", "tr_hist_signin": "로그인하여 번역 기록을 유지하십시오.", "tr_hist_empty": "아직 저장된 번역이 없습니다.", "tr_hist_fail": "기록을 로드할 수 없습니다.", "hp_eyebrow": "트라이아지 및 병원", "hp_title": "적절한 병원을 찾으십시오", "hp_lede": "증상을 설명하십시오 — TransMed는 증상을 설명하여 부서로 분류하고 실제 병원을 얼마나 잘 맞는지에 따라 순위를 매기고 이유를 알려줍니다.", "hp_sym_label": "증상을 설명하십시오", "hp_sym_ph": "예: 2일간 지속되는 두통과 고열", "hp_dept_label": "부서 (선택 사항)", "hp_dept_auto": "자동 감지", "hp_analyze": "분석 및 추천", "hp_use_loc": "📍 거리 계산을 위해 내 위치 사용", "hp_loc_set": "📍 위치 설정", "hp_locating": "📍 위치 찾는 중…", "hp_sort_by": "정렬 기준", "hp_sort_match": "최적의 매칭", "hp_sort_rating": "평점", "hp_sort_distance": "거리", "hp_loading": "병원 로딩 중…", "hp_matching": "매칭 병원 중…", "hp_describe_first": "먼저 증상을 설명하세요", "hp_loc_first": "먼저 \"내 위치 사용\"을 탭하세요", "hp_loc_added": "위치 설정 — 거리 추가됨", "hp_urgent": "🚨 긴급", "hp_recommended": "✓ 추천 부서", "hp_call120": "이 경우 응급이라면 지금 120에 전화하세요.", "hp_best_match": "#{n} 최적의 매칭", "hp_match_cap": "매칭", "nv_use_loc": "📍 내 위치 사용", "nv_locating": "📍 위치 찾는 중...", "nv_map_loading": "지도 로딩...", "nv_origin_default": "📍 출발지: 北京 도심 (기본값) · \"내 위치 사용\" 탭", "nv_origin_gps": "📍 출발지: 현재 위치", "nv_map_unavail": "실시간 지도 사용 불가.", "nv_map_no_js": "AMap JS 키가 구성되지 않음.", "nv_map_no_backend": "백엔드가 구성되지 않음.", "nv_map_hint": "아래 버튼을 사용하여 지도 앱에서 이 장소를 열어보세요.", "nv_open_in": "지도에서 열기:", "nv_planning": "경로 계획 중...", "nv_turn_by_turn": "🧭 교통 정보", "nv_arrive": "{name}에 도착", "nv_you": "당신", "nv_fallback": "교통 정보는 AMap 보안 키가 필요합니다. 거리/시간은 직선 거리 추정값입니다. 위의 버튼을 사용하여 지도 앱에서 내비게이션을 사용하세요.", "nv_dist": "거리", "nv_straight": "직선", "nv_duration": "소요 시간", "nv_est": "예상 시간", "nv_mode_label": "모드", "nv_walk": "산책", "nv_drive": "운전", "nv_transit_txt": "대중교통", "nv_using_loc": "현재 위치 사용", "md_eyebrow": "약물", "md_title": "약물 및 알림", "md_lede": "이중언어 도서관에서 약물을 검색한 다음 개인 목록에 알림 시간과 함께 저장합니다.", "md_add": "약물 추가", "md_from_lib": "도서관에서", "md_choose": "— 선택 —", "md_custom": "또는 사용자 지정 이름", "md_custom_ph": "예: 비타민 D", "md_dosage": "용량/사용법", "md_dosage_ph": "예: 매일 아침 1정", "md_times": "알림 시간", "md_notes": "메모", "md_notes_ph": "식사 후 우유와 함께 섭취하지 마십시오…", "md_save": "내 목록에 저장", "md_login_req": "로그인이 필요합니다. 계정에 저장됩니다.", "md_drug_info": "약 정보", "md_pick": "도서관에서 약을 선택하여 용량, 경고 및 부작용을 확인하세요.", "md_rx": "처방전", "md_otc": "非처방전", "md_dosage_h": "용량", "md_warnings_h": "경고", "md_side_h": "부작용", "md_my_list": "나의 약 목록", "md_list_signin": "저장하고 알림을 받으려면 로그인하세요.", "md_list_empty": "아직 저장된 약이 없습니다.", "md_saved": "목록에 저장됨", "md_removed": "삭제됨", "md_remove": "삭제", "md_pick_first": "도서관에서 약을 선택하세요", "md_login_first": "먼저 로그인하세요", "md_load_fail": "목록을 불러올 수 없습니다.", "ac_eyebrow": "계정", "ac_title": "계정 및 개인 정보", "ac_lede": "귀하의 신원은 선택 사항입니다. 민감한 의료 텍스트는 최소한의 보존으로 처리되며 언제든지 모든 것을 내보내거나 지울 수 있습니다.", "ac_signin_p": "프로필, 저장된 번역 및 약을 보려면 로그인하세요.", "ac_signin_btn": "로그인 / 등록", "ac_member_since": "{date}부터 회원입니다", "ac_your_data": "您的 데이터", "ac_data_desc": "계정과 관련된 모든 것을 JSON 형식으로 전체 복사본을 내보내기 또는 로그인 정보만 유지하고 개인 기록을 영구적으로 삭제합니다.", "ac_export": "⬇︎ 내 모든 데이터 내보내기", "ac_wipe": "🗑 개인 기록 모두 삭제", "ac_exported": "아래 내보내기", "ac_wipe_confirm": "모든 번역, 약물, 분류 및 피드백을 삭제합니다. 로그인은 유지됩니다. 이 작업은 취소할 수 없습니다.", "ac_wiped": "모든 개인 기록 삭제됨", "ac_feedback": "피드백", "ac_category": "카테고리", "ac_cat_translation": "번역", "ac_cat_hospital": "병원", "ac_cat_navigation": "내비게이션", "ac_cat_medication": "약물", "ac_cat_feature": "기능 요청", "ac_cat_other": "기타", "ac_rating": "평점 (1–5)", "ac_your_msg": "메시지", "ac_msg_ph": "우리가 어떻게 개선할 수 있는지 알려주세요…", "ac_submit": "피드백 제출", "ac_fb_thanks": "감사합니다! 귀하의 의견이 전달되었습니다.", "ac_fb_write": "메시지를 작성해 주세요", "ac_fb_sent": "의견 전송", "footer_a": "TransMed · 다문화 의료를 위한 AI — 시연 목적으로만 사용됩니다. 비상 시 120에 전화하거나 가장 가까운 응급실로 가세요.", "footer_b": "중요한 결정은 면허 의사와 확인해야 합니다.", "loc_prefix": "위치: {msg}", "ui_translating": "번역 인터페이스…", "ui_ready": "언어 준비 완료", "please_login": "먼저 로그인해 주세요", "pref_lang": "선호 언어", "country": "국가", "signing_in": "로그인 중...", "creating": "계정 생성중…", "welcome_back": "Welcome back, {name}", "account_created": "계정 생성 완료 — 환영합니다!", "signed_out": "로그아웃됨", "login_failed": "로그인 실패", "reg_failed": "등록에 실패했습니다", "please_name": "이름을 입력해 주십시오", "hero_eyebrow": "중국에 거주하는 외국인을 위한 AI 의료 동반자", "hero_title_a": "중국에서 치료를 받으십시오", "hero_title_b": "언어 장벽 없이.", "hero_lead": "의료급 다국어 번역과 신뢰도 평가, 증상 기반 병원 매칭, 실제 지도 내비게이션을 통해 올바른 진료과로 안내 — 모든 것이 하나의 차분하고 신뢰할 수 있는 곳에서 제공됩니다.", "hero_cta_translate": "번역을 시작하세요", "hero_cta_hospital": "적합한 병원을 찾으세요", "trust_langs": "12개 언어", "trust_data": "베이징 실제 병원 데이터", "trust_privacy": "디자인 시 보안", "feat_eyebrow": "TransMed이 하는 일", "tr_conf_line": "confidence {n}% · {risk}", "hp_strong_in": "강한 {sp}에서", "hp_rated": "평점 {r}/5", "hp_reviews": "{n}개의 리뷰", "hp_reviews_paren": "({n}개의 리뷰)", "hp_km_you": "{km} km 거리에서 당신에게", "hp_km": "{km} 킬로미터", "hp_speaks": "당신의 언어를 말합니다", "hp_emergency": "긴급구조 서비스", "hp_navigate": "네비게이트 →", "hp_no_hosp": "병원이 없습니다. 더 넓은 증상이나 과를 시도하세요.", "hp_waking_t": "추천 서비스가 활성화되었습니다", "hp_waking_d": "모든 병원을 표시 중입니다. 잠시 후 다시 시도하세요.", "nv_eyebrow": "네비게이션", "nv_title": "의료 서비스로 이동하십시오", "nv_lede": "실시간 지도에서 그려진 경로와 턴바이턴 방향을 확인하거나 한 번의 탭으로 휴대폰의 지도 앱으로 전환할 수 있습니다.", "nv_hospital": "병원", "nv_mode": "모드", "nv_walking": "🚶 걷기", "nv_driving": "🚗 운전", "nv_transit": "🚇 교통수단", "hp_national_leader": "{sp} 전국 선도", "hp_grade_3a": "3급 갑등(최상위)"}, "fr": {"tagline": "Compagnon médical IA · soins en Chine", "nav_home": "Accueil", "nav_translate": "Traduire", "nav_hospitals": "Hôpitaux", "nav_navigation": "Navigation", "nav_medication": "Médicaments", "nav_account": "Compte", "login_register": "Se connecter / S'inscrire", "signout": "Se déconnecter", "lang_pick_title": "Choisissez votre langue", "lang_pick_sub": "L'ensemble de l'application passera à celle-ci. Vous pouvez la modifier à tout moment depuis la barre du haut.", "login_tab": "Se connecter", "register_tab": "S'inscrire", "email": "Adresse e-mail", "password": "Mot de passe", "password_min": "Mot de passe (min 6 caractères)", "do_login": "Se connecter", "create_account": "Créer mon compte", "demo_hint": "Démo : demo@transmed.io / demo123 · Administrateur : admin@transmed.io / admin123", "fullname": "Nom complet", "pref_lang": "Langue préférée", "country": "Pays", "signing_in": "Connexion en cours…", "creating": "Création de compte…", "welcome_back": "Bienvenue à nouveau, {name}", "account_created": "Compte créé — bienvenue !", "signed_out": "Déconnecté", "login_failed": "Échec de la connexion", "reg_failed": "Échec de l'enregistrement", "please_name": "Veuillez entrer votre nom", "hero_eyebrow": "Compagnon médical d'intelligence artificielle pour les étrangers en Chine", "hero_title_a": "Obtenez des soins en Chine", "hero_title_b": "sans la barrière de la langue.", "hero_lead": "Traduction multilingue de qualité médicale avec notation de confiance, mise en correspondance des hôpitaux basée sur les symptômes et navigation réelle sur carte vers le service approprié — tout en un seul endroit calme et digne de confiance.", "hero_cta_translate": "Commencer la traduction", "hero_cta_hospital": "Trouver l'hôpital approprié", "trust_langs": "12 langues", "trust_data": "Données réelles d'hôpitaux de Pékin", "trust_privacy": "Confidentialité par conception", "feat_eyebrow": "Ce que fait TransMed", "feat_title": "Quatre étapes d'une visite médicale, gérées.", "feat_sub": "De la description de vos symptômes à la présence dans le département approprié — chaque étape est conçue pour éliminer les frictions et les incertitudes.", "feat1_t": "Traduction médicale par IA", "feat1_d": "Modèle médical vertical avec alignement de termes, un score de confiance et des alertes de risque à 4 niveaux pour que rien de critique ne soit perdu dans la traduction.", "feat2_t": "Appariement d'hôpitaux intelligents", "feat2_d": "Décrivez vos symptômes ; TransMed trie les cas par département et classe les hôpitaux réels par spécialité, notation et distance — avec des raisons.", "feat3_t": "Navigation dans la carte", "feat3_d": "Un itinéraire tracé et des directions étape par étape sur une carte en temps réel, ainsi qu'un seul tap pour passer à Apple, Google, AMap ou Baidu Maps.", "feat4_t": "Médicaments et confidentialité", "feat4_d": "Une bibliothèque bilingue de médicaments avec des rappels, et un centre de confidentialité pour exporter ou effacer vos dossiers personnels à tout moment.", "how_eyebrow": "Fonctionnement", "how_title": "De symptôme à consultation.", "how1_t": "Décrivez-le", "how1_d": "Tapez vos symptômes dans votre langue. Obtenez une traduction médicale propre avec niveau de risque.", "how2_t": "Soit orienté", "how2_d": "TransMed identifie le département approprié et signale les cas urgents.", "how3_t": "Choisissez un hôpital", "how3_d": "Comparez les hôpitaux classés avec des notations, des avis et une distance de déplacement réels.", "how4_t": "Allez-y", "how4_d": "Suivez l'itinéraire tracé, ou passez à votre application de cartes préférée.", "stats_eyebrow": "Plateforme en direct", "stats_title": "Fondée sur des données réelles.", "st_langs": "Langues", "st_terms": "Banques terminologiques", "st_hosp": "Hôpitaux", "st_rules": "Règles de triage", "st_trans": "Traductions servies", "tr_eyebrow": "Traduction", "tr_title": "Traduction médicale par IA", "tr_lede": "Un moteur médical vertical. Chaque traduction est notée pour la confiance et le risque, avec les termes médicaux reconnus mis en évidence.", "tr_from": "De", "tr_to": "À", "tr_src_ph": "Décrivez les symptômes, ou collez ce que le médecin a dit…", "tr_tip": "Conseil : soyez précis sur la durée, l'intensité et les allergies.", "tr_btn": "Traduire", "tr_translating": "En train de traduire…", "tr_result_ph": "La traduction apparaîtra ici.", "tr_confidence": "Confiance", "tr_risk": "Risque", "tr_ack": "Je reconnais l'alerte de risque", "tr_ack_done": "Risque reconnu", "tr_templates": "Modèles de symptômes rapides", "tr_my_recent": "Mes traductions récentes", "tr_signin_save": "(connexion pour enregistrer)", "tr_terms_label": "Termes médicaux reconnus", "tr_ref_label": "Référence médicale ({n})", "tr_advice_low": "Confiance élevée. Confirmez néanmoins les détails critiques avec votre clinicien.", "tr_advice_med": "Confiance modérée — vérifiez les doses, les nombres et les négations.", "tr_advice_high": "Confiance faible. Veuillez vérifier avec un membre du personnel bilingue avant d'agir sur ceci.", "tr_online": "En ligne", "tr_offline": "Hors ligne", "tr_hist_signin": "Connectez-vous pour conserver un historique de vos traductions.", "tr_hist_empty": "Aucune traduction enregistrée pour le moment.", "tr_hist_fail": "Impossible de charger l'historique.", "hp_eyebrow": "Triage et hôpitaux", "hp_title": "Trouvez l'hôpital approprié", "hp_lede": "Décrivez vos symptômes — TransMed vous dirige vers un service et classe les hôpitaux réels en fonction de leur adéquation, en vous expliquant pourquoi.", "hp_sym_label": "Décrivez vos symptômes", "hp_sym_ph": "par exemple, céphalée persistante et fièvre élevée pendant 2 jours", "hp_dept_label": "Département (facultatif)", "hp_dept_auto": "Détection automatique", "hp_analyze": "Analyser et recommander", "hp_use_loc": "📍 Utiliser ma localisation pour la distance", "hp_loc_set": "📍 Localisation définie", "hp_locating": "📍 Localisation en cours…", "hp_sort_by": "Trier par", "hp_sort_match": "Meilleure correspondance", "hp_sort_rating": "Évaluation", "hp_sort_distance": "Distance", "hp_loading": "Chargement des hôpitaux…", "hp_matching": "Hôpitaux correspondants…", "hp_describe_first": "Décrivez d’abord vos symptômes", "hp_loc_first": "Appuyez sur « Utiliser ma localisation » en premier", "hp_loc_added": "Localisation définie — distances ajoutées", "hp_urgent": "🚨 URGENT", "hp_recommended": "✓ Département recommandé", "hp_call120": "En cas d’urgence, appelez le 120 maintenant.", "hp_best_match": "#{n} meilleure correspondance", "hp_match_cap": "correspondance", "hp_strong_in": "Fort en {sp}", "hp_rated": "Évalué {r}/5", "hp_reviews": "{n} avis", "hp_reviews_paren": "({n} avis)", "hp_km_you": "À {km} km de vous", "hp_km": "{km} km", "hp_speaks": "Parle votre langue", "hp_emergency": "Services d'urgence solides", "hp_navigate": "Naviguer →", "hp_no_hosp": "Aucun hôpital trouvé. Essayez un symptôme ou un service plus large.", "hp_waking_t": "Le service de recommandation se réveille", "hp_waking_d": "Affichage de tous les hôpitaux en attendant. Réessayez dans un instant.", "nv_eyebrow": "Navigation", "nv_title": "Naviguer vers les soins", "nv_lede": "Voir l'itinéraire tracé et les directions étape par étape sur une carte en direct - ou passer à l'application de cartes de votre téléphone en une seule touche.", "nv_hospital": "Hôpital", "nv_mode": "Mode", "nv_walking": "🚶 Marche", "nv_driving": "🚗 Conduite", "nv_transit": "🚇 Transport en commun", "nv_use_loc": "📍 Utiliser ma localisation", "nv_locating": "📍 Localisation…", "nv_map_loading": "Chargement de la carte…", "nv_origin_default": "📍 Origine : centre-ville de Pékin (par défaut) · appuyer sur « Utiliser ma localisation ».", "nv_origin_gps": "📍 Origine : votre emplacement actuel", "nv_map_unavail": "Carte interactive indisponible.", "nv_map_no_js": "La clé AMap JS n'est pas configurée.", "nv_map_no_backend": "Le backend n'est pas configuré.", "nv_map_hint": "Utilisez les boutons ci-dessous pour ouvrir cet endroit dans une application de cartes.", "nv_open_in": "Ouvrir dans les cartes :", "nv_planning": "Planification de l'itinéraire…", "nv_turn_by_turn": "🧭 Étape par étape", "nv_arrive": "Arrivée à {name}", "nv_you": "Vous", "nv_fallback": "L'itinéraire étape par étape nécessite la clé de sécurité AMap. Les distances/temps sont des estimations en ligne droite — utilisez les boutons ci-dessus pour naviguer dans une application de cartes.", "nv_dist": "Distance", "nv_straight": "En ligne droite", "nv_duration": "Durée", "nv_est": "Temps estimé", "nv_mode_label": "Mode", "nv_walk": "Marche", "nv_drive": "Conduite", "nv_transit_txt": "Transit", "nv_using_loc": "Utilisation de votre emplacement", "md_eyebrow": "Médicament", "md_title": "Médicament et rappels", "md_lede": "Recherchez un médicament dans la bibliothèque bilingue, puis enregistrez-le avec les heures de rappel dans votre liste personnelle.", "md_add": "Ajouter un médicament", "md_from_lib": "De la bibliothèque", "md_choose": "— choisir —", "md_custom": "Ou nom personnalisé", "md_custom_ph": "par exemple Vitamine D", "md_dosage": "Posologie / instructions", "md_dosage_ph": "par exemple 1 comprimé chaque matin", "md_times": "Heures de rappel", "md_notes": "Notes", "md_notes_ph": "Après les repas, tenir à l'écart des produits laitiers…", "md_save": "Enregistrer dans ma liste", "md_login_req": "Nécessite une connexion. Stocké contre votre compte.", "md_drug_info": "Informations sur les médicaments", "md_pick": "Sélectionnez un médicament dans la bibliothèque pour voir la posologie, les avertissements et les effets secondaires.", "md_rx": "Rx", "md_otc": "OTC", "md_dosage_h": "Posologie", "md_warnings_h": "Avertissements", "md_side_h": "Effets secondaires", "md_my_list": "Ma liste de médicaments", "md_list_signin": "Connectez-vous pour enregistrer les médicaments et les rappels.", "md_list_empty": "Aucun médicament enregistré pour le moment.", "md_saved": "Enregistré dans votre liste", "md_removed": "Supprimé", "md_remove": "Supprimer", "md_pick_first": "Sélectionnez un médicament dans la bibliothèque", "md_login_first": "Veuillez vous connecter d'abord", "md_load_fail": "Impossible de charger votre liste.", "ac_eyebrow": "Votre compte", "ac_title": "Compte et confidentialité", "ac_lede": "Votre identité est facultative. Les textes médicaux sensibles sont traités avec une rétention minimale — et vous pouvez exporter ou effacer tout à tout moment.", "ac_signin_p": "Connectez-vous pour voir votre profil, les traductions enregistrées et les médicaments.", "ac_signin_btn": "Connexion / Inscription", "ac_member_since": "Membre depuis {date}", "ac_your_data": "Vos données", "ac_data_desc": "Exportez une copie JSON complète de tout ce qui est lié à votre compte, ou supprimez définitivement vos dossiers personnels (votre identifiant de connexion est conservé).", "ac_export": "⬇︎ Exporter toutes mes données", "ac_wipe": "🗑 Supprimer tous les dossiers personnels", "ac_exported": "Exporté ci-dessous", "ac_wipe_confirm": "Supprimer TOUTES vos traductions, médicaments, triage et commentaires ? Votre identifiant de connexion est conservé. Cela ne peut pas être annulé.", "ac_wiped": "Tous les dossiers personnels supprimés", "ac_feedback": "Commentaires", "ac_category": "Catégorie", "ac_cat_translation": "traduction", "ac_cat_hospital": "hôpital", "ac_cat_navigation": "navigation", "ac_cat_medication": "médicament", "ac_cat_feature": "demande de fonctionnalité", "ac_cat_other": "autre", "ac_rating": "Évaluation (1-5)", "ac_your_msg": "Votre message", "ac_msg_ph": "Dites-nous comment nous pouvons améliorer…", "ac_submit": "Soumettre les commentaires", "ac_fb_thanks": "Merci ! Vos commentaires ont été reçus.", "ac_fb_write": "Veuillez écrire un message", "ac_fb_sent": "Commentaires envoyés", "footer_a": "TransMed · IA pour les soins de santé interculturels — à titre de démonstration uniquement. En cas d'urgence, appelez le 120 ou rendez-vous au service des urgences le plus proche.", "footer_b": "Les décisions critiques doivent être confirmées par un médecin agréé.", "loc_prefix": "Emplacement : {msg}", "ui_translating": "Interface de traduction…", "ui_ready": "Langue prête", "please_login": "Veuillez vous connecter d'abord", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "Leader national en {sp}", "hp_grade_3a": "Niveau III-A (top)"}, "de": {"tagline": "Künstliche-Intelligenz-Medizinbegleiter · in-China-Betreuung", "nav_home": "Startseite", "nav_translate": "Übersetzen", "nav_hospitals": "Krankenhäuser", "nav_navigation": "Navigation", "nav_medication": "Medikation", "nav_account": "Konto", "login_register": "Anmelden / Registrieren", "signout": "Abmelden", "lang_pick_title": "Wählen Sie Ihre Sprache", "lang_pick_sub": "Die gesamte App wird darauf umgeschaltet. Sie können sie jederzeit von der oberen Leiste aus ändern.", "login_tab": "Anmelden", "register_tab": "Registrieren", "email": "E-Mail", "password": "Passwort", "password_min": "Passwort (min. 6 Zeichen)", "do_login": "Anmelden", "create_account": "Mein Konto erstellen", "demo_hint": "Demo: demo@transmed.io / demo123 · Admin: admin@transmed.io / admin123", "fullname": "Vollständiger Name", "pref_lang": "Bevorzugte Sprache", "country": "Land", "signing_in": "Anmelden…", "creating": "Konto erstellen…", "welcome_back": "Willkommen zurück, {name}", "account_created": "Konto erstellt — herzlich willkommen!", "signed_out": "Abgemeldet", "login_failed": "Anmeldung fehlgeschlagen", "reg_failed": "Registrierung fehlgeschlagen", "please_name": "Bitte geben Sie Ihren Namen ein", "hero_eyebrow": "Künstliche-Intelligenz-Medizinbegleiter für Ausländer in China", "hero_title_a": "Erhalten Sie medizinische Versorgung in China", "hero_title_b": "ohne Sprachbarriere.", "hero_lead": "Medizinisch geeignete mehrsprachige Übersetzung mit Vertrauensbewertung, symptombezogene Krankenhauszuweisung und echte Navigation im Kartensystem zur richtigen Abteilung — all dies an einem ruhigen, vertrauenswürdigen Ort.", "hero_cta_translate": "Übersetzung starten", "hero_cta_hospital": "Das richtige Krankenhaus finden", "trust_langs": "12 Sprachen", "trust_data": "Echte Daten von Krankenhäusern in Peking", "trust_privacy": "Datenschutz durch Design", "feat_eyebrow": "Was TransMed macht", "feat_title": "Vier Schritte eines Arztbesuchs, abgewickelt.", "feat_sub": "Von der Beschreibung Ihrer Symptome bis zum Stehen in der richtigen Abteilung – jeder Schritt ist darauf ausgelegt, Reibung und Unsicherheit zu beseitigen.", "feat1_t": "Künstliche Intelligenz für medizinische Übersetzungen", "feat1_d": "Vertikales medizinisches Modell mit Term-Übereinstimmung, einem Vertrauensscore und 4-stufigen Risikowarnungen, damit nichts Kritisches bei der Übersetzung verloren geht.", "feat2_t": "Intelligente Krankenhausvermittlung", "feat2_d": "Beschreiben Sie Ihre Symptome; TransMed leitet Sie zu einer Abteilung weiter und ordnet echte Krankenhäuser nach Fachbereich, Bewertung und Entfernung – mit Begründungen.", "feat3_t": "Navigation im Kartensystem", "feat3_d": "Eine gezeichnete Route und schrittweise Anweisungen auf einer Live-Karte, plus einem Tap, um die Navigation an Apple, Google, AMap oder Baidu Maps zu übergeben.", "feat4_t": "Medikamente und Datenschutz", "feat4_d": "Eine zweisprachige Arzneimittelbibliothek mit Erinnerungen und einem Datenschutzzentrum, um Ihre persönlichen Aufzeichnungen jederzeit zu exportieren oder zu löschen.", "how_eyebrow": "So funktioniert es", "how_title": "Von Symptom zu Untersuchung.", "how1_t": "Beschreiben Sie", "how1_d": "Geben Sie Ihre Symptome in Ihrer Sprache ein. Erhalten Sie eine saubere medizinische Übersetzung mit Risikostufe.", "how2_t": "Klassifizieren", "how2_d": "TransMed identifiziert die richtige Abteilung und kennzeichnet dringende Fälle.", "how3_t": "Wählen Sie ein Krankenhaus", "how3_d": "Vergleichen Sie Krankenhäuser mit echten Bewertungen, Rezensionen und Entfernung.", "how4_t": "Navigieren Sie dorthin", "how4_d": "Folgen Sie der gezeichneten Route oder übergeben Sie die Navigation an Ihre bevorzugte Karten-App.", "stats_eyebrow": "Live-Plattform", "stats_title": "Basiert auf echten Daten.", "st_langs": "Sprachen", "st_terms": "Terminologiebanken", "st_hosp": "Krankenhäuser", "st_rules": "Triage-Regeln", "st_trans": "Übersetzungen bereitgestellt", "tr_eyebrow": "Übersetzung", "tr_title": "KI-Medizinübersetzung", "tr_lede": "Ein vertikaler medizinischer Motor. Jede Übersetzung wird nach Vertrauenswürdigkeit und Risiko bewertet, wobei die erkannten medizinischen Fachbegriffe hervorgehoben werden.", "tr_from": "Von", "tr_to": "Nach", "tr_src_ph": "Beschreiben Sie Symptome oder fügen Sie das ein, was der Arzt gesagt hat…", "tr_tip": "Tipp: Seien Sie spezifisch bezüglich Dauer, Intensität und Allergien.", "tr_btn": "Übersetzen", "tr_translating": "Wird übersetzt…", "tr_result_ph": "Die Übersetzung wird hier erscheinen.", "tr_confidence": "Vertrauenswürdigkeit", "tr_risk": "Risiko", "tr_ack": "Ich bestätige die Risikowarnung", "tr_ack_done": "Risiko anerkannt", "tr_templates": "Schnell-Symptom-Vorlagen", "tr_my_recent": "Meine kürzlichen Übersetzungen", "tr_signin_save": "(anmelden, um zu speichern)", "tr_terms_label": "Anerkannte medizinische Fachbegriffe", "tr_ref_label": "Medizinische Referenz ({n})", "tr_advice_low": "Hohe Zuverlässigkeit. Bitte bestätigen Sie dennoch kritische Details mit Ihrem Arzt.", "tr_advice_med": "Mittlere Zuverlässigkeit — überprüfen Sie Dosen, Zahlen und Negationen.", "tr_advice_high": "Niedrige Zuverlässigkeit. Bitte überprüfen Sie dies vorher mit einem zweisprachigen Mitarbeiter, bevor Sie handeln.", "tr_online": "Online", "tr_offline": "Offline", "tr_hist_signin": "Anmelden, um eine Übersicht Ihrer Übersetzungen zu speichern.", "tr_hist_empty": "Noch keine gespeicherten Übersetzungen.", "tr_hist_fail": "Übersetzungsverlauf konnte nicht geladen werden.", "hp_eyebrow": "Triage & Krankenhäuser", "hp_title": "Finden Sie das richtige Krankenhaus", "hp_lede": "Beschreiben Sie Ihre Symptome — TransMed leitet Sie an eine Abteilung weiter und ordnet Krankenhäuser nach ihrer Eignung, wobei es Ihnen den Grund nennt.", "hp_sym_label": "Beschreiben Sie Ihre Symptome", "hp_sym_ph": "z. B. anhaltende Kopfschmerzen und hohes Fieber seit 2 Tagen", "hp_dept_label": "Abteilung (optional)", "hp_dept_auto": "Automatische Erkennung", "hp_analyze": "Analyse und Empfehlung", "hp_use_loc": "📍 Verwende meinen Standort für Entfernung", "hp_loc_set": "📍 Standort festgelegt", "hp_locating": "📍 Ortung…", "hp_sort_by": "Sortieren nach", "hp_sort_match": "Beste Übereinstimmung", "hp_sort_rating": "Bewertung", "hp_sort_distance": "Entfernung", "hp_loading": "Lade Krankenhäuser…", "hp_matching": "Krankenhäuser finden…", "hp_describe_first": "Beschreiben Sie zunächst Ihre Symptome", "hp_loc_first": "Tippen Sie zuerst auf \"Standort verwenden\"", "hp_loc_added": "Standort festgelegt — Entfernungen hinzugefügt", "hp_urgent": "🚨 DRINGEND", "hp_recommended": "✓ Empfohlene Abteilung", "hp_call120": "Wenn es sich um einen Notfall handelt, rufen Sie jetzt 120 an.", "hp_best_match": "#{n} beste Übereinstimmung", "hp_match_cap": "Übereinstimmung", "hp_strong_in": "Stark in {sp}", "hp_rated": "Bewertung {r}/5", "hp_reviews": "{n} Bewertungen", "hp_reviews_paren": "({n} Bewertungen)", "hp_km_you": "{km} km von Ihnen entfernt", "hp_km": "{km} km", "hp_speaks": "Spricht Ihre Sprache", "hp_emergency": "Starkes Notdienstangebot", "hp_navigate": "Navigieren →", "hp_no_hosp": "Keine Krankenhäuser gefunden. Versuchen Sie, ein breiteres Symptom oder eine Abteilung zu suchen.", "hp_waking_t": "Empfehlungsdienst wird aktiviert", "hp_waking_d": "Zeigt alle Krankenhäuser in der Zwischenzeit. Versuchen Sie es in einem Moment noch einmal.", "nv_eyebrow": "Navigation", "nv_title": "Zu Pflege navigieren", "nv_lede": "Zeigen Sie die gezeichnete Route und die Schritt-für-Schritt-Anweisungen auf einer Live-Karte — oder übergeben Sie sie mit einem Tap an die Karten-App Ihres Telefons.", "nv_hospital": "Krankenhaus", "nv_mode": "Modus", "nv_walking": "🚶 Zu Fuß", "nv_driving": "🚗 Mit dem Auto", "nv_transit": "🚇 Öffentliche Verkehrsmittel", "nv_use_loc": "📍 Verwenden Sie meinen Standort", "nv_locating": "📍 Ortung…", "nv_map_loading": "Karte wird geladen…", "nv_origin_default": "📍 Ursprung: Stadtzentrum Peking (Standard) · Tippen Sie auf „Verwenden Sie meinen Standort“.", "nv_origin_gps": "📍 Ursprung: Ihr aktueller Standort", "nv_map_unavail": "Live-Karte nicht verfügbar.", "nv_map_no_js": "AMap JS-Schlüssel nicht konfiguriert.", "nv_map_no_backend": "Backend nicht konfiguriert.", "nv_map_hint": "Verwenden Sie die Schaltflächen unten, um diesen Ort in einer Karten-App zu öffnen.", "nv_open_in": "Öffnen in Karten:", "nv_planning": "Route planen…", "nv_turn_by_turn": "🧭 Schritt-für-Schritt-Anweisungen", "nv_arrive": "Ankunft bei {name}", "nv_you": "Sie", "nv_fallback": "Schritt-für-Schritt-Anweisungen benötigen den AMap-Sicherheitsschlüssel. Entfernung/Zeit sind geradlinige Schätzungen — verwenden Sie die Schaltflächen oben, um in einer Karten-App zu navigieren.", "nv_dist": "Entfernung", "nv_straight": "Geradlinig", "nv_duration": "Dauer", "nv_est": "Geschätzte Zeit", "nv_mode_label": "Modus", "nv_walk": "Gehen", "nv_drive": "Fahren", "nv_transit_txt": "Öffentliche Verkehrsmittel", "nv_using_loc": "Verwenden Sie Ihren Standort", "md_eyebrow": "Medikamente", "md_title": "Medikamente und Erinnerungen", "md_lede": "Suchen Sie in der zweisprachigen Bibliothek nach einem Medikament und speichern Sie es mit Erinnerungszeiten in Ihrer persönlichen Liste.", "md_add": "Ein Medikament hinzufügen", "md_from_lib": "Aus der Bibliothek", "md_choose": "— wählen —", "md_custom": "Oder benutzerdefinierter Name", "md_custom_ph": "z. B. Vitamin D", "md_dosage": "Dosierung / Anweisungen", "md_dosage_ph": "z. B. 1 Tablette jeden Morgen", "md_times": "Erinnerungszeiten", "md_notes": "Notizen", "md_notes_ph": "Nach den Mahlzeiten, fern von Milchprodukten…", "md_save": "Speichern in meiner Liste", "md_login_req": "Benötigt Anmeldung. Gespeichert gegen Ihr Konto.", "md_drug_info": "Medikamenteninformationen", "md_pick": "Wählen Sie ein Medikament aus der Bibliothek, um Dosierungen, Warnungen und Nebenwirkungen zu sehen.", "md_rx": "Rx", "md_otc": "OTC", "md_dosage_h": "Dosierung", "md_warnings_h": "Warnungen", "md_side_h": "Nebenwirkungen", "md_my_list": "Meine Medikamentenliste", "md_list_signin": "Melden Sie sich an, um Medikamente und Erinnerungen zu speichern.", "md_list_empty": "Noch keine Medikamente gespeichert.", "md_saved": "Gespeichert in Ihrer Liste", "md_removed": "Entfernt", "md_remove": "Entfernen", "md_pick_first": "Wählen Sie ein Medikament aus der Bibliothek", "md_login_first": "Bitte melden Sie sich zunächst an", "md_load_fail": "Konnte Ihre Liste nicht laden.", "ac_eyebrow": "Ihr Konto", "ac_title": "Konto & Datenschutz", "ac_lede": "Ihre Identität ist optional. Sensible medizinische Texte werden mit minimalem Speicher verarbeitet - und Sie können alles jederzeit exportieren oder löschen.", "ac_signin_p": "Melden Sie sich an, um Ihr Profil, gespeicherte Übersetzungen und Medikamente zu sehen.", "ac_signin_btn": "Anmelden / Registrieren", "ac_member_since": "Mitglied seit {date}", "ac_your_data": "Ihre Daten", "ac_data_desc": "Exportieren Sie eine vollständige JSON-Kopie aller mit Ihrem Konto verknüpften Daten oder löschen Sie Ihre persönlichen Aufzeichnungen dauerhaft (Ihr Login bleibt erhalten).", "ac_export": "⬇︎ Alle meine Daten exportieren", "ac_wipe": "🗑 Alle persönlichen Aufzeichnungen löschen", "ac_exported": "Exportiert unten", "ac_wipe_confirm": "Löschen Sie ALLE Ihre Übersetzungen, Medikamente, Triage und Feedback? Ihr Login bleibt erhalten. Dies kann nicht rückgängig gemacht werden.", "ac_wiped": "Alle persönlichen Aufzeichnungen gelöscht", "ac_feedback": "Feedback", "ac_category": "Kategorie", "ac_cat_translation": "Übersetzung", "ac_cat_hospital": "Krankenhaus", "ac_cat_navigation": "Navigation", "ac_cat_medication": "Medikament", "ac_cat_feature": "Funktionswunsch", "ac_cat_other": "anderes", "ac_rating": "Bewertung (1–5)", "ac_your_msg": "Ihre Nachricht", "ac_msg_ph": "Erzählen Sie uns, wie wir verbessern können…", "ac_submit": "Feedback senden", "ac_fb_thanks": "Vielen Dank! Ihre Rückmeldung wurde erhalten.", "ac_fb_write": "Bitte schreiben Sie eine Nachricht", "ac_fb_sent": "Rückmeldung gesendet", "footer_a": "TransMed · KI für gesundheitliche Versorgung über Kulturen hinweg — nur zur Demonstration. Im Notfall 120 anrufen oder zur nächstgelegenen Notaufnahme gehen.", "footer_b": "Kritische Entscheidungen müssen mit einem lizenzierten Arzt bestätigt werden.", "loc_prefix": "Standort: {msg}", "ui_translating": "Übersetzungsinterface…", "ui_ready": "Sprache bereit", "please_login": "Bitte melden Sie sich zunächst an", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "Bundesweit führend in {sp}", "hp_grade_3a": "Klasse III-A (Spitze)"}, "es": {"tagline": "Compañero médico de IA · atención en China", "nav_home": "Inicio", "nav_translate": "Traducir", "nav_hospitals": "Hospitales", "nav_navigation": "Navegación", "nav_medication": "Medicación", "nav_account": "Cuenta", "login_register": "Iniciar sesión / Registrarse", "signout": "Cerrar sesión", "lang_pick_title": "Elige tu idioma", "lang_pick_sub": "Toda la aplicación cambiará a este idioma. Puedes cambiarlo en cualquier momento desde la barra superior.", "login_tab": "Iniciar sesión", "register_tab": "Registrarse", "email": "Correo electrónico", "password": "Contraseña", "password_min": "Contraseña (mínimo 6 caracteres)", "do_login": "Iniciar sesión", "create_account": "Crear mi cuenta", "demo_hint": "Demo: demo@transmed.io / demo123 · Administrador: admin@transmed.io / admin123", "fullname": "Nombre completo", "pref_lang": "Idioma preferido", "country": "País", "signing_in": "Iniciando sesión…", "creating": "Creando cuenta…", "welcome_back": "Bienvenido de nuevo, {name}", "account_created": "Cuenta creada — bienvenido", "signed_out": "Cerró la sesión", "login_failed": "Inicio de sesión fallido", "reg_failed": "Registro fallido", "please_name": "Por favor, ingrese su nombre", "hero_eyebrow": "Asistente médico de inteligencia artificial para extranjeros en China", "hero_title_a": "Obtenga atención en China", "hero_title_b": "sin la barrera del lenguaje.", "hero_lead": "Traducción multilingüe de grado médico con puntuación de confianza, coincidencia de hospitales basada en síntomas y navegación en mapa real hasta el departamento adecuado — todo en un lugar tranquilo y confiable.", "hero_cta_translate": "Comenzar a traducir", "hero_cta_hospital": "Encontrar el hospital adecuado", "trust_langs": "12 idiomas", "trust_data": "Datos reales de hospitales de Beijing", "trust_privacy": "Privacidad por diseño", "feat_eyebrow": "Qué hace TransMed", "feat_title": "Cuatro pasos de una visita médica, manejados.", "feat_sub": "Desde describir sus síntomas hasta estar en el departamento adecuado — cada paso está diseñado para eliminar la fricción y la incertidumbre.", "feat1_t": "Traducción médica con inteligencia artificial", "feat1_d": "Modelo médico vertical con alineación de términos, una puntuación de confianza y alertas de riesgo de 4 niveles para que nada crítico se pierda en la traducción.", "feat2_t": "Coincidencia de hospital inteligente", "feat2_d": "Describa sus síntomas; TransMed los evalúa y asigna a un departamento y clasifica los hospitales reales por ajuste de especialidad, calificación y distancia — con razones.", "feat3_t": "Navegación en el mapa", "feat3_d": "Una ruta dibujada y direcciones paso a paso en un mapa en vivo, más un toque para transferir a Apple, Google, AMap o Baidu Maps.", "feat4_t": "Medicación y privacidad", "feat4_d": "Una biblioteca de medicamentos bilingüe con recordatorios, y un centro de privacidad para exportar o borrar sus registros personales en cualquier momento.", "how_eyebrow": "Cómo funciona", "how_title": "Desde el síntoma hasta la atención.", "how1_t": "Describa", "how1_d": "Escriba sus síntomas en su idioma. Obtenga una traducción médica limpia con nivel de riesgo.", "how2_t": "Evalúe", "how2_d": "TransMed identifica el departamento adecuado y marca los casos urgentes.", "how3_t": "Elija un hospital", "how3_d": "Compare los hospitales clasificados con calificaciones, reseñas y distancia de viaje reales.", "how4_t": "Navegue hasta allí", "how4_d": "Siga la ruta dibujada, o transfiera a su aplicación de mapas favorita.", "stats_eyebrow": "Plataforma en vivo", "stats_title": "Basada en datos reales.", "st_langs": "Idiomas", "st_terms": "Bancos terminológicos", "st_hosp": "Hospitales", "st_rules": "Reglas de triaje", "st_trans": "Traducciones servidas", "tr_eyebrow": "Traducción", "tr_title": "Traducción médica de inteligencia artificial", "tr_lede": "Un motor médico vertical. Cada traducción se puntuación para confianza y riesgo, con los términos médicos que reconoció resaltados.", "tr_from": "De", "tr_to": "A", "tr_src_ph": "Describa los síntomas, o pegue lo que dijo el médico…", "tr_tip": "Consejo: sea específico sobre la duración, intensidad y alergias.", "tr_btn": "Traducir", "tr_translating": "Traduciendo…", "tr_result_ph": "La traducción aparecerá aquí.", "tr_confidence": "Confianza", "tr_risk": "Riesgo", "tr_ack": "Reconozco la alerta de riesgo", "tr_ack_done": "Riesgo reconocido", "tr_templates": "Plantillas de síntomas rápidos", "tr_my_recent": "Mis traducciones recientes", "tr_signin_save": "(iniciar sesión para guardar)", "tr_terms_label": "Términos médicos reconocidos", "tr_ref_label": "Referencia médica ({n})", "tr_advice_low": "Alta confianza. Sin embargo, confirme los detalles críticos con su médico.", "tr_advice_med": "Confianza moderada — verifique dosis, números y negaciones.", "tr_advice_high": "Baja confianza. Por favor, verifique con un miembro del personal bilingüe antes de actuar sobre esto.", "tr_online": "En línea", "tr_offline": "Fuera de línea", "tr_hist_signin": "Inicie sesión para mantener un historial de sus traducciones.", "tr_hist_empty": "No hay traducciones guardadas aún.", "tr_hist_fail": "No se pudo cargar el historial.", "hp_eyebrow": "Triaje y hospitales", "hp_title": "Encuentre el hospital adecuado", "hp_lede": "Describa sus síntomas — TransMed lo triaje a un departamento y clasifica los hospitales reales según lo bien que encajan, explicándole por qué.", "hp_sym_label": "Describa sus síntomas", "hp_sym_ph": "p. ej. dolor de cabeza persistente y fiebre alta durante 2 días", "hp_dept_label": "Departamento (opcional)", "hp_dept_auto": "Detección automática", "hp_analyze": "Analizar y recomendar", "hp_use_loc": "📍 Utilizar mi ubicación para la distancia", "hp_loc_set": "📍 Ubicación establecida", "hp_locating": "📍 Localizando…", "hp_sort_by": "Ordenar por", "hp_sort_match": "Mejor coincidencia", "hp_sort_rating": "Calificación", "hp_sort_distance": "Distancia", "hp_loading": "Cargando hospitales…", "hp_matching": "Coincidencias de hospitales…", "hp_describe_first": "Describe primero tus síntomas", "hp_loc_first": "Pulsa “Utilizar mi ubicación” primero", "hp_loc_added": "Ubicación establecida — distancias agregadas", "hp_urgent": "🚨 URGENTE", "hp_recommended": "✓ Departamento recomendado", "hp_call120": "Si es una emergencia, llama al 120 ahora.", "hp_best_match": "#{n} mejor coincidencia", "hp_match_cap": "coincidencia", "hp_strong_in": "Fuerte en {sp}", "hp_rated": "Calificado {r}/5", "hp_reviews": "{n} reseñas", "hp_reviews_paren": "({n} reseñas)", "hp_km_you": "{km} km desde tu ubicación", "hp_km": "{km} km", "hp_speaks": "Habla tu idioma", "hp_emergency": "Fuertes servicios de emergencia", "hp_navigate": "Navegar →", "hp_no_hosp": "No se encontraron hospitales. Intenta con un síntoma o departamento más amplio.", "hp_waking_t": "El servicio de recomendación se está activando", "hp_waking_d": "Mostrando todos los hospitales mientras tanto. Inténtalo de nuevo en un momento.", "nv_eyebrow": "Navegación", "nv_title": "Navegar hacia la atención", "nv_lede": "Ver la ruta dibujada y las direcciones paso a paso en un mapa en vivo — o pasar a la aplicación de mapas de tu teléfono en un solo toque.", "nv_hospital": "Hospital", "nv_mode": "Modo", "nv_walking": "🚶 Caminando", "nv_driving": "🚗 Conduciendo", "nv_transit": "🚇 Transporte público", "nv_use_loc": "📍 Usar mi ubicación", "nv_locating": "📍 Localizando…", "nv_map_loading": "Cargando mapa…", "nv_origin_default": "📍 Origen: centro de la ciudad de Beijing (predeterminado) · tocar “Usar mi ubicación”.", "nv_origin_gps": "📍 Origen: tu ubicación actual", "nv_map_unavail": "Mapa en vivo no disponible.", "nv_map_no_js": "La clave de AMap JS no está configurada.", "nv_map_no_backend": "El backend no está configurado.", "nv_map_hint": "Utilice los botones a continuación para abrir este lugar en una aplicación de mapas.", "nv_open_in": "Abrir en mapas:", "nv_planning": "Planificando ruta…", "nv_turn_by_turn": "🧭 Paso a paso", "nv_arrive": "Llegar a {name}", "nv_you": "Usted", "nv_fallback": "Paso a paso necesita la clave de seguridad de AMap. La distancia/tiempo son estimaciones de línea recta — use los botones de arriba para navegar en una aplicación de mapas.", "nv_dist": "Distancia", "nv_straight": "Línea recta", "nv_duration": "Duración", "nv_est": "Tiempo est.", "nv_mode_label": "Modo", "nv_walk": "Caminar", "nv_drive": "Conducir", "nv_transit_txt": "Tránsito", "nv_using_loc": "Usar tu ubicación", "md_eyebrow": "Medicación", "md_title": "Medicación y recordatorios", "md_lede": "Busca un medicamento en la biblioteca bilingüe, luego guárdalo con recordatorios de hora en tu lista personal.", "md_add": "Agregar un medicamento", "md_from_lib": "De la biblioteca", "md_choose": "— elige —", "md_custom": "O nombre personalizado", "md_custom_ph": "p. ej. Vitamina D", "md_dosage": "Dosis / instrucciones", "md_dosage_ph": "p. ej. 1 tableta cada mañana", "md_times": "Horarios de recordatorio", "md_notes": "Notas", "md_notes_ph": "Después de las comidas, mantener alejado de lácteos…", "md_save": "Guardar en mi lista", "md_login_req": "Requiere inicio de sesión. Almacenado contra tu cuenta.", "md_drug_info": "Información de medicamentos", "md_pick": "Elige un medicamento de la biblioteca para ver la dosis, advertencias y efectos secundarios.", "md_rx": "Rx", "md_otc": "OTC", "md_dosage_h": "Dosis", "md_warnings_h": "Advertencias", "md_side_h": "Efectos secundarios", "md_my_list": "Mi lista de medicamentos", "md_list_signin": "Inicia sesión para guardar medicamentos y recordatorios.", "md_list_empty": "No se han guardado medicamentos todavía.", "md_saved": "Guardado en tu lista", "md_removed": "Eliminado", "md_remove": "Eliminar", "md_pick_first": "Elige un medicamento de la biblioteca", "md_login_first": "Inicia sesión primero", "md_load_fail": "No se pudo cargar tu lista.", "ac_eyebrow": "Tu cuenta", "ac_title": "Cuenta y privacidad", "ac_lede": "Tu identidad es opcional. El texto médico sensible se procesa con retención mínima — y puedes exportar o borrar todo en cualquier momento.", "ac_signin_p": "Inicia sesión para ver tu perfil, traducciones guardadas y medicamentos.", "ac_signin_btn": "Inicia sesión / Regístrate", "ac_member_since": "Miembro desde {date}", "ac_your_data": "Sus datos", "ac_data_desc": "Exporte una copia JSON completa de todo lo relacionado con su cuenta, o elimine permanentemente sus registros personales (se mantiene su inicio de sesión).", "ac_export": "⬇︎ Exportar todos mis datos", "ac_wipe": "🗑 Eliminar todos los registros personales", "ac_exported": "Exportado a continuación", "ac_wipe_confirm": "¿Eliminar TODAS sus traducciones, medicamentos, triaje y comentarios? Se mantiene su inicio de sesión. Esto no se puede deshacer.", "ac_wiped": "Todos los registros personales eliminados", "ac_feedback": "Comentarios", "ac_category": "Categoría", "ac_cat_translation": "traducción", "ac_cat_hospital": "hospital", "ac_cat_navigation": "navegación", "ac_cat_medication": "medicamento", "ac_cat_feature": "solicitud de función", "ac_cat_other": "otro", "ac_rating": "Calificación (1–5)", "ac_your_msg": "Su mensaje", "ac_msg_ph": "Dígannos cómo podemos mejorar…", "ac_submit": "Enviar comentarios", "ac_fb_thanks": "¡Gracias. Su retroalimentación ha sido recibida.", "ac_fb_write": "Escriba un mensaje", "ac_fb_sent": "Retroalimentación enviada", "footer_a": "TransMed · IA para atención médica transcultural — solo para demostración. En caso de emergencia, llame al 120 o acuda al servicio de urgencias más cercano.", "footer_b": "Las decisiones críticas deben ser confirmadas con un médico licenciado.", "loc_prefix": "Ubicación: {msg}", "ui_translating": "Interfaz de traducción…", "ui_ready": "Idioma listo", "please_login": "Por favor, inicie sesión primero", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "Líder nacional en {sp}", "hp_grade_3a": "Clase III-A (máximo)"}, "it": {"tagline": "Compagno medico AI · assistenza in Cina", "nav_home": "Home", "nav_translate": "Traduci", "nav_hospitals": "Ospedali", "nav_navigation": "Navigazione", "nav_medication": "Farmaci", "nav_account": "Account", "login_register": "Accedi / Registrati", "signout": "Disconnetti", "lang_pick_title": "Scegli la tua lingua", "lang_pick_sub": "L'intera app passerà a essa. Puoi cambiarla in qualsiasi momento dalla barra superiore.", "login_tab": "Accedi", "register_tab": "Registrati", "email": "Email", "password": "Password", "password_min": "Password (min 6 caratteri)", "do_login": "Accedi", "create_account": "Crea il mio account", "demo_hint": "Demo: demo@transmed.io / demo123 · Amministratore: admin@transmed.io / admin123", "fullname": "Nome completo", "pref_lang": "Lingua preferita", "country": "Paese", "signing_in": "Accesso in corso…", "creating": "Creazione account…", "account_created": "Account creato — benvenuto!", "signed_out": "Disconnesso", "login_failed": "Accesso fallito", "reg_failed": "Registrazione fallita", "please_name": "Inserisci il tuo nome", "hero_eyebrow": "Compagno medico di intelligenza artificiale per stranieri in Cina", "hero_title_a": "Ottieni assistenza in Cina", "hero_title_b": "senza la barriera linguistica.", "hero_lead": "Traduzione multilingue di livello medico con punteggio di attendibilità, abbinamento dell'ospedale in base ai sintomi e navigazione nella mappa reale al reparto giusto — tutto in un unico luogo calmo e affidabile.", "hero_cta_translate": "Inizia a tradurre", "hero_cta_hospital": "Trova l'ospedale giusto", "trust_langs": "12 lingue", "trust_data": "Dati reali degli ospedali di Pechino", "trust_privacy": "Riservatezza progettata", "feat_eyebrow": "Cosa fa TransMed", "feat_title": "Quattro passaggi di una visita medica, gestiti.", "feat_sub": "Dalla descrizione dei sintomi alla presenza nel reparto giusto — ogni passaggio è progettato per ridurre l'attrito e l'incertezza.", "feat1_t": "Traduzione medica con intelligenza artificiale", "feat1_d": "Modello medico verticale con allineamento dei termini, un punteggio di confidenza e avvisi di rischio a 4 livelli in modo che nulla di critico vada perso nella traduzione.", "feat2_t": "Abbinamento ospedaliero intelligente", "feat2_d": "Descrivi i tuoi sintomi; TransMed ti indirizza a un reparto e classifica gli ospedali reali in base alla specialità, alla valutazione e alla distanza — con relative motivazioni.", "feat3_t": "Navigazione nella mappa", "feat3_d": "Un percorso disegnato e indicazioni passo dopo passo su una mappa live, più un tap per passare ad Apple, Google, AMap o Baidu Maps.", "feat4_t": "Farmaci e privacy", "feat4_d": "Una libreria di farmaci bilingue con promemoria, e un centro di privacy per esportare o cancellare i tuoi dati personali in qualsiasi momento.", "how_eyebrow": "Come funziona", "how_title": "Dai sintomi alla visita.", "how1_t": "Descrivilo", "how1_d": "Digita i sintomi nella tua lingua. Ottieni una traduzione medica pulita con livello di rischio.", "how2_t": "Fai la triage", "how2_d": "TransMed identifica il reparto giusto e segnala i casi urgenti.", "how3_t": "Scegli un ospedale", "how3_d": "Confronta gli ospedali classificati con valutazioni, recensioni e distanza di viaggio reali.", "how4_t": "Naviga fin là", "how4_d": "Segui il percorso disegnato, o passa alla tua app di mappe preferita.", "stats_eyebrow": "Piattaforma live", "stats_title": "Basata su dati reali.", "st_langs": "Lingue", "st_terms": "Banche terminologiche", "st_hosp": "Ospedali", "st_rules": "Regole di triage", "st_trans": "Traduzioni fornite", "tr_eyebrow": "Traduzione", "tr_title": "Traduzione medica AI", "tr_lede": "Un motore medico verticale. Ogni traduzione viene valutata per confidenza e rischio, con i termini medici riconosciuti evidenziati.", "tr_from": "Da", "tr_to": "A", "tr_src_ph": "Descrivi i sintomi o incolla ciò che ha detto il medico…", "tr_tip": "Suggerimento: essere specifici sulla durata, intensità e allergie.", "tr_btn": "Traduci", "tr_translating": "Sto traducendo…", "tr_result_ph": "La traduzione apparirà qui.", "tr_confidence": "Confidenza", "tr_risk": "Rischio", "tr_ack": "Riconosco l'avviso di rischio", "tr_ack_done": "Rischio riconosciuto", "tr_templates": "Modelli di sintomi rapidi", "tr_my_recent": "Le mie traduzioni recenti", "tr_signin_save": "(accedi per salvare)", "tr_terms_label": "Termini medici riconosciuti", "tr_ref_label": "Riferimento medico ({n})", "tr_advice_low": "Alta fiducia. Comunque conferma i dettagli critici con il tuo clinico.", "tr_advice_med": "Fiducia moderata — controlla le dosi, i numeri e le negazioni.", "tr_advice_high": "Bassa fiducia. Verifica con un membro dello staff bilingue prima di agire in base a questo.", "tr_online": "Online", "tr_offline": "Offline", "tr_hist_signin": "Accedi per mantenere una storia delle tue traduzioni.", "tr_hist_empty": "Nessuna traduzione salvata ancora.", "tr_hist_fail": "Impossibile caricare la storia.", "hp_eyebrow": "Triage e ospedali", "hp_title": "Trova l'ospedale giusto", "hp_lede": "Descrivi i tuoi sintomi — TransMed ti triage in un reparto e classifica gli ospedali reali in base a quanto si adattano, dicendoti il perché.", "hp_sym_label": "Descrivi i tuoi sintomi", "hp_sym_ph": "ad es. mal di testa persistente e febbre alta per 2 giorni", "hp_dept_label": "Dipartimento (opzionale)", "hp_dept_auto": "Rileva automaticamente", "hp_analyze": "Analizza e consiglia", "hp_use_loc": "📍 Usa la mia posizione per la distanza", "hp_loc_set": "📍 Posizione impostata", "hp_locating": "📍 Stiamo cercando…", "hp_sort_by": "Ordina per", "hp_sort_match": "Miglior corrispondenza", "hp_sort_rating": "Valutazione", "hp_sort_distance": "Distanza", "hp_loading": "Caricamento degli ospedali…", "hp_matching": "Ricerca di ospedali corrispondenti…", "hp_describe_first": "Descrivi prima i tuoi sintomi", "hp_loc_first": "Tocca \"Usa la mia posizione\" per prima", "hp_loc_added": "Posizione impostata — distanze aggiunte", "hp_urgent": "🚨 URGENTE", "hp_recommended": "✓ Dipartimento consigliato", "hp_call120": "Se si tratta di un'emergenza, chiama il 120 adesso.", "hp_best_match": "#{n} miglior corrispondenza", "hp_match_cap": "corrispondenza", "hp_strong_in": "Forti in {sp}", "hp_rated": "Valutato {r}/5", "hp_reviews": "{n} recensioni", "hp_reviews_paren": "({n} recensioni)", "hp_km_you": "{km} km da te", "hp_km": "{km} km", "hp_speaks": "Parla la tua lingua", "hp_emergency": "Servizi di emergenza forti", "hp_navigate": "Naviga →", "hp_no_hosp": "Nessun ospedale trovato. Prova a utilizzare un sintomo o un reparto più ampio.", "hp_waking_t": "Il servizio di raccomandazione si sta attivando", "hp_waking_d": "Mostrando tutti gli ospedali nel frattempo. Riprova tra un attimo.", "nv_eyebrow": "Navigazione", "nv_title": "Naviga verso l'assistenza", "nv_lede": "Vedi il percorso disegnato e le indicazioni passo dopo passo su una mappa live — o passa all'app delle mappe del tuo telefono con un solo tocco.", "nv_hospital": "Ospedale", "nv_mode": "Modalità", "nv_walking": "🚶 A piedi", "nv_driving": "🚗 In auto", "nv_transit": "🚇 Trasporto pubblico", "nv_use_loc": "📍 Usa la mia posizione", "nv_locating": "📍 Localizzazione…", "nv_map_loading": "Caricamento mappa…", "nv_origin_default": "📍 Origine: centro città di Pechino (predefinito) · tocca “Usa la mia posizione”.", "nv_origin_gps": "📍 Origine: la tua posizione attuale", "nv_map_unavail": "Mappa live non disponibile.", "nv_map_no_js": "Chiave AMap JS non configurata.", "nv_map_no_backend": "Backend non configurato.", "nv_map_hint": "Usa i pulsanti qui sotto per aprire questo luogo in un'app di mappe.", "nv_open_in": "Apri in mappe:", "nv_planning": "Pianificazione del percorso…", "nv_turn_by_turn": "🧭 Passo dopo passo", "nv_arrive": "Arrivo a {name}", "nv_you": "Tu", "nv_fallback": "Il percorso passo dopo passo richiede la chiave di sicurezza AMap. La distanza/ora sono stime in linea retta — usa i pulsanti sopra per navigare in un'app di mappe.", "nv_dist": "Distanza", "nv_straight": "Linea retta", "nv_duration": "Durata", "nv_est": "Tempo stimato", "nv_mode_label": "Modalità", "nv_walk": "Camminare", "nv_drive": "Guidare", "nv_transit_txt": "Trasporto pubblico", "nv_using_loc": "Utilizzare la tua posizione", "md_eyebrow": "Medicinale", "md_title": "Medicinale e promemoria", "md_lede": "Cerca un farmaco nella libreria bilingue, poi salvalo con gli orari di promemoria nella tua lista personale.", "md_add": "Aggiungi un medicinale", "md_from_lib": "Dalla libreria", "md_choose": "— scegli —", "md_custom": "O nome personalizzato", "md_custom_ph": "ad es. Vitamina D", "md_dosage": "Dosaggio / istruzioni", "md_dosage_ph": "ad es. 1 compressa ogni mattina", "md_times": "Orari di promemoria", "md_notes": "Note", "md_notes_ph": "Dopo i pasti, tenere lontano dal lattosio…", "md_save": "Salva nella mia lista", "md_login_req": "Richiede accesso. Memorizzato sul tuo account.", "md_drug_info": "Informazioni sul farmaco", "md_pick": "Scegli un farmaco dalla libreria per vedere la posologia, gli avvertimenti e gli effetti collaterali.", "md_rx": "Rx", "md_otc": "OTC", "md_dosage_h": "Posologia", "md_warnings_h": "Avvertimenti", "md_side_h": "Effetti collaterali", "md_my_list": "La mia lista dei farmaci", "md_list_signin": "Accedi per salvare i farmaci e i promemoria.", "md_list_empty": "Nessun farmaco salvato ancora.", "md_saved": "Salvato nella tua lista", "md_removed": "Rimosso", "md_remove": "Rimuovi", "md_pick_first": "Scegli un farmaco dalla libreria", "md_login_first": "Per favore, accedi prima", "md_load_fail": "Non è stato possibile caricare la tua lista.", "ac_eyebrow": "Il tuo account", "ac_title": "Account e privacy", "ac_lede": "La tua identità è opzionale. Il testo medico sensibile viene elaborato con una conservazione minima - e puoi esportare o cancellare tutto in qualsiasi momento.", "ac_signin_p": "Accedi per vedere il tuo profilo, le traduzioni salvate e i farmaci.", "ac_signin_btn": "Accedi / Registra", "ac_member_since": "Membro dal {date}", "ac_your_data": "I tuoi dati", "ac_data_desc": "Esporta una copia JSON completa di tutto ciò che è legato al tuo account, o cancella definitivamente i tuoi dati personali (il tuo accesso verrà conservato).", "ac_export": "⬇︎ Esporta tutti i miei dati", "ac_wipe": "🗑 Cancella tutti i dati personali", "ac_exported": "Esportato di seguito", "ac_wipe_confirm": "Cancella TUTTI i tuoi dati di traduzione, farmaci, triage e feedback? Il tuo accesso verrà conservato. Questa azione non può essere annullata.", "ac_wiped": "Tutti i dati personali cancellati", "ac_feedback": "Feedback", "ac_category": "Categoria", "ac_cat_translation": "traduzione", "ac_cat_hospital": "ospedale", "ac_cat_navigation": "navigazione", "ac_cat_medication": "farmaco", "ac_cat_feature": "richiesta di funzionalità", "ac_cat_other": "altro", "ac_rating": "Valutazione (1–5)", "ac_your_msg": "Il tuo messaggio", "ac_msg_ph": "Dici ci come possiamo migliorare…", "ac_submit": "Invia feedback", "ac_fb_thanks": "Grazie! Il tuo feedback è stato ricevuto.", "ac_fb_write": "Per favore, scrivi un messaggio", "ac_fb_sent": "Feedback inviato", "footer_a": "TransMed · AI per l'assistenza sanitaria transculturale — solo a scopo dimostrativo. In caso di emergenza chiama il 120 o vai al pronto soccorso più vicino.", "footer_b": "Le decisioni critiche devono essere confermate con un medico abilitato.", "loc_prefix": "Posizione: {msg}", "ui_translating": "Interfaccia di traduzione…", "ui_ready": "Lingua pronta", "please_login": "Per favore, accedi prima", "welcome_back": "Benvenuto di nuovo, {name}", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "Leader nazionale in {sp}", "hp_grade_3a": "Classe III-A (top)"}, "ru": {"tagline": "Интеллектуальный медицинский компаньон · уход в Китае", "nav_home": "Главная", "nav_translate": "Перевод", "nav_hospitals": "Больницы", "nav_navigation": "Навигация", "nav_medication": "Лекарства", "nav_account": "Аккаунт", "login_register": "Войти / Зарегистрироваться", "signout": "Выйти", "lang_pick_title": "Выберите язык", "lang_pick_sub": "Весь приложение будет переключено на него. Вы можете изменить его в любой момент из верхней панели.", "login_tab": "Войти", "register_tab": "Зарегистрироваться", "email": "Электронная почта", "password": "Пароль", "password_min": "Пароль (мин 6 символов)", "do_login": "Войти", "create_account": "Создать мой аккаунт", "demo_hint": "Демо: demo@transmed.io / demo123 · Админ: admin@transmed.io / admin123", "fullname": "Полное имя", "pref_lang": "Предпочитаемый язык", "country": "Страна", "signing_in": "Вход в систему…", "creating": "Создание учетной записи…", "account_created": "Учетная запись создана — добро пожаловать!", "signed_out": "Выход из системы", "login_failed": "Неудачный вход", "reg_failed": "Неудачная регистрация", "please_name": "Пожалуйста, введите ваше имя", "hero_eyebrow": "Искусственный интеллект-медицинский компаньон для иностранцев в Китае", "hero_title_a": "Получите медицинскую помощь в Китае", "hero_title_b": "без языкового барьера.", "hero_lead": "Медицинский перевод с многими языками и оценкой достоверности, поиск больницы на основе симптомов и навигация на карте к нужному отделению — все в одном спокойном и достоверном месте.", "hero_cta_translate": "Начать перевод", "hero_cta_hospital": "Найти подходящую больницу", "trust_langs": "12 языков", "trust_data": "Реальные данные больниц Пекина", "trust_privacy": "Конфиденциальность по умолчанию", "feat_eyebrow": "Что делает TransMed", "feat_title": "Четыре шага медицинского визита, обработаны.", "feat_sub": "От описания ваших симптомов до стояния в правильном отделении — каждый шаг предназначен для удаления трения и неопределенности.", "feat1_t": "Искусственный интеллект медицинского перевода", "feat1_d": "Вертикальная медицинская модель с выравниванием терминов, баллом уверенности и 4-уровневыми предупреждениями о риске, чтобы ничего критического не было потеряно в переводе.", "feat2_t": "Умное сопоставление больниц", "feat2_d": "Опишите ваши симптомы; TransMed триажирует в отделение и ранжирует реальные больницы по соответствию специальности, рейтингу и расстоянию — с причинами.", "feat3_t": "Навигация на карте", "feat3_d": "Протянутый маршрут и пошаговые указания на живой карте, плюс один касание, чтобы передать управление Apple, Google, AMap или Baidu Maps.", "feat4_t": "Лекарства и конфиденциальность", "feat4_d": "Двухъязычная библиотека лекарств с напоминаниями и центром конфиденциальности для экспорта или удаления ваших личных записей в любое время.", "how_eyebrow": "Как это работает", "how_title": "От симптома до приема.", "how1_t": "Опишите", "how1_d": "Введите симптомы на вашем языке. Получите чистый медицинский перевод с уровнем риска.", "how2_t": "Триаж", "how2_d": "TransMed определяет правильное отделение и помечает срочные случаи.", "how3_t": "Выберите больницу", "how3_d": "Сравните ранжированные больницы с реальными рейтингами, отзывами и расстоянием путешествия.", "how4_t": "Навигируйте туда", "how4_d": "Следуйте протянутому маршруту или передайте управление вашему любимому картографическому приложению.", "stats_eyebrow": "Живая платформа", "stats_title": "Основана на реальных данных.", "st_langs": "Языки", "st_terms": "Терминологические базы", "st_hosp": "Больницы", "st_rules": "Правила триажа", "st_trans": "Переводы", "tr_eyebrow": "Перевод", "tr_title": "Искусственный интеллект медицинского перевода", "tr_lede": "Вертикальный медицинский движок. Каждый перевод оценивается по степени уверенности и риска, с выделением распознанных медицинских терминов.", "tr_from": "Из", "tr_to": "В", "tr_src_ph": "Опишите симптомы или вставьте то, что сказал врач…", "tr_tip": "Совет: будьте конкретны о продолжительности, интенсивности и аллергии.", "tr_btn": "Перевести", "tr_translating": "Перевожу…", "tr_result_ph": "Перевод появится здесь.", "tr_confidence": "Уверенность", "tr_risk": "Риск", "tr_ack": "Я подтверждаю предупреждение о риске", "tr_ack_done": "Риск подтвержден", "tr_templates": "Шаблоны быстрых симптомов", "tr_my_recent": "Мои недавние переводы", "tr_signin_save": "(войдите, чтобы сохранить)", "tr_terms_label": "Признанные медицинские термины", "tr_ref_label": "Медицинская справка ({n})", "tr_advice_low": "Высокая уверенность. Тем не менее подтвердите критические детали с вашим врачом.", "tr_advice_med": "Умеренная уверенность — дважды проверьте дозировки, числа и отрицания.", "tr_advice_high": "Низкая уверенность. Пожалуйста, подтвердите с помощью билингвального сотрудника перед тем, как действовать на основе этого.", "tr_online": "Онлайн", "tr_offline": "Офлайн", "tr_hist_signin": "Войдите, чтобы сохранить историю ваших переводов.", "tr_hist_empty": "Еще нет сохраненных переводов.", "tr_hist_fail": "Не удалось загрузить историю.", "hp_eyebrow": "Триаж и больницы", "hp_title": "Найдите подходящую больницу", "hp_lede": "Опишите ваши симптомы — TransMed направляет вас в отделение и ранжирует реальные больницы по степени соответствия, рассказывая вам почему.", "hp_sym_label": "Опишите ваши симптомы", "hp_sym_ph": "например, постоянная головная боль и высокая температура в течение 2 дней", "hp_dept_label": "Отделение (необязательно)", "hp_dept_auto": "Автоопределение", "hp_analyze": "Анализ и рекомендация", "hp_use_loc": "📍 Использовать моё местоположение для расстояния", "hp_loc_set": "📍 Местоположение установлено", "hp_locating": "📍 Определение местоположения…", "hp_sort_by": "Сортировать по", "hp_sort_match": "Лучшее совпадение", "hp_sort_rating": "Рейтинг", "hp_sort_distance": "Расстояние", "hp_loading": "Загрузка больниц…", "hp_matching": "Совпадающие больницы…", "hp_describe_first": "Опишите ваши симптомы сначала", "hp_loc_first": "Нажмите «Использовать моё местоположение» сначала", "hp_loc_added": "Местоположение установлено — добавлены расстояния", "hp_urgent": "🚨 СРОЧНО", "hp_recommended": "✓ Рекомендуемое отделение", "hp_call120": "Если это чрезвычайная ситуация, позвоните 120 сейчас.", "hp_best_match": "#{n} лучшее совпадение", "hp_match_cap": "совпадение", "hp_strong_in": "Сильный в {sp}", "hp_rated": "Оценено {r}/5", "hp_reviews": "{n} отзывов", "hp_reviews_paren": "({n} отзывов)", "hp_km_you": "{km} км от вас", "hp_km": "{km} км", "hp_speaks": "Говорит на вашем языке", "hp_emergency": "Сильные службы экстренной помощи", "hp_navigate": "Навигация →", "hp_no_hosp": "Больницы не найдены. Попробуйте более широкий симптом или отделение.", "hp_waking_t": "Служба рекомендаций просыпается", "hp_waking_d": "Показать все больницы тем временем. Попробуйте снова через момент.", "nv_eyebrow": "Навигация", "nv_title": "Навигация к медицинской помощи", "nv_lede": "Посмотрите на нарисованную маршрут и пошаговые указания на живой карте — или передайте в приложение карт вашего телефона в один клик.", "nv_hospital": "Больница", "nv_mode": "Режим", "nv_walking": "🚶 Хождение пешком", "nv_driving": "🚗 Вождение", "nv_transit": "🚇 Транспорт", "nv_use_loc": "📍 Используйте моё местоположение", "nv_locating": "📍 Определение местоположения…", "nv_map_loading": "Загрузка карты…", "nv_origin_default": "📍 Начало: центр города Пекин (по умолчанию) · нажмите «Используйте моё местоположение».", "nv_origin_gps": "📍 Начало: ваше текущее местоположение", "nv_map_unavail": "Карта недоступна.", "nv_map_no_js": "Ключ AMap JS не настроен.", "nv_map_no_backend": "Бэкенд не настроен.", "nv_map_hint": "Используйте кнопки ниже, чтобы открыть это место в приложении карт.", "nv_open_in": "Открыть в картах:", "nv_planning": "Планирование маршрута…", "nv_turn_by_turn": "🧭 Поворот за поворотом", "nv_arrive": "Прибыть в {name}", "nv_you": "Вы", "nv_fallback": "Поворот за поворотом требует ключа безопасности AMap. Расстояние/время — прямые оценки — используйте кнопки выше, чтобы ориентироваться в приложении карт.", "nv_dist": "Расстояние", "nv_straight": "Прямая линия", "nv_duration": "Продолжительность", "nv_est": "Оценочное время", "nv_mode_label": "Режим", "nv_walk": "Ходьба", "nv_drive": "Вождение", "nv_transit_txt": "Транспорт", "nv_using_loc": "Использование вашего местоположения", "md_eyebrow": "Лекарства", "md_title": "Лекарства и напоминания", "md_lede": "Найдите лекарство в двуязычной библиотеке, затем сохраните его с напоминаниями о времени приема в вашем личном списке.", "md_add": "Добавить лекарство", "md_from_lib": "Из библиотеки", "md_choose": "— выберите —", "md_custom": "Или ввести наименование вручную", "md_custom_ph": "например, Витамин D", "md_dosage": "Дозировка/инструкции", "md_dosage_ph": "например, 1 таблетка каждое утро", "md_times": "Время напоминаний", "md_notes": "Примечания", "md_notes_ph": "После еды, держать подальше от молочных продуктов…", "md_save": "Сохранить в мой список", "md_login_req": "Требуется вход в систему. Хранится на вашем счете.", "md_drug_info": "Информация о лекарстве", "md_pick": "Выберите лекарство из библиотеки, чтобы увидеть дозировку, предупреждения и побочные эффекты.", "md_rx": "Рецептурные", "md_otc": "Без рецепта", "md_dosage_h": "Дозировка", "md_warnings_h": "Предупреждения", "md_side_h": "Побочные эффекты", "md_my_list": "Список моих лекарств", "md_list_signin": "Войдите, чтобы сохранить лекарства и напоминания.", "md_list_empty": "Лекарства еще не сохранены.", "md_saved": "Сохранено в вашем списке", "md_removed": "Удалено", "md_remove": "Удалить", "md_pick_first": "Выберите лекарство из библиотеки", "md_login_first": "Пожалуйста, сначала войдите в систему", "md_load_fail": "Не удалось загрузить ваш список.", "ac_eyebrow": "Ваш аккаунт", "ac_title": "Аккаунт и конфиденциальность", "ac_lede": "Ваше личность не обязательно. Чувствительный медицинский текст обрабатывается с минимальным хранением — и вы можете экспортировать или удалить все в любое время.", "ac_signin_p": "Войдите, чтобы увидеть ваш профиль, сохраненные переводы и лекарства.", "ac_signin_btn": "Войти / Зарегистрироваться", "ac_member_since": "Член с {date}", "ac_your_data": "Ваши данные", "ac_data_desc": "Экспортировать полную копию JSON всего, что связано с вашим аккаунтом, или永久но удалить ваши личные записи (ваш логин сохраняется).", "ac_export": "⬇︎ Экспортировать все мои данные", "ac_wipe": "🗑 Удалить все личные записи", "ac_exported": "Экспортировано ниже", "ac_wipe_confirm": "Удалить ВСЕ ваши переводы, лекарства,_triаж и обратную связь? Ваш логин сохраняется. Это действие нельзя отменить.", "ac_wiped": "Все личные записи удалены", "ac_feedback": "Обратная связь", "ac_category": "Категория", "ac_cat_translation": "перевод", "ac_cat_hospital": "больница", "ac_cat_navigation": "навигация", "ac_cat_medication": "лекарство", "ac_cat_feature": "запрос функции", "ac_cat_other": "другое", "ac_rating": "Рейтинг (1–5)", "ac_your_msg": "Ваше сообщение", "ac_msg_ph": "Расскажите нам, как мы можем улучшиться…", "ac_submit": "Отправить обратную связь", "ac_fb_thanks": "Спасибо! Ваш отзыв был получен.", "ac_fb_write": "Пожалуйста, напишите сообщение", "ac_fb_sent": "Отзыв отправлен", "footer_a": "TransMed · AI для транскультурного здравоохранения — только для демонстрации. В случае чрезвычайной ситуации позвоните 120 или обратитесь в ближайшее отделение неотложной помощи.", "footer_b": "Критические решения должны быть подтверждены лицензированным врачом.", "loc_prefix": "Местоположение: {msg}", "ui_translating": "Перевод интерфейса…", "ui_ready": "Язык готов", "please_login": "Пожалуйста, сначала войдите в систему", "welcome_back": "Добро пожаловать обратно, {name}", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "Национальный лидер в {sp}", "hp_grade_3a": "Класс III-A (высший)"}, "ar": {"tagline": "رفيق طبي ذكاء اصطناعي · الرعاية في الصين", "nav_home": "الصفحة الرئيسية", "nav_translate": "ترجمة", "nav_hospitals": "المستشفيات", "nav_navigation": "التوجيه", "nav_medication": "الأدوية", "nav_account": "الحساب", "login_register": "تسجيل الدخول / التسجيل", "signout": "تسجيل الخروج", "lang_pick_title": "اختر لغتك", "lang_pick_sub": "سيتم переключение التطبيق بالكامل إلى اللغة التي تختارها. يمكنك تغييرها في أي وقت من شريط أعلى الصفحة.", "login_tab": "تسجيل الدخول", "register_tab": "التسجيل", "email": "البريد الإلكتروني", "password": "كلمة المرور", "password_min": "كلمة المرور (أدنى 6 أحرف)", "do_login": "تسجيل الدخول", "create_account": "إنشاء حسابي", "demo_hint": "عرض التوضيحي: demo@transmed.io / demo123 · مسؤول: admin@transmed.io / admin123", "fullname": "الاسم الكامل", "pref_lang": "اللغة المفضلة", "country": "بلد", "signing_in": "تسجيل الدخول...", "creating": "إنشاء حساب...", "account_created": "تم إنشاء الحساب — مرحباً!", "signed_out": "تسجيل الخروج", "login_failed": "فشل تسجيل الدخول", "reg_failed": "فشل التسجيل", "please_name": "الرجاء إدخال اسمك", "hero_eyebrow": "مرافق طبية ذكية للأجانب في الصين", "hero_title_a": "احصل على رعاية في الصين", "hero_title_b": "بدون حواجز اللغة.", "hero_lead": "ترجمة متعددة اللغات ذات جودة طبية مع تقييم الثقة وتماثل المستشفى حسب الأعراض والتنقل الحقيقي على الخريطة إلى القسم الصحيح - كل ذلك في مكان هادئ وموثوق.", "hero_cta_translate": "ابدأ الترجمة", "hero_cta_hospital": "ابحث عن المستشفى الصحيح", "trust_langs": "12 لغة", "trust_data": "بيانات مستشفى بيجينج الحقيقية", "trust_privacy": "الخصوصية من التصميم", "feat_eyebrow": "ما الذي يفعله TransMed", "feat_title": "أربعة خطوات لزيارة طبية، تمت المعالجة.", "feat_sub": "من وصف أعراضك إلى الوقوف في القسم الصحيح — كل خطوة مصممة لإزالة الاحتكاك والشك.", "feat1_t": "ترجمة طبية بالذكاء الاصطناعي", "feat1_d": "نموذج طبي رأسي مع محاذاة المصطلحات ودرجة ثقة وتنبيهات مخاطر من المستوى 4 حتى لا يفقد شيء حاسم في الترجمة.", "feat2_t": "مطابقة مستشفى ذكية", "feat2_d": "وصف أعراضك؛ يقوم TransMed بترشيح القسم وترتيب المستشفيات الحقيقية حسب التخصص والتصنيف والمسافة — مع الأسباب.", "feat3_t": "التوجيه على الخريطة", "feat3_d": "مسار مخطط وتوجيهات خطوة بخطوة على خريطة حية، بالإضافة إلى لمسة واحدة لنقلها إلى Apple أو Google أو AMap أو Baidu Maps.", "feat4_t": "الأدوية والخصوصية", "feat4_d": "مكتبة أدوية ثنائية اللغة مع تذكيرات، ومركز خصوصية لتصدير أو مسح سجلاتك الشخصية في أي وقت.", "how_eyebrow": "كيف يعمل", "how_title": "من الأعراض إلى المعالجة.", "how1_t": "أوصفها", "how1_d": "اكتب الأعراض بلغتك. احصل على ترجمة طبية نظيفة مع مستوى المخاطر.", "how2_t": "احصل على ترشيح", "how2_d": "يحدد TransMed القسم الصحيح ويرفع أعلام الحالات العاجلة.", "how3_t": "اختر مستشفى", "how3_d": "قارن بين المستشفيات المرتبة مع التصنيفات والمراجعات والمسافة الحقيقية.", "how4_t": "اتجه هناك", "how4_d": "اتبع المسار المخطط أو انقلها إلى تطبيق الخرائط المفضل لديك.", "stats_eyebrow": "منصة حية", "stats_title": "مبنية على بيانات حقيقية.", "st_langs": "اللغات", "st_terms": "قواعد المصطلحات", "st_hosp": "المستشفيات", "st_rules": "قواعد التriage", "st_trans": "الترجمات المقدمة", "tr_eyebrow": "الترجمة", "tr_title": "ترجمة طبية بالذكاء الاصطناعي", "tr_lede": "محرك طبي رأسي. يتم تقييم كل ترجمة للاطمان والخطر، مع تhighlight المصطلحات الطبية التي تم التعرف عليها.", "tr_from": "من", "tr_to": "إلى", "tr_src_ph": "أصف الأعراض، أو الصق ما قاله الطبيب…", "tr_tip": "نصيحة: كن محددًا حول المدة والشدة والحساسية.", "tr_btn": "ترجمة", "tr_translating": "جاري الترجمة…", "tr_result_ph": "ستظهر الترجمة هنا.", "tr_confidence": "الاطمان", "tr_risk": "الخطر", "tr_ack": "أقر بتحذير الخطر", "tr_ack_done": "المخاطر المعترف بها", "tr_templates": "قوالب الأعراض السريعة", "tr_my_recent": "ترجماتي الأخيرة", "tr_signin_save": "(سجّل الدخول لحفظ)", "tr_terms_label": "المصطلحات الطبية المعترف بها", "tr_ref_label": "مرجع طبي ({n})", "tr_advice_low": "ثقة عالية. لا يزال يتعين عليك التحقق من التفاصيل الحاسمة مع طبيبك.", "tr_advice_med": "ثقة متوسطة — تحقق مرة أخرى من الجرعات والأرقام والnegations.", "tr_advice_high": "ثقة منخفضة. يرجى التحقق مع موظف ثنائي اللغة قبل اتخاذ أي إجراء بناءً على ذلك.", "tr_online": "オンライン", "tr_offline": "أوفلاين", "tr_hist_signin": "سجّل الدخول لحفظ تاريخ ترجماتك.", "tr_hist_empty": "لا توجد ترجمات محفوظة حتى الآن.", "tr_hist_fail": "تعذر تحميل التاريخ.", "hp_eyebrow": "الترياج والمستشفيات", "hp_title": "ابحث عن المستشفى الصحيح", "hp_lede": "أصف أعراضي — يوجهك TransMed إلى قسم ويصنف المستشفيات الحقيقية حسب مدى ملاءمتها ، ويخبرك بالسبب.", "hp_sym_label": "أصف أعراضي", "hp_sym_ph": "على سبيل المثال ، صداع مستمر وحرارة عالية لمدة 2 يوم", "hp_dept_label": "قسم (اختياري)", "hp_dept_auto": "التحديد التلقائي", "hp_analyze": "تحليل وتوصية", "hp_use_loc": "📍 استخدم موقعي للحصول على المسافة", "hp_loc_set": "📍 تم تعيين الموقع", "hp_locating": "📍 تحديد الموقع…", "hp_sort_by": "ترتيب حسب", "hp_sort_match": "أفضل تطابق", "hp_sort_rating": "التقييم", "hp_sort_distance": "المسافة", "hp_loading": "تحميل المستشفيات…", "hp_matching": "مستشفيات مطابقة…", "hp_describe_first": "أصف أعراضك أولاً", "hp_loc_first": "انقر على \"استخدم موقعي\" أولاً", "hp_loc_added": "تم تعيين الموقع — تم إضافة المسافات", "hp_urgent": "🚨 عاجل", "hp_recommended": "✓ قسم موصى به", "hp_call120": "إذا كانت هذه حالة طارئة، اتصل بالرقم 120 الآن.", "hp_best_match": "#{n} أفضل تطابق", "hp_match_cap": "تطابق", "hp_strong_in": "قوي في {sp}", "hp_rated": "مصنف {r}/5", "hp_reviews": "{n} تقييمات", "hp_reviews_paren": "({n} تقييمات)", "hp_km_you": "{km} كم منك", "hp_km": "{km} كم", "hp_speaks": "يتحدث لغتك", "hp_emergency": "خدمات الطوارئ القوية", "hp_navigate": "توجيه →", "hp_no_hosp": "لم يتم العثور على مستشفيات. حاول استخدام عرض أعراض أو قسم أوسع.", "hp_waking_t": "خدمة التوصية تستيقظ", "hp_waking_d": "عرض جميع المستشفيات في الوقت الحالي. حاول مرة أخرى بعد لحظة.", "nv_eyebrow": "التنقل", "nv_title": "توجيه إلى الرعاية", "nv_lede": "انظر المسار المرسوم والتعليمات خطوة بخطوة على خريطة حية - أو قم بنقلها إلى تطبيق خرائط هاتفك في لمسة واحدة.", "nv_hospital": "المستشفى", "nv_mode": "الوضع", "nv_walking": "🚶 المشي", "nv_driving": "🚗 القيادة", "nv_transit": "🚇 النقل العام", "nv_use_loc": "📍 استخدم موقعي", "nv_locating": "📍 يُحدد الموقع…", "nv_map_loading": "تحميل الخريطة…", "nv_origin_default": "📍 المنشأ: وسط مدينة بيجين (افتراضي) · انقر على \"استخدم موقعي\".", "nv_origin_gps": "📍 المنشأ: موقعك الحالي", "nv_map_unavail": "خريطة مباشرة غير متاحة.", "nv_map_no_js": "مفتاح AMap JS غير معين.", "nv_map_no_backend": "الخلفية غير معينة.", "nv_map_hint": "استخدم الأزرار أدناه لفتح هذا المكان في تطبيق خريطة.", "nv_open_in": "افتح في الخريطة:", "nv_planning": "تخطيط المسار…", "nv_turn_by_turn": "🧭 التوجيه خطوة بخطوة", "nv_arrive": "وصل إلى {name}", "nv_you": "أنت", "nv_fallback": "التوجيه خطوة بخطوة يحتاج إلى مفتاح أمان AMap. المسافة / الوقت هي تقديرات خط مستقيم — استخدم الأزرار أعلاه للتنقل في تطبيق خريطة.", "nv_dist": "المسافة", "nv_straight": "الخط المستقيم", "nv_duration": "المدة", "nv_est": "الوقت المقدر", "nv_mode_label": "الوضع", "nv_walk": "المشي", "nv_drive": "القيادة", "nv_transit_txt": "النقل العام", "nv_using_loc": "استخدام موقعك", "md_eyebrow": "الأدوية", "md_title": "الأدوية وتذكيراتها", "md_lede": "ابحث عن دواء في المكتبة الثنائية اللغة، ثم احفظه مع أوقات التذكير إلى قائمة خاصة بك.", "md_add": "أضف دواء", "md_from_lib": "من المكتبة", "md_choose": "— اختر —", "md_custom": "أو اسم مخصص", "md_custom_ph": "مثل فيتامين د", "md_dosage": "الجرعة / الإرشادات", "md_dosage_ph": "مثل حبة واحدة في كل صباح", "md_times": "أوقات التذكير", "md_notes": "ملاحظات", "md_notes_ph": "بعد الأكل، ابق بعيدا عن الألبان…", "md_save": "احفظ إلى قائمتى", "md_login_req": "يتطلب تسجيل الدخول. يتم تخزينه ضد حسابك.", "md_drug_info": "معلومات الدواء", "md_pick": "اختر دواءً من المكتبة لمشاهدة الجرعة والتحذيرات والأعراض الجانبية.", "md_rx": "الوصفات الطبية", "md_otc": "العلاجات بدون وصفة طبية", "md_dosage_h": "الجرعة", "md_warnings_h": "التحذيرات", "md_side_h": "الأعراض الجانبية", "md_my_list": "قائمة أدويتي", "md_list_signin": "سجّل الدخول لحفظ الأدوية والتذكيرات.", "md_list_empty": "لا توجد أدوية محفوظة حتى الآن.", "md_saved": "تم الحفظ إلى قائمةك", "md_removed": "تم الإزالة", "md_remove": "إزالة", "md_pick_first": "اختر دواءً من المكتبة", "md_login_first": "يرجى تسجيل الدخول أولاً", "md_load_fail": "لم يتم تحميل قائمةك.", "ac_eyebrow": "حسабك", "ac_title": "الحساب والخصوصية", "ac_lede": "هويتك اختيارية. يتم معالجة النصوص الطبية الحساسة مع الحد الأدنى من الاحتفاظ - ويمكنك تصدير أو مسح كل شيء في أي وقت.", "ac_signin_p": "سجّل الدخول لمشاهدة ملفك الشخصي والترجمات المحفوظة والأدوية.", "ac_signin_btn": "سجّل الدخول / سجّل", "ac_member_since": "عضو منذ {date}", "ac_your_data": "بياناتك", "ac_data_desc": "استخرج نسخة JSON كاملة من كل ما مربوط بحسابك ، أو احذف بشكل دائم سجلاتك الشخصية (سوف يتم الاحتفاظ بمعلومات تسجيل الدخول الخاصة بك).", "ac_export": "⬇︎ استخرج كل بياناتي", "ac_wipe": "🗑 احذف كل السجلات الشخصية", "ac_exported": "تم استخراج ما يلي", "ac_wipe_confirm": "احذف كل الترجمات الخاصة بك والادوية والترشيح والتعليقات؟ سوف يتم الاحتفاظ بمعلومات تسجيل الدخول الخاصة بك. لا يمكن التراجع عن هذا.", "ac_wiped": "تم حذف كل السجلات الشخصية", "ac_feedback": "التعليقات", "ac_category": "الفئة", "ac_cat_translation": "الترجمة", "ac_cat_hospital": "المستشفى", "ac_cat_navigation": "التنقل", "ac_cat_medication": "الأدوية", "ac_cat_feature": "طلب ميزة", "ac_cat_other": "أخرى", "ac_rating": "التقييم (1-5)", "ac_your_msg": "رسالتك", "ac_msg_ph": "告نا كيف يمكننا تحسين...", "ac_submit": "إرسال التعليقات", "ac_fb_thanks": "شكراً! تم استلام ملاحظاتك.", "ac_fb_write": "الرجاء كتابة رسالة", "ac_fb_sent": "تم إرسال ملاحظات", "footer_a": "TransMed · الذكاء الاصطناعي للرعاية الصحية عبر الثقافات — للعرض فقط. في حالة الطوارئ اتصل بالرقم 120 أو اذهب إلى أقرب غرفة طوارئ.", "footer_b": "يجب تأكيد القرارات الحاسمة مع طبيب مرخص.", "loc_prefix": "الموقع: {msg}", "ui_translating": "واجهة الترجمة…", "ui_ready": "اللغة جاهزة", "please_login": "الرجاء تسجيل الدخول أولاً", "welcome_back": "مرحباً بك مرة أخرى، {name}", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "رائد وطني في {sp}", "hp_grade_3a": "الفئة III-A (الأعلى)"}, "pt": {"tagline": "Companheiro médico de IA · cuidado na China", "nav_home": "Início", "nav_translate": "Traduzir", "nav_hospitals": "Hospitais", "nav_navigation": "Navegação", "nav_medication": "Medicação", "nav_account": "Conta", "login_register": "Entrar / Registrar", "signout": "Sair", "lang_pick_title": "Escolha seu idioma", "lang_pick_sub": "Todo o aplicativo mudará para ele. Você pode alterá-lo a qualquer momento a partir da barra superior.", "login_tab": "Entrar", "register_tab": "Registrar", "email": "E-mail", "password": "Senha", "password_min": "Senha (min 6 caracteres)", "do_login": "Entrar", "create_account": "Criar minha conta", "demo_hint": "Demonstração: demo@transmed.io / demo123 · Administrador: admin@transmed.io / admin123", "fullname": "Nome completo", "pref_lang": "Idioma preferido", "country": "País", "signing_in": "Conectando…", "creating": "Criando conta…", "account_created": "Conta criada — bem-vindo!", "signed_out": "Desconectado", "login_failed": "Falha no login", "reg_failed": "Falha no registro", "please_name": "Por favor, insira seu nome", "hero_eyebrow": "Companheiro médico de IA para estrangeiros na China", "hero_title_a": "Obtenha atendimento na China", "hero_title_b": "sem a barreira linguística.", "hero_lead": "Tradução multilíngue de grau médico com pontuação de confiança, combinação de sintomas com hospitais e navegação real no mapa para o departamento correto — tudo em um lugar calmo e confiável.", "hero_cta_translate": "Iniciar tradução", "hero_cta_hospital": "Encontrar o hospital certo", "trust_langs": "12 idiomas", "trust_data": "Dados reais de hospitais de Pequim", "trust_privacy": "Privacidade por design", "feat_eyebrow": "O que a TransMed faz", "feat_title": "Quatro etapas de uma visita médica, tratadas.", "feat_sub": "Desde descrever seus sintomas até estar no departamento certo — cada etapa é projetada para remover atrito e incerteza.", "feat1_t": "Tradução médica por IA", "feat1_d": "Modelo médico vertical com alinhamento de termos, pontuação de confiança e alertas de risco em 4 níveis, para que nada crítico se perca na tradução.", "feat2_t": "Combinação de hospitais inteligentes", "feat2_d": "Descreva seus sintomas; TransMed tria para um departamento e classifica hospitais reais por ajuste de especialidade, classificação e distância — com razões.", "feat3_t": "Navegação no mapa", "feat3_d": "Uma rota desenhada e direções passo a passo em um mapa ao vivo, mais um toque para passar para Apple, Google, AMap ou Baidu Maps.", "feat4_t": "Medicação e privacidade", "feat4_d": "Uma biblioteca de medicamentos bilíngue com lembretes, e um centro de privacidade para exportar ou apagar seus registros pessoais a qualquer momento.", "how_eyebrow": "Como funciona", "how_title": "Desde o sintoma até o atendimento.", "how1_t": "Descreva", "how1_d": "Digite os sintomas em seu idioma. Obtenha uma tradução médica limpa com nível de risco.", "how2_t": "Seja triado", "how2_d": "TransMed identifica o departamento certo e sinaliza casos urgentes.", "how3_t": "Escolha um hospital", "how3_d": "Compare hospitais classificados com classificações reais, avaliações e distância de viagem.", "how4_t": "Navegue até lá", "how4_d": "Siga a rota desenhada ou passe para seu aplicativo de mapas favorito.", "stats_eyebrow": "Plataforma ao vivo", "stats_title": "Baseado em dados reais.", "st_langs": "Línguas", "st_terms": "Bancos terminológicos", "st_hosp": "Hospitais", "st_rules": "Regras de triagem", "st_trans": "Traduções fornecidas", "tr_eyebrow": "Tradução", "tr_title": "Tradução médica por IA", "tr_lede": "Um motor médico vertical. Cada tradução é pontuada para confiança e risco, com os termos médicos que reconheceu destacados.", "tr_from": "De", "tr_to": "Para", "tr_src_ph": "Descreva os sintomas ou cole o que o médico disse…", "tr_tip": "Dica: seja específico sobre duração, intensidade e alergias.", "tr_btn": "Traduzir", "tr_translating": "Traduzindo…", "tr_result_ph": "A tradução aparecerá aqui.", "tr_confidence": "Confiança", "tr_risk": "Risco", "tr_ack": "Eu reconheço o alerta de risco", "tr_ack_done": "Risco reconhecido", "tr_templates": "Modelos de sintomas rápidos", "tr_my_recent": "Minhas traduções recentes", "tr_signin_save": "(entre para salvar)", "tr_terms_label": "Termos médicos reconhecidos", "tr_ref_label": "Referência médica ({n})", "tr_advice_low": "Alta confiança. Confirme ainda os detalhes críticos com seu clínico.", "tr_advice_med": "Confiança moderada — verifique as dosagens, números e negações.", "tr_advice_high": "Baixa confiança. Por favor, verifique com um membro da equipe bilíngue antes de agir com base nisso.", "tr_online": "Online", "tr_offline": "Offline", "tr_hist_signin": "Entre para manter um histórico de suas traduções.", "tr_hist_empty": "Nenhuma tradução salva ainda.", "tr_hist_fail": "Não foi possível carregar o histórico.", "hp_eyebrow": "Triage & hospitais", "hp_title": "Encontre o hospital certo", "hp_lede": "Descreva seus sintomas — TransMed o tria para um departamento e classifica hospitais reais por quão bem se encaixam, dizendo-lhe por quê.", "hp_sym_label": "Descreva seus sintomas", "hp_sym_ph": "ex. dor de cabeça persistente e febre alta por 2 dias", "hp_dept_label": "Departamento (opcional)", "hp_dept_auto": "Detecção automática", "hp_analyze": "Analisar e recomendar", "hp_use_loc": "📍 Use minha localização para distância", "hp_loc_set": "📍 Localização definida", "hp_locating": "📍 Localizando…", "hp_sort_by": "Classificar por", "hp_sort_match": "Melhor combinação", "hp_sort_rating": "Avaliação", "hp_sort_distance": "Distância", "hp_loading": "Carregando hospitais…", "hp_matching": "Hospitais combinados…", "hp_describe_first": "Descreva seus sintomas primeiro", "hp_loc_first": "Toque em “Use minha localização” primeiro", "hp_loc_added": "Localização definida — distâncias adicionadas", "hp_urgent": "🚨 URGENTE", "hp_recommended": "✓ Departamento recomendado", "hp_call120": "Se for uma emergência, ligue para 120 agora.", "hp_best_match": "#{n} melhor combinação", "hp_match_cap": "combinação", "hp_strong_in": "Fortes em {sp}", "hp_rated": "Avaliado {r}/5", "hp_reviews": "{n} avaliações", "hp_reviews_paren": "({n} avaliações)", "hp_km_you": "{km} km de distância de você", "hp_km": "{km} km", "hp_speaks": "Fala o seu idioma", "hp_emergency": "Serviços de emergência fortes", "hp_navigate": "Navegar →", "hp_no_hosp": "Nenhum hospital encontrado. Tente uma sintoma ou departamento mais amplo.", "hp_waking_t": "Serviço de recomendação está acordando", "hp_waking_d": "Mostrando todos os hospitais enquanto isso. Tente novamente em um momento.", "nv_eyebrow": "Navegação", "nv_title": "Navegar para o atendimento", "nv_lede": "Veja a rota desenhada e as direções passo a passo em um mapa ao vivo — ou transfira para o aplicativo de mapas do seu telefone em um toque.", "nv_hospital": "Hospital", "nv_mode": "Modo", "nv_walking": "🚶 A pé", "nv_driving": "🚗 Dirigindo", "nv_transit": "🚇 Transporte público", "nv_use_loc": "📍 Use minha localização", "nv_locating": "📍 Localizando…", "nv_map_loading": "Carregando mapa…", "nv_origin_default": "📍 Origem: centro da cidade de Pequim (padrão) · toque em “Use minha localização”.", "nv_origin_gps": "📍 Origem: sua localização atual", "nv_map_unavail": "Mapa ao vivo indisponível.", "nv_map_no_js": "Chave JS do AMap não configurada.", "nv_map_no_backend": "Backend não configurado.", "nv_map_hint": "Use os botões abaixo para abrir este local em um aplicativo de mapas.", "nv_open_in": "Abrir no mapa:", "nv_planning": "Planejando rota…", "nv_turn_by_turn": "🧭 Rota passo a passo", "nv_arrive": "Chegar em {name}", "nv_you": "Você", "nv_fallback": "Rota passo a passo precisa da chave de segurança do AMap. Distância/temps são estimativas em linha reta — use os botões acima para navegar em um aplicativo de mapas.", "nv_dist": "Distância", "nv_straight": "Em linha reta", "nv_duration": "Duração", "nv_est": "Tempo estimado", "nv_mode_label": "Modo", "nv_walk": "Caminhada", "nv_drive": "Dirigindo", "nv_transit_txt": "Trânsito", "nv_using_loc": "Usando sua localização", "md_eyebrow": "Medicação", "md_title": "Medicação e lembretes", "md_lede": "Pesquise um medicamento na biblioteca bilíngue, então salve-o com horários de lembrete para sua lista pessoal.", "md_add": "Adicionar um medicamento", "md_from_lib": "Da biblioteca", "md_choose": "— escolher —", "md_custom": "Ou nome personalizado", "md_custom_ph": "ex. Vitamina D", "md_dosage": "Dosagem / instruções", "md_dosage_ph": "ex. 1 comprimido todas as manhãs", "md_times": "Horários de lembrete", "md_notes": "Notas", "md_notes_ph": "Após as refeições, mantenha afastado de laticínios…", "md_save": "Salvar para minha lista", "md_login_req": "Requer login. Armazenado contra sua conta.", "md_drug_info": "Informações de medicamento", "md_pick": "Escolha um medicamento da biblioteca para ver a dosagem, advertências e efeitos colaterais.", "md_rx": "Rx", "md_otc": "OTC", "md_dosage_h": "Dosagem", "md_warnings_h": "Advertências", "md_side_h": "Efeitos colaterais", "md_my_list": "Minha lista de medicamentos", "md_list_signin": "Faça login para salvar medicamentos e lembretes.", "md_list_empty": "Nenhum medicamento salvo ainda.", "md_saved": "Salvo para sua lista", "md_removed": "Removido", "md_remove": "Remover", "md_pick_first": "Escolha um medicamento da biblioteca", "md_login_first": "Por favor, faça login primeiro", "md_load_fail": "Não foi possível carregar sua lista.", "ac_eyebrow": "Sua conta", "ac_title": "Conta e privacidade", "ac_lede": "Sua identidade é opcional. Textos médicos sensíveis são processados com retenção mínima — e você pode exportar ou apagar tudo a qualquer momento.", "ac_signin_p": "Faça login para ver seu perfil, traduções salvas e medicamentos.", "ac_signin_btn": "Faça login / Registrar-se", "ac_member_since": "Membro desde {date}", "ac_your_data": "Seus dados", "ac_data_desc": "Exporte uma cópia JSON completa de tudo vinculado à sua conta, ou exclua permanentemente seus registros pessoais (seu login é mantido).", "ac_export": "⬇︎ Exportar todos os meus dados", "ac_wipe": "🗑 Excluir todos os registros pessoais", "ac_exported": "Exportado abaixo", "ac_wipe_confirm": "Excluir TODAS as suas traduções, medicamentos, triagem e feedback? Seu login é mantido. Isso não pode ser desfeito.", "ac_wiped": "Todos os registros pessoais excluídos", "ac_feedback": "Comentários", "ac_category": "Categoria", "ac_cat_translation": "tradução", "ac_cat_hospital": "hospital", "ac_cat_navigation": "navegação", "ac_cat_medication": "medicamento", "ac_cat_feature": "solicitação de recurso", "ac_cat_other": "outro", "ac_rating": "Avaliação (1–5)", "ac_your_msg": "Sua mensagem", "ac_msg_ph": "Diga-nos como podemos melhorar…", "ac_submit": "Enviar comentários", "ac_fb_thanks": "Obrigado! Seu feedback foi recebido.", "ac_fb_write": "Por favor, escreva uma mensagem", "ac_fb_sent": "Feedback enviado", "footer_a": "TransMed · IA para saúde transcultural — apenas para demonstração. Em caso de emergência, ligue 120 ou vá para o pronto-socorro mais próximo.", "footer_b": "Decisões críticas devem ser confirmadas com um médico licenciado.", "loc_prefix": "Localização: {msg}", "ui_translating": "Interface de tradução…", "ui_ready": "Idioma pronto", "please_login": "Por favor, faça login primeiro", "welcome_back": "Bem-vindo de volta, {name}", "tr_conf_line": "confidence {n}% · {risk}", "hp_national_leader": "Líder nacional em {sp}", "hp_grade_3a": "Classe III-A (topo)"}, "hi": {"tagline": "एआई मेडिकल साथी · चीन में देखभाल", "nav_home": "होम", "nav_translate": "अनुवाद", "nav_hospitals": "अस्पताल", "nav_navigation": "नेविगेशन", "nav_medication": "दवा", "nav_account": "खाता", "login_register": "लॉग इन / पंजीकरण", "signout": "लॉग आउट", "lang_pick_title": "अपनी भाषा चुनें", "lang_pick_sub": "पूरा ऐप इस पर स्विच हो जाएगा। आप इसे कभी भी ऊपरी बार से बदल सकते हैं।", "login_tab": "लॉग इन", "register_tab": "पंजीकरण", "email": "ईमेल", "password": "पासवर्ड", "password_min": "पासवर्ड (न्यूनतम ६ अक्षर)", "do_login": "लॉग इन", "create_account": "मेरा खाता बनाएं", "demo_hint": "डेमो: demo@transmed.io / demo123 · प्रशासक: admin@transmed.io / admin123", "fullname": "पूरा नाम", "pref_lang": "पसंदीदा भाषा", "country": "देश", "signing_in": "साइन इन कर रहा है…", "creating": "खाता बना रहा है…", "account_created": "खाता बनाया गया — स्वागत है!", "signed_out": "साइन आउट किया गया", "login_failed": "लॉगिन विफल", "reg_failed": "पंजीकरण विफल", "please_name": "कृपया अपना नाम दर्ज करें", "hero_eyebrow": "चीन में विदेशियों के लिए एआई मेडिकल साथी", "hero_title_a": "चीन में देखभाल प्राप्त करें", "hero_title_b": "भाषा बाधा के बिना।", "hero_lead": "आत्मविश्वास स्कोरिंग, लक्षण-आधारित अस्पताल मिलान, और सही विभाग के लिए वास्तविक मानचित्र नेविगेशन के साथ चिकित्सा ग्रेड बहुभाषी अनुवाद — सभी एक शांत, विश्वसनीय स्थान पर।", "hero_cta_translate": "अनुवाद शुरू करें", "hero_cta_hospital": "सही अस्पताल ढूंढें", "trust_langs": "12 भाषाएं", "trust_data": "वास्तविक बीजिंग अस्पताल डेटा", "trust_privacy": "डिज़ाइन द्वारा गोपनीयता", "feat_eyebrow": "ट्रांसमेड क्या करता है", "feat_title": "चिकित्सा यात्रा के चार चरण, संभाले गए।", "feat_sub": "अपने लक्षणों का वर्णन करने से लेकर सही विभाग में खड़े होने तक — प्रत्येक चरण घर्षण और अनिश्चितता को दूर करने के लिए डिज़ाइन किया गया है।", "feat1_t": "एआई चिकित्सा अनुवाद", "feat1_d": "शब्द संरेखण, एक विश्वास स्कोर और ४-स्तरीय जोखिम अलर्ट के साथ ऊर्ध्वाधर चिकित्सा मॉडल, ताकि अनुवाद में कुछ भी महत्वपूर्ण न खो जाए।", "feat2_t": "स्मार्ट अस्पताल मिलान", "feat2_d": "अपने लक्षणों का वर्णन करें; ट्रांसमेड एक विभाग के लिए त्रि-स्तरीय और वास्तविक अस्पतालों को विशेषज्ञता, रेटिंग और दूरी के अनुसार रैंक करता है — कारणों के साथ।", "feat3_t": "मानचित्र नेविगेशन", "feat3_d": "एक लाइव मानचित्र पर एक आकर्षित मार्ग और मोड़-दर-मोड़ दिशाएं, साथ ही एप्पल, गूगल, एएमएपी या बaidu मानचित्रों को हाथ में देने के लिए एक टैप।", "feat4_t": "दवा और गोपनीयता", "feat4_d": "एक द्विभाषी दवा पुस्तकालय अनुस्मारक के साथ, और अपने व्यक्तिगत रिकॉर्ड को कभी भी निर्यात या मिटाने के लिए एक गोपनीयता केंद्र।", "how_eyebrow": "यह कैसे काम करता है", "how_title": "लक्षण से देखा जाना।", "how1_t": "वर्णन करें", "how1_d": "अपनी भाषा में लक्षण टाइप करें। जोखिम स्तर के साथ एक साफ़ चिकित्सा अनुवाद प्राप्त करें।", "how2_t": "त्रि-स्तरीय प्राप्त करें", "how2_d": "ट्रांसमेड सही विभाग की पहचान करता है और तत्काल मामलों को झंडा दिखाता है।", "how3_t": "एक अस्पताल चुनें", "how3_d": "वास्तविक रेटिंग, समीक्षा और यात्रा दूरी के साथ रैंक किए गए अस्पतालों की तुलना करें।", "how4_t": "वहां नेविगेट करें", "how4_d": "आकर्षित मार्ग का पालन करें, या अपने पसंदीदा मानचित्र ऐप को हाथ में दें।", "stats_eyebrow": "लाइव प्लेटफ़ॉर्म", "stats_title": "वास्तविक डेटा पर आधारित।", "st_langs": "भाषाएँ", "st_terms": "शब्दावली बैंक", "st_hosp": "अस्पताल", "st_rules": "त्रियाज नियम", "st_trans": "अनुवाद की सेवाएँ", "tr_eyebrow": "अनुवाद", "tr_title": "एआई चिकित्सा अनुवाद", "tr_lede": "एक ऊर्ध्वाधर चिकित्सा इंजन। प्रत्येक अनुवाद विश्वास और जोखिम के लिए स्कोर किया जाता है, जिसमें पहचाने गए चिकित्सा शब्दों को हाइलाइट किया जाता है।", "tr_from": "से", "tr_to": "लिए", "tr_src_ph": "लक्षणों का वर्णन करें, या डॉक्टर ने जो कहा उसे पेस्ट करें…", "tr_tip": "सुझाव: अवधि, तीव्रता और एलर्जी के बारे में विशिष्ट रहें।", "tr_btn": "अनुवादित करें", "tr_translating": "अनुवादित किया जा रहा है…", "tr_result_ph": "अनुवाद यहाँ दिखाई देगा।", "tr_confidence": "विश्वास", "tr_risk": "जोखिम", "tr_ack": "मैं जोखिम चेतावनी को स्वीकार करता हूँ", "tr_ack_done": "जोखिम स्वीकार किया गया", "tr_templates": "त्वरित लक्षण टेम्पलेट", "tr_my_recent": "मेरे हाल के अनुवाद", "tr_signin_save": "(साइन इन करें और सेव करें)", "tr_terms_label": "मान्यता प्राप्त चिकित्सा शब्द", "tr_ref_label": "चिकित्सा संदर्भ ({n})", "tr_advice_low": "उच्च विश्वास। अभी भी अपने चिकित्सक के साथ महत्वपूर्ण विवरण की पुष्टि करें।", "tr_advice_med": "मध्यम विश्वास - खुराक, संख्या और नकारात्मकता की जांच दो बार करें।", "tr_advice_high": "निम्न विश्वास। कृपया द्विभाषी कर्मचारी सदस्य के साथ सत्यापित करें trước कि आप इस पर कार्रवाई करें।", "tr_online": "ऑनलाइन", "tr_offline": "ऑफलाइन", "tr_hist_signin": "अपने अनुवादों का इतिहास रखने के लिए साइन इन करें।", "tr_hist_empty": "अब तक कोई सेव अनुवाद नहीं है।", "tr_hist_fail": "इतिहास लोड नहीं किया जा सका।", "hp_eyebrow": "ट्रायज और अस्पताल", "hp_title": "सही अस्पताल ढूंढें", "hp_lede": "अपने लक्षणों का वर्णन करें - ट्रांसमेड आपको एक विभाग में ट्रायज करता है और अस्पतालों को उनकी फिटनेस के अनुसार रैंक करता है, बताता है कि क्यों।", "hp_sym_label": "अपने लक्षणों का वर्णन करें", "hp_sym_ph": "उदाहरण के लिए, 2 दिनों से लगातार सिरदर्द और उच्च बुखार", "hp_dept_label": "विभाग (वैकल्पिक)", "hp_dept_auto": "स्वचालित रूप से पता लगाएं", "hp_analyze": "विश्लेषण और सिफारिश करें", "hp_use_loc": "📍 मेरे स्थान का उपयोग दूरी के लिए करें", "hp_loc_set": "📍 स्थान निर्धारित", "hp_locating": "📍 स्थान ढूंढ रहा है...", "hp_sort_by": "द्वारा छाँटें", "hp_sort_match": "सर्वोत्तम मेल", "hp_sort_rating": "रेटिंग", "hp_sort_distance": "दूरी", "hp_loading": "अस्पतालों को लोड कर रहा है...", "hp_matching": "मेल खाने वाले अस्पतालों को ढूंढ रहा है...", "hp_describe_first": "अपने लक्षणों का वर्णन पहले करें", "hp_loc_first": "\"मेरे स्थान का उपयोग करें\" पर टैप करें", "hp_loc_added": "स्थान निर्धारित — दूरी जोड़ी गई", "hp_urgent": "🚨 आपातकालीन", "hp_recommended": "✓ अनुशंसित विभाग", "hp_call120": "यदि यह एक आपातकालीन स्थिति है, तो अभी 120 पर कॉल करें।", "hp_best_match": "#{n} सर्वोत्तम मेल", "hp_match_cap": "मेल", "hp_strong_in": "मजबूत {sp} में", "hp_rated": "{r}/5 रेटिंग", "hp_reviews": "{n} समीक्षाएं", "hp_reviews_paren": "({n} समीक्षाएं)", "hp_km_you": "आपसे {km} किमी दूर", "hp_km": "{km} किमी", "hp_speaks": "आपकी भाषा बोलता है", "hp_emergency": "मजबूत आपातकालीन सेवाएं", "hp_navigate": "नेविगेट →", "hp_no_hosp": "कोई अस्पताल नहीं मिला। एक व्यापक लक्षण या विभाग का प्रयास करें।", "hp_waking_t": "सिफारिश सेवा जाग रही है", "hp_waking_d": "इस बीच सभी अस्पतालों को दिखा रहा है। एक पल में फिर से कोशिश करें।", "nv_eyebrow": "नेविगेशन", "nv_title": "देखभाल की ओर नेविगेट करें", "nv_lede": "एक लाइव मानचित्र पर खींची गई मार्ग और मोड़-दर-मोड़ दिशाएं देखें — या एक टैप में अपने फोन के मानचित्र ऐप को हाथ में दे दें।", "nv_hospital": "अस्पताल", "nv_mode": "मोड", "nv_walking": "🚶 पैदल चलना", "nv_driving": "🚗 ड्राइविंग", "nv_transit": "🚇 ट्रांजिट", "nv_use_loc": "📍 मेरे स्थान का उपयोग करें", "nv_locating": "📍 स्थान ढूंढ रहा है…", "nv_map_loading": "मानचित्र लोड हो रहा है…", "nv_origin_default": "📍 मूल: बीजिंग शहर केंद्र (डिफ़ॉल्ट) · \"मेरे स्थान का उपयोग करें\" पर टैप करें।", "nv_origin_gps": "📍 मूल: आपका वर्तमान स्थान", "nv_map_unavail": "लाइव मानचित्र उपलब्ध नहीं है।", "nv_map_no_js": "एएमएपी जेएस कुंजी कॉन्फ़िगर नहीं की गई है।", "nv_map_no_backend": "बैकएंड कॉन्फ़िगर नहीं किया गया है।", "nv_map_hint": "नीचे दिए गए बटनों का उपयोग करके इस स्थान को मानचित्र ऐप में खोलें।", "nv_open_in": "मानचित्र में खोलें:", "nv_planning": "मार्ग योजना…", "nv_turn_by_turn": "🧭 टर्न-बाय-टर्न", "nv_arrive": "{name} पर पहुंचें", "nv_you": "आप", "nv_fallback": "टर्न-बाय-टर्न के लिए एएमएपी सुरक्षा कुंजी की आवश्यकता है। दूरी/समय सीधी रेखा के अनुमान हैं — नेविगेट करने के लिए ऊपर दिए गए बटनों का उपयोग करें।", "nv_dist": "दूरी", "nv_straight": "सीधी रेखा", "nv_duration": "अवधि", "nv_est": "अनुमानित समय", "nv_mode_label": "मोड", "nv_walk": "पैदल चलना", "nv_drive": "ड्राइविंग", "nv_transit_txt": "परिवहन", "nv_using_loc": "अपने स्थान का उपयोग करना", "md_eyebrow": "दवा", "md_title": "दवा और अनुस्मारक", "md_lede": "द्विभाषी पुस्तकालय में एक दवा की खोज करें, फिर अपने व्यक्तिगत सूची में अनुस्मारक समय के साथ इसे सहेजें।", "md_add": "एक दवा जोड़ें", "md_from_lib": "पुस्तकालय से", "md_choose": "— चुनें —", "md_custom": "या कस्टम नाम", "md_custom_ph": "उदाहरण के लिए विटामिन डी", "md_dosage": "खुराक / निर्देश", "md_dosage_ph": "उदाहरण के लिए प्रत्येक सुबह 1 गोली", "md_times": "अनुस्मारक समय", "md_notes": "नोट्स", "md_notes_ph": "भोजन के बाद, डेयरी से दूर रखें…", "md_save": "मेरी सूची में सहेजें", "md_login_req": "लॉगिन की आवश्यकता है। आपके खाते के खिलाफ संग्रहीत।", "md_drug_info": "दवा की जानकारी", "md_pick": "लाइब्रेरी से एक दवा चुनें खुराक, चेतावनी और दुष्प्रभाव देखने के लिए।", "md_rx": "Rx", "md_otc": "ओटीसी", "md_dosage_h": "खुराक", "md_warnings_h": "चेतावनी", "md_side_h": "दुष्प्रभाव", "md_my_list": "मेरी दवा सूची", "md_list_signin": "बचाए गए दवाओं और अनुस्मारकों को सहेजने के लिए साइन इन करें।", "md_list_empty": "अब तक कोई दवा सहेजी नहीं गई है।", "md_saved": "आपकी सूची में सहेजा गया", "md_removed": "हटा दिया गया", "md_remove": "हटाएं", "md_pick_first": "लाइब्रेरी से एक दवा चुनें", "md_login_first": "कृपया पहले लॉग इन करें।", "md_load_fail": "आपकी सूची लोड नहीं की जा सकी।", "ac_eyebrow": "आपका खाता", "ac_title": "खाता और गोपनीयता", "ac_lede": "आपकी पहचान वैकल्पिक है। संवेदनशील चिकित्सा पाठ को न्यूनतम प्रतिधारण के साथ संसाधित किया जाता है — और आप कुछ भी निर्यात या मिटा सकते हैं।", "ac_signin_p": "अपने प्रोफ़ाइल, सहेजे गए अनुवाद और दवा देखने के लिए लॉग इन करें।", "ac_signin_btn": "लॉग इन / पंजीकरण", "ac_member_since": "सदस्य दिनांक से {date}", "ac_your_data": "आपका डेटा", "ac_data_desc": "अपने खाते से जुड़ी सभी जानकारी की पूरी जेसन प्रतिलिपि निर्यात करें या अपने व्यक्तिगत रिकॉर्ड को स्थायी रूप से हटा दें (आपका लॉगिन रखा जाता है)।", "ac_export": "⬇︎ मेरा सभी डेटा निर्यात करें", "ac_wipe": "🗑 सभी व्यक्तिगत रिकॉर्ड हटाएं", "ac_exported": "नीचे निर्यात किया गया", "ac_wipe_confirm": "सभी अनुवाद, दवाएं, ट्राइएज और फीडबैक हटा दें? आपका लॉगिन रखा जाता है। यह वापस नहीं किया जा सकता।", "ac_wiped": "सभी व्यक्तिगत रिकॉर्ड हटा दिए गए", "ac_feedback": "फीडबैक", "ac_category": "श्रेणी", "ac_cat_translation": "अनुवाद", "ac_cat_hospital": "अस्पताल", "ac_cat_navigation": "नेविगेशन", "ac_cat_medication": "दवा", "ac_cat_feature": "विशेषता अनुरोध", "ac_cat_other": "अन्य", "ac_rating": "रेटिंग (1–5)", "ac_your_msg": "आपका संदेश", "ac_msg_ph": "हमें बताएं कि हम कैसे सुधार सकते हैं…", "ac_submit": "फीडबैक जमा करें", "ac_fb_thanks": "धन्यवाद! आपकी प्रतिक्रिया प्राप्त हुई।", "ac_fb_write": "कृपया एक संदेश लिखें", "ac_fb_sent": "प्रतिक्रिया भेजी गई", "footer_a": "TransMed · AI से सांस्कृतिक स्वास्थ्य देखभाल — केवल प्रदर्शन के लिए। आपात स्थिति में 120 पर कॉल करें या निकटतम आपातकालीन कक्ष में जाएं।", "footer_b": "महत्वपूर्ण निर्णय एक लाइसेंस प्राप्त चिकित्सक के साथ पुष्टि किए जाने चाहिए।", "loc_prefix": "स्थान: {msg}", "ui_translating": "अनुवाद इंटरफ़ेस…", "ui_ready": "भाषा तैयार", "please_login": "कृपया पहले लॉग इन करें", "welcome_back": "स्वागत है, {name}", "tr_conf_line": "आत्मविश्वास {n}% · {risk}", "hp_national_leader": "{sp} में राष्ट्रीय अग्रणी", "hp_grade_3a": "श्रेणी III-A (शीर्ष)"}};

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
    {"id": "bj-pumch", "name": "Peking Union Medical College Hospital", "name_zh": "中国医学科学院北京协和医院", "city": "北京", "address_zh": "北京市东城区帅府园一号", "phone": "+86 10 6915 6114", "grade": "三级甲等", "specialties": ["General Medicine", "Endocrinology", "Rheumatology", "Gynecology"], "lng": 116.4178, "lat": 39.9123},
    {"id": "bj-fuwai", "name": "Fuwai Hospital", "name_zh": "中国医学科学院阜外医院", "city": "北京", "address_zh": "北京市西城区北礼士路167号", "phone": "+86 10 8839 6114", "grade": "三级甲等", "specialties": ["Cardiology", "Cardiovascular Surgery"], "lng": 116.3568, "lat": 39.9261},
    {"id": "bj-anzhen", "name": "Beijing Anzhen Hospital", "name_zh": "首都医科大学附属北京安贞医院", "city": "北京", "address_zh": "北京市朝阳区安贞路2号", "phone": "+86 10 6445 6699", "grade": "三级甲等", "specialties": ["Cardiology", "Cardiovascular Surgery"], "lng": 116.403, "lat": 39.971},
    {"id": "bj-tiantan", "name": "Beijing Tiantan Hospital", "name_zh": "首都医科大学附属北京天坛医院", "city": "北京", "address_zh": "北京市丰台区南四环西路119号", "phone": "+86 10 5997 8001", "grade": "三级甲等", "specialties": ["Neurosurgery", "Neurology"], "lng": 116.3022, "lat": 39.8336},
    {"id": "bj-xuanwu", "name": "Xuanwu Hospital, Capital Medical University", "name_zh": "首都医科大学宣武医院", "city": "北京", "address_zh": "北京市西城区长椿街45号", "phone": "+86 10 8319 8899", "grade": "三级甲等", "specialties": ["Neurology", "Neurosurgery", "Geriatrics"], "lng": 116.3617, "lat": 39.8893},
    {"id": "bj-tongren", "name": "Beijing Tongren Hospital", "name_zh": "首都医科大学附属北京同仁医院", "city": "北京", "address_zh": "北京市东城区东交民巷1号", "phone": "+86 10 5826 9911", "grade": "三级甲等", "specialties": ["Ophthalmology", "ENT"], "lng": 116.4145, "lat": 39.9},
    {"id": "bj-jishuitan", "name": "Beijing Jishuitan Hospital", "name_zh": "北京积水潭医院", "city": "北京", "address_zh": "北京市西城区新街口东街31号", "phone": "+86 10 5851 6688", "grade": "三级甲等", "specialties": ["Orthopedics", "Sports Medicine"], "lng": 116.3736, "lat": 39.945},
    {"id": "bj-childrens", "name": "Beijing Children's Hospital", "name_zh": "首都医科大学附属北京儿童医院", "city": "北京", "address_zh": "北京市西城区南礼士路56号", "phone": "+86 10 5961 6161", "grade": "三级甲等", "specialties": ["Pediatrics", "Pediatric Surgery"], "lng": 116.3548, "lat": 39.909},
    {"id": "bj-cancer", "name": "Cancer Hospital, Chinese Academy of Medical Sciences", "name_zh": "中国医学科学院肿瘤医院", "city": "北京", "address_zh": "北京市朝阳区潘家园南里17号", "phone": "+86 10 8778 8899", "grade": "三级甲等", "specialties": ["Oncology", "Surgical Oncology"], "lng": 116.465, "lat": 39.878},
    {"id": "bj-bjcancer", "name": "Peking University Cancer Hospital", "name_zh": "北京大学肿瘤医院", "city": "北京", "address_zh": "北京市海淀区阜成路52号", "phone": "+86 10 8812 1122", "grade": "三级甲等", "specialties": ["Oncology", "Surgical Oncology", "Gastroenterology"], "lng": 116.2876, "lat": 39.932},
    {"id": "bj-stomatology", "name": "Peking University School of Stomatology", "name_zh": "北京大学口腔医院", "city": "北京", "address_zh": "北京市海淀区中关村南大街22号", "phone": "+86 10 8219 5114", "grade": "三级甲等", "specialties": ["Dental", "Oral Surgery"], "lng": 116.3247, "lat": 39.962},
    {"id": "bj-anding", "name": "Beijing Anding Hospital", "name_zh": "首都医科大学附属北京安定医院", "city": "北京", "address_zh": "北京市西城区安康胡同5号", "phone": "+86 10 5830 3000", "grade": "三级甲等", "specialties": ["Mental Health / Psychiatry", "Geriatrics"], "lng": 116.37, "lat": 39.946},
    {"id": "bj-pku6", "name": "Peking University Sixth Hospital", "name_zh": "北京大学第六医院", "city": "北京", "address_zh": "北京市海淀区花园北路51号", "phone": "+86 10 8280 3355", "grade": "三级甲等", "specialties": ["Mental Health / Psychiatry", "Neurology"], "lng": 116.364, "lat": 39.977},
    {"id": "bj-zhongri", "name": "China-Japan Friendship Hospital", "name_zh": "中日友好医院", "city": "北京", "address_zh": "北京市朝阳区樱花园东街2号", "phone": "+86 10 8420 5566", "grade": "三级甲等", "specialties": ["Pulmonary / Respiratory", "Respiratory", "Dermatology", "Endocrinology"], "lng": 116.418, "lat": 39.981},
    {"id": "bj-youyi", "name": "Beijing Friendship Hospital", "name_zh": "首都医科大学附属北京友谊医院", "city": "北京", "address_zh": "北京市西城区永安路95号", "phone": "+86 10 6313 8585", "grade": "三级甲等", "specialties": ["Gastroenterology", "Nephrology", "General Medicine"], "lng": 116.387, "lat": 39.882},
    {"id": "bj-chaoyang", "name": "Beijing Chaoyang Hospital", "name_zh": "首都医科大学附属北京朝阳医院", "city": "北京", "address_zh": "北京市朝阳区工人体育场南路8号", "phone": "+86 10 8523 1000", "grade": "三级甲等", "specialties": ["Pulmonary / Respiratory", "Respiratory", "Emergency"], "lng": 116.449, "lat": 39.923},
    {"id": "bj-301", "name": "Chinese PLA General Hospital (301 Hospital)", "name_zh": "中国人民解放军总医院", "city": "北京", "address_zh": "北京市海淀区复兴路28号", "phone": "+86 10 6693 8114", "grade": "三级甲等", "specialties": ["General Medicine", "Urology", "Nephrology", "Orthopedics"], "lng": 116.273, "lat": 39.907},
    {"id": "bj-pku1", "name": "Peking University First Hospital", "name_zh": "北京大学第一医院", "city": "北京", "address_zh": "北京市西城区西什库大街8号", "phone": "+86 10 8357 2211", "grade": "三级甲等", "specialties": ["Nephrology", "Dermatology", "Urology"], "lng": 116.373, "lat": 39.927},
    {"id": "bj-pku3", "name": "Peking University Third Hospital", "name_zh": "北京大学第三医院", "city": "北京", "address_zh": "北京市海淀区花园北路49号", "phone": "+86 10 8226 6699", "grade": "三级甲等", "specialties": ["Sports Medicine", "Orthopedics", "Obstetrics & Gynecology"], "lng": 116.361, "lat": 39.981},
    {"id": "bj-pkuph", "name": "Peking University People's Hospital", "name_zh": "北京大学人民医院", "city": "北京", "address_zh": "北京市西城区西直门南大街11号", "phone": "+86 10 8832 6666", "grade": "三级甲等", "specialties": ["Hematology", "Rheumatology", "Orthopedics"], "lng": 116.352, "lat": 39.938},
    {"id": "bj-fuxing-ufh", "name": "Beijing United Family Hospital", "name_zh": "北京和睦家医院", "city": "北京", "address_zh": "北京市朝阳区将台路2号", "phone": "+86 10 5927 7000", "grade": "未定级", "specialties": ["General Medicine", "Pediatrics", "Obstetrics & Gynecology", "Emergency"], "lng": 116.4677, "lat": 39.9754},
    {"id": "bj-ditan", "name": "Beijing Ditan Hospital", "name_zh": "首都医科大学附属北京地坛医院", "city": "北京", "address_zh": "北京市朝阳区京顺东街8号", "phone": "+86 10 8431 9999", "grade": "三级甲等", "specialties": ["Infectious Diseases", "Pulmonary / Respiratory"], "lng": 116.447, "lat": 40.005},
    {"id": "bj-guanganmen", "name": "Guang'anmen Hospital, China Academy of Chinese Medical Sciences", "name_zh": "中国中医科学院广安门医院", "city": "北京", "address_zh": "北京市西城区北线阁5号", "phone": "+86 10 8800 1122", "grade": "三级甲等", "specialties": ["Traditional Chinese Medicine", "Oncology"], "lng": 116.354, "lat": 39.897},
    {"id": "sh-ruijin", "name": "Ruijin Hospital", "name_zh": "上海交通大学医学院附属瑞金医院", "city": "上海", "address_zh": "上海市黄浦区瑞金二路197号", "phone": "+86 21 6437 0045", "grade": "三级甲等", "specialties": ["Endocrinology", "Hematology", "General Medicine", "Cardiology"], "lng": 121.4683, "lat": 31.2126},
    {"id": "sh-zhongshan", "name": "Zhongshan Hospital, Fudan University", "name_zh": "复旦大学附属中山医院", "city": "上海", "address_zh": "上海市徐汇区枫林路180号", "phone": "+86 21 6404 1990", "grade": "三级甲等", "specialties": ["Cardiology", "Gastroenterology", "Cardiovascular Surgery"], "lng": 121.4514, "lat": 31.1958},
    {"id": "sh-huashan", "name": "Huashan Hospital, Fudan University", "name_zh": "复旦大学附属华山医院", "city": "上海", "address_zh": "上海市静安区乌鲁木齐中路12号", "phone": "+86 21 5288 9999", "grade": "三级甲等", "specialties": ["Neurology", "Neurosurgery", "Dermatology", "Infectious Diseases"], "lng": 121.4404, "lat": 31.2192},
    {"id": "sh-fudancancer", "name": "Fudan University Shanghai Cancer Center", "name_zh": "复旦大学附属肿瘤医院", "city": "上海", "address_zh": "上海市徐汇区东安路270号", "phone": "+86 21 6417 5590", "grade": "三级甲等", "specialties": ["Oncology", "Surgical Oncology"], "lng": 121.453, "lat": 31.192},
    {"id": "sh-eent", "name": "Eye and ENT Hospital of Fudan University", "name_zh": "复旦大学附属眼耳鼻喉科医院", "city": "上海", "address_zh": "上海市徐汇区汾阳路83号", "phone": "+86 21 6437 7134", "grade": "三级甲等", "specialties": ["Ophthalmology", "ENT"], "lng": 121.452, "lat": 31.207},
    {"id": "sh-ninth", "name": "Shanghai Ninth People's Hospital", "name_zh": "上海交通大学医学院附属第九人民医院", "city": "上海", "address_zh": "上海市黄浦区制造局路639号", "phone": "+86 21 2327 1699", "grade": "三级甲等", "specialties": ["Oral Surgery", "Dental", "Ophthalmology"], "lng": 121.483, "lat": 31.198},
    {"id": "sh-redhouse", "name": "Obstetrics and Gynecology Hospital of Fudan University (Red House)", "name_zh": "复旦大学附属妇产科医院", "city": "上海", "address_zh": "上海市黄浦区方斜路419号", "phone": "+86 21 6345 5050", "grade": "三级甲等", "specialties": ["Obstetrics & Gynecology", "Gynecology"], "lng": 121.479, "lat": 31.211},
    {"id": "sh-scmc", "name": "Shanghai Children's Medical Center", "name_zh": "上海交通大学医学院附属上海儿童医学中心", "city": "上海", "address_zh": "上海市浦东新区东方路1678号", "phone": "+86 21 3862 6161", "grade": "三级甲等", "specialties": ["Pediatrics", "Pediatric Surgery"], "lng": 121.532, "lat": 31.224},
    {"id": "sh-mentalhealth", "name": "Shanghai Mental Health Center", "name_zh": "上海市精神卫生中心", "city": "上海", "address_zh": "上海市徐汇区宛平南路600号", "phone": "+86 21 6438 7250", "grade": "三级甲等", "specialties": ["Mental Health / Psychiatry", "Geriatrics"], "lng": 121.444, "lat": 31.183},
    {"id": "sh-changhai", "name": "Changhai Hospital", "name_zh": "海军军医大学第一附属医院（上海长海医院）", "city": "上海", "address_zh": "上海市杨浦区长海路168号", "phone": "+86 21 3116 1818", "grade": "三级甲等", "specialties": ["Gastroenterology", "Urology", "Cardiology"], "lng": 121.529, "lat": 31.305},
    {"id": "gz-sysu1", "name": "The First Affiliated Hospital of Sun Yat-sen University", "name_zh": "中山大学附属第一医院", "city": "广州", "address_zh": "广州市越秀区中山二路58号", "phone": "+86 20 2882 3388", "grade": "三级甲等", "specialties": ["General Medicine", "Nephrology", "Urology", "Cardiology"], "lng": 113.289, "lat": 23.129},
    {"id": "gz-zoc", "name": "Zhongshan Ophthalmic Center, Sun Yat-sen University", "name_zh": "中山大学中山眼科中心", "city": "广州", "address_zh": "广州市越秀区先烈南路54号", "phone": "+86 20 8733 0000", "grade": "三级甲等", "specialties": ["Ophthalmology", "General Medicine"], "lng": 113.295, "lat": 23.139},
    {"id": "gz-gyfyy1", "name": "The First Affiliated Hospital of Guangzhou Medical University", "name_zh": "广州医科大学附属第一医院", "city": "广州", "address_zh": "广州市越秀区沿江西路151号", "phone": "+86 20 8333 7750", "grade": "三级甲等", "specialties": ["Pulmonary / Respiratory", "Respiratory"], "lng": 113.252, "lat": 23.117},
    {"id": "gz-nanfang", "name": "Nanfang Hospital, Southern Medical University", "name_zh": "南方医科大学南方医院", "city": "广州", "address_zh": "广州市白云区广州大道北1838号", "phone": "+86 20 6164 1888", "grade": "三级甲等", "specialties": ["Gastroenterology", "Nephrology", "Infectious Diseases", "Oncology"], "lng": 113.317, "lat": 23.188},
    {"id": "gz-sysu-cancer", "name": "Sun Yat-sen University Cancer Center", "name_zh": "中山大学肿瘤防治中心", "city": "广州", "address_zh": "广州市越秀区东风东路651号", "phone": "+86 20 8734 3088", "grade": "三级甲等", "specialties": ["Oncology", "Surgical Oncology"], "lng": 113.298, "lat": 23.138},
    {"id": "cd-huaxi", "name": "West China Hospital, Sichuan University", "name_zh": "四川大学华西医院", "city": "成都", "address_zh": "成都市武侯区国学巷37号", "phone": "+86 28 8542 2114", "grade": "三级甲等", "specialties": ["General Medicine", "Pulmonary / Respiratory", "Oncology", "Neurosurgery"], "lng": 104.064, "lat": 30.642},
    {"id": "cd-huaxi-stoma", "name": "West China Hospital of Stomatology, Sichuan University", "name_zh": "四川大学华西口腔医院", "city": "成都", "address_zh": "成都市武侯区人民南路三段14号", "phone": "+86 28 8550 1428", "grade": "三级甲等", "specialties": ["Dental", "Oral Surgery"], "lng": 104.066, "lat": 30.64},
    {"id": "cd-huaxi-women", "name": "West China Second University Hospital, Sichuan University", "name_zh": "四川大学华西第二医院", "city": "成都", "address_zh": "成都市锦江区成龙大道一段1416号", "phone": "+86 28 8550 3960", "grade": "三级甲等", "specialties": ["Obstetrics & Gynecology", "Pediatrics", "Gynecology"], "lng": 104.153, "lat": 30.581},
    {"id": "wh-tongji", "name": "Tongji Hospital, Tongji Medical College, HUST", "name_zh": "华中科技大学同济医学院附属同济医院", "city": "武汉", "address_zh": "武汉市硚口区解放大道1095号", "phone": "+86 27 8366 2688", "grade": "三级甲等", "specialties": ["General Medicine", "Urology", "Oncology", "Gastroenterology"], "lng": 114.248, "lat": 30.587},
    {"id": "wh-xiehe", "name": "Wuhan Union Hospital, Tongji Medical College, HUST", "name_zh": "华中科技大学同济医学院附属协和医院", "city": "武汉", "address_zh": "武汉市江汉区解放大道1277号", "phone": "+86 27 8572 6114", "grade": "三级甲等", "specialties": ["Cardiology", "Hematology", "Cardiovascular Surgery", "Oncology"], "lng": 114.268, "lat": 30.587},
    {"id": "xa-xijing", "name": "Xijing Hospital, Air Force Medical University", "name_zh": "空军军医大学西京医院", "city": "西安", "address_zh": "西安市新城区长乐西路127号", "phone": "+86 29 8477 5507", "grade": "三级甲等", "specialties": ["Gastroenterology", "Dermatology", "Cardiovascular Surgery", "General Medicine"], "lng": 108.976, "lat": 34.27},
    {"id": "xa-tangdu", "name": "Tangdu Hospital, Air Force Medical University", "name_zh": "空军军医大学唐都医院", "city": "西安", "address_zh": "西安市灞桥区新寺路1号", "phone": "+86 29 8477 7426", "grade": "三级甲等", "specialties": ["Neurosurgery", "Pulmonary / Respiratory", "Infectious Diseases"], "lng": 109.048, "lat": 34.268},
    {"id": "hz-zju1", "name": "The First Affiliated Hospital, Zhejiang University School of Medicine", "name_zh": "浙江大学医学院附属第一医院", "city": "杭州", "address_zh": "杭州市上城区庆春路79号", "phone": "+86 571 8723 6114", "grade": "三级甲等", "specialties": ["Infectious Diseases", "General Medicine", "Hematology", "Nephrology"], "lng": 120.175, "lat": 30.259},
    {"id": "hz-srrsh", "name": "Sir Run Run Shaw Hospital, Zhejiang University", "name_zh": "浙江大学医学院附属邵逸夫医院", "city": "杭州", "address_zh": "杭州市江干区庆春东路3号", "phone": "+86 571 8600 6118", "grade": "三级甲等", "specialties": ["General Medicine", "Gastroenterology", "Urology"], "lng": 120.212, "lat": 30.258},
    {"id": "nj-gulou", "name": "Nanjing Drum Tower Hospital", "name_zh": "南京鼓楼医院", "city": "南京", "address_zh": "南京市鼓楼区中山路321号", "phone": "+86 25 8310 6666", "grade": "三级甲等", "specialties": ["General Medicine", "Gastroenterology", "Orthopedics", "Rheumatology"], "lng": 118.778, "lat": 32.062},
    {"id": "nj-jspph", "name": "Jiangsu Province Hospital (First Affiliated Hospital of Nanjing Medical University)", "name_zh": "江苏省人民医院", "city": "南京", "address_zh": "南京市鼓楼区广州路300号", "phone": "+86 25 6830 6565", "grade": "三级甲等", "specialties": ["Cardiology", "Endocrinology", "Geriatrics", "General Medicine"], "lng": 118.772, "lat": 32.056},
    {"id": "cs-xiangya", "name": "Xiangya Hospital, Central South University", "name_zh": "中南大学湘雅医院", "city": "长沙", "address_zh": "长沙市开福区湘雅路87号", "phone": "+86 731 8432 7925", "grade": "三级甲等", "specialties": ["Neurology", "General Medicine", "Dermatology", "Geriatrics"], "lng": 112.987, "lat": 28.209},
    {"id": "cs-xiangya2", "name": "The Second Xiangya Hospital, Central South University", "name_zh": "中南大学湘雅二医院", "city": "长沙", "address_zh": "长沙市芙蓉区人民中路139号", "phone": "+86 731 8529 2999", "grade": "三级甲等", "specialties": ["Mental Health / Psychiatry", "Endocrinology", "Cardiology", "Rheumatology"], "lng": 113.015, "lat": 28.192},
    {"id": "tj-tmugh", "name": "Tianjin Medical University General Hospital", "name_zh": "天津医科大学总医院", "city": "天津", "address_zh": "天津市和平区鞍山道154号", "phone": "+86 22 6036 2255", "grade": "三级甲等", "specialties": ["Neurosurgery", "Neurology", "Pulmonary / Respiratory", "General Medicine"], "lng": 117.184, "lat": 39.118},
    {"id": "tj-ihbdt", "name": "Institute of Hematology & Blood Diseases Hospital, CAMS", "name_zh": "中国医学科学院血液病医院", "city": "天津", "address_zh": "天津市和平区南京路288号", "phone": "+86 22 2390 9001", "grade": "三级甲等", "specialties": ["Hematology", "Oncology"], "lng": 117.201, "lat": 39.117},
    {"id": "sy-cmu1", "name": "The First Hospital of China Medical University", "name_zh": "中国医科大学附属第一医院", "city": "沈阳", "address_zh": "沈阳市和平区南京北街155号", "phone": "+86 24 8328 2888", "grade": "三级甲等", "specialties": ["General Medicine", "Cardiology", "Hematology", "Endocrinology"], "lng": 123.409, "lat": 41.796},
    {"id": "sy-shengjing", "name": "Shengjing Hospital of China Medical University", "name_zh": "中国医科大学附属盛京医院", "city": "沈阳", "address_zh": "沈阳市和平区三好街36号", "phone": "+86 24 9662 5222", "grade": "三级甲等", "specialties": ["Pediatrics", "Obstetrics & Gynecology", "Pediatric Surgery"], "lng": 123.428, "lat": 41.777}
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
    var _termSrc = (d.terminology_sources && d.terminology_sources.length) ? d.terminology_sources : ['WHO ICD-11', 'RxNorm (NIH)', 'NCBI MeSH'];
    var cards = [{ v: 12, k: 'st_langs' }, { v: _termSrc.length, k: 'st_terms', sub: _termSrc.map(function (s) { return s.replace(/\s*\(.*?\)/, ''); }).join(' · ') }, { v: d.hospitals || 6, k: 'st_hosp' }, { v: d.triage_rules || 55, k: 'st_rules' }, { v: d.translations || 0, k: 'st_trans' }];
    box.innerHTML = cards.map(function (c) { return '<div class="stat"><div class="stat-num" data-to="' + c.v + '">' + (animate === false ? c.v.toLocaleString() : '0') + '</div><div class="stat-label">' + t(c.k) + '</div>' + (c.sub ? '<div class="stat-sub muted" style="font-size:11px;margin-top:3px;line-height:1.3;">' + esc(c.sub) + '</div>' : '') + '</div>'; }).join('');
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
    (rec && rec.matched_specialties || []).slice(0, 3).forEach(function (sp) {
      push('spec', t(rec.evidence_source === 'curated_profile' ? 'hp_strong_in' : 'hp_name_indicates', { sp: sp }));
    });
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
      var absolute = num(h.recommendation.calibrated_score);
      if (absolute == null) absolute = num(h.recommendation.score);
      var pct = Math.max(0, Math.min(100, Math.round(absolute == null ? 0 : absolute)));
      var level = h.recommendation.match_level || (pct >= 70 ? 'high' : (pct >= 50 ? 'moderate' : 'low'));
      ring = '<div class="score-ring score-' + esc(level) + '" style="--p:' + pct + '" title="' + esc(t('hp_preliminary')) + '"><div class="score-inner"><div class="score-val">' + pct + '</div><div class="score-cap">' + t('hp_match_cap') + '</div></div></div>';
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
    var confidence = num(tr.confidence), confidenceText = confidence == null ? '' : '<span class="triage-confidence">' + esc(t('hp_triage_conf', { n: Math.round(confidence * 100) })) + '</span>';
    var recommendation = curLang === 'zh' ? tr.recommendation_zh : tr.recommendation_en;
    var questions = (curLang === 'zh' ? (tr.follow_up_questions || []) : (tr.follow_up_questions_en || tr.follow_up_questions || [])).slice(0, 3);
    banner.className = 'triage-banner' + (tr.urgent ? ' urgent' : '') + (tr.needs_clarification ? ' needs-detail' : ''); banner.classList.remove('hidden');
    banner.innerHTML = '<span class="triage-tag">' + (tr.urgent ? t('hp_urgent') : t('hp_recommended')) + '</span>' +
      confidenceText +
      '<h4>' + esc(tr.department_en || 'General Medicine') + ' <span class="dept-zh">' + esc(tr.department_zh || '') + '</span></h4>' +
      (tr.urgent ? '<p style="margin:4px 0 0;color:var(--danger);font-weight:600;">' + t('hp_call120') + '</p>' : '') +
      (!tr.urgent && recommendation ? '<p class="triage-copy">' + esc(recommendation) + '</p>' : '') +
      (tr.needs_clarification ? '<div class="triage-clarify"><strong>' + esc(t('hp_need_more')) + '</strong>' + (questions.length ? '<div class="triage-question-label">' + esc(t('hp_follow_up')) + '</div><ul>' + questions.map(function (q) { return '<li>' + esc(q) + '</li>'; }).join('') + '</ul>' : '') + '</div>' : '') +
      ((tr.matched_symptoms && tr.matched_symptoms.length) ? '<div class="chips" style="margin-top:8px;">' + tr.matched_symptoms.slice(0, 6).map(function (s) { return '<span class="chip static">' + esc(s) + '</span>'; }).join('') + '</div>' : '');
  }
  function loadHospitals() {
    var box = byId('hospital-list'); if (!box) return;
    var myReq = ++_hospReq;
    box.innerHTML = '<div class="empty-state"><span class="spinner"></span> ' + t('hp_loading') + '</div>';
    renderHospitals(FALLBACK_HOSPITALS, false, 0);
    api('/api/hospitals?limit=12').then(function (d) { if (myReq !== _hospReq) return; if (d && d.hospitals && d.hospitals.length) renderHospitals(d.hospitals, false, 0); }).catch(function () {});
  }

  var LOCAL_DEPT_ZH = {
    'Emergency': '急诊科', 'General Medicine': '全科医学科 / 普通内科', 'Internal Medicine': '普通内科',
    'Family Medicine': '全科医学科', 'Mental Health / Psychiatry': '精神心理科', 'Cardiology': '心血管内科',
    'Pulmonary / Respiratory': '呼吸与危重症医学科', 'Neurology': '神经内科', 'Gastroenterology': '消化内科',
    'Orthopedics': '骨科', 'Dermatology': '皮肤科', 'Ophthalmology': '眼科', 'ENT': '耳鼻咽喉科',
    'Dental': '口腔科', 'Pediatrics': '儿科', 'Obstetrics & Gynecology': '妇产科', 'Urology': '泌尿外科',
    'Endocrinology': '内分泌科', 'Oncology': '肿瘤科'
  };
  var LOCAL_TRIAGE_RULES = [
    { id: 'self_harm', terms: ['不想活','想死','轻生','自杀','自残','伤害自己','suicidal','suicide','kill myself','self harm'], scores: {'Emergency':150,'Mental Health / Psychiatry':140}, c:.98, urgent:true, q:['你现在是否有伤害自己的计划或已经采取行动？'] },
    { id: 'stroke', terms: ['口角歪斜','一侧无力','单侧无力','说话含糊','言语不清','中风','face droop','one-sided weakness','slurred speech','stroke'], scores: {'Emergency':150,'Neurology':140}, c:.97, urgent:true },
    { id: 'pregnancy_bleeding', terms: ['孕期出血','怀孕出血','孕妇出血','pregnant and bleeding','bleeding during pregnancy'], scores: {'Emergency':145,'Obstetrics & Gynecology':135}, c:.96, urgent:true },
    { id: 'chest_pain', terms: ['胸口疼','胸部疼痛','胸痛','胸闷','chest pain','chest pressure','chest tightness'], scores: {'Emergency':125,'Cardiology':120}, c:.90, urgent:true, q:['胸痛是否突然发生，是否伴出汗、恶心或向手臂/下颌放射？'] },
    { id: 'breathing', terms: ['呼吸困难','喘不上气','不能呼吸','憋气','shortness of breath','difficulty breathing','cannot breathe','breathless'], scores: {'Emergency':130,'Pulmonary / Respiratory':120,'Cardiology':55}, c:.92, urgent:true },
    { id: 'low_mood', terms: ['心情不好','情绪低落','情绪不好','很难过','提不起精神','depressed','low mood','feeling down','hopeless'], scores: {'Mental Health / Psychiatry':110}, c:.76, clarify:true, q:['这种状态持续多久了，是否已影响睡眠、学习或工作？','是否出现过伤害自己或不想活的想法？'] },
    { id: 'anxiety', terms: ['焦虑','压力很大','压力大','惊恐发作','恐慌','anxiety','anxious','panic attack','severe stress'], scores: {'Mental Health / Psychiatry':105}, c:.80, clarify:true },
    { id: 'sleep', terms: ['失眠','睡不着','早醒','睡眠很差','insomnia','cannot sleep','trouble sleeping'], scores: {'Mental Health / Psychiatry':80,'General Medicine':35}, c:.72, clarify:true },
    { id: 'palpitations', terms: ['心悸','心跳很快','心跳不齐','心慌','palpitations','heart racing'], scores: {'Cardiology':105,'General Medicine':35}, c:.83 },
    { id: 'cough', terms: ['咳嗽','咳痰','有痰','干咳','cough','coughing','phlegm','sputum'], scores: {'Pulmonary / Respiratory':100,'Internal Medicine':45,'Family Medicine':35}, c:.82 },
    { id: 'fever', terms: ['高烧','高热','发烧','发热','fever','high fever'], scores: {'Internal Medicine':75,'Pulmonary / Respiratory':35}, c:.72, clarify:true },
    { id: 'headache', terms: ['偏头痛','剧烈头痛','头痛','头疼','headache','migraine'], scores: {'Neurology':95,'Internal Medicine':40}, c:.78 },
    { id: 'dizziness', terms: ['天旋地转','头晕','眩晕','dizziness','dizzy','vertigo'], scores: {'Neurology':80,'ENT':65,'Cardiology':40}, c:.70, clarify:true },
    { id: 'abdominal', terms: ['肚子痛','肚子疼','胃痛','胃疼','腹痛','abdominal pain','stomach pain'], scores: {'Gastroenterology':100,'Internal Medicine':40}, c:.78, clarify:true },
    { id: 'digestive', terms: ['恶心','呕吐','腹泻','拉肚子','便秘','反酸','nausea','vomiting','diarrhea','constipation','reflux'], scores: {'Gastroenterology':90,'Internal Medicine':35}, c:.76 },
    { id: 'injury', terms: ['骨折','摔伤','扭伤','运动损伤','fracture','broken bone','sprain','sports injury'], scores: {'Orthopedics':115,'Emergency':65}, c:.88 },
    { id: 'joint', terms: ['腰痛','腰疼','背痛','关节痛','膝盖疼','肩膀疼','back pain','joint pain','knee pain','shoulder pain'], scores: {'Orthopedics':95}, c:.80 },
    { id: 'skin', terms: ['皮疹','皮肤瘙痒','皮肤痒','湿疹','荨麻疹','rash','itchy skin','eczema','hives'], scores: {'Dermatology':110}, c:.86 },
    { id: 'eye', terms: ['眼睛痛','眼痛','视力下降','看不清','眼睛红','eye pain','vision loss','blurred vision','red eye'], scores: {'Ophthalmology':115}, c:.88 },
    { id: 'ent', terms: ['耳朵疼','耳痛','听力下降','耳鸣','鼻塞','流鼻涕','喉咙痛','吞咽痛','ear pain','hearing loss','sore throat'], scores: {'ENT':105,'Internal Medicine':30}, c:.82 },
    { id: 'dental', terms: ['牙龈肿','牙龈出血','牙痛','牙疼','toothache','tooth pain','dental pain'], scores: {'Dental':120}, c:.92 },
    { id: 'urinary', terms: ['排尿疼痛','尿痛','尿频','尿急','血尿','排尿困难','painful urination','frequent urination','blood in urine'], scores: {'Urology':105}, c:.84 },
    { id: 'pregnancy', terms: ['怀孕','孕期','孕妇','月经异常','妇科','pregnant','pregnancy','gynecology','gynaecology'], scores: {'Obstetrics & Gynecology':110}, c:.86 },
    { id: 'endocrine', terms: ['糖尿病','血糖高','甲状腺','甲亢','甲减','diabetes','high blood sugar','thyroid'], scores: {'Endocrinology':115}, c:.90 },
    { id: 'oncology', terms: ['癌症','恶性肿瘤','肿瘤复查','化疗','cancer','malignant tumor','chemotherapy'], scores: {'Oncology':125}, c:.94 },
    { id: 'general', terms: ['身体不舒服','不舒服','很难受','感觉不对劲','乏力','feeling unwell','not feeling well','fatigue'], scores: {'General Medicine':70,'Internal Medicine':45}, c:.38, clarify:true, q:['最不舒服的部位在哪里？','症状持续多久、严重程度如何，并伴有哪些症状？'] }
  ];

  function localPositiveTerm(text, terms) {
    var sorted = terms.slice().sort(function (a, b) { return b.length - a.length; });
    for (var i = 0; i < sorted.length; i++) {
      var term = sorted[i].toLowerCase(), from = 0, at;
      while ((at = text.indexOf(term, from)) >= 0) {
        var prefix = text.slice(Math.max(0, at - 36), at).split(/[，。；,.!?！？\n]/).pop();
        var negated = /(?:没有|并无|否认|未见|未出现|不伴|没|无|不)(?:任何)?[^，。；,.!?！？]{0,5}$/.test(prefix) || /(?:\bno|\bnot|\bwithout|\bdenies|\bdenied)\s+(?:[a-z'-]+\s+){0,3}$/i.test(prefix);
        if (!negated) return term;
        from = at + term.length;
      }
    }
    return '';
  }

  function localTriage(sym, spec) {
    var text = String(sym || '').toLowerCase().replace(/\s+/g, ' ').trim();
    if (spec) return { department_en: spec, department_zh: LOCAL_DEPT_ZH[spec] || spec, urgent: spec === 'Emergency', matched_symptoms: [], specialty_scores: (function () { var x = {}; x[spec] = 180; return x; })(), confidence: .96, needs_clarification: false, follow_up_questions: [], recommendation_en: 'Hospitals are ranked against your selected department.', recommendation_zh: '已按你手动选择的科室匹配医院。', engine_version: 'local-triage-v2.0' };
    var scores = {}, matched = [], questions = [], confidence = .20, urgent = false, clarify = false, concepts = 0;
    LOCAL_TRIAGE_RULES.forEach(function (rule) {
      var term = localPositiveTerm(text, rule.terms);
      if (!term) return;
      concepts += 1; matched.push(term); confidence = Math.max(confidence, rule.c || .6); urgent = urgent || !!rule.urgent; clarify = clarify || !!rule.clarify;
      Object.keys(rule.scores).forEach(function (sp) { scores[sp] = (scores[sp] || 0) + rule.scores[sp]; });
      (rule.q || []).forEach(function (q) { if (questions.indexOf(q) < 0) questions.push(q); });
    });
    var child = localPositiveTerm(text, ['婴儿','宝宝','儿童','孩子','小孩','baby','infant','toddler','child']);
    if (child) { scores.Pediatrics = (scores.Pediatrics || 0) + 140; matched.push(child); confidence = Math.max(confidence, .78); }
    if (!Object.keys(scores).length) { scores['General Medicine'] = 40; clarify = true; questions = ['最不舒服的部位在哪里？','症状持续多久、严重程度如何，并伴有哪些症状？']; }
    confidence = Math.min(.99, confidence + Math.min(.10, Math.max(0, concepts - 1) * .035));
    var ranked = Object.keys(scores).sort(function (a, b) { return scores[b] - scores[a] || a.localeCompare(b); });
    if (urgent && ranked[0] !== 'Emergency') { scores.Emergency = Math.max(scores.Emergency || 0, scores[ranked[0]] + 10); ranked = Object.keys(scores).sort(function (a, b) { return scores[b] - scores[a]; }); }
    var primary = ranked[0], needs = clarify || confidence < .68;
    var recZh = urgent ? '检测到可能的红旗症状，请立即拨打 120 或前往最近急诊。' : (primary === 'Mental Health / Psychiatry' ? '初步建议精神心理科或心理门诊；如出现自伤或轻生想法，请立即寻求急诊帮助。' : (needs ? '当前信息不足以做高置信度分诊，请补充细节后再选择医院。' : '这是初步就医分流建议，不构成诊断。'));
    var recEn = urgent ? 'A possible red flag was detected. Call 120 or go to the nearest emergency department now.' : (needs ? 'More detail is needed before choosing a hospital.' : 'This is preliminary routing guidance, not a diagnosis.');
    var qEn = primary === 'Mental Health / Psychiatry' ? ['How long has this lasted, and is it affecting sleep, study or work?','Have you had thoughts of harming yourself or not wanting to live?'] : ['How long has this lasted, how severe is it, and what other symptoms are present?'];
    return { department_en: primary, department_zh: LOCAL_DEPT_ZH[primary] || primary, urgent: urgent, matched_symptoms: matched.slice(0, 8), specialty_scores: scores, confidence: confidence, needs_clarification: needs, follow_up_questions: questions.slice(0, 3), follow_up_questions_en: qEn, recommendation_en: recEn, recommendation_zh: recZh, engine_version: 'local-triage-v2.0' };
  }

  function localHospitalStrength(h, specialty) {
    var specs = (h.specialties || []).map(function (x) { return String(x).toLowerCase(); });
    var target = String(specialty || '').toLowerCase();
    var direct = specs.indexOf(target) >= 0 ? 90 : 0;
    if ((specialty === 'Internal Medicine' || specialty === 'Family Medicine') && specs.indexOf('general medicine') >= 0) direct = Math.max(direct, 62);
    var name = ((h.name_zh || '') + ' ' + (h.name || '')).toLowerCase();
    var leaders = {
      'Mental Health / Psychiatry': /安定医院|北京大学第六医院|精神卫生中心/,
      'Cardiology': /阜外|安贞/, 'Neurology': /宣武|天坛/, 'Ophthalmology': /同仁医院|眼科中心/,
      'ENT': /同仁医院|眼耳鼻喉/, 'Orthopedics': /积水潭|北京大学第三医院/,
      'Dental': /北京大学口腔|华西口腔|第九人民/, 'Pediatrics': /儿童医院|儿童医学中心/,
      'Gastroenterology': /友谊医院|西京医院/, 'Pulmonary / Respiratory': /中日友好|朝阳医院|广州医科大学附属第一/,
      'Dermatology': /北京大学第一医院|华山医院/, 'Emergency': /协和医院|朝阳医院|和睦家/,
      'Endocrinology': /协和医院|瑞金医院/, 'Oncology': /肿瘤医院|肿瘤防治中心/,
      'Obstetrics & Gynecology': /妇产|华西第二医院/, 'Urology': /北京大学第一医院|解放军总医院/,
      'General Medicine': /协和医院|解放军总医院|华西医院/
    };
    return Math.max(direct, leaders[specialty] && leaders[specialty].test(name) ? 100 : 0);
  }

  function localRecommendationFallback(analysis) {
    var scores = analysis.specialty_scores || {}, totalWeight = Object.keys(scores).reduce(function (sum, sp) { return sum + Math.max(0, scores[sp] || 0); }, 0) || 1;
    var factor = .70 + .30 * Math.max(0, Math.min(1, analysis.confidence || .2));
    return FALLBACK_HOSPITALS.filter(function (h) { return !h.city || h.city === '北京'; }).map(function (h) {
      var weighted = 0, matched = [], leaders = [];
      Object.keys(scores).forEach(function (sp) { var strength = localHospitalStrength(h, sp); weighted += strength * scores[sp]; if (strength >= 40) matched.push(sp); if (strength === 100) leaders.push(sp); });
      var fit = weighted / totalWeight, emergency = localHospitalStrength(h, 'Emergency');
      var eligible = fit >= 40 && (!analysis.urgent || emergency >= 60);
      var raw = fit * .55 + (leaders.length ? 12 : 0) + (/三级甲等|三甲/.test(h.grade || '') ? 8 : 0) + 4 + (curLang === 'zh' ? 6 : 0) + (analysis.urgent && emergency >= 60 ? 12 : 0);
      var score = Math.max(0, Math.min(100, raw * factor));
      var copy = Object.assign({}, h);
      copy.recommendation = { score: score, calibrated_score: score, match_level: score >= 70 ? 'high' : (score >= 50 ? 'moderate' : 'low'), eligible: eligible, matched_specialties: matched, leader_specialties: leaders, reasons: [], evidence_source: 'curated_profile', score_version: 'hospital-fit-v2.0-local' };
      return copy;
    }).filter(function (h) { return h.recommendation.eligible; }).sort(function (a, b) { return b.recommendation.score - a.recommendation.score || String(a.name_zh).localeCompare(String(b.name_zh)); }).slice(0, 10);
  }

  // Read-only hook used by browser regression tests and support diagnostics.
  window.TransMedRecommendation = { analyze: localTriage, rank: localRecommendationFallback };

  function runRecommend() {
    var sym = ((byId('triage-input') || {}).value || '').trim(), spec = (byId('specialty-filter') || {}).value || '';
    var banner = byId('triage-result'), box = byId('hospital-list');
    if (!sym && !spec) { toast(t('hp_describe_first'), 'warn'); return; }
    _sortMode = 'match'; syncSortUI();
    _lastTriage = localTriage(sym, spec); renderTriageBanner();
    var localHospitals = localRecommendationFallback(_lastTriage);
    if (localHospitals.length) renderHospitals(localHospitals, true, 0);
    else if (box) box.innerHTML = '<div class="empty-state"><span class="spinner"></span> ' + t('hp_matching') + '</div>';
    var myReq = ++_hospReq, body = { symptoms: sym || spec, city: '北京', limit: 10 };
    if (spec) body.specialty_override = spec;
    body.language = curLang || (currentUser && currentUser.language) || 'en';
    api('/api/recommendations', { method: 'POST', body: body, timeout: 30000 }).then(function (d) {
      if (myReq !== _hospReq) return;
      _lastTriage = d.triage || {}; renderTriageBanner();
      renderHospitals(d.hospitals || [], true, 0);
    }).catch(function () {
      if (myReq !== _hospReq) return;
      toast(t('hp_waking_d'), 'warn');
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
