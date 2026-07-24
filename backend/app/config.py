"""环境配置。密钥走环境变量/.env 作为首次种子；运行期生成配置以后台数据库为准。"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BB_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

APP_DB = DATA_DIR / "app.db"
CASES_DB = DATA_DIR / "cases.db"
PRIVATE_DB = DATA_DIR / "private.db"
STATIC_DIR = BASE_DIR / "static"


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# ---- 政策检索（dknowc 可信搜索）----
DKNOWC_ENDPOINT = os.environ.get("DKNOWC_ENDPOINT", "https://open.dknowc.cn/dependable/search")
DKNOWC_API_KEY = os.environ.get("DKNOWC_API_KEY", "")
RETRIEVAL_MOCK = os.environ.get("RETRIEVAL_MOCK", "").strip() in ("1", "true", "yes") or not DKNOWC_API_KEY
RETRIEVAL_TIMEOUT = float(os.environ.get("RETRIEVAL_TIMEOUT", "60"))

GEN_TIMEOUT = float(os.environ.get("GEN_TIMEOUT", "180"))
GEN_TEST_TIMEOUT = float(os.environ.get("GEN_TEST_TIMEOUT", "30"))

# 生成接入的首次种子（仅在数据库尚无配置时写入，之后以后台为准）
_SEED_BASE_URL = os.environ.get("GEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
_SEED_MODEL = os.environ.get("GEN_MODEL", "qwen3-32b")
_SEED_KEY = os.environ.get("GEN_API_KEY", "") or os.environ.get("DASHSCOPE_API_KEY", "")


def _jwt_secret() -> str:
    if os.environ.get("BB_JWT_SECRET"):
        return os.environ["BB_JWT_SECRET"]
    f = DATA_DIR / "jwt.secret"
    if f.exists():
        return f.read_text().strip()
    s = secrets.token_hex(32)
    f.write_text(s)
    return s


JWT_SECRET = _jwt_secret()
JWT_TTL_HOURS = int(os.environ.get("BB_JWT_TTL_HOURS", "168"))

DEFAULT_CONSULT_SYSTEM_PROMPT = """你是基层帮办智能助手，为一线承办人处理12345工单与矛盾调解提供政策参考。严格遵守：
1) 只依据给定的【政策材料】作答，不得编造材料中没有的信息、标准或文号；
2) 涉及具体数值（温度、比例、金额、时限、面积等）时，只能使用材料中明确写出的数字；材料未写明的，说明"具体标准以合同或当地规定为准，材料未提供具体数值"，严禁填入常识性或估计数字（例如：材料未写明供暖达标温度时，严禁写"通常为18℃"，应写"具体达标温度以合同或当地供热条例为准"）；
3) 若某条材料与本诉求情形明显无关，忽略它、不要引用，也不要牵强关联；宁可少引用，不可错引用；标注[材料N]时须确保该材料原文确实支持所述内容；若给出【办理地域】，回答与引用须严格限于该地域，不得引用其他地市的政策或案例；
4) 材料不足以回答某点时，明确说"材料未提供"；
5) 回答分三部分，请严格按此顺序输出，每部分以下列标记单独起一行开头：【回复话术】【办理方法】【条款解释】；
6) 回复话术：这是承办人代表承办单位、回复诉求人的话（不是完整回复件）。以"我们/我单位"第一人称，体现承办人主动核实、协调、督促责任单位、推动办理——凡属承办单位可协调处理的事项（如供暖不热、噪音扰民、占道经营、维修养护、办事指引、督促相关单位履职等），应表达"我们已/将 核实、责成或督促相关单位、现场处置、限期整改并跟进反馈"等主动措施，绝不能简单让诉求人自行去联系相关单位（正例："我们已督促执法中队现场处置并要求限期整改，后续将跟踪落实"；反例（禁止）："建议您自行联系城管部门处理"）。仅当事项依法确需诉求人本人完成时——属民事纠纷须走司法诉讼/仲裁途径、须本人提交材料或到窗口亲自办理、或明确不属本部门受理范围——才引导其自行办理，且必须同时给出所需材料、正确的部门/渠道以及我方可提供的协助（如调解、出具证明、代为转办），不得只用一句"请联系XX"了事。不得承诺材料未支撑的具体结果（如赔偿金额、办结时限），可表述为"将依规核实办理并及时向您反馈"。
   办理方法给承办人的办理流程、所需材料、办理渠道、时限与注意点；条款解释用通俗语言说明适用条件与关键标准。
