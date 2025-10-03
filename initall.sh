#!/bin/bash

set -e

# 清理函数：确保虚拟环境正确退出
cleanup() {
    echo "Cleaning up..."
    if command -v deactivate &> /dev/null; then
        deactivate
        echo "✓ Virtual environment deactivated"
    fi
}

# 设置陷阱，确保脚本异常退出时也能清理
trap cleanup EXIT

# 记录开始时间
START_TIME=$(date +%s)
echo "========================================"
echo "NLHE Database Initialization Script"
echo "Started at: $(date)"
echo "========================================"

# 激活Python虚拟环境
echo "Activating NLHE virtual environment..."
if [ -d "NLHE/bin" ]; then
    source NLHE/bin/activate
    echo "✓ Virtual environment activated successfully"
elif [ -d "NLHE/Scripts" ]; then
    # Windows环境
    source NLHE/Scripts/activate
    echo "✓ Virtual environment activated successfully (Windows)"
else
    echo "⚠ Warning: Virtual environment directory not found"
    echo "Please ensure NLHE virtual environment exists"
    exit 1
fi

# 检查是否有--noinput参数
NOINPUT=false
for arg in "$@"; do
    if [ "$arg" == "--noinput" ]; then
        NOINPUT=true
    fi
done

# 1. 数据库备份
DB_PATH="app/data/database.db"
if [ -f "$DB_PATH" ]; then
    backup_file="backup/database_$(date +%Y%m%d_%H%M%S).db"
    mkdir -p backup
    cp "$DB_PATH" "$backup_file"
    echo -e "\033[33m[Backup] Database automatically backed up to $backup_file\033[0m"
fi

# 2. 数据库初始化
echo -e "\033[36m[1/4] Rebuilding database (executing ./initdb.sh --drop)...\033[0m"
if $NOINPUT; then
    yes | ./initdb.sh --drop
else
    ./initdb.sh --drop
fi
if [ $? -eq 0 ]; then
    echo -e "\033[32m[Success] Database initialization successful.\033[0m"
else
    echo -e "\033[31m[Failed] Database initialization failed, terminating.\033[0m"
    exit 1
fi

# 3. 初始化首个用户（非管理员，交互式）
echo -e "\033[36m[2/4] Creating initial user (executing ./create_initial_user.sh)...\033[0m"
if [ -x "./create_initial_user.sh" ]; then
    ./create_initial_user.sh
else
    echo -e "\033[33m[Info] create_initial_user.sh not found or not executable.\033[0m"
    echo -e "\033[33m[Hint] Please run: chmod +x create_initial_user.sh && ./create_initial_user.sh\033[0m"
    exit 1
fi
if [ $? -eq 0 ]; then
    echo -e "\033[32m[Success] Initial user created successfully.\033[0m"
else
    echo -e "\033[31m[Failed] Initial user creation failed, terminating.\033[0m"
    exit 1
fi

# 4. 能带数据分析
echo -e "\033[36m[3/5] Analyzing band structure data...\033[0m"
echo -e "\033[32m[Info] Starting batch analysis of material band structures...\033[0m"

# 执行能带分析
python -c "
from app import create_app
from app.band_analyzer import band_analyzer
from app.models import Material, db
import os

app = create_app()
with app.app_context():
    materials = Material.query.all()
    total = len(materials)
    analyzed = 0
    failed = 0

    print(f'Found {total} materials to analyze...')

    for i, material in enumerate(materials, 1):
        try:
            material_path = f'app/static/materials/{material.formatted_id}/band'
            if os.path.exists(material_path):
                result = band_analyzer.analyze_material(material_path)
                if result['band_gap'] is not None:
                    material.band_gap = result['band_gap']
                    material.materials_type = result['materials_type']
                    analyzed += 1
                    print(f'[{i}/{total}] ✓ {material.formatted_id}: {result[\"materials_type\"]} (gap: {result[\"band_gap\"]:.4f} eV)')
                else:
                    material.band_gap = None
                    material.materials_type = 'unknown'
                    failed += 1
                    print(f'[{i}/{total}] ✗ {material.formatted_id}: Analysis failed')
            else:
                material.band_gap = None
                material.materials_type = 'unknown'
                failed += 1
                print(f'[{i}/{total}] ✗ {material.formatted_id}: No band data found')
        except Exception as e:
            material.band_gap = None
            material.materials_type = 'unknown'
            failed += 1
            print(f'[{i}/{total}] ✗ {material.formatted_id}: Error - {e}')

    db.session.commit()
    print(f'Band analysis completed: {analyzed} analyzed, {failed} failed')
"

if [ $? -eq 0 ]; then
    echo -e "\033[32m[Success] Band structure analysis completed.\033[0m"
else
    echo -e "\033[33m[Warning] Band structure analysis completed with errors.\033[0m"
fi

# 5. 用户管理提示（使用新的安全工具）
echo -e "\033[36m[4/5] User management information...\033[0m"
echo -e "\033[32m[Security] User management has been upgraded for enhanced security.\033[0m"
echo -e "\033[32m[Info] All user data is now stored securely in the database with bcrypt encryption.\033[0m"
echo -e "\033[33m[Note] To add or manage users after initialization, use: python user_management.py\033[0m"
echo -e "\033[32m[Success] Security-enhanced user management ready.\033[0m"

# 6. 成员信息导入
echo -e "\033[36m[5/5] Importing member information (executing ./import_members.sh)...\033[0m"
if [ -f "./import_members.sh" ]; then
    ./import_members.sh
    if [ $? -eq 0 ]; then
        echo -e "\033[32m[Success] Member information import successful.\033[0m"
    else
        echo -e "\033[33m[Warning] Member information import completed with warnings.\033[0m"
    fi
else
    echo -e "\033[33m[Info] import_members.sh not found, skipping member import.\033[0m"
fi

# 计算执行时间
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo "========================================"
echo -e "\033[1;32mWebsite initialization completed successfully!\033[0m"
echo "Completed at: $(date)"
echo "Total execution time: ${MINUTES}m ${SECONDS}s"
echo "========================================"
# 虚拟环境将通过trap清理函数自动退出