import os
import json

class ResourceUtils:
    _RESOURCE_PATH = None
    @classmethod
    def init_app(cls,app):
        cls._RESOURCE_PATH = os.path.abspath(os.path.join(app.root_path, '..', 'resources'))

    @classmethod
    def get_resource_path(cls, filename):
        if cls._RESOURCE_PATH is None:
            raise RuntimeError("ResourceUtils is not initialized. Call init_app() first.")
        return os.path.join(cls._RESOURCE_PATH, filename)

    @classmethod
    def ensure_resource_dir(cls, dirname):
        path = cls.get_resource_path(dirname)
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def load_json_resource(cls, filename):
        with open(cls.get_resource_path(filename), 'r', encoding='utf-8') as f:
            return json.load(f)

    @classmethod
    def load_text_resource(cls, filename):
        with open(cls.get_resource_path(filename), 'r', encoding='utf-8') as f:
            return f.readlines()
