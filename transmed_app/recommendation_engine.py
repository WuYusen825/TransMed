"""Deterministic, bilingual triage primitives for TransMed.

The engine is intentionally conservative: it routes to a department, detects
common red flags, understands simple negation, and reports uncertainty.  It is
not a diagnosis model.  Keeping this module pure makes it easy to benchmark
without starting FastAPI or calling an external service.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ENGINE_VERSION = "triage-v2.0"

DEPARTMENT_ZH: Dict[str, str] = {
    "Emergency": "急诊科",
    "General Medicine": "全科医学科 / 普通内科",
    "Internal Medicine": "普通内科",
    "Family Medicine": "全科医学科",
    "Cardiology": "心血管内科",
    "Cardiovascular Surgery": "心血管外科",
    "Pulmonary / Respiratory": "呼吸与危重症医学科",
    "Neurology": "神经内科",
    "Neurosurgery": "神经外科",
    "Gastroenterology": "消化内科",
    "Orthopedics": "骨科",
    "Sports Medicine": "运动医学科",
    "Rheumatology": "风湿免疫科",
    "Dermatology": "皮肤科",
    "Ophthalmology": "眼科",
    "ENT": "耳鼻咽喉科",
    "Dental": "口腔科",
    "Oral Surgery": "口腔颌面外科",
    "Pediatrics": "儿科",
    "Pediatric Surgery": "小儿外科",
    "Obstetrics & Gynecology": "妇产科",
    "Gynecology": "妇科",
    "Urology": "泌尿外科",
    "Nephrology": "肾内科",
    "Endocrinology": "内分泌科",
    "Oncology": "肿瘤科",
    "Hematology": "血液科",
    "Infectious Diseases": "感染科",
    "Mental Health / Psychiatry": "精神心理科",
    "Allergy & Immunology": "变态反应科 / 过敏科",
    "Physiotherapy / Rehabilitation": "康复医学科",
    "Geriatrics": "老年医学科",
    "Traditional Chinese Medicine": "中医科",
}

_FOLLOW_UP_EN: Dict[str, Tuple[str, ...]] = {
    "Mental Health / Psychiatry": (
        "How long has this lasted, and is it affecting sleep, study or work?",
        "Have you had thoughts of harming yourself or not wanting to live?",
    ),
    "Pulmonary / Respiratory": ("How long has this lasted, and is there fever, chest pain or breathing difficulty?",),
    "Neurology": ("Was the onset sudden, and are there vision, speech or one-sided strength changes?",),
    "Gastroenterology": ("Where is the pain, how long has it lasted, and is there vomiting, fever, bleeding or possible pregnancy?",),
    "General Medicine": (
        "Which part of your body feels worst?",
        "How long has it lasted, how severe is it, and what other symptoms are present?",
    ),
    "Emergency": ("Are you safe right now, and has emergency help already been called?",),
}


def _rule(
    rule_id: str,
    label_zh: str,
    terms: Sequence[str],
    specialties: Mapping[str, float],
    confidence: float,
    *,
    urgent: bool = False,
    red_flag: str = "",
    clarify: bool = False,
    questions: Sequence[str] = (),
) -> Dict[str, Any]:
    return {
        "id": rule_id,
        "label_zh": label_zh,
        "terms": tuple(sorted(set(terms), key=len, reverse=True)),
        "specialties": dict(specialties),
        "confidence": confidence,
        "urgent": urgent,
        "red_flag": red_flag,
        "clarify": clarify,
        "questions": tuple(questions),
    }


# Rules are concept-level rather than one row per spelling.  This prevents a
# sentence such as "焦虑、很焦虑" from being counted as two independent facts.
SYMPTOM_RULES: Tuple[Dict[str, Any], ...] = (
    _rule(
        "self_harm",
        "自伤或轻生想法",
        ("不想活", "想死", "轻生", "自杀", "自残", "伤害自己", "结束生命",
         "suicidal", "suicide", "kill myself", "end my life", "self harm", "self-harm"),
        {"Emergency": 150, "Mental Health / Psychiatry": 140},
        0.98,
        urgent=True,
        red_flag="可能存在自伤或轻生风险",
        questions=("你现在是否有伤害自己的计划或已经采取行动？",),
    ),
    _rule(
        "stroke",
        "疑似卒中表现",
        ("口角歪斜", "一侧无力", "单侧无力", "半身不遂", "说话含糊", "言语不清",
         "突然失语", "脑卒中", "中风", "face droop", "one-sided weakness", "slurred speech", "stroke"),
        {"Emergency": 150, "Neurology": 140},
        0.97,
        urgent=True,
        red_flag="疑似卒中表现，需要立即急诊评估",
    ),
    _rule(
        "loss_of_consciousness",
        "意识异常或抽搐",
        ("失去意识", "意识不清", "昏迷", "晕厥", "抽搐", "癫痫发作", "不省人事",
         "unconscious", "loss of consciousness", "fainted", "fainting", "seizure", "convulsion"),
        {"Emergency": 145, "Neurology": 125, "Cardiology": 55},
        0.95,
        urgent=True,
        red_flag="意识异常或抽搐属于急症信号",
    ),
    _rule(
        "severe_allergy",
        "严重过敏表现",
        ("喉咙肿", "喉头水肿", "嘴唇肿", "舌头肿", "全身过敏", "严重过敏", "过敏性休克",
         "anaphylaxis", "throat swelling", "swollen tongue", "swollen lips"),
        {"Emergency": 145, "Allergy & Immunology": 115},
        0.95,
        urgent=True,
        red_flag="可能存在严重过敏反应",
    ),
    _rule(
        "major_bleeding",
        "大量或持续出血",
        ("大量出血", "血流不止", "止不住血", "呕血", "咳血", "便血", "黑便",
         "heavy bleeding", "uncontrolled bleeding", "vomiting blood", "coughing blood", "black stool"),
        {"Emergency": 145, "Gastroenterology": 75},
        0.94,
        urgent=True,
        red_flag="大量或持续出血需要立即评估",
    ),
    _rule(
        "pregnancy_bleeding",
        "孕期出血或剧烈腹痛",
        ("孕期出血", "怀孕出血", "孕妇出血", "孕期剧烈腹痛", "怀孕剧烈腹痛",
         "bleeding during pregnancy", "pregnant and bleeding", "severe pain during pregnancy"),
        {"Emergency": 145, "Obstetrics & Gynecology": 135},
        0.96,
        urgent=True,
        red_flag="孕期出血或剧烈腹痛需要急诊评估",
    ),
    _rule(
        "chest_pain",
        "胸痛或胸闷",
        ("胸痛", "胸口疼", "胸部疼痛", "胸闷", "心前区疼", "chest pain", "chest pressure", "chest tightness"),
        {"Emergency": 125, "Cardiology": 120},
        0.90,
        urgent=True,
        red_flag="胸痛可能需要紧急排除心肺急症",
        questions=("胸痛是否突然发生，是否伴出汗、恶心或向手臂/下颌放射？",),
    ),
    _rule(
        "breathing_difficulty",
        "呼吸困难",
        ("呼吸困难", "喘不上气", "不能呼吸", "气短严重", "憋气", "呼吸急促",
         "shortness of breath", "difficulty breathing", "cannot breathe", "breathless"),
        {"Emergency": 130, "Pulmonary / Respiratory": 120, "Cardiology": 55},
        0.92,
        urgent=True,
        red_flag="呼吸困难可能是急症",
    ),
    _rule(
        "low_mood",
        "情绪低落",
        ("心情不好", "情绪低落", "情绪不好", "很难过", "持续难过", "提不起精神",
         "对什么都没兴趣", "无望感", "低落", "depressed", "low mood", "feeling down", "hopeless"),
        {"Mental Health / Psychiatry": 110},
        0.76,
        clarify=True,
        questions=("这种状态持续多久了，是否已影响睡眠、学习或工作？", "是否出现过伤害自己或不想活的想法？"),
    ),
    _rule(
        "anxiety",
        "焦虑或惊恐",
        ("焦虑", "紧张不安", "压力很大", "压力大", "惊恐发作", "恐慌", "坐立不安",
         "anxiety", "anxious", "panic attack", "panic", "overwhelmed", "severe stress"),
        {"Mental Health / Psychiatry": 105},
        0.80,
        clarify=True,
        questions=("是否伴随心悸、呼吸急促，或已明显影响日常生活？",),
    ),
    _rule(
        "sleep_problem",
        "睡眠问题",
        ("失眠", "睡不着", "早醒", "反复醒", "噩梦", "睡眠很差", "insomnia", "cannot sleep", "trouble sleeping"),
        {"Mental Health / Psychiatry": 80, "General Medicine": 35},
        0.72,
        clarify=True,
        questions=("睡眠问题持续多久，是否伴随情绪低落、焦虑或白天功能下降？",),
    ),
    _rule(
        "palpitations",
        "心悸",
        ("心悸", "心跳很快", "心跳不齐", "心慌", "palpitations", "heart racing", "irregular heartbeat"),
        {"Cardiology": 105, "General Medicine": 35},
        0.83,
        questions=("是否伴胸痛、晕厥或呼吸困难？",),
    ),
    _rule(
        "hypertension",
        "血压异常",
        ("高血压", "血压高", "低血压", "血压低", "hypertension", "high blood pressure", "hypotension", "low blood pressure"),
        {"Cardiology": 85, "General Medicine": 55},
        0.82,
    ),
    _rule(
        "cough",
        "咳嗽或咳痰",
        ("咳嗽", "咳痰", "有痰", "干咳", "cough", "coughing", "phlegm", "sputum"),
        {"Pulmonary / Respiratory": 100, "Internal Medicine": 45, "Family Medicine": 35},
        0.82,
        questions=("咳嗽持续多久，是否伴高热、胸痛或呼吸困难？",),
    ),
    _rule(
        "fever",
        "发热",
        ("高烧", "高热", "发烧", "发热", "持续发热", "fever", "high fever", "temperature"),
        {"Internal Medicine": 75, "Infectious Diseases": 60, "Pulmonary / Respiratory": 35},
        0.72,
        clarify=True,
        questions=("最高体温是多少，持续多久，并伴有哪些其他症状？",),
    ),
    _rule(
        "headache",
        "头痛",
        ("头痛", "头疼", "偏头痛", "剧烈头痛", "headache", "migraine"),
        {"Neurology": 95, "Internal Medicine": 40, "Family Medicine": 30},
        0.78,
        questions=("头痛是否突然达到最严重程度，或伴发热、颈部僵硬、视力/肢体变化？",),
    ),
    _rule(
        "dizziness",
        "头晕或眩晕",
        ("头晕", "眩晕", "天旋地转", "站不稳", "dizziness", "dizzy", "vertigo"),
        {"Neurology": 80, "ENT": 65, "Cardiology": 40},
        0.70,
        clarify=True,
        questions=("是旋转感还是要晕倒的感觉？是否伴听力变化、胸痛或肢体无力？",),
    ),
    _rule(
        "abdominal_pain",
        "腹痛或胃痛",
        ("腹痛", "肚子痛", "肚子疼", "胃痛", "胃疼", "上腹痛", "下腹痛", "abdominal pain", "stomach pain"),
        {"Gastroenterology": 100, "Internal Medicine": 40},
        0.78,
        clarify=True,
        questions=("疼痛位于哪里、持续多久，是否伴呕吐、发热、黑便或孕期可能？",),
    ),
    _rule(
        "digestive_upset",
        "消化道症状",
        ("恶心", "呕吐", "腹泻", "拉肚子", "便秘", "反酸", "烧心",
         "nausea", "vomiting", "diarrhea", "diarrhoea", "constipation", "reflux", "heartburn"),
        {"Gastroenterology": 90, "Internal Medicine": 35},
        0.76,
    ),
    _rule(
        "bone_joint_pain",
        "骨关节或肌肉疼痛",
        ("腰痛", "腰疼", "背痛", "颈痛", "脖子疼", "关节痛", "膝盖疼", "肩膀疼", "肌肉痛",
         "back pain", "neck pain", "joint pain", "knee pain", "shoulder pain", "muscle pain"),
        {"Orthopedics": 95, "Physiotherapy / Rehabilitation": 55, "Rheumatology": 45},
        0.80,
    ),
    _rule(
        "injury",
        "外伤或骨折",
        ("骨折", "摔伤", "扭伤", "运动损伤", "外伤", "fracture", "broken bone", "sprain", "sports injury", "injury"),
        {"Orthopedics": 115, "Emergency": 65, "Sports Medicine": 55},
        0.88,
    ),
    _rule(
        "skin_problem",
        "皮疹或皮肤症状",
        ("皮疹", "出疹子", "皮肤瘙痒", "皮肤痒", "湿疹", "荨麻疹", "痘痘", "rash", "itchy skin", "eczema", "hives", "acne"),
        {"Dermatology": 110, "Allergy & Immunology": 35},
        0.86,
    ),
    _rule(
        "eye_problem",
        "眼部症状",
        ("眼睛痛", "眼痛", "视力下降", "看不清", "眼睛红", "眼红", "复视", "eye pain", "vision loss", "blurred vision", "red eye", "double vision"),
        {"Ophthalmology": 115},
        0.88,
    ),
    _rule(
        "ent_problem",
        "耳鼻咽喉症状",
        ("耳痛", "耳朵疼", "听力下降", "耳鸣", "鼻塞", "流鼻涕", "咽痛", "喉咙痛", "吞咽痛",
         "ear pain", "hearing loss", "tinnitus", "blocked nose", "runny nose", "sore throat"),
        {"ENT": 105, "Internal Medicine": 30},
        0.82,
    ),
    _rule(
        "dental_problem",
        "牙齿或口腔症状",
        ("牙痛", "牙疼", "牙龈肿", "牙龈出血", "口腔溃疡", "toothache", "tooth pain", "gum swelling", "mouth ulcer", "dental pain"),
        {"Dental": 120, "Oral Surgery": 35},
        0.92,
    ),
    _rule(
        "urinary_problem",
        "泌尿系统症状",
        ("尿痛", "尿频", "尿急", "血尿", "排尿困难", "腰部绞痛", "painful urination", "frequent urination", "blood in urine", "difficulty urinating"),
        {"Urology": 105, "Nephrology": 45},
        0.84,
    ),
    _rule(
        "pregnancy_or_gynecology",
        "孕产或妇科问题",
        ("怀孕", "孕期", "孕妇", "月经异常", "阴道出血", "妇科", "备孕",
         "pregnant", "pregnancy", "missed period", "vaginal bleeding", "gynecology", "gynaecology"),
        {"Obstetrics & Gynecology": 110, "Gynecology": 65},
        0.86,
    ),
    _rule(
        "endocrine_problem",
        "内分泌问题",
        ("糖尿病", "血糖高", "甲亢", "甲减", "甲状腺", "diabetes", "high blood sugar", "thyroid", "hyperthyroidism", "hypothyroidism"),
        {"Endocrinology": 115, "Internal Medicine": 35},
        0.90,
    ),
    _rule(
        "cancer_followup",
        "肿瘤相关问题",
        ("癌症", "恶性肿瘤", "肿瘤复查", "化疗", "放疗", "cancer", "malignant tumor", "malignant tumour", "chemotherapy", "radiotherapy"),
        {"Oncology": 125},
        0.94,
    ),
    _rule(
        "general_unwell",
        "全身不适（信息不足）",
        ("不舒服", "很难受", "身体不适", "感觉不对劲", "浑身没劲", "乏力", "feeling unwell", "not feeling well", "malaise", "fatigue"),
        {"General Medicine": 70, "Internal Medicine": 45},
        0.38,
        clarify=True,
        questions=("最不舒服的部位在哪里？", "症状持续多久、严重程度如何，是否伴发热、疼痛或呼吸困难？"),
    ),
)


_NEGATION_ZH = re.compile(r"(?:没有|并没有|并无|否认|未见|未出现|不伴|没|无|不)(?:任何)?[^，。；,.!?！？]{0,5}$")
_NEGATION_EN = re.compile(r"(?:\bno|\bnot|\bwithout|\bdenies|\bdenied)\s+(?:[a-z'-]+\s+){0,3}$", re.I)
_SEPARATOR = re.compile(r"[，。；,.!?！？\n]")


def normalize_text(text: str) -> str:
    """Unicode-normalize user input while preserving Chinese characters."""
    normalized = unicodedata.normalize("NFKC", text or "").lower().strip()
    return re.sub(r"\s+", " ", normalized)


def _term_occurrences(text: str, term: str) -> Iterable[Tuple[int, int]]:
    term_l = normalize_text(term)
    if not term_l:
        return ()
    if re.search(r"[a-z0-9]", term_l):
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(term_l) + r"(?![a-z0-9])", re.I)
        return ((m.start(), m.end()) for m in pattern.finditer(text))

    def _iter() -> Iterable[Tuple[int, int]]:
        start = 0
        while True:
            idx = text.find(term_l, start)
            if idx < 0:
                return
            yield idx, idx + len(term_l)
            start = idx + len(term_l)

    return _iter()


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 36):start]
    # Negation cannot cross a clause boundary.
    parts = _SEPARATOR.split(prefix)
    clause = parts[-1] if parts else prefix
    return bool(_NEGATION_ZH.search(clause) or _NEGATION_EN.search(clause))


def _first_positive_match(text: str, terms: Sequence[str]) -> str:
    for term in terms:
        for start, _end in _term_occurrences(text, term):
            if not _is_negated(text, start):
                return term
    return ""


def analyze_symptoms(text: str) -> Dict[str, Any]:
    """Analyze bilingual free text and return a calibrated triage result."""
    normalized = normalize_text(text)
    specialty_scores: Dict[str, float] = {}
    matched_terms: List[str] = []
    matched_concepts: List[str] = []
    red_flags: List[str] = []
    questions: List[str] = []
    confidences: List[float] = []
    urgent = False
    force_clarification = False

    for rule in SYMPTOM_RULES:
        term = _first_positive_match(normalized, rule["terms"])
        if not term:
            continue
        matched_terms.append(term)
        matched_concepts.append(rule["id"])
        confidences.append(float(rule["confidence"]))
        urgent = urgent or bool(rule["urgent"])
        force_clarification = force_clarification or bool(rule["clarify"])
        if rule["red_flag"] and rule["red_flag"] not in red_flags:
            red_flags.append(rule["red_flag"])
        for question in rule["questions"]:
            if question not in questions:
                questions.append(question)
        for specialty, weight in rule["specialties"].items():
            specialty_scores[specialty] = specialty_scores.get(specialty, 0.0) + float(weight)

    # Context modifiers are deliberately smaller than an explicit symptom.
    child_term = _first_positive_match(normalized, ("婴儿", "宝宝", "儿童", "孩子", "小孩", "baby", "infant", "toddler", "child"))
    if child_term:
        specialty_scores["Pediatrics"] = specialty_scores.get("Pediatrics", 0.0) + 140.0
        if child_term not in matched_terms:
            matched_terms.append(child_term)
        confidences.append(0.78)
    older_term = _first_positive_match(normalized, ("老年人", "老人", "高龄", "elderly", "older adult", "senior"))
    if older_term:
        specialty_scores["Geriatrics"] = specialty_scores.get("Geriatrics", 0.0) + 45.0

    ranked = sorted(specialty_scores.items(), key=lambda item: (-item[1], item[0]))
    if ranked:
        primary = ranked[0][0]
        confidence = max(confidences or [0.55]) + min(0.10, max(0, len(matched_concepts) - 1) * 0.035)
        confidence = min(0.99, confidence)
    else:
        primary = "General Medicine"
        specialty_scores = {"General Medicine": 40.0}
        ranked = [("General Medicine", 40.0)]
        confidence = 0.20
        force_clarification = True
        questions.extend(("最不舒服的部位在哪里？", "症状持续多久、严重程度如何，并伴有哪些症状？"))

    if urgent and primary != "Emergency":
        # Red flags should route to emergency first even if a disease-specific
        # service has a slightly larger aggregate score.
        specialty_scores["Emergency"] = max(specialty_scores.get("Emergency", 0.0), ranked[0][1] + 10.0)
        ranked = sorted(specialty_scores.items(), key=lambda item: (-item[1], item[0]))
        primary = ranked[0][0]

    needs_clarification = force_clarification or confidence < 0.68
    alternatives = [
        {"department_en": specialty, "department_zh": DEPARTMENT_ZH.get(specialty, specialty), "score": round(score, 1)}
        for specialty, score in ranked[1:4]
        if specialty != primary
    ]

    if urgent:
        recommendation_zh = "检测到可能的红旗症状：请立即拨打 120 或前往最近急诊，不要因医院排名延误就医。"
        recommendation_en = "A possible red flag was detected. Call 120 or go to the nearest emergency department now; do not delay care for a ranking."
    elif primary == "Mental Health / Psychiatry":
        recommendation_zh = "初步建议精神心理科或心理门诊。请补充持续时间和对生活的影响；若出现自伤或轻生想法，请立即拨打 120 或前往急诊。"
        recommendation_en = "A mental-health or psychiatry clinic is the preliminary route. Add duration and impact; if there are thoughts of self-harm, call 120 or seek emergency care now."
    elif needs_clarification:
        recommendation_zh = f"当前信息不足以做高置信度分诊，初步可咨询{DEPARTMENT_ZH.get(primary, primary)}；补充问题后再匹配医院。"
        recommendation_en = f"There is not enough detail for high-confidence triage. {primary} is a preliminary route; answer the follow-up questions before choosing a hospital."
    else:
        recommendation_zh = f"根据已识别的症状，初步建议{DEPARTMENT_ZH.get(primary, primary)}。这不是诊断，症状加重时请及时就医。"
        recommendation_en = f"Based on the recognised symptoms, {primary} is the preliminary department. This is not a diagnosis; seek timely care if symptoms worsen."

    return {
        "department_en": primary,
        "department_zh": DEPARTMENT_ZH.get(primary, primary),
        "recommendation_en": recommendation_en,
        "recommendation_zh": recommendation_zh,
        "urgent": urgent,
        "matched_symptoms": matched_terms[:8],
        "matched_concepts": matched_concepts,
        "specialty_scores": {key: round(value, 2) for key, value in ranked},
        "confidence": round(confidence, 2),
        "needs_clarification": needs_clarification,
        "red_flags": red_flags[:4],
        "alternative_departments": alternatives,
        "follow_up_questions": questions[:3],
        "follow_up_questions_en": list(_FOLLOW_UP_EN.get(primary, (
            "How long has this lasted, how severe is it, and what other symptoms are present?",
        )))[:3],
        "engine_version": ENGINE_VERSION,
    }
