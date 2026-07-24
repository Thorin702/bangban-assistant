# -*- coding: utf-8 -*-
"""黄金测试集回归：python scripts/regression.py [--limit N] [--set path]

对每条样本走 检索→过滤→生成→守卫 全链路（不写入 consults 留痕库），输出：
- 自动硬指标：空结果率、结构完整率、角标有效率、文号真实率、守卫违规清单
- 人工评审表（Markdown）：检索命中【参考依据】与期望行为需人工判定，表格留空待填

真实接口模式下每条生成约 20-40s，先用 --limit 3 冒烟再全量。
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, db, generation, guards, pii, retrieval  # noqa: E402

DEFAULT_SET = Path(__file__).resolve().parent.parent.parent / "测试样本集" / "golden-set-v0.1.json"


def run_case(case: dict, settings: dict) -> dict:
    query = pii.mask_for_external(case["complaint"])
    area = settings.get("default_service_area", "")
    t0 = time.time()
    r = {"gs_id": case["gs_id"], "scenario": case["scenario"], "tags": case.get("tags", [])}
    try:
        ret = retrieval.search(query, area, "", settings)
    except retrieval.RetrievalError as e:
        r.update(status="retrieval_error", error=str(e))
        return r
    r["material_count"] = len(ret["materials"])
    r["material_titles"] = [m["title"] for m in ret["materials"]]
    r["retrieval_mode"] = ret["mode"]
    if not ret["materials"]:
        r.update(status="empty", latency_s=round(time.time() - t0, 1))
        return r
    cfg = generation.resolve_config(settings)
    system_prompt = settings.get("consult_system_prompt") or config.DEFAULT_CONSULT_SYSTEM_PROMPT
    prompt = generation.build_user_prompt(query, ret["materials"], area)
    text = ""
    try:
        for piece in generation.stream_chat(cfg, system_prompt, prompt):
            text += piece
    except generation.GenerationError as e:
        r.update(status="generation_error", error=str(e))
        return r
    v = guards.validate(text, ret["materials"], kind="consult")
    r.update(
        status="done",
        latency_s=round(time.time() - t0, 1),
        gen_len=len(text),
        structure_ok=not any(i["type"] == "structure_broken" for i in v["issues"]),
        citations_ok=not any(i["type"].startswith("citation") for i in v["issues"]),
        docno_ok=not any(i["type"] == "docno_unverified" for i in v["issues"]),
        document_like=any(i["type"] == "document_like" for i in v["issues"]),
        issues=[i["detail"] for i in v["issues"]],
        gen_text=text,
    )
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(DEFAULT_SET))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    data = json.loads(Path(args.set).read_text(encoding="utf-8"))
    cases = data["cases"][: args.limit] if args.limit else data["cases"]
    settings = db.get_settings()
    cfg = generation.resolve_config(settings)
    mode = "演示" if config.RETRIEVAL_MOCK else "真实"
    gen_mode = cfg["model"] if generation.is_configured(cfg) else "未配置"
    print(f"回归开始：{len(cases)} 条 | 检索={mode} | 生成={gen_mode}")
    if not generation.is_configured(cfg):
        print("⚠ 生成模型未配置（后台管理→生成模型接入），本次仅评估检索与空态。")

    results = []
    for i, c in enumerate(cases, 1):
        r = run_case(c, settings)
        results.append(r)
        flag = {"done": "✓", "empty": "空", "retrieval_error": "检索错", "generation_error": "生成错"}[r["status"]]
        extra = "" if r["status"] != "done" else ("" if not r["issues"] else f" ⚠{len(r['issues'])}")
        print(f"[{i}/{len(cases)}] {r['gs_id']} {flag}{extra}")

    done = [r for r in results if r["status"] == "done"]
    n = len(results)
    stats = {
        "总数": n,
        "完成": len(done),
        "空结果率": f"{sum(1 for r in results if r['status'] == 'empty') / n:.0%}",
        "结构完整率": f"{sum(1 for r in done if r['structure_ok']) / max(len(done), 1):.0%}",
        "角标有效率": f"{sum(1 for r in done if r['citations_ok']) / max(len(done), 1):.0%}",
        "文号真实率": f"{sum(1 for r in done if r['docno_ok']) / max(len(done), 1):.0%}",
        "文书越界数": sum(1 for r in done if r["document_like"]),
    }
    print("\n== 自动指标 ==")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    ts = time.strftime("%Y%m%d-%H%M")
    out = Path(args.out) if args.out else config.DATA_DIR / f"regression-{ts}.md"
    lines = [f"# 回归报告 {ts}", "", f"检索模式：{mode}　生成：{gen_mode}", "",
             "| 指标 | 值 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in stats.items()]
    lines += ["", "## 人工评审表（命中/行为两列人工填写）", "",
              "| 用例 | 场景 | 状态 | 材料数 | 守卫问题 | 检索命中参考依据？ | 期望行为达成？ |",
              "|---|---|---|---|---|---|---|"]
    for r in results:
        issues = "；".join(r.get("issues", [])) or "—"
        lines.append(f"| {r['gs_id']} | {r['scenario']} | {r['status']} | {r.get('material_count', '—')} | {issues} |  |  |")
    lines += ["", "## 生成原文（供评审）", ""]
    for r in results:
        if r.get("gen_text"):
            lines += [f"### {r['gs_id']}", "", "```", r["gen_text"], "```", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已写入：{out}")


if __name__ == "__main__":
    main()
