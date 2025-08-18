#!/usr/bin/env python3
"""
验证码日志记录模块
专门用于监控验证码生成和字体加载状态
"""
import logging
import os
from datetime import datetime
from flask import current_app

class CaptchaLogger:
    """验证码日志记录器"""
    
    @staticmethod
    def setup_captcha_logger():
        """设置验证码专用日志记录器"""
        logger = logging.getLogger('captcha')
        logger.setLevel(logging.INFO)
        
        # 避免重复添加处理器
        if logger.handlers:
            return logger
        
        # 创建日志目录
        log_dir = os.path.join(current_app.root_path, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建文件处理器
        log_file = os.path.join(log_dir, 'captcha.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    @staticmethod
    def log_font_loading(font_path, font_size, success=True, error=None):
        """记录字体加载状态"""
        try:
            logger = CaptchaLogger.setup_captcha_logger()
            
            if success:
                logger.info(f"字体加载成功: {font_path} (大小: {font_size}px)")
            else:
                logger.warning(f"字体加载失败: {font_path} - {error}")
                
        except Exception as e:
            # 如果日志记录失败，使用Flask的日志系统
            current_app.logger.error(f"验证码日志记录失败: {e}")
    
    @staticmethod
    def log_captcha_generation(text_length, image_size, generation_time=None, success=True, error=None):
        """记录验证码生成状态"""
        try:
            logger = CaptchaLogger.setup_captcha_logger()
            
            if success:
                msg = f"验证码生成成功: 长度={text_length}, 尺寸={image_size}"
                if generation_time:
                    msg += f", 耗时={generation_time:.3f}s"
                logger.info(msg)
            else:
                logger.error(f"验证码生成失败: {error}")
                
        except Exception as e:
            current_app.logger.error(f"验证码日志记录失败: {e}")
    
    @staticmethod
    def log_font_fallback(attempted_fonts, final_font):
        """记录字体回退情况"""
        try:
            logger = CaptchaLogger.setup_captcha_logger()
            
            logger.warning(f"字体回退: 尝试了 {len(attempted_fonts)} 个字体，最终使用: {final_font}")
            logger.info(f"尝试的字体列表: {', '.join(attempted_fonts)}")
            
        except Exception as e:
            current_app.logger.error(f"验证码日志记录失败: {e}")
    
    @staticmethod
    def log_performance_metrics(metrics):
        """记录性能指标"""
        try:
            logger = CaptchaLogger.setup_captcha_logger()
            
            logger.info(f"验证码性能指标: {metrics}")
            
        except Exception as e:
            current_app.logger.error(f"验证码日志记录失败: {e}")
