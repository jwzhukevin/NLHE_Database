#!/usr/bin/env python3
"""
字体管理模块 - 处理验证码字体加载和管理
"""
import os
import urllib.request
from flask import current_app
from PIL import ImageFont
import tempfile
from .captcha_logger import CaptchaLogger
from .embedded_font import EmbeddedFont
import time

class FontManager:
    """字体管理器"""
    
    # 字体缓存
    _font_cache = {}
    _download_attempted = False
    _download_failed = False
    
    @staticmethod
    def get_fonts_dir():
        """获取字体目录路径"""
        cfg_dir = current_app.config.get('FONT_DIR')
        if cfg_dir:
            return cfg_dir
        return os.path.join(current_app.root_path, 'static', 'fonts')
    
    @staticmethod
    def ensure_fonts_dir():
        """确保字体目录存在"""
        fonts_dir = FontManager.get_fonts_dir()
        os.makedirs(fonts_dir, exist_ok=True)
        return fonts_dir
    
    @staticmethod
    def download_default_font():
        """下载默认字体文件"""
        fonts_dir = FontManager.ensure_fonts_dir()
        font_path = os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf')
        
        if os.path.exists(font_path):
            current_app.logger.info(f"字体文件已存在: {font_path}")
            return font_path
        
        # 读取配置的下载源与开关
        if not current_app.config.get('ENABLE_FONT_DOWNLOAD', True):
            current_app.logger.info("字体下载被禁用，跳过下载步骤")
            return None

        # 尝试多个可靠的字体下载源（从配置读取）
        font_urls = current_app.config.get('CAPTCHA_FONT_SOURCES') or [
            'https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans-Bold.ttf',
            'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf',
            'https://fonts.gstatic.com/s/liberationsans/v15/LiberationSans-Bold.ttf'
        ]
        timeout = int(current_app.config.get('FONT_DOWNLOAD_TIMEOUT', 5))
        
        # 尝试从多个源下载字体（快速失败模式）
        for i, font_url in enumerate(font_urls):
            try:
                current_app.logger.info(f"正在从源 {i+1}/{len(font_urls)} 下载字体文件...")
                current_app.logger.info(f"下载URL: {font_url}")
                
                # 设置请求头，模拟浏览器访问
                request = urllib.request.Request(
                    font_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                
                # 使用配置的超时时间，避免阻塞
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    with open(font_path, 'wb') as f:
                        f.write(response.read())
                
                # 验证下载的文件大小
                file_size = os.path.getsize(font_path)
                if file_size > 50000:  # 至少50KB
                    current_app.logger.info(f"✅ 字体文件下载成功: {font_path} ({file_size:,} bytes)")
                    FontManager._download_attempted = True
                    return font_path
                else:
                    current_app.logger.warning(f"下载的文件过小: {file_size} bytes，尝试下一个源")
                    os.remove(font_path)
                    
            except Exception as e:
                current_app.logger.warning(f"从源 {i+1} 下载失败: {e}")
                if os.path.exists(font_path):
                    os.remove(font_path)
                continue
        
        current_app.logger.error(f"❌ 所有字体下载源都失败")
        FontManager._download_attempted = True
        FontManager._download_failed = True
        return None
    
    @staticmethod
    def get_captcha_font(font_size=28):
        """
        获取验证码字体（优化版本，避免请求阻塞）
        
        参数:
            font_size: 字体大小
            
        返回:
            PIL.ImageFont对象
        """
        start_time = time.time()
        
        # 检查字体缓存
        cache_key = f"font_{font_size}"
        if cache_key in FontManager._font_cache:
            current_app.logger.info(f"✅ 使用缓存字体: {cache_key}")
            return FontManager._font_cache[cache_key]
        
        # 记录字体加载开始
        CaptchaLogger.log_font_loading("开始加载", font_size, success=None)
        
        font = None
        loaded_font_path = None
        attempted_fonts = []
        
        # 预设字体路径列表（按优先级排序）
        font_paths = [
            # 项目字体目录
            os.path.join(FontManager.get_fonts_dir(), 'DejaVuSans-Bold.ttf'),
            os.path.join(FontManager.get_fonts_dir(), 'DejaVuSans.ttf'),
            os.path.join(FontManager.get_fonts_dir(), 'arial.ttf'),
            
            # 相对路径字体
            'arial.ttf',
            'Arial.ttf', 
            'DejaVuSans-Bold.ttf',
            'calibri.ttf',
            'Helvetica.ttc',
            
            # 系统字体路径
            '/System/Library/Fonts/Arial.ttf',  # macOS
            'C:/Windows/Fonts/arial.ttf',       # Windows
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',  # Ubuntu/Debian
            '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',  # Arch Linux
        ]
        
        # 尝试加载预设字体
        for font_path in font_paths:
            try:
                attempted_fonts.append(font_path)
                font = ImageFont.truetype(font_path, font_size)
                loaded_font_path = font_path
                current_app.logger.info(f"✅ 成功加载字体: {font_path}")
                break
            except Exception as e:
                CaptchaLogger.log_font_loading(font_path, font_size, success=False, error=str(e))
                continue
        
        # 如果所有预设字体都失败，且未尝试过下载，则快速尝试下载
        if font is None and not FontManager._download_attempted:
            current_app.logger.warning("所有预设字体加载失败，快速尝试下载默认字体...")
            try:
                # 设置较短的超时时间，避免阻塞
                default_font_path = FontManager.download_default_font()
                if default_font_path:
                    font = ImageFont.truetype(default_font_path, font_size)
                    loaded_font_path = default_font_path
                    current_app.logger.info(f"✅ 成功加载下载的字体: {default_font_path}")
            except Exception as e:
                current_app.logger.error(f"快速下载字体失败: {e}")
                FontManager._download_failed = True
        
        # 最后的备选方案：使用默认字体或嵌入式字体
        if font is None:
            current_app.logger.error("❌ 所有字体加载失败，使用备选方案")
            
            # 如果下载失败，直接使用嵌入式字体避免阻塞
            if FontManager._download_failed:
                current_app.logger.warning("⚡ 使用嵌入式字体避免请求阻塞")
                font = ImageFont.load_default()
                font._use_embedded = True
                loaded_font_path = "嵌入式字体"
            else:
                font = ImageFont.load_default()
                loaded_font_path = "系统默认字体"
                
                # 检查默认字体是否过小
                try:
                    from PIL import Image, ImageDraw
                    test_image = Image.new('RGB', (100, 50), color=(255, 255, 255))
                    test_draw = ImageDraw.Draw(test_image)
                    bbox = test_draw.textbbox((0, 0), "TEST", font=font)
                    text_height = bbox[3] - bbox[1]
                    
                    if text_height < 15:  # 如果字体高度小于15像素，标记为需要嵌入式字体
                        current_app.logger.warning(f"默认字体过小 (高度: {text_height}px)，使用嵌入式字体")
                        font._use_embedded = True
                        
                except Exception:
                    # 如果测试失败，也标记为需要嵌入式字体
                    font._use_embedded = True
            
            CaptchaLogger.log_font_fallback(attempted_fonts, loaded_font_path)
        
        # 缓存字体对象，避免重复加载（遵循简单容量限制）
        if font:
            max_items = int(current_app.config.get('FONT_CACHE_MAX_ITEMS', 32))
            if len(FontManager._font_cache) >= max_items:
                try:
                    # 简单策略：清空缓存以释放内存（避免引入复杂LRU依赖）
                    FontManager._font_cache.clear()
                    current_app.logger.info(f"字体缓存已达上限，执行清空：max_items={max_items}")
                except Exception:
                    pass
            FontManager._font_cache[cache_key] = font
        
        # 记录最终使用的字体
        current_app.logger.info(f"验证码使用字体: {loaded_font_path}")
        CaptchaLogger.log_font_loading(loaded_font_path, font_size, success=True)
        
        return font
    
    @staticmethod
    def test_font_rendering():
        """测试字体渲染效果"""
        start_time = time.time()
        try:
            font = FontManager.get_captcha_font(28)
            # 简单测试文本边界框
            from PIL import Image, ImageDraw
            
            test_image = Image.new('RGB', (200, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(test_image)
            
            test_text = "ABC123"
            try:
                bbox = draw.textbbox((0, 0), test_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                test_time = time.time() - start_time
                metrics = {
                    'text_size': f'{text_width}x{text_height}',
                    'test_time': f'{test_time:.3f}s',
                    'font_type': type(font).__name__
                }
                
                CaptchaLogger.log_performance_metrics(metrics)
                current_app.logger.info(f"字体测试成功 - 文本尺寸: {text_width}x{text_height}")
                return True
            except AttributeError:
                # 兼容旧版本Pillow
                current_app.logger.info("使用兼容模式测试字体")
                CaptchaLogger.log_performance_metrics({'mode': 'compatibility', 'test_time': f'{time.time() - start_time:.3f}s'})
                return True
                
        except Exception as e:
            current_app.logger.error(f"字体测试失败: {e}")
            CaptchaLogger.log_performance_metrics({'error': str(e), 'test_time': f'{time.time() - start_time:.3f}s'})
            return False
