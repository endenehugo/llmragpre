from enum import Enum


class HttpCode(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    VERIFIED_ERROR = "verified_error"
