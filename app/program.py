from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
from docx import Document

program_bp = Blueprint('program', __name__, url_prefix='/program')

UPLOAD_FOLDER = os.path.join('app', 'static', 'functions', 'trans_txt')
ALLOWED_EXTENSIONS = {'txt'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@program_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('没有文件被上传', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            flash('请上传txt文件', 'danger')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        # 转换为dat
        dat_filename = filename.rsplit('.', 1)[0] + '.dat'
        dat_path = os.path.join(UPLOAD_FOLDER, dat_filename)
        with open(save_path, 'r', encoding='utf-8') as fin, open(dat_path, 'w', encoding='utf-8') as fout:
            fout.write(fin.read())
        # 转换为word
        docx_filename = filename.rsplit('.', 1)[0] + '.docx'
        docx_path = os.path.join(UPLOAD_FOLDER, docx_filename)
        doc = Document()
        with open(save_path, 'r', encoding='utf-8') as fin:
            for line in fin:
                doc.add_paragraph(line.rstrip())
        doc.save(docx_path)
        flash('转换成功！', 'success')
        return render_template('program_index.html', dat_file=dat_filename, docx_file=docx_filename)
    return render_template('program_index.html')

@program_bp.route('/download/<filename>')
@login_required
def download(filename):
    abs_folder = os.path.join(current_app.root_path, 'static', 'functions', 'trans_txt')
    return send_from_directory(abs_folder, filename, as_attachment=True) 