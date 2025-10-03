#!/bin/bash
# [New] Create initial (non-admin) user interactively
# Platform: Ubuntu/Linux
# This script creates the first application user without any role field.
# It runs inside the Flask app context and writes to the database securely.

set -e

# Try to activate local virtual environment if present
if [ -d "NLHE/bin" ]; then
  # shellcheck disable=SC1091
  source NLHE/bin/activate || true
fi

# Ensure FLASK_APP
export FLASK_APP="wsgi.py"

# Collect inputs interactively
read -r -p "邮箱地址 (Email): " INIT_USER_EMAIL
if [ -z "$INIT_USER_EMAIL" ]; then
  echo "❌ 邮箱不能为空"; exit 1
fi

read -r -p "用户名 (Username): " INIT_USER_USERNAME
if [ -z "$INIT_USER_USERNAME" ]; then
  echo "❌ 用户名不能为空"; exit 1
fi

prompt_password() {
  local p1 p2
  while true; do
    read -r -s -p "密码 (Password): " p1; echo
    if [ -z "$p1" ]; then
      echo "❌ 密码不能为空"; continue
    fi
    read -r -s -p "确认密码 (Confirm Password): " p2; echo
    if [ "$p1" != "$p2" ]; then
      echo "❌ 两次输入的密码不一致"; continue
    fi
    PASSWORD_RESULT="$p1"
    break
  done
}

prompt_password
INIT_USER_PASSWORD="$PASSWORD_RESULT"

# Export variables for Python heredoc
export INIT_USER_EMAIL_INPUT="$INIT_USER_EMAIL"
export INIT_USER_USERNAME_INPUT="$INIT_USER_USERNAME"
export INIT_USER_PASSWORD_INPUT="$INIT_USER_PASSWORD"

# Run within Flask app context
python - <<'PYCODE'
import sys
import getpass
from app import create_app, db
from app.models import User

# Read env passed by shell heredoc is not needed; use pre-collected stdin variables via placeholders
# We'll import os for environment if needed in the future.
import os

email = os.environ.get('INIT_USER_EMAIL_INPUT')
username = os.environ.get('INIT_USER_USERNAME_INPUT')
password = os.environ.get('INIT_USER_PASSWORD_INPUT')

if not email or not username or not password:
    print('❌ 缺少必要参数 (email/username/password)')
    sys.exit(1)

app = create_app()
with app.app_context():
    # Check existence
    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f"ℹ️ 用户已存在，跳过创建: {email} ({existing.username})")
        sys.exit(0)

    existing_username = User.query.filter_by(username=username).first()
    if existing_username:
        print(f"❌ 用户名已存在: {username}")
        sys.exit(1)

    # Create user (no role field)
    user = User(email=email, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print('✅ 初始用户创建成功:')
    print(f'   邮箱: {email}')
    print(f'   用户名: {username}')
PYCODE
