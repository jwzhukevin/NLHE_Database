import os
import re
import markdown
from datetime import datetime
from flask import Blueprint, render_template, request, abort, current_app

# Create a blueprint for content management
articles = Blueprint('articles', __name__)

# Define base path for content files
CONTENT_BASE_PATH = os.path.join('app', 'static', 'contents')

# Helper function to extract metadata from markdown content
def extract_metadata(content, filename):
    """Extract title, date, and summary from markdown content"""
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

# List all articles with optional filtering
@articles.route('/articles')
@articles.route('/articles/<category>')
def listing(category=None):
    query = request.args.get('q', '').lower()
    
    # Default to 'all' if no category is specified
    if not category:
        category = 'all'
    
    # Normalize category name
    selected_category = category.lower()
    
    # Define categories to search based on selected category
    if selected_category == 'all':
        categories = ['Articles', 'Instructions', 'Changelog']
    else:
        # Map URL parameter to folder name (capitalize first letter)
        folder_name = selected_category.capitalize()
        if folder_name == 'Changelog':  # Special case for correct capitalization
            folder_name = 'Changelog'
        categories = [folder_name]
    
    articles_list = []
    
    # Search through each category
    for cat in categories:
        cat_path = os.path.join(CONTENT_BASE_PATH, cat)
        
        # Skip if category folder doesn't exist
        if not os.path.exists(cat_path):
            continue
        
        # List all markdown files in the category
        for filename in os.listdir(cat_path):
            if filename.endswith('.md'):
                file_path = os.path.join(cat_path, filename)
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract metadata from content first to get the title
                metadata = extract_metadata(content, filename)
                metadata['category'] = cat
                
                # Skip if search query doesn't match title
                if query and query not in metadata['title'].lower():
                    continue
                
                # Add to articles list
                articles_list.append(metadata)
    
    # Sort articles by date (if available) or title
    articles_list.sort(key=lambda x: (x['date'] is None, x['date'] if x['date'] else '', x['title']), reverse=True)
    
    return render_template('articles/listing.html', 
                          articles=articles_list,
                          selected_category=selected_category,
                          query=query)

# View a specific article
@articles.route('/articles/<category>/<filename>')
def view(category, filename):
    # Normalize category name for file system
    folder_name = category.capitalize()
    if folder_name == 'Changelog':  # Special case for correct capitalization
        folder_name = 'Changelog'
    
    # Construct file path
    file_path = os.path.join(CONTENT_BASE_PATH, folder_name, f"{filename}.md")
    
    # Check if file exists
    if not os.path.exists(file_path):
        abort(404)
    
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract metadata
    metadata = extract_metadata(content, f"{filename}.md")
    metadata['category'] = folder_name
    
    # Convert markdown to HTML
    html_content = markdown.markdown(
        content,
        extensions=['extra', 'codehilite', 'toc', 'fenced_code']
    )
    
    return render_template('articles/view.html',
                          article=metadata,
                          category=category.lower(),
                          content=html_content) 