#!/usr/bin/env bash
# 用途：交互式辅助设置邮件服务的环境变量与本地收件方案
# 适用：Ubuntu 开发环境（不修改 config/ 目录，不写入代码仓库敏感信息）
# 产物：在项目根目录生成/覆盖 .env.mail 文件，并给出启动与验证指引

set -euo pipefail

PROJECT_ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT_DIR/.env.mail"

print_line() { printf "\n%s\n" "$1"; }

# 模式 4：Postfix 内网测试（无 DKIM，仅本机监听）
case_postfix_internal() {
  echo "\n模式：Postfix 内网测试（无 DKIM，仅 127.0.0.1 监听，避免开放中继）"
  ask_common_vars
  MAIL_SERVER="127.0.0.1"
  MAIL_PORT="587"
  MAIL_USE_TLS="true"
  MAIL_USE_SSL="false"
  MAIL_USERNAME=""
  MAIL_PASSWORD=""
  write_env_file

  PROVISION_SH="$PROJECT_ROOT_DIR/scripts/provision_postfix_internal.sh"
  cat > "$PROVISION_SH" <<'EOSH'
#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] 安装 Postfix 与证书依赖..."
sudo apt update
sudo apt install -y postfix ssl-cert

echo "[2/6] 生成/确保 snakeoil 证书可用（用于 STARTTLS）..."
sudo make-ssl-cert generate-default-snakeoil --force-overwrite || true
sudo adduser postfix ssl-cert || true

echo "[3/6] 备份并写入 /etc/postfix/main.cf（最小安全配置，仅本机监听）..."
sudo cp -a /etc/postfix/main.cf "/etc/postfix/main.cf.bak.$(date +%s)" || true
sudo bash -c 'cat > /etc/postfix/main.cf' <<'EOF'
# 最小可用内网提交配置（仅本机监听，不开放中继）
myhostname = localhost
myorigin = /etc/mailname
mydestination = localhost
inet_interfaces = loopback-only
inet_protocols = ipv4
relayhost =

# 仅允许本机网络提交
mynetworks = 127.0.0.0/8

# 启用发信 TLS（opportunistic STARTTLS）
smtp_tls_security_level = may
smtp_tls_loglevel = 1

# 接收端（submission/25）启用 TLS（使用 snakeoil 证书）
smtpd_tls_cert_file = /etc/ssl/certs/ssl-cert-snakeoil.pem
smtpd_tls_key_file  = /etc/ssl/private/ssl-cert-snakeoil.key
smtpd_use_tls = yes
smtpd_tls_security_level = may

# 安全收敛
disable_vrfy_command = yes
smtpd_helo_required = yes

# 基本限流与策略（仅演示，必要时在生产加强）
smtpd_recipient_limit = 100
EOF

echo "[4/6] 启用 submission(587) 并收敛为本机用途..."
sudo cp -a /etc/postfix/master.cf "/etc/postfix/master.cf.bak.$(date +%s)" || true
sudo sed -i 's/^#\s*submission/submission/' /etc/postfix/master.cf || true
sudo awk '
  BEGIN{printed=0}
  /^submission\s+inet/ {
    print;
    print "  -o syslog_name=postfix/submission";
    print "  -o smtpd_tls_security_level=may";
    print "  -o smtpd_sasl_auth_enable=no";
    print "  -o smtpd_recipient_restrictions=permit_mynetworks,reject";
    printed=1; next
  }
  {print}
' /etc/postfix/master.cf | sudo tee /etc/postfix/master.cf.tmp >/dev/null
sudo mv /etc/postfix/master.cf.tmp /etc/postfix/master.cf

echo "[5/6] 重载 Postfix 并自检..."
sudo postfix check || true
sudo systemctl enable --now postfix
sleep 1
sudo systemctl status postfix --no-pager || true

echo "[6/6] 验证指引："
echo "- 本机监听：127.0.0.1:25 与 127.0.0.1:587 (submission)"
echo "- 建议客户端（Flask-Mail）连接 127.0.0.1:587 并启用 TLS=true（STARTTLS）"
echo "- 快速测试："
echo "  openssl s_client -starttls smtp -connect 127.0.0.1:587 -crlf -quiet <<< 'QUIT'"
echo "  echo -e 'Subject: Test\n\nHello' | sendmail -v root@localhost"
echo "- 查看日志： tail -f /var/log/mail.log"
echo "完成。"
EOSH
  chmod +x "$PROVISION_SH"

  print_line "下一步："
  echo "1) 执行一键配置脚本（需要 sudo）："
  echo "   $PROVISION_SH"
  echo "2) 在当前 shell 加载环境变量："
  echo "   source $ENV_FILE"
  echo "3) 启动应用并从 /apply 提交表单（仅本机 Postfix 中转，不发公网）"
  echo "4) 观察 /var/log/mail.log 确认邮件已进入队列或投递到本地邮箱"
}

print_header() {
  echo "============================================="
  echo " NLHE Database 邮件服务本地设置向导"
  echo "============================================="
}

