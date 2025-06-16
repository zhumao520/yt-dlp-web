# -*- coding: utf-8 -*-
"""
认证管理 - 统一JWT认证系统
"""

import jwt
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, Optional
from flask import request, jsonify, redirect, url_for, current_app

logger = logging.getLogger(__name__)


class AuthManager:
    """统一认证管理器"""
    
    def __init__(self):
        self.algorithm = 'HS256'
    
    def _get_secret_key(self) -> str:
        """获取JWT密钥"""
        from .config import get_config
        return get_config('app.secret_key', 'change-this-secret-key')
    
    def generate_token(self, user_data: Dict[str, Any]) -> str:
        """生成JWT令牌"""
        try:
            from .config import get_config
            
            # 设置过期时间
            timeout = get_config('auth.session_timeout', 86400)  # 默认24小时
            expiration = datetime.utcnow() + timedelta(seconds=timeout)
            
            # 创建payload
            payload = {
                'user_id': user_data.get('id'),
                'username': user_data.get('username'),
                'is_admin': user_data.get('is_admin', False),
                'exp': expiration,
                'iat': datetime.utcnow()
            }
            
            # 生成令牌
            token = jwt.encode(payload, self._get_secret_key(), algorithm=self.algorithm)
            logger.debug(f"✅ 生成JWT令牌: {user_data.get('username')}")
            return token
            
        except Exception as e:
            logger.error(f"❌ JWT令牌生成失败: {e}")
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证JWT令牌"""
        try:
            if not token:
                return None
            
            # 移除Bearer前缀（如果存在）
            if token.startswith('Bearer '):
                token = token[7:]
            
            # 解码令牌
            payload = jwt.decode(
                token, 
                self._get_secret_key(), 
                algorithms=[self.algorithm]
            )
            
            logger.debug(f"✅ JWT令牌验证成功: {payload.get('username')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ JWT令牌已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ JWT令牌无效: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ JWT令牌验证失败: {e}")
            return None
    
    def login(self, username: str, password: str) -> Optional[str]:
        """用户登录"""
        try:
            from .database import get_database
            
            db = get_database()
            
            # 验证用户凭据
            if not db.verify_user_password(username, password):
                logger.warning(f"❌ 登录失败: {username} - 凭据无效")
                return None
            
            # 获取用户信息
            user = db.get_user_by_username(username)
            if not user:
                logger.warning(f"❌ 登录失败: {username} - 用户不存在")
                return None
            
            # 更新最后登录时间
            db.update_user_login_time(username)
            
            # 生成令牌
            token = self.generate_token(user)
            
            logger.info(f"✅ 用户登录成功: {username}")
            
            # 发送登录事件
            from .events import emit, Events
            emit(Events.USER_LOGIN, {
                'username': username,
                'user_id': user['id'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return token
            
        except Exception as e:
            logger.error(f"❌ 登录处理失败: {e}")
            return None
    
    def logout(self, token: str):
        """用户登出"""
        try:
            # 验证令牌获取用户信息
            payload = self.verify_token(token)
            if payload:
                username = payload.get('username')
                logger.info(f"✅ 用户登出: {username}")
                
                # 发送登出事件
                from .events import emit, Events
                emit(Events.USER_LOGOUT, {
                    'username': username,
                    'user_id': payload.get('user_id'),
                    'timestamp': datetime.utcnow().isoformat()
                })
            
        except Exception as e:
            logger.error(f"❌ 登出处理失败: {e}")
    
    def get_current_user(self, token: str) -> Optional[Dict[str, Any]]:
        """获取当前用户信息"""
        payload = self.verify_token(token)
        if not payload:
            return None
        
        try:
            from .database import get_database
            db = get_database()
            return db.get_user_by_username(payload.get('username'))
        except Exception as e:
            logger.error(f"❌ 获取用户信息失败: {e}")
            return None


# 全局认证管理器实例
auth_manager = AuthManager()


def get_auth_manager() -> AuthManager:
    """获取认证管理器实例"""
    return auth_manager


def get_token_from_request() -> Optional[str]:
    """从请求中提取令牌"""
    # 1. 从Authorization头获取
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]
        logger.debug(f"🔑 从Authorization头获取token: {token[:20]}...")
        return token

    # 2. 从Cookie获取
    token = request.cookies.get('auth_token')
    if token:
        logger.debug(f"🍪 从Cookie获取token: {token[:20]}...")
        return token

    # 3. 从查询参数获取（用于某些特殊场景）
    token = request.args.get('token')
    if token:
        logger.debug(f"🔗 从查询参数获取token: {token[:20]}...")
        return token

    logger.debug("❌ 未找到任何token")
    return None


def auth_required(f):
    """认证装饰器 - 要求用户登录"""
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.debug(f"🔐 认证检查: {request.method} {request.path}")
        token = get_token_from_request()

        if not token:
            logger.debug("❌ 未找到token，重定向到登录页")
            if request.is_json:
                return jsonify({'error': '需要认证'}), 401
            else:
                return redirect(url_for('auth.login'))

        payload = auth_manager.verify_token(token)
        if not payload:
            logger.debug("❌ token验证失败，重定向到登录页")
            if request.is_json:
                return jsonify({'error': '认证无效或已过期'}), 401
            else:
                return redirect(url_for('auth.login', token_expired='1'))

        logger.debug(f"✅ 认证成功: {payload.get('username')}")
        # 将用户信息添加到请求上下文
        request.current_user = payload

        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        
        if not token:
            if request.is_json:
                return jsonify({'error': '需要认证'}), 401
            else:
                return redirect(url_for('auth.login'))
        
        payload = auth_manager.verify_token(token)
        if not payload:
            if request.is_json:
                return jsonify({'error': '认证无效或已过期'}), 401
            else:
                return redirect(url_for('auth.login', token_expired='1'))
        
        if not payload.get('is_admin', False):
            if request.is_json:
                return jsonify({'error': '需要管理员权限'}), 403
            else:
                return redirect(url_for('main.index'))
        
        # 将用户信息添加到请求上下文
        request.current_user = payload
        
        return f(*args, **kwargs)
    
    return decorated


def optional_auth(f):
    """可选认证装饰器 - 如果有令牌则验证，没有则继续"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        
        if token:
            payload = auth_manager.verify_token(token)
            if payload:
                request.current_user = payload
            else:
                request.current_user = None
        else:
            request.current_user = None
        
        return f(*args, **kwargs)
    
    return decorated
