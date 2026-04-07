from dataclasses import dataclass, field, asdict
from typing import Any
from flask import jsonify
from .http_code import HttpCode


@dataclass
class Response:
    code: HttpCode = HttpCode.SUCCESS
    message: str = ''
    data: Any = field(default_factory=dict)
    
    def to_dict(self):
        """转换为字典，确保所有字段都可序列化"""
        return {
            'code': self.code.value if isinstance(self.code, HttpCode) else self.code,
            'message': self.message,
            'data': self.data
        }


def json(data: Response = None):
    if data is None:
        return jsonify({}), 200
    # 使用 to_dict 方法确保正确序列化
    if isinstance(data, Response):
        response_dict = data.to_dict()
    else:
        response_dict = data
    return jsonify(response_dict), 200


def success_json(data:Any=None):
    return json(Response(code=HttpCode.SUCCESS,message='',data=data))


def fail_json(data:Any=None):
    return json(Response(code=HttpCode.FAIL,message='',data=data))

def validate_error_json(errors:dict=None):
    first_key = next(iter(errors))
    if first_key is not None:
        msg = errors.get(first_key)[0]
    else:
        msg = ''
    return json(Response(code=HttpCode.VERIFIED_ERROR,message=msg,data=errors))


def message(code: HttpCode,msg:str=''):
    return json(Response(code=code,message=msg,data={}))


def success_message(msg:str=''):
    return json(Response(code=HttpCode.SUCCESS,message=msg))

def fail_message(msg:str=''):
    return json(Response(code=HttpCode.FAIL,message=msg))

def not_found_message(msg:str=''):
    return json(Response(code=HttpCode.NOT_FOUND,message=msg))

def unauthorized_message(msg:str=''):
    return json(Response(code=HttpCode.UNAUTHORIZED,message=msg))

def forbidden_message(msg:str=''):
    return json(Response(code=HttpCode.FORBIDDEN,message=msg))