choose_mode() {
  echo "请选择本地邮件收件方案（回车确认）："
  echo "  [1] MailHog（推荐，Docker，带 Web 收件箱 http://127.0.0.1:8025 ）"
  echo "  [2] aiosmtpd（零安装，控制台打印邮件）"
  echo "  [3] 外部 SMTP（填写你的企业邮/第三方 SMTP）"
  echo "  [4] Postfix 内网测试（无 DKIM，仅本机监听 25/587）"
  read -r -p "输入选项数字 [1/2/3]：" MODE
  case "${MODE:-1}" in
    1|2|3|4) ;;
    *) MODE=1 ;;
  esac
}

ask_common_vars() {
  echo "\n填写通用信息（建议使用你的测试接收邮箱）"
  read -r -p "APPLICATION_RECEIVER（管理员接收申请的邮箱）: " APPLICATION_RECEIVER
  read -r -p "MAIL_DEFAULT_SENDER（发件人显示，如: MatdataX <no-reply@nlhe-database.org>）: " MAIL_DEFAULT_SENDER
}

write_env_file() {
  cat > "$ENV_FILE" <<EOF
# 由 scripts/setup_local_mail.sh 生成（可手工编辑）
APPLICATION_RECEIVER=${APPLICATION_RECEIVER}
MAIL_DEFAULT_SENDER=${MAIL_DEFAULT_SENDER}
MAIL_SERVER=${MAIL_SERVER}
MAIL_PORT=${MAIL_PORT}
MAIL_USE_TLS=${MAIL_USE_TLS}
MAIL_USE_SSL=${MAIL_USE_SSL}
MAIL_USERNAME=${MAIL_USERNAME}
MAIL_PASSWORD=${MAIL_PASSWORD}
EOF
  echo "已生成环境文件：$ENV_FILE"
}

case_mailhog() {
  echo "\n模式：MailHog（Docker）"
  ask_common_vars
  MAIL_SERVER="127.0.0.1"
  MAIL_PORT="1025"
  MAIL_USE_TLS="false"
  MAIL_USE_SSL="false"
  MAIL_USERNAME=""
  MAIL_PASSWORD=""
  write_env_file

  echo "\n尝试检测 Docker 并启动 MailHog（如未安装将跳过）："
  if command -v docker >/dev/null 2>&1; then
    if ! docker ps --format '{{.Names}}' | grep -q '^mailhog$'; then
      echo "运行：docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog"
      docker run -d --name mailhog -p 1025:1025 -p 8025:8025 mailhog/mailhog || true
    else
      echo "容器 mailhog 已在运行"
    fi
  else
    echo "未检测到 Docker，跳过自动启动。你可以手动安装/启动 MailHog。"
  fi

  print_line "下一步："
  echo "1) 在当前 shell 加载环境变量："
  echo "   source $ENV_FILE"
  echo "2) 启动应用并访问 http://127.0.0.1:5000/apply 提交表单"
  echo "3) 打开 http://127.0.0.1:8025 查看两封邮件（管理员与回执）"
}

case_aiosmtpd() {
  echo "\n模式：aiosmtpd（控制台打印邮件，不提供网页收件箱）"
  ask_common_vars
  MAIL_SERVER="127.0.0.1"
  MAIL_PORT="1025"
  MAIL_USE_TLS="false"
  MAIL_USE_SSL="false"
  MAIL_USERNAME=""
  MAIL_PASSWORD=""
  write_env_file

  print_line "在另一个终端运行本地 SMTP（保持前台）："
  echo "  python3 -m aiosmtpd -n -l 127.0.0.1:1025"

  print_line "下一步："
  echo "1) 在当前 shell 加载环境变量：source $ENV_FILE"
  echo "2) 启动应用并访问 /apply 提交表单"
  echo "3) 观察运行 aiosmtpd 的终端，应该打印两封邮件内容"
}

case_external_smtp() {
  echo "\n模式：外部 SMTP（TLS 587 或 SSL 465，按服务商要求填写）"
  ask_common_vars
  read -r -p "SMTP 主机（MAIL_SERVER）: " MAIL_SERVER
  read -r -p "端口（常见: 587=TLS, 465=SSL）（MAIL_PORT）: " MAIL_PORT
  # TLS/SSL 仅二选一为 true
  read -r -p "启用 TLS? (true/false)（MAIL_USE_TLS）: " MAIL_USE_TLS
  read -r -p "启用 SSL? (true/false)（MAIL_USE_SSL）: " MAIL_USE_SSL
  read -r -p "SMTP 用户名（MAIL_USERNAME）: " MAIL_USERNAME
  read -r -p "SMTP 密码（MAIL_PASSWORD）: " MAIL_PASSWORD
  write_env_file

  print_line "下一步："
  echo "1) 确认 TLS/SSL 与端口匹配（587+TLS 或 465+SSL）"
  echo "2) 在当前 shell 加载环境变量：source $ENV_FILE"
  echo "3) 启动应用并从 /apply 提交表单；如失败查看日志与服务商文档"
}

print_header
choose_mode
case "$MODE" in
  1) case_mailhog ;;
  2) case_aiosmtpd ;;
  3) case_external_smtp ;;
  4) case_postfix_internal ;;
  *) case_mailhog ;;
(esac)

print_line "验证限流（可选）：1 分钟内提交 /apply 超过 5 次，应触发 429 流程"
print_line "完成。"
