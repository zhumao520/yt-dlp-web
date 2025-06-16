# -*- coding: utf-8 -*-
"""
Cookies管理路由
"""

import logging
from flask import Blueprint, request, jsonify, send_file
from ...core.auth import auth_required
from .manager import get_cookies_manager

logger = logging.getLogger(__name__)

cookies_bp = Blueprint('cookies', __name__)


@cookies_bp.route('/api/upload', methods=['POST'])
@auth_required
def upload_cookies():
    """上传Cookies"""
    try:
        # 支持JSON和FormData两种格式
        if request.content_type and 'application/json' in request.content_type:
            # JSON格式
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '无效的请求数据'}), 400

            website = data.get('website', '').strip()
            cookies_data = data.get('cookies', '').strip()
            format_type = data.get('format', 'auto')
        else:
            # FormData格式
            website = request.form.get('website', '').strip()
            format_type = request.form.get('format', 'auto')

            # 检查是否有文件上传
            if 'file' in request.files:
                file = request.files['file']
                if file.filename:
                    cookies_data = file.read().decode('utf-8')
                else:
                    return jsonify({'success': False, 'error': '请选择文件'}), 400
            else:
                # 文本内容
                cookies_data = request.form.get('content', '').strip()

        if not website:
            return jsonify({'success': False, 'error': '网站名称不能为空'}), 400

        if not cookies_data:
            return jsonify({'success': False, 'error': 'Cookies数据不能为空'}), 400

        # 保存Cookies
        cookies_manager = get_cookies_manager()
        result = cookies_manager.save_cookies(website, cookies_data, format_type)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"❌ 上传Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/list', methods=['GET'])
@auth_required
def list_cookies():
    """获取Cookies列表"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.list_cookies()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ 获取Cookies列表失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/get/<website>', methods=['GET'])
@auth_required
def get_cookies(website):
    """获取指定网站的Cookies"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.get_cookies(website)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"❌ 获取Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/delete/<website>', methods=['DELETE'])
