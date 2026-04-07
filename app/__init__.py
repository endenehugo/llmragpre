from flask import Flask
from flask_cors import CORS
from injector import Injector
import os
from app.router import Router
from app.module import ExtensionModule
from app.utils import ResourceUtils
injector = Injector([ExtensionModule])

app = Flask(__name__)

# 启用 CORS，允许所有来源访问
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

env = os.environ.get("FLASK_ENV", "dev")
allowed_envs = ["dev", "test", "pre","prod"]
if env not in allowed_envs:
    raise ValueError(f"无效的FLASK_ENV值: '{env}'. 允许的值为: {', '.join(allowed_envs)}.")

app.config.from_object(f"config.config_{env}")

os.environ['DASHSCOPE_API_KEY'] = app.config['DASHSCOPE_API_KEY']

ResourceUtils.init_app(app)
injector.get(Router).register_router(app)