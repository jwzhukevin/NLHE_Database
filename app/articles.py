import os
import re
import markdown
from datetime import datetime
from flask import Blueprint, render_template, request, abort, current_app

# 内容管理蓝图：用于展示与查看站内文档/教程/更新日志
articles = Blueprint('articles', __name__)

# 内容文件的基础目录（相对项目根目录）
CONTENT_BASE_PATH = os.path.join('app', 'static', 'contents')

# 元数据抽取：从 Markdown 内容中提取标题/日期/摘要
def extract_metadata(content, filename):
    """
    从 Markdown 内容中提取元数据（标题、日期、摘要）。

    参数：
        content: Markdown 文本内容
        filename: 文件名（用于在缺失标题时生成默认标题）

    返回：
        dict，包含 title/date/summary/filename 字段
    """
    # Default metadata
    metadata = {
        'title': filename.replace('_', ' ').replace('.md', '').title(),
        'date': None,
        'summary': '',
        'filename': filename.replace('.md', '')
    }
    
    # Extract title from first h1
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if title_match:
        metadata['title'] = title_match.group(1).strip()
    
    # Extract date from "Release Date:" lines in changelogs or estimate from file stats
    date_match = re.search(r'\*\*Release Date:\*\* (.+)$', content, re.MULTILINE)
    if date_match:
        metadata['date'] = date_match.group(1).strip()
    
    # Generate summary from first paragraph after the title or first 150 chars
    summary_match = re.search(r'^# .+\n+(.+)', content, re.MULTILINE)
    if summary_match:
        summary = summary_match.group(1).strip()
        # Clean up markdown symbols
        summary = re.sub(r'\*\*|\*|__|\||_', '', summary)
        metadata['summary'] = summary[:150] + ('...' if len(summary) > 150 else '')
    
    return metadata

# 列表页：按分类（Articles/Instructions/Changelog）与查询参数展示文章
@articles.route('/articles')
@articles.route('/articles/<category>')
def listing(category=None):
    query = request.args.get('q', '').lower()
    
    # 若未指定分类，默认显示全部分类
    if not category:
        category = 'all'
    
    # 归一化分类名（用于目录匹配）
    selected_category = category.lower()
    
    # 根据分类参数确定要遍历的文件夹集合
    if selected_category == 'all':
        categories = ['Articles', 'Instructions', 'Changelog']
    else:
        # 将URL参数映射为文件夹名（首字母大写）
        folder_name = selected_category.capitalize()
        if folder_name == 'Changelog':  # 特殊大小写
            folder_name = 'Changelog'
        categories = [folder_name]
    
    articles_list = []
    
    # 遍历分类目录并收集 Markdown 文件
    for cat in categories:
        cat_path = os.path.join(CONTENT_BASE_PATH, cat)
        
        # 分类目录不存在时跳过
        if not os.path.exists(cat_path):
            continue
        
        # 列出该分类下的所有 Markdown 文件
        for filename in os.listdir(cat_path):
            if filename.endswith('.md'):
                file_path = os.path.join(cat_path, filename)
                
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 先提取元数据（得到标题等）
                metadata = extract_metadata(content, filename)
                metadata['category'] = cat
                
                # 若查询关键字不在标题中则跳过
                if query and query not in metadata['title'].lower():
                    continue
                
                # 收集文章条目
                articles_list.append(metadata)
    
    # 排序：优先按日期（有日期在前），其次按标题
    articles_list.sort(key=lambda x: (x['date'] is None, x['date'] if x['date'] else '', x['title']), reverse=True)
    
    return render_template('articles/listing.html', 
                          articles=articles_list,
                          selected_category=selected_category,
                          query=query)

# 详情页：展示指定分类与文件名的文章内容
@articles.route('/articles/<category>/<filename>')
def view(category, filename):
    # 为文件系统归一化分类名
    folder_name = category.capitalize()
    if folder_name == 'Changelog':  # 特殊大小写
        folder_name = 'Changelog'
    
    # 构造文件路径
    file_path = os.path.join(CONTENT_BASE_PATH, folder_name, f"{filename}.md")
    
    # 文件存在性检查
    if not os.path.exists(file_path):
        abort(404)
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取元数据
    metadata = extract_metadata(content, f"{filename}.md")
    metadata['category'] = folder_name
    
    # Markdown 转 HTML（启用常用扩展）
    html_content = markdown.markdown(
        content,
        extensions=['extra', 'codehilite', 'toc', 'fenced_code']
    )
    
    return render_template('articles/view.html',
                          article=metadata,
                          category=category.lower(),
                          content=html_content) 