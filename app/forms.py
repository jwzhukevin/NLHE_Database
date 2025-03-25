from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, FloatField, SelectField
from wtforms.validators import DataRequired, Length

class MaterialForm(FlaskForm):
    name = StringField('材料名称', validators=[DataRequired(), Length(max=120)])
    status = SelectField('材料状态', choices=[('实验', '实验'), ('理论', '理论')], validators=[DataRequired()])
    total_energy = FloatField('总能量(eV)', validators=[DataRequired()])
    structure_file = FileField('结构文件', validators=[
        FileRequired('请选择一个CIF文件'),
        FileAllowed(['cif'], '只允许上传.cif格式的文件')
    ])