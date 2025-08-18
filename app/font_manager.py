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
    
    @staticmethod
    def get_fonts_dir():
        """获取字体目录路径"""
        return os.path.join(current_app.root_path, 'app', 'static', 'fonts')
    
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
        
        # 尝试多个可靠的字体下载源
        font_urls = [
            # GitHub官方仓库（主分支）
            'https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans-Bold.ttf',
            # 备用GitHub链接
            'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf',
            # SourceForge镜像
            'https://sourceforge.net/projects/dejavu/files/dejavu/2.37/dejavu-fonts-ttf-2.37.tar.bz2/download',
            # Google Fonts API（Liberation Sans作为备选）
            'https://fonts.gstatic.com/s/liberationsans/v15/LiberationSans-Bold.ttf'
        ]
        
        # 尝试从多个源下载字体
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
                
                with urllib.request.urlopen(request, timeout=30) as response:
                    with open(font_path, 'wb') as f:
                        f.write(response.read())
                
                # 验证下载的文件大小
                file_size = os.path.getsize(font_path)
                if file_size > 50000:  # 至少50KB
                    current_app.logger.info(f"✅ 字体文件下载成功: {font_path} ({file_size:,} bytes)")
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
        return None
    
    @staticmethod
    def get_captcha_font(font_size=28):
        """
        获取验证码字体
        
        参数:
            font_size: 字体大小
            
        返回:
            PIL ImageFont 对象
        """
        fonts_dir = FontManager.get_fonts_dir()
        
        # 字体候选列表 - 按优先级排序
        font_candidates = [
            # 1. 项目内置字体（最高优先级）
            os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf'),
            os.path.join(fonts_dir, 'DejaVuSans.ttf'),
            os.path.join(fonts_dir, 'arial.ttf'),
            
            # 2. 系统字体路径
            "arial.ttf",                    # Windows
            "Arial.ttf",                    # macOS
            "DejaVuSans-Bold.ttf",         # Linux
            "calibri.ttf",                  # Windows备选
            "Helvetica.ttc",               # macOS备选
            "/System/Library/Fonts/Arial.ttf",  # macOS系统路径
            "C:/Windows/Fonts/arial.ttf",  # Windows系统路径
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Ubuntu/Debian
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",  # Arch Linux
        ]
        
        font = None
        loaded_font_path = None
        
        # 尝试加载字体
        attempted_fonts = []
        for font_path in font_candidates:
            if not font_path:  # 跳过空路径
                continue
                
            attempted_fonts.append(font_path)
            try:
                font = ImageFont.truetype(font_path, font_size)
                loaded_font_path = font_path
                CaptchaLogger.log_font_loading(font_path, font_size, success=True)
                current_app.logger.info(f"✅ 成功加载字体: {font_path} (大小: {font_size})")
                break
            except (OSError, IOError) as e:
                CaptchaLogger.log_font_loading(font_path, font_size, success=False, error=str(e))
                current_app.logger.debug(f"字体加载失败: {font_path} - {e}")
                continue
        
        # 如果所有字体都加载失败，尝试下载默认字体
        if font is None:
            current_app.logger.warning("所有预设字体加载失败，尝试下载默认字体...")
            default_font_path = FontManager.download_default_font()
            
            if default_font_path:
                try:
                    font = ImageFont.truetype(default_font_path, font_size)
                    loaded_font_path = default_font_path
                    current_app.logger.info(f"✅ 成功加载下载的字体: {default_font_path}")
                except Exception as e:
                    current_app.logger.error(f"下载的字体也无法加载: {e}")
        
        # 最后的备选方案：使用默认字体但记录警告
        if font is None:
            current_app.logger.error("❌ 所有字体加载失败，使用系统默认字体（可能很小）")
            font = ImageFont.load_default()
            loaded_font_path = "系统默认字体"
            CaptchaLogger.log_font_fallback(attempted_fonts, loaded_font_path)
            
            # 检查默认字体是否过小
            try:
                test_image = Image.new('RGB', (100, 50), color=(255, 255, 255))
                test_draw = ImageDraw.Draw(test_image)
                bbox = test_draw.textbbox((0, 0), "TEST", font=font)
                text_height = bbox[3] - bbox[1]
                
                if text_height < 15:  # 如果字体高度小于15像素，标记为需要嵌入式字体
                    current_app.logger.warning(f"默认字体过小 (高度: {text_height}px)，建议使用嵌入式字体")
                    font._is_too_small = True
                    
            except Exception:
                # 如果测试失败，也标记为需要嵌入式字体
                font._is_too_small = True
        
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
