#!/usr/bin/env python3
"""
嵌入式字体模块 - 提供基本的验证码字体支持
当外部字体文件不可用时，使用程序生成的简单字体
"""
from PIL import Image, ImageDraw, ImageFont
import io
import os

class EmbeddedFont:
    """嵌入式字体生成器"""
    
    @staticmethod
    def create_simple_font_image(text, font_size=32, width=140, height=50):
        """
        使用简单的像素字体绘制验证码
        当所有外部字体都不可用时的最后备选方案
        """
        # 创建图像
        image = Image.new('RGB', (width, height), color=(245, 248, 255))
        draw = ImageDraw.Draw(image)
        
        # 字符映射 - 简单的5x7像素字体
        char_patterns = {
            'A': [
                "  ██  ",
                " █  █ ",
                "█    █",
                "██████",
                "█    █",
                "█    █",
                "      "
            ],
            'B': [
                "█████ ",
                "█    █",
                "█████ ",
                "█████ ",
                "█    █",
                "█████ ",
                "      "
            ],
            'C': [
                " █████",
                "█     ",
                "█     ",
                "█     ",
                "█     ",
                " █████",
                "      "
            ],
            'D': [
                "█████ ",
                "█    █",
                "█    █",
                "█    █",
                "█    █",
                "█████ ",
                "      "
            ],
            'E': [
                "██████",
                "█     ",
                "█████ ",
                "█████ ",
                "█     ",
                "██████",
                "      "
            ],
            'F': [
                "██████",
                "█     ",
                "█████ ",
                "█████ ",
                "█     ",
                "█     ",
                "      "
            ],
            'G': [
                " █████",
                "█     ",
                "█  ███",
                "█    █",
                "█    █",
                " █████",
                "      "
            ],
            'H': [
                "█    █",
                "█    █",
                "██████",
                "██████",
                "█    █",
                "█    █",
                "      "
            ],
            'J': [
                "██████",
                "    █ ",
                "    █ ",
                "    █ ",
                "█   █ ",
                " ████ ",
                "      "
            ],
            'K': [
                "█   █ ",
                "█  █  ",
                "███   ",
                "███   ",
                "█  █  ",
                "█   █ ",
                "      "
            ],
            'L': [
                "█     ",
                "█     ",
                "█     ",
                "█     ",
                "█     ",
                "██████",
                "      "
            ],
            'M': [
                "█    █",
                "██  ██",
                "█ ██ █",
                "█    █",
                "█    █",
                "█    █",
                "      "
            ],
            'N': [
                "█    █",
                "██   █",
                "█ █  █",
                "█  █ █",
                "█   ██",
                "█    █",
                "      "
            ],
            'P': [
                "█████ ",
                "█    █",
                "█████ ",
                "█     ",
                "█     ",
                "█     ",
                "      "
            ],
            'Q': [
                " ████ ",
                "█    █",
                "█    █",
                "█  █ █",
                "█   ██",
                " █████",
                "      "
            ],
            'R': [
                "█████ ",
                "█    █",
                "█████ ",
                "█  █  ",
                "█   █ ",
                "█    █",
                "      "
            ],
            'S': [
                " █████",
                "█     ",
                " ████ ",
                "     █",
                "     █",
                "█████ ",
                "      "
            ],
            'T': [
                "██████",
                "  █   ",
                "  █   ",
                "  █   ",
                "  █   ",
                "  █   ",
                "      "
            ],
            'U': [
                "█    █",
                "█    █",
                "█    █",
                "█    █",
                "█    █",
                " ████ ",
                "      "
            ],
            'V': [
                "█    █",
                "█    █",
                "█    █",
                " █  █ ",
                "  ██  ",
                "  ██  ",
                "      "
            ],
            'W': [
                "█    █",
                "█    █",
                "█    █",
                "█ ██ █",
                "██  ██",
                "█    █",
                "      "
            ],
            'X': [
                "█    █",
                " █  █ ",
                "  ██  ",
                "  ██  ",
                " █  █ ",
                "█    █",
                "      "
            ],
            'Y': [
                "█    █",
                " █  █ ",
                "  ██  ",
                "  █   ",
                "  █   ",
                "  █   ",
                "      "
            ],
            'Z': [
                "██████",
                "    █ ",
                "   █  ",
                "  █   ",
                " █    ",
                "██████",
                "      "
            ],
            '2': [
                " ████ ",
                "█    █",
                "    █ ",
                "   █  ",
                "  █   ",
                "██████",
                "      "
            ],
            '3': [
                " ████ ",
                "█    █",
                "  ███ ",
                "     █",
                "█    █",
                " ████ ",
                "      "
            ],
            '4': [
                "█   █ ",
                "█   █ ",
                "█   █ ",
                "██████",
                "    █ ",
                "    █ ",
                "      "
            ],
            '5': [
                "██████",
                "█     ",
                "█████ ",
                "     █",
                "█    █",
                " ████ ",
                "      "
            ],
            '6': [
                " ████ ",
                "█     ",
                "█████ ",
                "█    █",
                "█    █",
                " ████ ",
                "      "
            ],
            '7': [
                "██████",
                "    █ ",
                "   █  ",
                "  █   ",
                " █    ",
                "█     ",
                "      "
            ],
            '8': [
                " ████ ",
                "█    █",
                " ████ ",
                " ████ ",
                "█    █",
                " ████ ",
                "      "
            ],
            '9': [
                " ████ ",
                "█    █",
                "█    █",
                " █████",
                "     █",
                " ████ ",
                "      "
            ]
        }
        
        # 计算字符位置
        char_width = 8
        char_height = 7
        pixel_size = min(width // (len(text) * char_width), height // char_height)
        pixel_size = max(1, pixel_size)  # 至少1像素
        
        start_x = (width - len(text) * char_width * pixel_size) // 2
        start_y = (height - char_height * pixel_size) // 2
        
        # 绘制每个字符
        for i, char in enumerate(text.upper()):
            if char in char_patterns:
                pattern = char_patterns[char]
                char_x = start_x + i * char_width * pixel_size
                
                for row, line in enumerate(pattern):
                    for col, pixel in enumerate(line):
                        if pixel == '█':
                            x1 = char_x + col * pixel_size
                            y1 = start_y + row * pixel_size
                            x2 = x1 + pixel_size
                            y2 = y1 + pixel_size
                            
                            # 使用主题色绘制像素
                            draw.rectangle([x1, y1, x2, y2], fill=(0, 71, 171))
        
        return image
    
    @staticmethod
    def generate_embedded_captcha(text, width=140, height=50):
        """生成嵌入式验证码图片"""
        try:
            image = EmbeddedFont.create_simple_font_image(text, width=width, height=height)
            
            # 添加一些装饰
            draw = ImageDraw.Draw(image)
            
            # 添加边框
            draw.rectangle([0, 0, width-1, height-1], outline=(0, 71, 171), width=1)
            
            # 保存到BytesIO
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG', quality=100)
            img_buffer.seek(0)
            
            return img_buffer
            
        except Exception as e:
            # 如果连嵌入式字体都失败，创建最简单的错误图片
            error_image = Image.new('RGB', (width, height), color=(245, 248, 255))
            error_draw = ImageDraw.Draw(error_image)
            error_draw.text((10, 15), "FONT ERROR", fill=(220, 53, 69))
            
            error_buffer = io.BytesIO()
            error_image.save(error_buffer, format='PNG')
            error_buffer.seek(0)
            
            return error_buffer
