from app import app
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=True)
