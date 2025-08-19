import os
import sys
import pytest

# 说明：确保项目根目录加入 sys.path，避免 `ModuleNotFoundError: No module named 'app'`
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app

@pytest.fixture(scope="function")
def app():
    app = create_app()
    # 覆盖测试配置
    app.config.update({
        "TESTING": True,
        # 使用临时目录避免污染真实字体目录
        "FONT_DIR": os.path.join(app.root_path, "static", "_test_fonts"),
        "ENABLE_FONT_DOWNLOAD": True,
        "FONT_PRELOAD_SIZES": [],  # 测试禁用预热，避免线程干扰
        "FONT_DOWNLOAD_TIMEOUT": 1,
        "FONT_CACHE_MAX_ITEMS": 2,
        "CAPTCHA_FONT_SOURCES": [
            # 由测试用例 monkeypatch urlopen 行为，不真正访问网络
            "https://example.com/fonts/DejaVuSans-Bold.ttf"
        ],
    })
    # 确保测试字体目录存在
    os.makedirs(app.config["FONT_DIR"], exist_ok=True)
    with app.app_context():
        yield app
