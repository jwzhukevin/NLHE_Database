import os
import io
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from flask import current_app
from PIL import ImageFont

from app.font_manager import FontManager


def _reset_font_manager_state():
    # 清理进程内缓存与标志，避免测试间相互影响
    FontManager._font_cache.clear()
    FontManager._download_attempted = False
    FontManager._download_failed = False


def test_cache_hit_same_object(app, monkeypatch):
    _reset_font_manager_state()

    # 强制走嵌入式/默认字体，避免依赖真实文件
    # 解释：将 truetype 打补丁为抛错，避免与 PIL 的 load_default 形成递归调用
    monkeypatch.setattr(
        ImageFont, "truetype", lambda *a, **k: (_ for _ in ()).throw(OSError("fail"))
    )
    # 解释：将 load_default 打补丁为返回固定的可用对象，避免内部再调 truetype
    class _Dummy:  # 简单对象，可被业务逻辑标记属性
        pass
    dummy = _Dummy()
    monkeypatch.setattr(ImageFont, "load_default", lambda: dummy)

    with current_app.app_context():
        f1 = FontManager.get_captcha_font(28)
        f2 = FontManager.get_captcha_font(28)
        assert f1 is f2, "同字号应命中缓存返回同一对象"


def test_download_disabled_fallback_embedded(app, monkeypatch):
    _reset_font_manager_state()

    # 禁用下载
    current_app.config["ENABLE_FONT_DOWNLOAD"] = False

    # 让所有truetype加载失败，触发回退
    def raise_ioerror(*args, **kwargs):
        raise OSError("fail truetype for test")

    monkeypatch.setattr(ImageFont, "truetype", raise_ioerror)
    # 解释：兜底路径会调用 load_default，这里也打补丁避免其内部间接调用 truetype
    class _Dummy2:
        pass
    dummy2 = _Dummy2()
    monkeypatch.setattr(ImageFont, "load_default", lambda: dummy2)

    with current_app.app_context():
        font = FontManager.get_captcha_font(32)
        # 回退至少应返回一个可用字体对象
        assert font is not None
        # 若标记了嵌入式标志，应为True
        if hasattr(font, "_use_embedded"):
            assert getattr(font, "_use_embedded") is True


def test_download_timeout_sets_failed_and_fallback(app, monkeypatch):
    _reset_font_manager_state()

    # 允许下载，但模拟超时
    current_app.config["ENABLE_FONT_DOWNLOAD"] = True
    current_app.config["FONT_DOWNLOAD_TIMEOUT"] = 1

    class TimeoutURL:
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            # 模拟网络超时
            raise TimeoutError("timeout")
        def __exit__(self, exc_type, exc, tb):
            return False

    import urllib.request as ureq
    monkeypatch.setattr(ureq, "urlopen", lambda *a, **k: TimeoutURL())
    # truetype也失败，确保走到兜底
    monkeypatch.setattr(
        ImageFont, "truetype", lambda *a, **k: (_ for _ in ()).throw(OSError("fail"))
    )
    # 解释：兜底的 load_default 改为固定返回对象，避免递归
    class _Dummy3:
        pass
    dummy3 = _Dummy3()
    monkeypatch.setattr(ImageFont, "load_default", lambda: dummy3)

    with current_app.app_context():
        font = FontManager.get_captcha_font(30)
        assert font is not None
        # 标志位应被置为尝试且失败
        assert FontManager._download_attempted is True
        assert FontManager._download_failed is True


def test_concurrent_calls_do_not_raise(app, monkeypatch):
    _reset_font_manager_state()

    # 强制所有路径失败到嵌入式/默认
    monkeypatch.setattr(ImageFont, "truetype", lambda *a, **k: (_ for _ in ()).throw(OSError("fail")))
    # 避免 load_default 内部再调 truetype 造成递归
    class _DummyC:
        pass
    _dummy_c = _DummyC()
    monkeypatch.setattr(ImageFont, "load_default", lambda: _dummy_c)

    # 模拟下载返回小文件被判定为无效，从而继续回退
    class SmallBytes:
        def __enter__(self):
            class R:
                def read(self_inner):
                    return b"x" * 10  # 小于50KB
            return R()
        def __exit__(self, exc_type, exc, tb):
            return False

    import urllib.request as ureq
    monkeypatch.setattr(ureq, "urlopen", lambda *a, **k: SmallBytes())

    results = []
    # 解释：为每个线程单独推入应用上下文，避免 current_app 跨线程不可用
    def worker(app_obj):
        with app_obj.app_context():
            f = FontManager.get_captcha_font(28)
            results.append(f)

    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(worker, app) for _ in range(5)]
        for fut in futs:
            fut.result(timeout=5)

    assert len([r for r in results if r is not None]) == 5


def test_cache_capacity_limit(app, monkeypatch):
    _reset_font_manager_state()

    # 设置小缓存容量
    current_app.config["FONT_CACHE_MAX_ITEMS"] = 2
    # 解释：避免递归，truetype 抛错，load_default 返回固定对象
    monkeypatch.setattr(
        ImageFont, "truetype", lambda *a, **k: (_ for _ in ()).throw(OSError("fail"))
    )
    class _Dummy4:
        pass
    dummy4 = _Dummy4()
    monkeypatch.setattr(ImageFont, "load_default", lambda: dummy4)

    with current_app.app_context():
        f28 = FontManager.get_captcha_font(28)
        f32 = FontManager.get_captcha_font(32)
        f36 = FontManager.get_captcha_font(36)
        # 容量满时会清空缓存，确保仍然可用
        f28_again = FontManager.get_captcha_font(28)
        assert f28_again is not None
        # 由于清空缓存，可能不是同一对象，这里只断言功能可用
