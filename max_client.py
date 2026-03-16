import requests
import logging
from typing import Optional, Dict, Any, List
from config import MAX_API_BASE

logger = logging.getLogger(__name__)

class MaxBotClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = MAX_API_BASE
        self.session = requests.Session()
        self.session.headers.update({"Authorization": token})

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_me(self) -> Dict[str, Any]:
        return self._request("GET", "/me")

    def get_updates(self, marker: Optional[int] = None, timeout: int = 30, limit: int = 100) -> Dict[str, Any]:
        params = {"timeout": timeout, "limit": limit}
        if marker:
            params["marker"] = marker
        return self._request("GET", "/updates", params=params)

    def send_action(self, chat_id: int, action: str) -> bool:
        path = f"/chats/{chat_id}/actions"
        resp = self._request("POST", path, json={"action": action})
        return resp.get("success", False)

    def upload_file(self, file_path: str, file_type: str) -> Optional[str]:
        # В навигаторе не используется, но оставим для совместимости
        return None

    def build_attachment(self, file_type: str, token: str) -> Dict:
        return {"type": file_type, "payload": {"token": token}}

    def send_message(self, user_id, text, attachments=None, format=None):
        params = {"user_id": user_id, "disable_link_preview": "false"}
        payload = {"text": text, "attachments": attachments or []}
        if format:
            payload["format"] = format
        logger.info(f"Sending message to {user_id}: text={text}, attachments={attachments}")
        try:
            result = self._request("POST", "/messages", params=params, json=payload)
            logger.info(f"Message sent, result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            raise
