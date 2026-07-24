"""咨询管线：检索→过滤→短路→生成→分段流式→守卫→留痕，以 SSE 事件下发。"""
import json
import re
import time

from . import cases as cases_mod
from . import config, db, generation, guards, pii, research, retrieval

SECTION_KEYS = {"【条款解释】": "interpret", "【回复话术】": "reply", "【办理方法】": "method"}
_MARKER_RE = re.compile("|".join(re.escape(m) for m in SECTION_KEYS))
EXPERIENCE_KEYS = {"【常见处理路径】": "paths", "【经验与注意点】": "tips"}
_EXP_MARKER_RE = re.compile("|".join(re.escape(m) for m in EXPERIENCE_KEYS))


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class _SectionRouter:
    """把生成流按【标记】切分路由；标记不全时容错为 raw 整块。"""

    def __init__(self, marker_re, key_map):
        self.marker_re = marker_re
        self.key_map = key_map
        self.maxlen = max(len(m) for m in key_map)  # 保留可能是标记前缀的尾巴时用
        self.buf = ""
        self.current = None
        self.sections = {}
        self.events = []

    def _emit(self, name, text):
        if not text:
            return
        self.sections[name] = self.sections.get(name, "") + text
        self.events.append(("delta", {"name": name, "text": text}))

    def feed(self, piece: str):
        self.events = []
        self.buf += piece
        while True:
            m = self.marker_re.search(self.buf)
            if not m:
                break
            before, marker = self.buf[: m.start()], m.group(0)
            if self.current is None:
                if before.strip():
                    self._emit("raw", before)
            else:
                self._emit(self.current, before)
            new_name = self.key_map[marker]
            if new_name != self.current:
                if self.current is not None:
                    self.events.append(("section", {"name": self.current, "status": "end"}))
                self.current = new_name
                self.events.append(("section", {"name": self.current, "status": "start"}))
            self.buf = self.buf[m.end():]
        hold = 0
        for i in range(min(len(self.buf), self.maxlen), 0, -1):
            tail = self.buf[-i:]
            if any(mk.startswith(tail) for mk in self.key_map):
                hold = i
                break
        emit_now, self.buf = (self.buf[:-hold], self.buf[-hold:]) if hold else (self.buf, "")
        if emit_now:
            self._emit(self.current or "raw", emit_now)
        return self.events

    def finish(self):
        self.events = []
        if self.buf:
            self._emit(self.current or "raw", self.buf)
            self.buf = ""
        if self.current is not None:
            self.events.append(("section", {"name": self.current, "status": "end"}))
        return self.events


