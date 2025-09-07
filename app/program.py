from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
# 说明：python-docx 为可选依赖；未安装时仅生成 .dat 文件并提示，不影响主流程
try:
    from docx import Document
except ImportError:
    Document = None

program_bp = Blueprint('program', __name__, url_prefix='/program')

UPLOAD_FOLDER = os.path.join('app', 'static', 'functions', 'trans_txt')
ALLOWED_EXTENSIONS = {'txt'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@program_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    文本转换工具：上传 txt，生成 dat 与（可选）docx。

    说明：
    - 未安装 python-docx 时，不生成 docx，仅提示；
    - 所有路径位于 static/functions/trans_txt 下，避免越权访问。
    """
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
        # 转换为 Word（可选，未安装 python-docx 则跳过）
        docx_filename = filename.rsplit('.', 1)[0] + '.docx'
        docx_path = os.path.join(UPLOAD_FOLDER, docx_filename)
        docx_generated = False
        if Document is None:
            flash('已生成 .dat；未安装 python-docx，跳过 Word 生成。', 'warning')
        else:
            try:
                doc = Document()
                with open(save_path, 'r', encoding='utf-8') as fin:
                    for line in fin:
                        doc.add_paragraph(line.rstrip())
                doc.save(docx_path)
                docx_generated = True
            except Exception as e:
                current_app.logger.error(f"生成 Word 失败: {e}")
                flash('已生成 .dat；Word 生成失败，请联系管理员查看日志。', 'warning')

        flash('转换成功！', 'success')
        return render_template('program/index.html', dat_file=dat_filename, docx_file=(docx_filename if docx_generated else None))
    return render_template('program/index.html')

@program_bp.route('/download/<filename>')
@login_required
def download(filename):
    abs_folder = os.path.join(current_app.root_path, 'static', 'functions', 'trans_txt')
    return send_from_directory(abs_folder, filename, as_attachment=True) 