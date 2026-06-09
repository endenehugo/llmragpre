from app import app
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    from app.utils.api_key_checker import check_all
    report = check_all()
    print(report.format_text())
    if not report.all_passed:
        print("[警告] API Key 检测未通过，请先配置有效的 DASHSCOPE_API_KEY。")
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=True)
