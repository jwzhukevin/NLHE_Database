#!/bin/bash
# 推送前自动更新requirements.txt

# 1. 生成依赖文件
echo "[1/4] 激活虚拟环境并生成 requirements.txt ..."
source ./NLHE/bin/activate
pip freeze > requirements.txt
deactivate

echo "[2/4] 添加所有更改到暂存区 ..."
git add .

echo "[3/4] 请输入本次提交的额外说明（可选，直接回车跳过）："
read -p "Commit message: " extra_msg

# 获取当前仓库信息
COMMIT_HASH=$(git rev-parse --short HEAD)
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
REPO_NAME=$(basename `git rev-parse --show-toplevel`)
TIMESTAMP=$(date +'%Y-%m-%d %H:%M:%S')

# 组装commit message，用户输入在前，自动信息在后
if [ -z "$extra_msg" ]; then
    msg="auto: update requirements and push | $REPO_NAME@$BRANCH_NAME:$COMMIT_HASH ($TIMESTAMP)"
else
    msg="$extra_msg | $REPO_NAME@$BRANCH_NAME:$COMMIT_HASH ($TIMESTAMP)"
fi

echo "[4/4] 提交并推送到远程仓库 ..."
git commit -m "$msg"
git push origin master

echo "推送完成！"
