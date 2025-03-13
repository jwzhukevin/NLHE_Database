# 可选文件，用于数据导入前的校验
import csv
from decimal import Decimal, InvalidOperation

def validate_csv(filepath):
    errors = []
    with open(filepath) as f:
        reader = csv.DictReader(f)
        required_fields = ['name', 'total_energy', 'formation_energy']
        
        for i, row in enumerate(reader, start=2):  # 从第2行开始
            # 检查必填字段
            for field in required_fields:
                if not row.get(field):
                    errors.append(f"Row {i}: Missing {field}")
            
            # 检查数值格式
            numeric_fields = ['total_energy', 'formation_energy', 'efermi']
            for field in numeric_fields:
                if row.get(field):
                    try:
                        Decimal(row[field])
                    except InvalidOperation:
                        errors.append(f"Row {i}: Invalid numeric value in {field}")
    
    if errors:
        for error in errors:
            print(error)
        return False
    return True