@auth_required
def delete_cookies(website):
    """删除指定网站的Cookies"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.delete_cookies(website)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"❌ 删除Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/export/<website>', methods=['GET'])
@auth_required
def export_cookies(website):
    """导出Cookies"""
    try:
        format_type = request.args.get('format', 'netscape')
        
        cookies_manager = get_cookies_manager()
        result = cookies_manager.export_cookies(website, format_type)
        
        if result['success']:
            # 创建临时文件并返回
            import tempfile
            import os
            
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                suffix=f".{'txt' if format_type == 'netscape' else 'json'}", 
                delete=False,
                encoding='utf-8'
            )
            
            temp_file.write(result['content'])
            temp_file.close()
            
            def remove_file(response):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
                return response
            
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=result['filename'],
                mimetype='text/plain' if format_type == 'netscape' else 'application/json'
            )
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"❌ 导出Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/validate', methods=['POST'])
@auth_required
def validate_cookies():
    """验证Cookies格式"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400
        
        cookies_data = data.get('cookies', '').strip()
        if not cookies_data:
            return jsonify({'success': False, 'error': 'Cookies数据不能为空'}), 400
        
        cookies_manager = get_cookies_manager()
        
        # 检测格式
        format_type = cookies_manager._detect_format(cookies_data)
        
        # 尝试解析
        parsed_cookies = cookies_manager._parse_cookies(cookies_data, format_type)
        
        if parsed_cookies:
            return jsonify({
                'success': True,
                'format': format_type,
                'count': len(parsed_cookies),
                'preview': parsed_cookies[:3] if len(parsed_cookies) > 3 else parsed_cookies
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Cookies格式无效或无法解析'
            }), 400
            
    except Exception as e:
        logger.error(f"❌ 验证Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/fix-cookies', methods=['POST'])
@auth_required
def fix_cookies():
    """修复损坏的Cookies文件"""
    try:
        logger.info("🔧 开始修复cookies文件")
        cookies_manager = get_cookies_manager()
        fixed_count = 0
        errors = []

        # 获取所有cookies文件
        cookies_list = cookies_manager.list_cookies()
        if not cookies_list['success']:
            error_msg = f"无法获取cookies列表: {cookies_list.get('error', '未知错误')}"
            logger.error(f"❌ {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

        total_count = len(cookies_list['cookies'])
        logger.info(f"📊 找到 {total_count} 个cookies文件需要检查")

        for cookie_info in cookies_list['cookies']:
            website = cookie_info['website']
            try:
                logger.info(f"🔧 正在修复: {website}")

                # 检查文件是否存在
                cookies_file = cookies_manager.cookies_dir / f"{website}.json"
                if not cookies_file.exists():
                    errors.append(f"{website}: 文件不存在")
                    continue

                # 重新导出并保存，这会触发格式修复
                export_result = cookies_manager.export_cookies(website, 'netscape')
                if export_result['success']:
                    # 重新解析并保存
                    parsed = cookies_manager._parse_cookies(export_result['content'], 'netscape')
                    if parsed:
                        # 更新保存的数据
                        save_data = {
                            'website': website,
                            'format': 'netscape',
                            'cookies': parsed,
                            'created_at': cookie_info.get('created_at'),
                            'updated_at': cookies_manager._get_current_timestamp(),
                            'count': len(parsed)
                        }

                        with open(cookies_file, 'w', encoding='utf-8') as f:
                            json.dump(save_data, f, indent=2, ensure_ascii=False)

                        fixed_count += 1
                        logger.info(f"✅ 修复cookies成功: {website} ({len(parsed)} 个cookies)")
                    else:
                        error_msg = f"{website}: 解析失败 - 无法解析cookies内容"
                        errors.append(error_msg)
                        logger.warning(f"⚠️ {error_msg}")
                else:
                    error_msg = f"{website}: 导出失败 - {export_result.get('error', '未知错误')}"
                    errors.append(error_msg)
                    logger.warning(f"⚠️ {error_msg}")
            except Exception as e:
                error_msg = f"{website}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ 修复cookies失败 {website}: {e}")

        total_count = len(cookies_list['cookies'])
        success_message = f'成功修复 {fixed_count}/{total_count} 个cookies文件'

        if errors:
            logger.warning(f"⚠️ 修复完成，但有 {len(errors)} 个错误")
        else:
            logger.info(f"✅ 修复完成，无错误")

        logger.info(f"📊 修复结果: {success_message}")

        return jsonify({
            'success': True,
            'fixed_count': fixed_count,
            'total_count': total_count,
            'errors': errors,
            'message': success_message
        })

    except Exception as e:
        logger.error(f"❌ 修复cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/test/<website>', methods=['POST'])
@auth_required
def test_cookies(website):
    """测试Cookies有效性"""
    try:
        cookies_manager = get_cookies_manager()
        cookies_data = cookies_manager.get_cookies(website)
        
        if not cookies_data['success']:
            return jsonify(cookies_data), 404
        
        # 这里可以添加实际的Cookies测试逻辑
        # 比如发送HTTP请求验证Cookies是否有效
        
        # 目前返回基本信息
        cookies = cookies_data['data']['cookies']
        
        # 检查过期时间
        expired_count = 0
        valid_count = 0
        current_time = int(__import__('time').time())
        
        for cookie in cookies:
            expiration = cookie.get('expiration', 0)
            if expiration > 0 and expiration < current_time:
                expired_count += 1
            else:
                valid_count += 1
        
        return jsonify({
            'success': True,
            'website': website,
            'total_cookies': len(cookies),
            'valid_cookies': valid_count,
            'expired_cookies': expired_count,
            'test_time': __import__('datetime').datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 测试Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/batch-test', methods=['POST'])
@auth_required
def batch_test_cookies():
    """批量测试Cookies"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400

        websites = data.get('websites', [])
        if not websites:
            return jsonify({'success': False, 'error': '没有指定要测试的网站'}), 400

        cookies_manager = get_cookies_manager()
        results = []
        total_valid = 0
        total_cookies = 0

        for website in websites:
            try:
                cookies_data = cookies_manager.get_cookies(website)

                if not cookies_data['success']:
                    results.append({
                        'website': website,
                        'success': False,
                        'error': cookies_data.get('error', '获取失败'),
                        'valid_cookies': 0,
                        'total_cookies': 0
                    })
                    continue

                # 检查过期时间
                cookies = cookies_data['data']['cookies']
                expired_count = 0
                valid_count = 0
                current_time = int(__import__('time').time())

                for cookie in cookies:
                    expiration = cookie.get('expiration', 0)
                    if expiration > 0 and expiration < current_time:
                        expired_count += 1
                    else:
                        valid_count += 1

                results.append({
                    'website': website,
                    'success': True,
                    'valid_cookies': valid_count,
                    'total_cookies': len(cookies),
                    'expired_cookies': expired_count
                })

                total_valid += valid_count
                total_cookies += len(cookies)

            except Exception as e:
                logger.error(f"❌ 测试网站 {website} 的Cookies失败: {e}")
                results.append({
                    'website': website,
                    'success': False,
                    'error': '测试失败',
                    'valid_cookies': 0,
                    'total_cookies': 0
                })

        return jsonify({
            'success': True,
            'total_websites': len(websites),
            'total_valid_cookies': total_valid,
            'total_cookies': total_cookies,
            'results': results,
            'test_time': __import__('datetime').datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 批量测试Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/batch-delete', methods=['POST'])
@auth_required
def batch_delete_cookies():
    """批量删除Cookies"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400

        websites = data.get('websites', [])
        if not websites:
            return jsonify({'success': False, 'error': '没有指定要删除的网站'}), 400

        cookies_manager = get_cookies_manager()
        results = []
        success_count = 0

        for website in websites:
            result = cookies_manager.delete_cookies(website)
            results.append({
                'website': website,
                'success': result['success'],
                'message': result.get('message', result.get('error', ''))
            })
            if result['success']:
                success_count += 1

        return jsonify({
            'success': True,
            'total': len(websites),
            'success_count': success_count,
            'failed_count': len(websites) - success_count,
            'results': results
        })

    except Exception as e:
        logger.error(f"❌ 批量删除Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/oauth2/save', methods=['POST'])
@auth_required
def save_oauth2_config():
    """保存 OAuth2 配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400

        oauth2_token = data.get('oauth2_token', '').strip()
        visitor_data = data.get('visitor_data', '').strip()
        po_token = data.get('po_token', '').strip()

        cookies_manager = get_cookies_manager()
        result = cookies_manager.save_oauth2_config(oauth2_token, visitor_data, po_token)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"❌ 保存 OAuth2 配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/oauth2/get', methods=['GET'])
@auth_required
def get_oauth2_config():
    """获取 OAuth2 配置"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.get_oauth2_config()

        if result['success']:
            # 为了安全，只返回配置状态和部分预览
            return jsonify({
                'success': True,
                'oauth2_available': result['oauth2_available'],
                'visitor_data_available': result['visitor_data_available'],
                'po_token_available': result['po_token_available'],
                'oauth2_token_preview': result['oauth2_token'][:20] + '...' if result['oauth2_token'] else '',
                'visitor_data_preview': result['visitor_data'][:20] + '...' if result['visitor_data'] else '',
                'po_token_preview': result['po_token'][:20] + '...' if result['po_token'] else '',
                'updated_at': result.get('updated_at')
            })
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"❌ 获取 OAuth2 配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/oauth2/delete', methods=['DELETE'])
@auth_required
def delete_oauth2_config():
    """删除 OAuth2 配置"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.delete_oauth2_config()

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"❌ 删除 OAuth2 配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/oauth2/test', methods=['POST'])
@auth_required
def test_oauth2_config():
    """测试 OAuth2 配置"""
    try:
        cookies_manager = get_cookies_manager()
        oauth2_config = cookies_manager.get_oauth2_config()

        if not oauth2_config['success']:
            return jsonify(oauth2_config), 500

        # 检查配置状态
        test_results = {
            'oauth2_token': {
                'available': oauth2_config['oauth2_available'],
                'length': len(oauth2_config['oauth2_token']) if oauth2_config['oauth2_token'] else 0,
                'valid_format': oauth2_config['oauth2_token'].startswith('ya29.') if oauth2_config['oauth2_token'] else False
            },
            'visitor_data': {
                'available': oauth2_config['visitor_data_available'],
                'length': len(oauth2_config['visitor_data']) if oauth2_config['visitor_data'] else 0,
                'valid_format': len(oauth2_config['visitor_data']) >= 20 if oauth2_config['visitor_data'] else False
            },
            'po_token': {
                'available': oauth2_config['po_token_available'],
                'length': len(oauth2_config['po_token']) if oauth2_config['po_token'] else 0,
                'valid_format': len(oauth2_config['po_token']) >= 20 if oauth2_config['po_token'] else False
            }
        }

        # 计算总体状态
        total_available = sum(1 for config in test_results.values() if config['available'])
        total_valid = sum(1 for config in test_results.values() if config['valid_format'])

        return jsonify({
            'success': True,
            'total_configs': 3,
            'available_configs': total_available,
            'valid_configs': total_valid,
            'details': test_results,
            'test_time': __import__('datetime').datetime.now().isoformat(),
            'recommendation': self._get_oauth2_recommendation(test_results)
        })

    except Exception as e:
        logger.error(f"❌ 测试 OAuth2 配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500

def _get_oauth2_recommendation(test_results):
    """获取 OAuth2 配置建议"""
    recommendations = []

    if not test_results['oauth2_token']['available']:
        recommendations.append("建议配置 OAuth2 Token 以提高下载成功率")
    elif not test_results['oauth2_token']['valid_format']:
        recommendations.append("OAuth2 Token 格式可能不正确，应以 'ya29.' 开头")

    if not test_results['visitor_data']['available']:
        recommendations.append("建议配置 Visitor Data 以增强身份验证")
    elif not test_results['visitor_data']['valid_format']:
        recommendations.append("Visitor Data 长度可能不足，建议检查格式")

    if not test_results['po_token']['available']:
        recommendations.append("可选配置 PO Token 以进一步提高成功率")

    if not recommendations:
        recommendations.append("OAuth2 配置看起来正常，应该能有效提高下载成功率")

    return recommendations
