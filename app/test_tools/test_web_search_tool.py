import os
import sys


def main() -> int:
    if not os.environ.get("FLASK_ENV"):
        os.environ["FLASK_ENV"] = "dev"

    import app  # noqa: F401  # 触发项目配置加载与环境变量注入
    from app.tools.web_search import WebSearchTool

    query = " ".join(sys.argv[1:]).strip() or "Python 3.11 的新特性有哪些？简洁回答"

    print(f"FLASK_ENV: {os.environ.get('FLASK_ENV')}")
    print(f"METASO_API_KEY 已配置: {bool(os.environ.get('METASO_API_KEY'))}")
    print(f"开始测试 web_search_tool，query: {query}\n")

    tool = WebSearchTool()
    result = tool.invoke({"query": query})

    print("工具返回结果:")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())