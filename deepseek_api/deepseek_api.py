
import asyncio
import json
import os
from typing import AsyncGenerator, Dict, Optional, Union

import aiofiles
import httpx
from aiohttp import ClientSession

from .utils import (AsyncClient, get_auth_token, get_cookies, get_headers,
                    get_session_id, process_stream_response, raise_for_status)


class AsyncDeepseekAPI:
    def __init__(
        self, 
        email: Optional[str] = None, 
        password: Optional[str] = None, 
        proxies: Optional[Dict] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = "https://chat.deepseek.com",
    ) -> None:
        self.email = email
        self.password = password
        self.proxies = proxies
        self.api_key = api_key
        self.base_url = base_url
        self.headers = get_headers()
        self.credentials_path = os.path.join(os.path.expanduser("~"), ".deepseek_credentials.json")
        self.chat_headers = None
        self.chat_history = []
        self.client = AsyncClient(proxies=self.proxies)

    async def __aenter__(self) -> "AsyncDeepseekAPI":
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def login(self) -> None:
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            return

        if os.path.exists(self.credentials_path):
            try:
                async with aiofiles.open(self.credentials_path, "r") as f:
                    content = await f.read()
                    self.credentials = json.loads(content)
                    self.headers["Cookie"] = self.credentials.get("cookie")
                    return
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading credentials: {e}")
                pass

        if not self.email or not self.password:
            raise ValueError("Email and password are required for login.")

        self.session_id = await get_session_id(self.client)
        self.headers["Cookie"] = f"session-id={self.session_id}"
        self.auth_token = await get_auth_token(
            self.client, self.email, self.password, self.session_id
        )
        self.headers["Authorization"] = f"Bearer {self.auth_token}"
        self.cookie = await get_cookies(self.client, self.auth_token)
        self.headers["Cookie"] = self.cookie
        self.credentials = {
            "session_id": self.session_id,
            "auth_token": self.auth_token,
            "cookie": self.cookie,
        }
        async with aiofiles.open(self.credentials_path, "w") as f:
            await f.write(json.dumps(self.credentials))

    async def get_models(self) -> Dict:
        url = f"{self.base_url}/api/models"
        async with ClientSession(headers=self.headers) as session:
            async with session.get(url, proxy=self.proxies.get("https") if self.proxies else None) as response:
                await raise_for_status(response)
                return await response.json()

    async def send_message(
        self, 
        message: str, 
        model: str = "deepseek-chat", 
        stream: bool = False,
        **kwargs
    ) -> Union[Dict, AsyncGenerator[Dict, None]]:
        if not self.chat_headers:
            self.chat_headers = self.headers.copy()
            self.chat_headers["Accept"] = "text/event-stream"
            self.chat_headers["Content-Type"] = "application/json"

        payload = {
            "message": message,
            "stream": stream,
            "model_class": "deepseek_chat" if model == "deepseek-chat" else "deepseek_code",
            "chat_history": self.chat_history,
            **kwargs
        }
        url = f"{self.base_url}/api/chat/send"
        async with self.client.stream("POST", url, headers=self.chat_headers, json=payload) as response:
            await raise_for_status(response)
            if stream:
                return process_stream_response(response)
            else:
                response_json = await response.json()
                self.chat_history.append({"role": "user", "content": message})
                self.chat_history.append({"role": "assistant", "content": response_json["choices"][0]["message"]["content"]})
                return response_json


class SyncDeepseekAPI:
    def __init__(
        self, 
        email: Optional[str] = None, 
        password: Optional[str] = None, 
        proxies: Optional[Dict] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = "https://chat.deepseek.com",
    ) -> None:
        self.email = email
        self.password = password
        self.proxies = proxies
        self.api_key = api_key
        self.base_url = base_url
        self.headers = get_headers()
        self.credentials_path = os.path.join(os.path.expanduser("~"), ".deepseek_credentials.json")
        self.chat_headers = None
        self.chat_history = []
        self.client = httpx.Client(proxies=self.proxies)

    def __enter__(self) -> "SyncDeepseekAPI":
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def login(self) -> None:
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
            return

        if os.path.exists(self.credentials_path):
            try:
                with open(self.credentials_path, "r") as f:
                    content = f.read()
                    self.credentials = json.loads(content)
                    self.headers["Cookie"] = self.credentials.get("cookie")
                    return
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading credentials: {e}")
                pass

        if not self.email or not self.password:
            raise ValueError("Email and password are required for login.")

        self.session_id = get_session_id(self.client)
        self.headers["Cookie"] = f"session-id={self.session_id}"
        self.auth_token = get_auth_token(
            self.client, self.email, self.password, self.session_id
        )
        self.headers["Authorization"] = f"Bearer {self.auth_token}"
        self.cookie = get_cookies(self.client, self.auth_token)
        self.headers["Cookie"] = self.cookie
        self.credentials = {
            "session_id": self.session_id,
            "auth_token": self.auth_token,
            "cookie": self.cookie,
        }
        with open(self.credentials_path, "w") as f:
            f.write(json.dumps(self.credentials))

    def get_models(self) -> Dict:
        url = f"{self.base_url}/api/models"
        response = self.client.get(url, headers=self.headers)
        raise_for_status(response)
        return response.json()

    def send_message(
        self, 
        message: str, 
        model: str = "deepseek-chat", 
        stream: bool = False,
        **kwargs
    ) -> Union[Dict, AsyncGenerator[Dict, None]]:
        if not self.chat_headers:
            self.chat_headers = self.headers.copy()
            self.chat_headers["Accept"] = "text/event-stream"
            self.chat_headers["Content-Type"] = "application/json"

        payload = {
            "message": message,
            "stream": stream,
            "model_class": "deepseek_chat" if model == "deepseek-chat" else "deepseek_code",
            "chat_history": self.chat_history,
            **kwargs
        }
        url = f"{self.base_url}/api/chat/send"
        with self.client.stream("POST", url, headers=self.chat_headers, json=payload) as response:
            raise_for_status(response)
            if stream:
                return process_stream_response(response)
            else:
                response_json = response.json()
                self.chat_history.append({"role": "user", "content": message})
                self.chat_history.append({"role": "assistant", "content": response_json["choices"][0]["message"]["content"]})
                return response_json
