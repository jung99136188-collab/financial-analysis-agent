"""
Gemini 适配器

将 OpenAI 格式的消息/工具/响应 与 Gemini API 格式互相转换。

Gemini API 文档:
    https://ai.google.dev/gemini-api/docs/function-calling

格式差异:
    | 概念       | OpenAI                          | Gemini                              |
    |-----------|---------------------------------|-------------------------------------|
    | 消息       | {role, content}                 | {role, parts: [{text}]}             |
    | 工具       | [{type:"function", function:{}}]| [{functionDeclarations:[{...}]}]    |
    | 工具调用    | message.tool_calls[...]         | content.parts[{functionCall:{}}]    |
    | 工具结果    | {role:"tool", tool_call_id, c}  | {role:"tool", parts:[{functionResponse:{name, response:{content}}}]}|
    | System    | messages[0] role="system"       | systemInstruction: {parts:[{text}]} |
"""

import json
import uuid
import requests
from . import LLMClient


class GeminiClient(LLMClient):
    """Google Gemini API 客户端"""

    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self._model = config.get("model", "gemini-2.5-flash")
        self._timeout = config.get("timeout", 120)
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def model_name(self):
        return self._model

    # ================================================================
    # 公开接口
    # ================================================================

    def chat(self, messages, tools=None, temperature=0.3, max_tokens=4096):
        """主入口 — 调用 Gemini API"""

        # 1. 分离 system prompt
        system_instruction = None
        conversation = []
        for msg in messages:
            if msg["role"] == "system":
                # 合并多个 system 消息
                existing = system_instruction["parts"][0]["text"] if system_instruction else ""
                system_instruction = {
                    "parts": [{"text": (existing + "\n" + msg["content"]).strip()}]
                }
            else:
                conversation.append(msg)

        # 2. 转换格式: OpenAI → Gemini
        gemini_contents = self._messages_to_gemini(conversation)
        gemini_tools = self._tools_to_gemini(tools) if tools else None
        tool_config = self._build_tool_config(tools) if tools else None

        # 3. 构建请求
        url = f"{self._base_url}/models/{self._model}:generateContent"
        if "?" not in url:
            url += f"?key={self.api_key}"
        else:
            url += f"&key={self.api_key}"

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if gemini_tools:
            payload["tools"] = gemini_tools
        if tool_config:
            payload["toolConfig"] = tool_config

        # 4. 调用 API
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, headers=headers, json=payload, timeout=self._timeout)

            if response.status_code == 200:
                result = response.json()
                return self._response_to_openai(result)
            else:
                error_msg = f"Gemini API error {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except Exception:
                    error_msg += f": {response.text[:300]}"
                print(f"  [LLM:Gemini] {error_msg}")
                return {"role": "assistant", "content": f"模型调用失败: {error_msg}"}

        except requests.exceptions.Timeout:
            print(f"  [LLM:Gemini] 请求超时")
            return {"role": "assistant", "content": "模型调用超时，请稍后重试。"}

        except Exception as e:
            print(f"  [LLM:Gemini] 请求异常: {str(e)}")
            return {"role": "assistant", "content": f"模型调用异常: {str(e)}"}

    # ================================================================
    # 格式转换: OpenAI → Gemini
    # ================================================================

    def _messages_to_gemini(self, messages):
        """将 OpenAI 消息列表转换为 Gemini contents 列表"""
        contents = []
        for msg in messages:
            role = msg["role"]
            gemini_role = self._map_role(role)
            parts = []

            if role == "assistant" and msg.get("tool_calls"):
                # Assistant 消息包含 tool_calls → 每个 tool_call 转为一个 functionCall part
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    parts.append({
                        "functionCall": {
                            "name": fn.get("name", ""),
                            "args": args,
                        }
                    })
                # 如果同时有文本内容，也加上
                if msg.get("content"):
                    parts.insert(0, {"text": msg["content"]})

            elif role == "tool":
                # Tool 结果 → functionResponse part
                parts.append({
                    "functionResponse": {
                        "name": msg.get("name", ""),
                        "response": {"content": msg.get("content", "")},
                    }
                })

            elif role == "user":
                parts.append({"text": msg.get("content", "")})

            elif role == "assistant":
                parts.append({"text": msg.get("content", "")})

            # Gemini 不区分 user/assistant/tool → 统一用 role
            # tool role 映射为 "tool", 其余保持 "user" 或 "model"
            contents.append({
                "role": gemini_role,
                "parts": parts,
            })

        return contents

    @staticmethod
    def _map_role(openai_role):
        """映射角色"""
        if openai_role in ("assistant", "system"):
            return "model"
        elif openai_role == "tool":
            return "tool"
        else:
            return "user"

    @staticmethod
    def _tools_to_gemini(tools):
        """将 OpenAI tools 转换为 Gemini functionDeclarations"""
        declarations = []
        for tool in tools:
            fn = tool.get("function", {})
            declarations.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return [{"functionDeclarations": declarations}]

    @staticmethod
    def _build_tool_config(tools):
        """构建 Gemini toolConfig"""
        return {
            "functionCallingConfig": {
                "mode": "AUTO",
            }
        }

    # ================================================================
    # 格式转换: Gemini → OpenAI
    # ================================================================

    def _response_to_openai(self, gemini_response):
        """将 Gemini 响应转换为 OpenAI 格式的 message"""
        try:
            candidate = gemini_response.get("candidates", [{}])[0]
            gemini_content = candidate.get("content", {})
            parts = gemini_content.get("parts", [])

            openai_content = ""
            tool_calls = []

            for part in parts:
                if "text" in part:
                    openai_content += part["text"]
                elif "functionCall" in part:
                    fn = part["functionCall"]
                    args = fn.get("args", {})
                    if isinstance(args, dict):
                        args = json.dumps(args, ensure_ascii=False)
                    tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "type": "function",
                        "function": {
                            "name": fn.get("name", ""),
                            "arguments": args,
                        }
                    })

            # 检查 finish_reason
            finish_reason = candidate.get("finishReason", "STOP")
            if finish_reason == "STOP" and not openai_content and not tool_calls:
                openai_content = "（模型未生成内容）"

            return {
                "role": "assistant",
                "content": openai_content or None,
                "tool_calls": tool_calls if tool_calls else None,
            }

        except Exception as e:
            print(f"  [LLM:Gemini] 响应转换异常: {str(e)}")
            return {
                "role": "assistant",
                "content": f"Gemini 响应解析失败: {str(e)}",
            }
