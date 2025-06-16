# -*- coding: utf-8 -*-
"""
认证路由 - 用户登录登出
"""

import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, make_response

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'GET':
        # 显示登录页面
        return render_template('auth/login.html')
    
    try:
        # 处理登录请求
        data = request.get_json() if request.is_json else request.form
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        if not username or not password:
            error_msg = '用户名和密码不能为空'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 400
            return render_template('auth/login.html', error=error_msg)
        
        # 验证用户凭据
        from ...core.auth import get_auth_manager
        auth_manager = get_auth_manager()
        
        token = auth_manager.login(username, password)
        if not token:
            error_msg = '用户名或密码错误'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 401
            return render_template('auth/login.html', error=error_msg)
        
        # 登录成功
        logger.info(f"✅ 用户登录成功: {username}")
        
        if request.is_json:
            # API响应
            return jsonify({
                'success': True,
                'message': '登录成功',
                'token': token,
                'username': username
            })
        else:
            # Web响应 - 设置Cookie并重定向
            response = make_response(redirect(url_for('main.index')))
            max_age = (30 * 24 * 60 * 60) if remember else (24 * 60 * 60)  # 记住我30天，否则1天
            response.set_cookie('auth_token', token,
                              max_age=max_age,
                              path='/',
                              httponly=False, secure=False, samesite='Lax')
            logger.info(f"🍪 Web登录设置cookie: auth_token={token[:20]}..., max_age={max_age}")
            return response
            
    except Exception as e:
        logger.error(f"❌ 登录处理失败: {e}")
        error_msg = '登录处理失败，请稍后重试'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        return render_template('auth/login.html', error=error_msg)


@auth_bp.route('/logout', methods=['POST', 'GET'])
def logout():
    """用户登出"""
    try:
        # 获取令牌
        from ...core.auth import get_token_from_request, get_auth_manager
        token = get_token_from_request()
        
        if token:
            auth_manager = get_auth_manager()
            auth_manager.logout(token)
        
        if request.is_json:
            # API响应
            return jsonify({'success': True, 'message': '登出成功'})
        else:
            # Web响应 - 清除Cookie并重定向
            response = make_response(redirect(url_for('auth.login', logout='1')))
            response.set_cookie('auth_token', '', expires=0, path='/')
            return response
            
    except Exception as e:
        logger.error(f"❌ 登出处理失败: {e}")
        if request.is_json:
            return jsonify({'success': False, 'error': '登出失败'}), 500
        return redirect(url_for('auth.login'))


@auth_bp.route('/status')
def status():
    """检查登录状态"""
    try:
        from ...core.auth import get_token_from_request, get_auth_manager
        
        token = get_token_from_request()
        if not token:
            return jsonify({'authenticated': False}), 401
        
        auth_manager = get_auth_manager()
        user_info = auth_manager.get_current_user(token)
        
        if not user_info:
            return jsonify({'authenticated': False}), 401
        
        return jsonify({
            'authenticated': True,
            'username': user_info.get('username'),
            'is_admin': user_info.get('is_admin', False)
        })
        
    except Exception as e:
        logger.error(f"❌ 状态检查失败: {e}")
        return jsonify({'authenticated': False, 'error': '状态检查失败'}), 500


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """刷新令牌"""
    try:
        from ...core.auth import get_token_from_request, get_auth_manager
        
        token = get_token_from_request()
        if not token:
            return jsonify({'error': '需要提供令牌'}), 401
        
        auth_manager = get_auth_manager()
        user_info = auth_manager.get_current_user(token)
        
        if not user_info:
            return jsonify({'error': '令牌无效'}), 401
        
        # 生成新令牌
        new_token = auth_manager.generate_token(user_info)
        
        return jsonify({
            'success': True,
            'token': new_token,
            'username': user_info.get('username')
        })
        
    except Exception as e:
        logger.error(f"❌ 令牌刷新失败: {e}")
        return jsonify({'error': '令牌刷新失败'}), 500
