from injector import inject
from dataclasses import dataclass
from flask import Flask
import logging
from flask import request
from app.response import success_message
logger = logging.getLogger(__name__)

@inject
@dataclass
class TestHandler:

    def test(self):
        user_name = request.args.get("user_name", default="None", type=str)
        return success_message(f" 你好啊 {user_name}！")
