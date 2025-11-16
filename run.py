import os
import sys
import logging
from app import create_app
from app.exceptions import register_error_handlers

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('codediff.log')
    ]
)

logger = logging.getLogger(__name__)

# 设置环境变量
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_APP', 'run.py')

app = create_app(os.getenv('FLASK_ENV'))

if __name__ == '__main__':
    # 从环境变量获取配置
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    # 检查 Firejail
    try:
        import shutil
        if shutil.which('firejail'):
            logger.info('Firejail detected - sandbox mode enabled')
        else:
            logger.warning('Firejail not found - running in UNSAFE mode')
            logger.warning('Install firejail: sudo apt-get install firejail')
    except Exception as e:
        logger.error(f'Firejail check failed: {str(e)}')
    
    # 启动应用
    logger.info(f'Starting CodeDiff backend in {os.getenv("FLASK_ENV")} mode')
    logger.info(f'Listening on {host}:{port}')
    
    app.run(host=host, port=port, debug=debug, threaded=True)
