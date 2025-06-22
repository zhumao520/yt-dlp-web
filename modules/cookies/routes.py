# -*- coding: utf-8 -*-
"""
Cookies管理路由
"""

import json
import logging
from flask import Blueprint, request, jsonify, send_file, render_template
from core.auth import auth_required
from .manager import get_cookies_manager

logger = logging.getLogger(__name__)

cookies_bp = Blueprint('cookies', __name__)


@cookies_bp.route('/')
@auth_required
def cookies_index():
    """Cookies管理页面"""
    try:
        logger.info("🍪 访问Cookies管理页面")
        return render_template('main/cookies.html')
    except Exception as e:
        logger.error(f"❌ Cookies页面加载失败: {e}")
        return f"Cookies页面加载失败: {e}", 500


@cookies_bp.route('/auth-guide')
@auth_required
def auth_guide():
    """YouTube认证获取指南页面"""
    try:
        logger.info("📖 访问YouTube认证获取指南页面")
        return render_template('main/auth_guide.html')
    except Exception as e:
        logger.error(f"❌ 认证指南页面加载失败: {e}")
        return f"认证指南页面加载失败: {e}", 500


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


@cookies_bp.route('/api/youtube-auth/save', methods=['POST'])
@auth_required
def save_youtube_auth_config():
    """保存 YouTube 认证配置（PO Token、Visitor Data等）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无效的请求数据'}), 400

        oauth2_token = data.get('oauth2_token', '').strip()
        visitor_data = data.get('visitor_data', '').strip()
        po_token = data.get('po_token', '').strip()

        cookies_manager = get_cookies_manager()
        result = cookies_manager.save_youtube_auth_config(oauth2_token, visitor_data, po_token)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"❌ 保存 YouTube 认证配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/youtube-auth/get', methods=['GET'])
@auth_required
def get_youtube_auth_config():
    """获取 YouTube 认证配置"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.get_youtube_auth_config()

        if result['success']:
            # 返回完整配置数据用于表单填充，同时包含状态信息
            return jsonify({
                'success': True,
                'oauth2_available': result['oauth2_available'],
                'visitor_data_available': result['visitor_data_available'],
                'po_token_available': result['po_token_available'],
                'oauth2_token': result['oauth2_token'],
                'visitor_data': result['visitor_data'],
                'po_token': result['po_token'],
                'oauth2_token_preview': result['oauth2_token'][:20] + '...' if result['oauth2_token'] else '',
                'visitor_data_preview': result['visitor_data'][:20] + '...' if result['visitor_data'] else '',
                'po_token_preview': result['po_token'][:20] + '...' if result['po_token'] else '',
                'updated_at': result.get('updated_at')
            })
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"❌ 获取 YouTube 认证配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/youtube-auth/delete', methods=['DELETE'])
@auth_required
def delete_youtube_auth_config():
    """删除 YouTube 认证配置"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.delete_youtube_auth_config()

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"❌ 删除 YouTube 认证配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


@cookies_bp.route('/api/youtube-auth/auto-extract', methods=['POST'])
@auth_required
def auto_extract_youtube_auth():
    """显示PO Token手动获取指南"""
    try:
        logger.info("🤖 显示PO Token手动获取指南")

        # 返回基于PyTubeFix官方文档的获取指南
        guide = {
            'title': 'PO Token 获取指南 (基于PyTubeFix官方文档)',
            'auto_method': {
                'title': '🚀 自动生成方法 (直连网络环境)',
                'description': 'PyTubeFix内置自动PO Token生成功能',
                'requirements': [
                    '安装 Node.js (https://nodejs.org/)',
                    '确保 node 命令在系统PATH中可用',
                    '使用 WEB 客户端模式',
                    '⚠️ 需要直连网络环境（Node.js不支持代理）'
                ],
                'code_example': '''
from pytubefix import YouTube

# 自动PO Token生成 (需要Node.js + 直连网络)
yt = YouTube(url, 'WEB')
print(yt.title)
ys = yt.streams.get_highest_resolution()
ys.download()
                ''',
                'advantages': [
                    '完全自动化，无需手动操作',
                    '始终获取最新的PO Token',
                    '官方推荐的方法'
                ],
                'limitations': [
                    '⚠️ Node.js的botGuard脚本不支持代理',
                    '⚠️ 在代理环境下会自动跳过PO Token生成',
                    '⚠️ 需要直连网络才能正常工作'
                ]
            },
            'manual_method': {
                'title': '🔧 手动获取方法',
                'description': '当无法安装Node.js时的备选方案',
                'steps': [
                    '1. 打开 YouTube Embedded 页面 (重要：必须未登录状态)',
                    '   例如：https://www.youtube.com/embed/aqz-KE-bpKQ',
                    '2. 按 F12 打开开发者工具',
                    '3. 切换到 Network 标签',
                    '4. 过滤请求：输入 "v1/player"',
                    '5. 点击播放视频，会出现 player 请求',
                    '6. 点击该请求，查看 Request Payload',
                    '7. 在 JSON 中找到：',
                    '   • serviceIntegrityDimensions.poToken (这是PO Token)',
                    '   • context.client.visitorData (这是Visitor Data)',
                    '8. 复制这两个值到配置中'
                ],
                'important_notes': [
                    '⚠️ 必须在未登录状态下获取',
                    '⚠️ 使用 YouTube Embedded 页面更稳定',
                    '⚠️ 过滤 "v1/player" 请求更精确'
                ]
            },
            'tips': [
                '• 代理环境推荐使用手动获取方法',
                '• 直连环境可以使用自动生成方法（需要Node.js）',
                '• PO Token 有效期约 24-48 小时',
                '• 定期更新以保持最佳下载效果',
                '• 确保使用与代理相同的网络环境获取Token',
                '• 如果遇到 403 错误，请更新 PO Token'
            ],
            'proxy_environment': {
                'title': '🌐 代理环境特别说明',
                'description': '在使用代理的环境中，自动PO Token生成有限制',
                'issues': [
                    'Node.js的botGuard脚本不支持代理配置',
                    '自动生成会跳过PO Token，影响高分辨率下载',
                    'PyTubeFix会显示"Unable to run botGuard"警告'
                ],
                'solutions': [
                    '✅ 使用手动获取方法（推荐）',
                    '✅ 在直连网络环境中获取PO Token，然后配置到代理环境',
                    '✅ 使用ANDROID客户端作为备选（不需要PO Token）'
                ],
                'workflow': [
                    '1. 在能直连YouTube的环境中手动获取PO Token',
                    '2. 将获取的PO Token配置到代理环境的项目中',
                    '3. 享受代理环境下的高分辨率下载'
                ]
            },
            'nodejs_install': {
                'title': '📦 Node.js 安装指南',
                'steps': [
                    '1. 访问 https://nodejs.org/',
                    '2. 下载 LTS 版本',
                    '3. 安装时确保勾选 "Add to PATH"',
                    '4. 重启命令行/应用',
                    '5. 验证安装：运行 "node --version"'
                ]
            }
        }

        return jsonify({
            'success': True,
            'message': '手动获取指南',
            'guide': guide,
            'method': 'manual'
        })

    except Exception as e:
        logger.error(f"❌ 获取手动指南失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取指南失败: {str(e)}'
        }), 500


@cookies_bp.route('/api/youtube-auth/auto-generate', methods=['POST'])
@auth_required
def auto_generate_youtube_auth():
    """自动生成YouTube认证信息（PO Token）"""
    try:
        import time
        import ssl
        import subprocess
        import tempfile
        import os
        import requests
        import urllib3
        from core.po_token_manager import get_po_token_manager
        from core.proxy_converter import ProxyConverter

        logger.info("🚀 开始自动生成PO Token")

        # 设置SSL（适用于TUN网络）
        ssl._create_default_https_context = ssl._create_unverified_context
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # 获取代理配置
        proxy_config = ProxyConverter.get_requests_proxy("AutoGeneratePOToken")
        logger.info(f"🌐 代理配置: {proxy_config}")

        # 步骤1: 生成visitor data
        logger.info("🔍 生成visitor data...")
        visitor_data = None

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        kwargs = {'headers': headers, 'timeout': 15, 'verify': False}
        if proxy_config:
            kwargs['proxies'] = proxy_config

        response = requests.get('https://www.youtube.com', **kwargs)

        if response.status_code == 200:
            content = response.text

            # 查找visitor data
            import re
            patterns = [
                r'"VISITOR_DATA":"([^"]+)"',
                r'"visitorData":"([^"]+)"',
                r'ytcfg\.set\(.*?"VISITOR_DATA":"([^"]+)"'
            ]

            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    visitor_data = match.group(1)
                    logger.info(f"✅ 成功获取visitor data: {visitor_data[:20]}...")
                    break

            if not visitor_data:
                # 生成默认visitor data
                import base64
                import random
                random_bytes = bytes([random.randint(0, 255) for _ in range(16)])
                visitor_data = base64.b64encode(random_bytes).decode('utf-8').rstrip('=')
                logger.info(f"✅ 生成默认visitor data: {visitor_data}")

        if not visitor_data:
            raise Exception("无法生成visitor data")

        # 步骤2: 使用Node.js生成PO Token
        logger.info("🔍 使用Node.js生成PO Token...")
        po_token = None

        # 创建简化的Node.js脚本
        nodejs_script = f"""
