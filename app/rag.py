"""RAG 链：多轮历史、查询重写、检索、重排序、生成与引用。"""
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from app.knowledge import ROOT, retrieve_and_rerank

SYSTEM_PROMPT = """你是 AI Solution Copilot，一名面向企业客户的 AI 解决方案顾问。
只能根据给定的知识库片段回答；没有依据时明确说“当前知识库未覆盖，需要业务确认”，不要编造具体厂商参数、报价或性能承诺。
输出必须使用以下五个标题：
1. 需求判断
2. 推荐架构
3. 实施步骤
4. 风险与待确认项
5. 下一步行动
用简洁、可落地的中文表达，并在相应句末用 [1]、[2] 标记资料引用。"""


def _client() -> OpenAI | None:
    load_dotenv(ROOT / ".env")
    key = os.getenv("DASHSCOPE_API_KEY")
    return OpenAI(api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1") if key else None


def rewrite_query(question: str, history: list[dict[str, str]]) -> str:
    client = _client()
    if not client or not history:
        return question
    dialogue = "\n".join(f"{item['role']}：{item['content']}" for item in history[-6:])
    try:
        response = client.chat.completions.create(
            model=os.getenv("CHAT_MODEL", "qwen-plus"), temperature=0,
            messages=[{"role": "system", "content": "将追问改写为可独立检索的一句话，只输出改写结果。"}, {"role": "user", "content": f"对话：\n{dialogue}\n\n当前问题：{question}"}],
        )
        return response.choices[0].message.content.strip() or question
    except Exception:
        return question


def _fallback_answer(hits: list[dict[str, Any]]) -> str:
    if not hits or hits[0]["score"] <= 0:
        return "知识库中暂未找到相关信息。"
    primary = hits[0]["content"]
    source = "[1]" if hits else ""
    return (
        "1. 需求判断\n"
        "当前需求适合先以单一部门或单一场景做 AI 试点，优先确认目标用户、资料来源、现有流程和验收指标。\n\n"
        "2. 推荐架构\n"
        f"建议采用“业务资料库 + 检索增强问答 + 人工审核/工单升级”的轻量架构。{source}\n\n"
        "3. 实施步骤\n"
        "先整理 20-50 份公开或脱敏资料，完成可引用问答；再接入工单或 CRM，并记录高频问题和人工修订。\n\n"
        "4. 风险与待确认项\n"
        "需要确认资料权限、真实系统接口、设备安全边界、预算和验收指标；演示阶段不输出真实报价或厂商性能承诺。\n\n"
        "5. 下一步行动\n"
        f"建议约一次需求澄清会，整理试点资料清单并定义首个验收指标。参考资料：{primary[:180]}… {source}"
    )


def answer(question: str, history: list[dict[str, str]]) -> dict[str, Any]:
    standalone_question = rewrite_query(question, history)
    hits = retrieve_and_rerank(standalone_question)
    context = "\n\n".join(f"[{i}] {hit['content']}" for i, hit in enumerate(hits, 1))
    client = _client()
    if client and hits:
        try:
            response = client.chat.completions.create(
                model=os.getenv("CHAT_MODEL", "qwen-plus"), temperature=0.2,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"知识库片段：\n{context}\n\n问题：{question}"}],
            )
            text = response.choices[0].message.content.strip()
        except Exception:
            text = _fallback_answer(hits)
    else:
        text = _fallback_answer(hits)
    sources = [{"index": i, "title": hit["metadata"]["title"], "source": hit["metadata"]["source"], "chunk_id": hit["metadata"]["chunk_id"], "content": hit["content"]} for i, hit in enumerate(hits, 1)]
    return {"answer": text, "rewritten_query": standalone_question, "sources": sources}