def run_consult(user, complaint: str):
    settings = db.get_settings()
    cfg = generation.resolve_config(settings)
    service_area = settings.get("default_service_area", "")
    eff_time = settings.get("default_eff_time", "")
    t0 = time.time()
    masked = pii.mask_for_external(complaint)
    cid = db.create_consult(user["id"], complaint, masked, service_area, eff_time,
                            "mock" if config.RETRIEVAL_MOCK else "live", cfg["model"])
    yield sse("meta", {"consult_id": cid})

    case_list = []
    if db.setting_bool(settings, "case_feature_enabled") and cases_mod.available():
        try:
            case_list = cases_mod.search_similar(masked, db.setting_int(settings, "case_top_k", 5))
        except Exception:
            case_list = []
        if case_list:
            db.update_consult(cid, cases_json=case_list)
            yield sse("cases", {"cases": case_list})

    # ---- 办件研判（时限/满意度/关联，基于历史工单结果）----
    if db.setting_bool(settings, "research_enabled") and cases_mod.available():
        try:
            sig = research.compute_signals(masked)
        except Exception:
            sig = None
        if sig:
            db.update_consult(cid, research_json=sig)
            yield sse("research", sig)

    try:
        try:
            ret = retrieval.search(masked, service_area, eff_time, settings)
        except retrieval.RetrievalError as e:
            db.update_consult(cid, status="error", error_message=str(e))
            yield sse("error", {"stage": "retrieval", "message": str(e), "retryable": e.retryable})
            return
        materials = ret["materials"]
        db.update_consult(cid, retrieval_json=ret)
        yield sse("retrieval", ret)

        if not materials:
            msg = "未检索到相关政策材料。建议换更具体的关键词描述（事项、对象、地域），或转人工渠道核实。"
            db.update_consult(cid, status="empty", latency_ms=int((time.time() - t0) * 1000))
            yield sse("empty", {"message": msg})
            return

        user_prompt = generation.build_user_prompt(masked, materials, service_area)
        system_prompt = settings.get("consult_system_prompt") or config.DEFAULT_CONSULT_SYSTEM_PROMPT
        router = _SectionRouter(_MARKER_RE, SECTION_KEYS)
        gen_text, first_token_ms = "", None
        try:
            for piece in generation.stream_chat(cfg, system_prompt, user_prompt):
                if first_token_ms is None:
                    first_token_ms = int((time.time() - t0) * 1000)
                gen_text += piece
                for ev, data in router.feed(piece):
                    yield sse(ev, data)
        except generation.GenerationError as e:
            db.update_consult(cid, status="error", error_message=str(e), gen_text=gen_text or None)
            yield sse("error", {"stage": "generation", "message": str(e), "retryable": e.retryable})
            return
        for ev, data in router.finish():
            yield sse(ev, data)

        validation = guards.validate(gen_text, materials, kind="consult")
        latency = int((time.time() - t0) * 1000)
        db.update_consult(cid, status="done", gen_text=gen_text, sections_json=router.sections,
                          validation_json=validation, latency_ms=latency, first_token_ms=first_token_ms)
        yield sse("validation", validation)
        yield sse("done", {"latency_ms": latency, "first_token_ms": first_token_ms})
    except Exception:
        # 兜底：任何未预期异常都要给前端终止事件并把工单落为 error（否则前端卡死、工单永久 running）
        db.update_consult(cid, status="error", error_message="内部处理异常")
        yield sse("error", {"stage": "internal", "message": "系统内部处理异常，请稍后重试", "retryable": True})
        return


def run_experience(user, consult_row):
    settings = db.get_settings()
    if not db.setting_bool(settings, "case_feature_enabled"):
        yield sse("error", {"stage": "experience", "message": "类案经验功能未开启", "retryable": False})
        return
    case_list = json.loads(consult_row["cases_json"]) if consult_row["cases_json"] else []
    if not case_list:
        yield sse("error", {"stage": "experience", "message": "本次咨询没有可用类案", "retryable": False})
        return
    cfg = generation.resolve_config(settings)
    prompt = generation.build_experience_prompt(consult_row["complaint_masked"], case_list)
    system_prompt = settings.get("experience_system_prompt") or config.DEFAULT_EXPERIENCE_SYSTEM_PROMPT
    router = _SectionRouter(_EXP_MARKER_RE, EXPERIENCE_KEYS)
    text = ""
    try:
        for piece in generation.stream_chat(cfg, system_prompt, prompt):
            text += piece
            for ev, data in router.feed(piece):
                yield sse(ev, data)
    except generation.GenerationError as e:
        yield sse("error", {"stage": "experience", "message": str(e), "retryable": e.retryable})
        return
    for ev, data in router.finish():
        yield sse(ev, data)
    validation = guards.validate(text, case_list, kind="experience")
    db.update_consult(consult_row["id"], experience_text=text)
    yield sse("validation", validation)
    yield sse("done", {})


def run_prescription(user, consult_row):
    """满意度处方：对比同类满意/不满意办理情况，提炼办到满意的关键（按需触发）。"""
    settings = db.get_settings()
    if not db.setting_bool(settings, "research_enabled"):
        yield sse("error", {"stage": "prescription", "message": "办件研判未开启", "retryable": False})
        return
    prompt = research.build_prescription_prompt(consult_row["complaint_masked"])
    if not prompt:
        yield sse("error", {"stage": "prescription", "message": "同类满意样本不足，暂无法生成处方", "retryable": False})
        return
    cfg = generation.resolve_config(settings)
    text = ""
    try:
        for piece in generation.stream_chat(cfg, research.PRESCRIPTION_SYSTEM, prompt):
            text += piece
            yield sse("delta", {"name": "prescription", "text": piece})
    except generation.GenerationError as e:
        yield sse("error", {"stage": "prescription", "message": str(e), "retryable": e.retryable})
        return
    yield sse("done", {})
