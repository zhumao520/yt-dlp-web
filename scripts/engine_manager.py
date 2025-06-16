# -*- coding: utf-8 -*-
"""
统一引擎管理器 - 管理所有下载引擎的安装和更新
"""

import logging
from typing import Dict, Any, List

try:
    from .ytdlp_installer import YtdlpInstaller
    from .pytubefix_installer import PyTubeFixInstaller
except ImportError:
    # 当作为独立脚本运行时
    from ytdlp_installer import YtdlpInstaller
    from pytubefix_installer import PyTubeFixInstaller

logger = logging.getLogger(__name__)


class EngineManager:
    """统一引擎管理器"""
    
    def __init__(self):
        self.ytdlp_installer = YtdlpInstaller()
        self.pytubefix_installer = PyTubeFixInstaller()
        
        self.engines = {
            'ytdlp': {
                'name': 'yt-dlp',
                'installer': self.ytdlp_installer,
                'description': '多平台视频下载器，支持1000+网站'
            },
            'pytubefix': {
                'name': 'PyTubeFix',
                'installer': self.pytubefix_installer,
                'description': 'YouTube专用下载器，网页解析技术'
            }
        }
    
    def get_all_engines_status(self) -> Dict[str, Any]:
        """获取所有引擎状态"""
        status = {}
        
        for engine_id, engine_info in self.engines.items():
            try:
                installer = engine_info['installer']
                
                if engine_id == 'ytdlp':
                    info = installer.get_ytdlp_info()
                elif engine_id == 'pytubefix':
                    info = installer.get_pytubefix_info()
                else:
                    info = None
                
                if info:
                    status[engine_id] = {
                        'name': engine_info['name'],
                        'description': engine_info['description'],
                        'available': info.get('available', False),
                        'version': info.get('version', 'unknown'),
                        'module_path': info.get('module_path', 'unknown'),
                        'status': 'installed' if info.get('available') else 'not_installed'
                    }
                else:
                    status[engine_id] = {
                        'name': engine_info['name'],
                        'description': engine_info['description'],
                        'available': False,
                        'version': 'unknown',
                        'module_path': 'unknown',
                        'status': 'not_installed'
                    }
                    
            except Exception as e:
                logger.error(f"❌ 获取引擎 {engine_id} 状态失败: {e}")
                status[engine_id] = {
                    'name': engine_info['name'],
                    'description': engine_info['description'],
                    'available': False,
                    'version': 'error',
                    'module_path': 'error',
                    'status': 'error',
                    'error': str(e)
                }
        
        return status
    
    def update_all_engines(self) -> Dict[str, Any]:
        """更新所有引擎"""
        results = {}
        
        logger.info("🔄 开始更新所有下载引擎...")
        
        for engine_id, engine_info in self.engines.items():
            try:
                logger.info(f"🔄 更新 {engine_info['name']}...")
                installer = engine_info['installer']
                
                if engine_id == 'ytdlp':
                    success = installer.update_ytdlp()
                elif engine_id == 'pytubefix':
                    success = installer.update_pytubefix()
                else:
                    success = False
                
                results[engine_id] = {
                    'name': engine_info['name'],
                    'success': success,
                    'message': '更新成功' if success else '更新失败'
                }
                
                if success:
                    logger.info(f"✅ {engine_info['name']} 更新成功")
                else:
                    logger.error(f"❌ {engine_info['name']} 更新失败")
                    
            except Exception as e:
                logger.error(f"❌ 更新引擎 {engine_id} 异常: {e}")
                results[engine_id] = {
                    'name': engine_info['name'],
                    'success': False,
                    'message': f'更新异常: {str(e)}',
                    'error': str(e)
                }
        
        # 统计结果
        successful_count = sum(1 for result in results.values() if result['success'])
        total_count = len(results)
        
        logger.info(f"📊 引擎更新完成: {successful_count}/{total_count} 成功")
        
        return {
            'results': results,
            'summary': {
                'total': total_count,
                'successful': successful_count,
                'failed': total_count - successful_count,
                'success_rate': successful_count / total_count if total_count > 0 else 0
            }
        }
    
    def install_all_engines(self) -> Dict[str, Any]:
        """安装所有引擎"""
        results = {}
        
        logger.info("📦 开始安装所有下载引擎...")
        
        for engine_id, engine_info in self.engines.items():
            try:
                logger.info(f"📦 安装 {engine_info['name']}...")
                installer = engine_info['installer']
                
                if engine_id == 'ytdlp':
                    success = installer.ensure_ytdlp(force_update=True)
                elif engine_id == 'pytubefix':
                    success = installer.ensure_pytubefix(force_update=True)
                else:
                    success = False
                
                results[engine_id] = {
                    'name': engine_info['name'],
                    'success': success,
                    'message': '安装成功' if success else '安装失败'
                }
                
                if success:
                    logger.info(f"✅ {engine_info['name']} 安装成功")
                else:
                    logger.error(f"❌ {engine_info['name']} 安装失败")
                    
            except Exception as e:
                logger.error(f"❌ 安装引擎 {engine_id} 异常: {e}")
                results[engine_id] = {
                    'name': engine_info['name'],
                    'success': False,
                    'message': f'安装异常: {str(e)}',
                    'error': str(e)
                }
        
        # 统计结果
        successful_count = sum(1 for result in results.values() if result['success'])
        total_count = len(results)
        
        logger.info(f"📊 引擎安装完成: {successful_count}/{total_count} 成功")
        
        return {
            'results': results,
            'summary': {
                'total': total_count,
                'successful': successful_count,
                'failed': total_count - successful_count,
                'success_rate': successful_count / total_count if total_count > 0 else 0
            }
        }
    
    def get_engine_info(self, engine_id: str) -> Dict[str, Any]:
        """获取指定引擎信息"""
        if engine_id not in self.engines:
            return {
                'error': 'engine_not_found',
                'message': f'引擎 {engine_id} 不存在'
            }
        
        try:
            engine_info = self.engines[engine_id]
            installer = engine_info['installer']
            
            if engine_id == 'ytdlp':
                info = installer.get_ytdlp_info()
            elif engine_id == 'pytubefix':
                info = installer.get_pytubefix_info()
            else:
                info = None
            
            if info:
                return {
                    'name': engine_info['name'],
                    'description': engine_info['description'],
                    **info
                }
            else:
                return {
                    'name': engine_info['name'],
                    'description': engine_info['description'],
                    'available': False,
                    'version': 'unknown',
                    'error': '无法获取引擎信息'
                }
                
        except Exception as e:
            logger.error(f"❌ 获取引擎 {engine_id} 信息失败: {e}")
            return {
                'error': 'info_failed',
                'message': f'获取引擎信息失败: {str(e)}'
            }
    
    def update_engine(self, engine_id: str) -> Dict[str, Any]:
        """更新指定引擎"""
        if engine_id not in self.engines:
            return {
                'success': False,
                'error': 'engine_not_found',
                'message': f'引擎 {engine_id} 不存在'
            }
        
        try:
            engine_info = self.engines[engine_id]
            installer = engine_info['installer']
            
            logger.info(f"🔄 更新 {engine_info['name']}...")
            
            if engine_id == 'ytdlp':
                success = installer.update_ytdlp()
            elif engine_id == 'pytubefix':
                success = installer.update_pytubefix()
            else:
                success = False
            
            result = {
                'name': engine_info['name'],
                'success': success,
                'message': '更新成功' if success else '更新失败'
            }
            
            if success:
                logger.info(f"✅ {engine_info['name']} 更新成功")
            else:
                logger.error(f"❌ {engine_info['name']} 更新失败")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 更新引擎 {engine_id} 异常: {e}")
            return {
                'name': self.engines[engine_id]['name'],
                'success': False,
                'message': f'更新异常: {str(e)}',
                'error': str(e)
            }
    
    def get_supported_engines(self) -> List[str]:
        """获取支持的引擎列表"""
        return list(self.engines.keys())


if __name__ == '__main__':
    # 测试引擎管理器
    logging.basicConfig(level=logging.INFO)
    
    manager = EngineManager()
    
    print("📊 获取所有引擎状态...")
    status = manager.get_all_engines_status()
    for engine_id, info in status.items():
        print(f"{info['name']}: {info['status']} (v{info['version']})")
    
    print("\n🔄 更新所有引擎...")
    result = manager.update_all_engines()
    print(f"更新结果: {result['summary']['successful']}/{result['summary']['total']} 成功")