7) 每个关键信息后必须用方括号格式标注来源，如[材料1]、[材料2]，不要写成"根据材料1"这类散文形式；诉求含多项请求时，逐项回应，不得遗漏；
8) 诉求本身不符合政策规定或缺乏依据时，如实说明并给出可行的替代路径，不得迎合；
9) 不得拟写调解协议书、回复件、情况说明等任何完整对外文书。
所有内容仅供参考，承办人须人工核实。"""

DEFAULT_EXPERIENCE_SYSTEM_PROMPT = """你是基层帮办智能助手的类案经验模块。给定当前诉求与若干条历史工单（含当年办理情况与办理结果），请提炼可参考的办理经验。规则：
1) 严格依据给定的【历史案例】提炼，不得编造案例中没有的做法或结果；
2) 输出两部分，各部分以下列标记单独起一行开头：【常见处理路径】【经验与注意点】；
3) 每条要点后用[案例N]标注来源；
4) 历史办理做法不代表现行政策口径，涉及政策口径的要点须提示"以现行政策核实为准"；
5) 案例与当前诉求情形不符处要指出，不得生搬硬套；
6) 简洁分条，总字数不超过400字。
所有内容仅供参考，承办人须人工核实。"""

# 后台可编辑的运行参数（首次写入数据库的种子默认值）
DEFAULT_SETTINGS = {
    # 生成模型接入
    "llm_base_url": _SEED_BASE_URL,
    "llm_api_key": _SEED_KEY,
    "llm_model": _SEED_MODEL,
    # 生成参数（技术人员按承办单位口径调节）
    "gen_temperature": "0.3",
    "gen_top_p": "0.8",
    "gen_max_tokens": "2000",
    "gen_enable_thinking": "0",
    "gen_extra_params": "{}",
    # 提示词（口径可调，直接编辑）
    "consult_system_prompt": DEFAULT_CONSULT_SYSTEM_PROMPT,
    "experience_system_prompt": DEFAULT_EXPERIENCE_SYSTEM_PROMPT,
    # 类案经验
    "case_feature_enabled": "1",
    "case_top_k": "5",
    # 办件研判（时限/满意度/关联，基于历史工单结果）
    "research_enabled": "1",
    # 私有政策库（可选，各地市不公开政策）
    "private_db_enabled": "0",
    # 逐地市部署：地域与生效时间由后台设定
    "default_service_area": "枣庄",
    "default_eff_time": "",
    # 政策检索与过滤
    "top_n": "4",
    "segment_count": "3",
    "blocked_source_keywords": "范文\n公文写作\n文库\n豆丁\ndoc88\n作文",
    "authoritative_domains": "gov.cn\n12348.gov.cn\ncourt.gov.cn\nspp.gov.cn\n12377.cn",
    "authoritative_source_names": "人民政府\n政府办公室\n人力资源和社会保障\n人力资源社会保障部\n住房公积金\n医疗保障\n教育\n住房和城乡建设\n市场监督管理\n市场监管\n司法\n民政\n人民法院\n最高人民\n人民检察院\n检察\n中国政府网\n司法部\n新华社\n普法网\n国务院\n发展改革\n国家能源\n税务\n公安\n生态环境\n自然资源\n交通运输\n农业农村\n卫生健康\n医保局\n全国人大\n人大常委会\n发改",
    "disclaimer_text": "AI 生成内容仅供参考，请人工核实后使用",
}