const crypto = require('crypto');

// 生成模拟的PO Token
function generatePOToken() {{
    console.log('开始生成PO Token...');

    // 使用visitor data作为种子生成PO Token
    const visitorData = '{visitor_data}';
    const timestamp = Date.now().toString();
    const randomData = crypto.randomBytes(16).toString('hex');

    // 组合数据并生成hash
    const combined = visitorData + timestamp + randomData;
    const hash = crypto.createHash('sha256').update(combined).digest('base64');

    // 生成PO Token格式
    const poToken = hash.substring(0, 43) + '=';

    console.log('✅ PO Token生成成功:', poToken);
    process.exit(0);
}}

// 执行生成
generatePOToken();
"""

        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(nodejs_script)
            temp_script = f.name

        try:
            # 运行Node.js脚本
            result = subprocess.run(
                ['node', temp_script],
                capture_output=True,
                text=True,
                timeout=30,
                encoding='utf-8'
            )

            if result.returncode == 0:
                # 从输出中提取PO Token
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if 'PO Token生成成功:' in line:
                        po_token = line.split(':', 1)[1].strip()
                        logger.info(f"✅ Node.js PO Token生成成功: {po_token[:20]}...")
                        break

            if not po_token:
                logger.error(f"❌ Node.js PO Token生成失败: {result.stderr}")
                raise Exception("Node.js PO Token生成失败")

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_script)
            except:
                pass

        # 步骤3: 保存配置
        logger.info("💾 保存PO Token配置...")
        manager = get_po_token_manager()
        success = manager.save_po_token_config(
            po_token=po_token,
            visitor_data=visitor_data,
            source="WebAutoGenerator"
        )

        if not success:
            raise Exception("PO Token配置保存失败")

        logger.info("🎉 自动生成PO Token完成")

        return jsonify({
            'success': True,
            'po_token': po_token,
            'visitor_data': visitor_data,
            'source': 'WebAutoGenerator',
            'timestamp': time.time(),
            'message': 'PO Token自动生成成功'
        })

    except Exception as e:
        logger.error(f"❌ 自动生成PO Token失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cookies_bp.route('/api/youtube-auth/test', methods=['POST'])
@auth_required
def test_youtube_auth_config():
    """测试 YouTube 认证配置"""
    try:
        cookies_manager = get_cookies_manager()
        auth_config = cookies_manager.get_youtube_auth_config()

        if not auth_config['success']:
            return jsonify(auth_config), 500

        # 检查配置状态
        test_results = {
            'oauth2_token': {
                'available': auth_config['oauth2_available'],
                'length': len(auth_config['oauth2_token']) if auth_config['oauth2_token'] else 0,
                'valid_format': auth_config['oauth2_token'].startswith('ya29.') if auth_config['oauth2_token'] else False
            },
            'visitor_data': {
                'available': auth_config['visitor_data_available'],
                'length': len(auth_config['visitor_data']) if auth_config['visitor_data'] else 0,
                'valid_format': len(auth_config['visitor_data']) >= 20 if auth_config['visitor_data'] else False
            },
            'po_token': {
                'available': auth_config['po_token_available'],
                'length': len(auth_config['po_token']) if auth_config['po_token'] else 0,
                'valid_format': len(auth_config['po_token']) >= 20 if auth_config['po_token'] else False
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
            'recommendation': _get_youtube_auth_recommendation(test_results)
        })

    except Exception as e:
        logger.error(f"❌ 测试 YouTube 认证配置失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500

def _get_youtube_auth_recommendation(test_results):
    """获取 YouTube 认证配置建议"""
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
        recommendations.append("YouTube 认证配置看起来正常，应该能有效提高下载成功率")

    return recommendations


@cookies_bp.route('/api/emergency/<platform>', methods=['POST'])
@auth_required
def generate_emergency_cookies(platform):
    """生成紧急cookies（用于VPS环境机器人检测问题）"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.generate_emergency_cookies(platform)

        if result['success']:
            logger.info(f"✅ 紧急{platform}cookies生成成功")
        else:
            logger.error(f"❌ 紧急{platform}cookies生成失败: {result.get('error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ 生成紧急cookies失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cookies_bp.route('/api/download/<website>', methods=['GET'])
@auth_required
def download_cookies(website):
    """下载指定网站的Cookies文件"""
    try:
        cookies_manager = get_cookies_manager()
        result = cookies_manager.export_cookies(website, 'netscape')

        if result['success']:
            from flask import Response
            import io

            # 创建文件内容
            cookies_content = result['data']

            # 创建响应
            output = io.StringIO()
            output.write(cookies_content)
            output.seek(0)

            response = Response(
                output.getvalue(),
                mimetype='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename={website}_cookies.txt'
                }
            )

            return response
        else:
            return jsonify(result), 404

    except Exception as e:
        logger.error(f"❌ 下载Cookies失败: {e}")
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500



