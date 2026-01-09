"""Kiro Provider"""
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple

from .base import BaseProvider
from ..credential import (
    KiroCredentials, TokenRefresher,
    generate_machine_id, get_kiro_version, get_system_info
)


class KiroProvider(BaseProvider):
    """Kiro/CodeWhisperer Provider"""
    
    API_URL = "https://q.us-east-1.amazonaws.com/generateAssistantResponse"
    MODELS_URL = "https://q.us-east-1.amazonaws.com/ListAvailableModels"
    
    def __init__(self, credentials: Optional[KiroCredentials] = None):
        self.credentials = credentials
        self._machine_id: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "kiro"
    
    @property
    def api_url(self) -> str:
        return self.API_URL
    
    def get_machine_id(self) -> str:
        """获取基于凭证的 Machine ID"""
        if self._machine_id:
            return self._machine_id
        
        if self.credentials:
            self._machine_id = generate_machine_id(
                self.credentials.profile_arn,
                self.credentials.client_id
            )
        else:
            self._machine_id = generate_machine_id()
        
        return self._machine_id
    
    def build_headers(
        self, 
        token: str, 
        agent_mode: str = "vibe",
        **kwargs
    ) -> Dict[str, str]:
        """构建 Kiro API 请求头 (与 kiro.rs 保持一致)"""
        machine_id = kwargs.get("machine_id") or self.get_machine_id()
        kiro_version = get_kiro_version()
        os_name, node_version = get_system_info()
        
        return {
            "content-type": "application/json",
            "x-amzn-codewhisperer-optout": "true",
            "x-amzn-kiro-agent-mode": agent_mode,
            "x-amz-user-agent": f"aws-sdk-js/1.0.27 KiroIDE-{kiro_version}-{machine_id}",
            "user-agent": f"aws-sdk-js/1.0.27 ua/2.1 os/{os_name} lang/js md/nodejs#{node_version} api/codewhispererstreaming#1.0.27 m/E KiroIDE-{kiro_version}-{machine_id}",
            "amz-sdk-invocation-id": str(uuid.uuid4()),
            "amz-sdk-request": "attempt=1; max=3",
            "Authorization": f"Bearer {token}",
            "Connection": "close",
        }
    
    def build_request(
        self,
        messages: list = None,
        model: str = "claude-sonnet-4",
        user_content: str = "",
        history: List[dict] = None,
        tools: List[dict] = None,
        images: List[dict] = None,
        tool_results: List[dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """构建 Kiro API 请求体"""
        conversation_id = str(uuid.uuid4())
        
        # 确保 content 不为空
        if not user_content:
            user_content = "Continue"
        
        user_input_message = {
            "content": user_content,
            "modelId": model,
            "origin": "AI_EDITOR",
        }
        
        if images:
            user_input_message["images"] = images
        
        # 只有在有 tools 或 tool_results 时才添加 userInputMessageContext
        context = {}
        if tools:
            context["tools"] = tools
        if tool_results:
            context["toolResults"] = tool_results
        
        if context:
            user_input_message["userInputMessageContext"] = context
        
        return {
            "conversationState": {
                "agentContinuationId": str(uuid.uuid4()),
                "agentTaskType": "vibe",
                "chatTriggerType": "MANUAL",
                "conversationId": conversation_id,
                "currentMessage": {"userInputMessage": user_input_message},
                "history": history or []
            }
        }
    
    def parse_response(self, raw: bytes) -> Dict[str, Any]:
        """解析 AWS event-stream 格式响应"""
        result = {
            "content": [],
            "tool_uses": [],
            "stop_reason": "end_turn"
        }
        
        tool_input_buffer = {}
        pos = 0
        
        while pos < len(raw):
            if pos + 12 > len(raw):
                break
            
            total_len = int.from_bytes(raw[pos:pos+4], 'big')
            headers_len = int.from_bytes(raw[pos+4:pos+8], 'big')
            
            if total_len == 0 or total_len > len(raw) - pos:
                break
            
            header_start = pos + 12
            header_end = header_start + headers_len
            headers_data = raw[header_start:header_end]
            event_type = None
            
            try:
                headers_str = headers_data.decode('utf-8', errors='ignore')
                if 'toolUseEvent' in headers_str:
                    event_type = 'toolUseEvent'
                elif 'assistantResponseEvent' in headers_str:
                    event_type = 'assistantResponseEvent'
            except:
                pass
            
            payload_start = pos + 12 + headers_len
            payload_end = pos + total_len - 4
            
            if payload_start < payload_end:
                try:
                    payload = json.loads(raw[payload_start:payload_end].decode('utf-8'))
                    
                    if 'assistantResponseEvent' in payload:
                        e = payload['assistantResponseEvent']
                        if 'content' in e:
                            result["content"].append(e['content'])
                    elif 'content' in payload and event_type != 'toolUseEvent':
                        result["content"].append(payload['content'])
                    
                    if event_type == 'toolUseEvent' or 'toolUseId' in payload:
                        tool_id = payload.get('toolUseId', '')
                        tool_name = payload.get('name', '')
                        tool_input = payload.get('input', '')
                        
                        if tool_id:
                            if tool_id not in tool_input_buffer:
                                tool_input_buffer[tool_id] = {
                                    "id": tool_id,
                                    "name": tool_name,
                                    "input_parts": []
                                }
                            if tool_name and not tool_input_buffer[tool_id]["name"]:
                                tool_input_buffer[tool_id]["name"] = tool_name
                            if tool_input:
                                tool_input_buffer[tool_id]["input_parts"].append(tool_input)
                except:
                    pass
            
            pos += total_len
        
        # 组装工具调用
        for tool_id, tool_data in tool_input_buffer.items():
            input_str = "".join(tool_data["input_parts"])
            try:
                input_json = json.loads(input_str)
            except:
                input_json = {"raw": input_str}
            
            result["tool_uses"].append({
                "type": "tool_use",
                "id": tool_data["id"],
                "name": tool_data["name"],
                "input": input_json
            })
        
        if result["tool_uses"]:
            result["stop_reason"] = "tool_use"
        
        return result
    
    def parse_response_text(self, raw: bytes) -> str:
        """解析响应，只返回文本内容"""
        result = self.parse_response(raw)
        return "".join(result["content"]) or "[No response]"
    
    async def refresh_token(self) -> Tuple[bool, str]:
        """刷新 token"""
        if not self.credentials:
            return False, "无凭证信息"
        
        refresher = TokenRefresher(self.credentials)
        return await refresher.refresh()
    
    def is_quota_exceeded(self, status_code: int, error_text: str) -> bool:
        """检查是否为配额超限错误"""
        if status_code in {429, 503, 529}:
            return True
        
        keywords = ["rate limit", "quota", "too many requests", "throttl"]
        error_lower = error_text.lower()
        return any(kw in error_lower for kw in keywords)
