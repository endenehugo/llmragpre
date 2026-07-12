from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from flask import current_app
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

JD_ANALYSIS_SYSTEM_PROMPT = """你是一位资深的招聘分析专家，擅长分析招聘职位描述（JD）。
请严格分析用户提供的 JD 文本，并返回 **严格的 JSON**，包含以下字段：

- `job_role` (str): 岗位名称/职位名称
- `keywords` (list[str]): 从 JD 中提取的核心技术关键词列表（如 Python、Flask、MySQL、Redis、Docker 等）
- `requirements` (list[str]): 硬性要求列表（学历、经验年限、必须掌握的技术等）
- `bonus_points` (list[str]): 加分项列表（优先条件、加分技能等）
- `suggested_project_angles` (list[str]): 建议在简历项目中突出的角度（如何让自己的经历贴合该 JD 的侧重点）

请确保：
1. 输出的内容必须是 **纯 JSON 对象**，不要包含 markdown 代码块标记（```json）、不要额外解释。
2. 每个字段的值即使为空也要给出空数组。
3. keywords 要尽可能全面，包括编程语言、框架、中间件、工具等。
4. requirements 和 bonus_points 请基于 JD 原文精准归纳，不要凭空添加。
"""


@dataclass
class JobDescriptionService:
    _llm: ChatTongyi | None = None

    def analyze(self, jd_text: str) -> dict:
        if not jd_text or not jd_text.strip():
            raise ValueError("JD 文本不能为空")

        if len(jd_text.strip()) < 10:
            raise ValueError("JD 文本太短，请提供完整的职位描述")

        content = self._invoke_llm(jd_text.strip())
        return self._parse_response(content)

    def _ensure_llm(self) -> ChatTongyi:
        if self._llm is None:
            model_name = "qwen-plus"
            try:
                model_name = current_app.config.get("LLM_MODEL", model_name)
            except RuntimeError:
                pass
            self._llm = ChatTongyi(
                model=model_name,
                temperature=0.3,
                top_p=0.7,
            )
        return self._llm

    def _invoke_llm(self, jd_text: str) -> str:
        llm = self._ensure_llm()
        messages = [
            SystemMessage(content=JD_ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=f"请分析以下职位描述：\n\n{jd_text}"),
        ]
        response = llm.invoke(messages)
        return response.content or ""

    def _parse_response(self, content: str) -> dict:
        logger.info("LLM JD analysis raw response (first 500 chars): %s", content[:500])
        try:
            result = json.loads(content)
            return self._validate_and_normalize(result)
        except json.JSONDecodeError:
            pass

        # 策略1: 从 markdown 代码块中提取
        json_text = _extract_json_from_markdown(content)
        if json_text:
            try:
                result = json.loads(json_text)
                return self._validate_and_normalize(result)
            except json.JSONDecodeError:
                pass
            repaired = _repair_json(json_text)
            if repaired != json_text:
                try:
                    result = json.loads(repaired)
                    return self._validate_and_normalize(result)
                except json.JSONDecodeError:
                    pass

        # 策略2: 用括号匹配提取最外层 JSON 对象
        json_text = _extract_json_by_braces(content)
        if json_text:
            try:
                result = json.loads(json_text)
                return self._validate_and_normalize(result)
            except json.JSONDecodeError:
                pass
            repaired = _repair_json(json_text)
            if repaired != json_text:
                try:
                    result = json.loads(repaired)
                    return self._validate_and_normalize(result)
                except json.JSONDecodeError:
                    pass

        # 策略3: 对原始内容尝试修复
        repaired = _repair_json(content)
        if repaired != content:
            try:
                result = json.loads(repaired)
                return self._validate_and_normalize(result)
            except json.JSONDecodeError:
                pass

        # 策略4: 正则兜底
        json_match = re.search(r"\{(?:[^{}]|\{[^{}]*\})*\}", content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return self._validate_and_normalize(result)
            except json.JSONDecodeError:
                pass

        raise ValueError("JD 解析返回格式异常，无法提取结构化结果")

    @staticmethod
    def _validate_and_normalize(result: dict) -> dict:
        normalized = {
            "job_role": str(result.get("job_role", "")).strip(),
            "keywords": result.get("keywords", []) or [],
            "requirements": result.get("requirements", []) or [],
            "bonus_points": result.get("bonus_points", []) or [],
            "suggested_project_angles": result.get("suggested_project_angles", []) or [],
        }

        # 确保列表字段都是字符串列表
        for list_field in ("keywords", "requirements", "bonus_points", "suggested_project_angles"):
            normalized[list_field] = [str(item).strip() for item in normalized[list_field] if item]

        return normalized


def _repair_json(text: str) -> str:
    """修复 LLM 常见 JSON 格式错误：数组被错误地用 } 闭合而不是 ]。"""
    pattern = r'"\s*\n(\s+)},\s*\n\1(")'
    fixed = re.sub(pattern, lambda m: '"\n' + m.group(1) + '],\n' + m.group(1) + m.group(2), text)
    return fixed


def _extract_json_from_markdown(text: str) -> str | None:
    """从 markdown 代码块中提取 JSON 内容（不限位置）"""
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        candidate = match.strip()
        if candidate.startswith("{"):
            return candidate
    return None


def _extract_json_by_braces(text: str) -> str | None:
    """通过括号计数提取最外层 JSON 对象"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None
