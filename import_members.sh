#!/bin/bash

# import_members.sh
# 实验室成员信息导入脚本
# 
# 功能：批量导入实验室成员的个人信息和照片
# 使用方法：./import_members.sh
# 
# 数据格式：
# - 成员信息存储在JSON文件中
# - 照片文件与JSON文件配对
# - 支持批量导入多个成员

echo "=========================================="
echo "🧑‍🔬 NLHE实验室成员信息导入工具"
echo "=========================================="

# 检查是否在正确的目录
if [ ! -f "run.py" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 激活虚拟环境（如果存在）
if [ -d "NLHE" ]; then
    echo "🔧 激活虚拟环境..."
    source NLHE/bin/activate
    if [ $? -eq 0 ]; then
        echo "✅ 虚拟环境激活成功"
    else
        echo "⚠️  虚拟环境激活失败，继续使用系统Python"
    fi
fi

# 设置成员数据目录
MEMBERS_DIR="app/static/members"

# 检查成员数据目录是否存在
if [ ! -d "$MEMBERS_DIR" ]; then
    echo "❌ 错误：成员数据目录不存在: $MEMBERS_DIR"
    echo "💡 请确保目录结构正确，每个成员应有独立的子目录"
    exit 1
fi

# 扫描成员目录结构
echo "🔍 扫描成员目录结构..."
MEMBER_DIRS=($(find "$MEMBERS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null))

if [ ${#MEMBER_DIRS[@]} -eq 0 ]; then
    echo "📝 没有找到成员目录，创建示例结构..."

    # 创建示例成员目录
    mkdir -p "$MEMBERS_DIR/example_member"

    cat > "$MEMBERS_DIR/example_member/info.json" << 'EOF'
{
    "name": "张三",
    "title": "博士研究生",
    "bio": "专注于材料科学与工程研究，主要研究方向为新型功能材料的设计与合成。",
    "achievements": [
        "发表SCI论文5篇",
        "获得国家奖学金",
        "参与国家自然科学基金项目2项"
    ],
    "photo": "photo.jpg"
}
EOF

    # 创建占位符照片
    touch "$MEMBERS_DIR/example_member/photo.jpg"

    echo "✅ 示例成员数据已创建在 $MEMBERS_DIR/example_member/"
    echo ""
    echo "📋 目录结构说明："
    echo "  $MEMBERS_DIR/"
    echo "  ├── member1/"
    echo "  │   ├── info.json    # 成员信息"
    echo "  │   └── photo.jpg    # 成员照片"
    echo "  └── member2/"
    echo "      ├── info.json"
    echo "      └── photo.jpg"
    echo ""
    echo "� JSON文件格式："
    echo "  - name: 姓名（必填）"
    echo "  - title: 职位/头衔"
    echo "  - bio: 个人简介"
    echo "  - achievements: 成就列表（数组格式）"
    echo "  - photo: 照片文件名（通常为photo.jpg）"
    echo ""

    # 重新扫描
    MEMBER_DIRS=($(find "$MEMBERS_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null))
fi

# 统计成员目录和文件
VALID_MEMBERS=()
for member_dir in "${MEMBER_DIRS[@]}"; do
    member_name=$(basename "$member_dir")
    info_file="$member_dir/info.json"
    photo_file="$member_dir/photo.jpg"

    if [ -f "$info_file" ]; then
        VALID_MEMBERS+=("$member_dir")
        echo "👤 发现成员: $member_name"
        if [ -f "$photo_file" ]; then
            echo "   ✅ 信息文件: ✓  照片文件: ✓"
        else
            echo "   ✅ 信息文件: ✓  ⚠️  照片文件: ✗"
        fi
    else
        echo "⚠️  跳过 $member_name: 缺少info.json文件"
    fi
done

echo ""
echo "📊 统计结果:"
echo "   📁 成员目录: ${#MEMBER_DIRS[@]} 个"
echo "   ✅ 有效成员: ${#VALID_MEMBERS[@]} 个"

if [ ${#VALID_MEMBERS[@]} -eq 0 ]; then
    echo "❌ 没有找到有效的成员数据"
    echo "💡 请确保每个成员目录都包含info.json文件"
    exit 0
fi

# 导入成员信息
echo ""
echo "🚀 开始导入成员信息..."
echo "----------------------------------------"

SUCCESS_COUNT=0
ERROR_COUNT=0

for member_dir in "${VALID_MEMBERS[@]}"; do
    member_name=$(basename "$member_dir")
    info_file="$member_dir/info.json"
    photo_file="$member_dir/photo.jpg"

    echo "📝 处理成员: $member_name"

    # 检查照片文件
    if [ ! -f "$photo_file" ]; then
        echo "  ⚠️  照片文件不存在，创建占位符"
        touch "$photo_file"
    fi

    echo "  � 信息文件: $(basename "$info_file")"
    echo "  📸 照片文件: $(basename "$photo_file")"

    # 执行导入命令
    if flask import-member --info="$info_file" --photo="$photo_file"; then
        echo "  ✅ 导入成功"
        ((SUCCESS_COUNT++))
    else
        echo "  ❌ 导入失败"
        ((ERROR_COUNT++))
    fi

    echo ""
done

# 显示导入结果
echo "=========================================="
echo "📊 导入结果统计"
echo "=========================================="
echo "✅ 成功导入: $SUCCESS_COUNT 个成员"
echo "❌ 导入失败: $ERROR_COUNT 个成员"
echo "📁 总计处理: $((SUCCESS_COUNT + ERROR_COUNT)) 个文件"

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo ""
    echo "🎉 成员信息导入完成！"
    echo "💡 您可以在网站的团队页面查看导入的成员信息"
fi

if [ $ERROR_COUNT -gt 0 ]; then
    echo ""
    echo "⚠️  部分成员导入失败，请检查："
    echo "   1. JSON文件格式是否正确"
    echo "   2. 必填字段（name）是否存在"
    echo "   3. 照片文件是否存在且可访问"
    echo "   4. 数据库连接是否正常"
fi

echo ""
echo "📋 使用说明："
echo "1. 每个成员都有独立的目录: $MEMBERS_DIR/成员名/"
echo "2. 每个成员目录包含: info.json (信息) 和 photo.jpg (照片)"
echo "3. 重新运行此脚本可以导入新增的成员"
echo "4. 如需修改成员信息，请直接编辑对应的info.json文件后重新导入"

echo ""
echo "🔧 维护命令："
echo "   查看所有成员: flask shell -c 'from app.models import Member; print([m.name for m in Member.query.all()])'"
echo "   清空成员数据: flask shell -c 'from app import db; from app.models import Member; Member.query.delete(); db.session.commit()'"

exit 0
