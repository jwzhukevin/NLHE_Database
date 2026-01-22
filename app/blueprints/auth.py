# -*- coding: utf-8 -*-
"""
认证蓝图
路由：登录、登出、申请、验证码、限流页面
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, send_file, current_app
from flask_login import login_user, logout_user, current_user, login_required
from flask_babel import _
from flask_mail import Message
import functools
import time
import random
import io
from PIL import Image, ImageDraw

auth_bp = Blueprint('auth', __name__)


# ==================== 辅助函数 ====================

def get_client_ip():
    """获取客户端IP地址"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr


def check_ip_blocked(view_func):
    """检查IP是否被封禁的装饰器"""
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        from ..models import BlockedIP
        client_ip = get_client_ip()
        blocked = BlockedIP.query.filter_by(ip_address=client_ip).first()
        if blocked:
            flash(_('Access denied. Your IP has been blocked due to multiple failed login attempts.'), 'error')
            return redirect(url_for('main.landing'))
        return view_func(*args, **kwargs)
    return wrapped_view


def generate_captcha_image(text, width=140, height=50, scale_factor=2):
    """
    使用Pillow生成符合网站风格的验证码图片
    """
    from ..font_manager import FontManager
    
    THEME_COLORS = {
        'primary': (0, 71, 171),
        'secondary': (30, 92, 179),
        'accent': (0, 127, 255),
        'light_bg': (245, 248, 255),
        'nav_bg': (181, 222, 253),
        'text_dark': (51, 51, 51),
    }

    render_width = int(width * scale_factor)
    render_height = int(height * scale_factor)

    image = Image.new('RGB', (render_width, render_height), color=THEME_COLORS['light_bg'])
    draw = ImageDraw.Draw(image)

    # 添加渐变背景
    for y in range(render_height):
        ratio = y / render_height
        r = int(THEME_COLORS['light_bg'][0] + (THEME_COLORS['nav_bg'][0] - THEME_COLORS['light_bg'][0]) * ratio * 0.3)
        g = int(THEME_COLORS['light_bg'][1] + (THEME_COLORS['nav_bg'][1] - THEME_COLORS['light_bg'][1]) * ratio * 0.3)
        b = int(THEME_COLORS['light_bg'][2] + (THEME_COLORS['nav_bg'][2] - THEME_COLORS['light_bg'][2]) * ratio * 0.3)
        draw.line([(0, y), (render_width, y)], fill=(r, g, b))

    base_font_size = 32
    font_size = int(base_font_size * scale_factor)
    font = FontManager.get_captcha_font(font_size)

    if hasattr(font, '_use_embedded') and font._use_embedded:
        from ..embedded_font import EmbeddedFont
        return EmbeddedFont.generate_embedded_captcha(text, width, height)

    # 装饰点
    dot_count = int(30 * scale_factor)
    dot_size = int(1 * scale_factor)
    for _ in range(dot_count):
        x = random.randint(0, render_width)
        y = random.randint(0, render_height)
        alpha = random.uniform(0.1, 0.3)
        base_color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        color = tuple(int(c + (255 - c) * (1 - alpha)) for c in base_color)
        draw.ellipse([x-dot_size, y-dot_size, x+dot_size, y+dot_size], fill=color)

    # 计算文本位置
    try:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except AttributeError:
        text_width = len(text) * int(20 * scale_factor)
        text_height = int(28 * scale_factor)

    start_x = (render_width - text_width) // 2
    start_y = (render_height - text_height) // 2

    char_colors = [
        THEME_COLORS['primary'],
        THEME_COLORS['secondary'],
        THEME_COLORS['accent'],
        THEME_COLORS['text_dark']
    ]

    char_width = text_width // len(text) if len(text) > 0 else int(20 * scale_factor)
    offset_range = int(3 * scale_factor)

    for i, char in enumerate(text):
        color = char_colors[i % len(char_colors)]
        char_x = start_x + i * char_width + random.randint(-offset_range, offset_range)
        char_y = start_y + random.randint(-offset_range, offset_range)
        draw.text((char_x, char_y), char, font=font, fill=color)

    # 装饰线
    line_width = max(1, int(1 * scale_factor))
    for _ in range(2):
        color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        alpha_color = tuple(int(c + (255 - c) * 0.6) for c in color)
        start_x_line = random.randint(0, render_width // 3)
        start_y_line = random.randint(render_height // 4, 3 * render_height // 4)
        end_x_line = random.randint(2 * render_width // 3, render_width)
        end_y_line = random.randint(render_height // 4, 3 * render_height // 4)
        draw.line([(start_x_line, start_y_line), (end_x_line, end_y_line)], fill=alpha_color, width=line_width)

    if scale_factor != 1:
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG', quality=100, optimize=True)
    img_buffer.seek(0)

    return img_buffer


# ==================== 限流相关路由 ====================

@auth_bp.before_app_request
def enforce_429_challenge():
    """全局拦截：若存在限流挑战且未通过验证码，一律拦截到 /rate-limited"""
    try:
        endpoint = (request.endpoint or '')
        if endpoint.startswith('static') or endpoint.startswith('errors.'):
            return
        if endpoint in {'auth.captcha429', 'auth.verify_captcha_429', 'auth.rate_limited'}:
            return
        path = request.path or ''
        if path in {'/captcha429', '/verify_captcha_429', '/rate-limited'}:
            return
        if bool(session.get('rl_verified', False)):
            return
        if 'rl_locked_until' in session:
            return redirect(url_for('auth.rate_limited'))
        return
    except Exception:
        return


@auth_bp.route('/rate-limited')
def rate_limited():
    """限流页面"""
    now = int(time.time())
    session['rl_locked_until'] = now + 60
    session['rl_verified'] = False
    return render_template('errors/429.html', retry_after=60), 429


@auth_bp.route('/captcha429')
def captcha429():
    """为429页面生成验证码"""
    from ..captcha_logger import CaptchaLogger
    start_time = time.time()
    try:
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        captcha_text = ''.join(random.choices(chars, k=5))
        session['captcha_429'] = captcha_text
        session.permanent = True
        img_buffer = generate_captcha_image(captcha_text, scale_factor=2)
        generation_time = time.time() - start_time
        CaptchaLogger.log_captcha_generation(
            text_length=len(captcha_text),
            image_size='140x50',
            generation_time=generation_time,
            success=True
        )
        response = send_file(img_buffer, mimetype='image/png', as_attachment=False, download_name='captcha429.png')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        current_app.logger.error(f"Error generating captcha429: {e}")
        error_image = Image.new('RGB', (140, 50), color=(245, 248, 255))
        error_draw = ImageDraw.Draw(error_image)
        error_draw.text((10, 15), "ERROR", fill=(220, 53, 69))
        error_buffer = io.BytesIO()
        error_image.save(error_buffer, format='PNG')
        error_buffer.seek(0)
        return send_file(error_buffer, mimetype='image/png')


@auth_bp.route('/verify_captcha_429', methods=['POST'])
def verify_captcha_429():
    """校验429页面验证码"""
    from .. import csrf
    if csrf:
        csrf.exempt(verify_captcha_429)
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get('captcha', '')).strip().upper()
        real = str(session.get('captcha_429', '')).strip().upper()
        ok = bool(code) and code == real

        now = int(time.time())
        locked_until = int(session.get('rl_locked_until') or 0)
        remaining = max(0, locked_until - now)

        if ok:
            if remaining > 0:
                return jsonify({'ok': False, 'need_wait': True, 'seconds': remaining})
            session.pop('captcha_429', None)
            session['rl_verified'] = True
            session.pop('rl_locked_until', None)
            return jsonify({'ok': True})
        else:
            return jsonify({'ok': False})
    except Exception as e:
        current_app.logger.error(f"verify_captcha_429 error: {e}")
        return jsonify({'ok': False})


# ==================== 验证码路由 ====================

@auth_bp.route('/captcha')
def captcha():
    """生成验证码图片"""
    from ..captcha_logger import CaptchaLogger
    start_time = time.time()
    try:
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        captcha_text = ''.join(random.choices(chars, k=5))
        session['captcha'] = captcha_text
        session.permanent = True
        img_buffer = generate_captcha_image(captcha_text, scale_factor=2)
        generation_time = time.time() - start_time
        CaptchaLogger.log_captcha_generation(
            text_length=len(captcha_text),
            image_size='140x50',
            generation_time=generation_time,
            success=True
        )
        response = send_file(img_buffer, mimetype='image/png', as_attachment=False, download_name='captcha.png')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        from ..captcha_logger import CaptchaLogger
        CaptchaLogger.log_captcha_generation(
            text_length=5,
            image_size='140x50',
            generation_time=time.time() - start_time,
            success=False,
            error=str(e)
        )
        current_app.logger.error(f"Error generating captcha: {str(e)}")
        error_image = Image.new('RGB', (140, 50), color=(245, 248, 255))
        error_draw = ImageDraw.Draw(error_image)
        error_draw.text((10, 15), "ERROR", fill=(220, 53, 69))
        error_buffer = io.BytesIO()
        error_image.save(error_buffer, format='PNG')
        error_buffer.seek(0)
        return send_file(error_buffer, mimetype='image/png')


# ==================== 登录/登出路由 ====================

@auth_bp.route('/login', methods=['GET', 'POST'])
@check_ip_blocked
def login():
    """用户登录"""
    from ..models import User, BlockedIP
    from .. import db
    from ..security import log_security_event, regenerate_session
    from ..security import LoginStateManager, LoginErrorHandler

    if current_user.is_authenticated:
        return redirect(url_for('functional_materials.index'))

    if request.method == 'POST':
        try:
            from flask_wtf.csrf import validate_csrf
            validate_csrf(request.form.get('csrf_token'))
        except Exception as e:
            flash(_('Security token expired or invalid. Please try again.'), 'error')
            current_app.logger.warning(f"CSRF validation failed for login: {str(e)}")
            return render_template('auth/login.html')

        email = request.form.get('email')
        username = request.form.get('username')
        captcha_input = request.form.get('captcha', '').upper()
        real_captcha = session.get('captcha', '')
        if captcha_input != real_captcha:
            flash(_('Invalid captcha code, please try again'), 'error')
            return render_template('auth/login.html')
        password = request.form.get('password')
        remember = 'remember' in request.form

        if not email or not username or not password:
            flash(_('All fields are required.'), 'error')
            return render_template('auth/login.html')

        ip = get_client_ip()
        failed_key = f"login_failed:{ip}"
        failed_attempts = session.get(failed_key, 0)
        max_attempts = 5

        log_security_event("LOGIN_ATTEMPT", f"User: {username}, Email: {email}", ip)

        user_by_email = User.query.filter_by(email=email).first()
        if not user_by_email:
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many failed login attempts.'), 'error')
                return redirect(url_for('auth.login'))
            flash(_('Email not found. Please check your email address. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')

        if user_by_email.username != username:
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many failed login attempts.'), 'error')
                return redirect(url_for('auth.login'))
            flash(_('Username does not match this email address. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')

        if not user_by_email.validate_password(password):
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many failed login attempts.'), 'error')
                return redirect(url_for('auth.login'))
            flash(_('Incorrect password. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')

        session.pop(failed_key, None)

        try:
            success, message, redirect_url = LoginStateManager.login_user(user_by_email)
            if success:
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('functional_materials.index'))
            else:
                flash(message, 'error')
                return render_template('auth/login.html')
        except Exception as e:
            current_app.logger.error(f"Login system error: {e}")
            error_msg = LoginErrorHandler.handle_login_error('system_error')
            flash(error_msg, 'error')
            return render_template('auth/login.html')

    return render_template('auth/login.html')


@auth_bp.route('/auth/login_json', methods=['POST'])
@check_ip_blocked
def login_json():
    """JSON登录接口"""
    from ..models import User, BlockedIP
    from .. import db, csrf
    from ..security import log_security_event
    from ..security import LoginStateManager, LoginErrorHandler

    if csrf:
        csrf.exempt(login_json)

    try:
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        captcha_input = (data.get('captcha') or '').strip().upper()

        real_captcha = session.get('captcha', '')
        if not captcha_input or captcha_input != real_captcha:
            return jsonify({'ok': False, 'error': _('Invalid captcha code, please try again')}), 200

        if not email or not username or not password:
            return jsonify({'ok': False, 'error': _('All fields are required.')}), 200

        ip = get_client_ip()
        failed_key = f"login_failed:{ip}"
        failed_attempts = session.get(failed_key, 0)
        max_attempts = 5

        log_security_event("LOGIN_ATTEMPT_JSON", f"User: {username}, Email: {email}", ip)

        user_by_email = User.query.filter_by(email=email).first()
        if not user_by_email:
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many failed login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('Email not found. Please check your email address. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        if user_by_email.username != username:
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many failed login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('Username does not match this email address. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        if not user_by_email.validate_password(password):
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many failed login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('Incorrect password. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        session.pop(failed_key, None)

        try:
            success, message, redirect_url = LoginStateManager.login_user(user_by_email)
            if success:
                next_page = request.args.get('next')
                return jsonify({'ok': True, 'redirect': next_page or url_for('functional_materials.index')})
            else:
                return jsonify({'ok': False, 'error': message or _('An error occurred: %(error)s', error='login')})
        except Exception as e:
            current_app.logger.error(f"Login system error (JSON): {e}")
            error_msg = LoginErrorHandler.handle_login_error('system_error')
            return jsonify({'ok': False, 'error': error_msg}), 200

    except Exception as e:
        current_app.logger.error(f"login_json unexpected error: {e}")
        return jsonify({'ok': False, 'error': 'Internal server error'}), 500


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """用户登出"""
    from ..security import LoginStateManager
    from ..security import regenerate_session

    try:
        success, message = LoginStateManager.logout_user()
        return redirect(url_for('functional_materials.index'))
    except Exception as e:
        current_app.logger.error(f"Logout system error: {e}")
        try:
            logout_user()
            session.clear()
            regenerate_session()
        except:
            pass
        flash(_('Logout completed.'), 'info')
        return redirect(url_for('functional_materials.index'))


# ==================== 申请路由 ====================

@auth_bp.route('/apply', methods=['GET', 'POST'])
def apply():
    """申请成为用户"""
    from .. import mail
    
    try:
        if request.method == 'GET':
            return render_template('auth/apply.html')

        full_name = (request.form.get('full_name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        username = (request.form.get('username') or '').strip()
        affiliation = (request.form.get('affiliation') or '').strip()
        reason = (request.form.get('reason') or '').strip()
        captcha_input = (request.form.get('captcha') or '').strip().upper()

        if not full_name or not email or not username or not reason:
            flash(_('All fields are required.'), 'error')
            return render_template('auth/apply.html')

        if '@' not in email or '.' not in email.split('@')[-1]:
            flash(_('Invalid data: %(error)s', error=_('Email format is invalid')), 'error')
            return render_template('auth/apply.html')

        real_captcha = session.get('captcha', '').upper()
        if not captcha_input or captcha_input != real_captcha:
            flash(_('Invalid captcha code, please try again'), 'error')
            return render_template('auth/apply.html')

        receiver = current_app.config.get('APPLICATION_RECEIVER') or ''
        if not receiver:
            current_app.logger.error('APPLICATION_RECEIVER not configured')
            flash(_('An error occurred: %(error)s', error=_('Receiver mailbox is not configured')), 'error')
            return render_template('auth/apply.html')

        subject = f"[MatdataX] New user application: {username}"
        body_lines = [
            f"Full Name: {full_name}",
            f"Email: {email}",
            f"Desired Username: {username}",
            f"Affiliation: {affiliation or '-'}",
            "",
            "Reason:",
            reason,
            "",
            f"Client IP: {request.remote_addr}",
            f"User-Agent: {request.headers.get('User-Agent', 'N/A')}",
        ]
        
        msg_admin = Message(subject=subject, recipients=[receiver], body='\n'.join(body_lines))
        try:
            mail.send(msg_admin)
        except Exception as e:
            current_app.logger.error(f"send application email failed: {e}")
            flash(_('An error occurred: %(error)s', error=_('Failed to send application email')), 'error')
            return render_template('auth/apply.html')

        try:
            ack_subject = _('[MatdataX] We have received your application')
            ack_body = '\n'.join([
                _('Hello %(name)s,', name=full_name),
                '',
                _('We have received your application. We will review it and contact you via email.'),
                '',
                _('Summary:'),
                "- " + _('Full Name') + ": " + full_name,
                "- " + _('Email') + ": " + email,
                "- " + _('Desired Username') + ": " + username,
                "- " + _('Affiliation') + ": " + (affiliation or '-'),
            ])
            msg_ack = Message(subject=ack_subject, recipients=[email], body=ack_body)
            mail.send(msg_ack)
        except Exception as e:
            current_app.logger.warning(f"send ack email failed: {e}")

        flash(_('Application submitted successfully, we will contact you via email.'), 'success')
        return redirect(url_for('functional_materials.index'))
    except Exception as e:
        current_app.logger.error(f"/apply error: {e}")
        return render_template('errors/500.html'), 500
