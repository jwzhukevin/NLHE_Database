#!/usr/bin/env python3
"""
下载验证码所需的字体文件
"""
import os
import urllib.request
import sys

def download_font(url, filename):
    """下载字体文件"""
    font_dir = os.path.join('app', 'static', 'fonts')
    os.makedirs(font_dir, exist_ok=True)
    
    font_path = os.path.join(font_dir, filename)
    
    if os.path.exists(font_path):
        print(f"字体文件 {filename} 已存在，跳过下载")
        return True
    
    try:
        print(f"正在下载 {filename}...")
        urllib.request.urlretrieve(url, font_path)
        print(f"✅ {filename} 下载完成")
        return True
    except Exception as e:
        print(f"❌ 下载 {filename} 失败: {e}")
        return False

def main():
    """主函数"""
    # DejaVu Sans Bold 字体 - 开源字体，适合验证码
    fonts = [
        {
            'url': 'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf',
            'filename': 'DejaVuSans-Bold.ttf'
        },
        {
            'url': 'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans.ttf', 
            'filename': 'DejaVuSans.ttf'
        }
    ]
    
    success_count = 0
    for font in fonts:
        if download_font(font['url'], font['filename']):
            success_count += 1
    
    print(f"\n下载完成: {success_count}/{len(fonts)} 个字体文件")
    
    if success_count == 0:
        print("⚠️  所有字体下载失败，请检查网络连接")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
