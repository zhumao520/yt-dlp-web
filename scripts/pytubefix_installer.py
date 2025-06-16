# -*- coding: utf-8 -*-
"""
PyTubeFix安装器 - 自动下载和安装PyTubeFix
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class PyTubeFixInstaller:
    """PyTubeFix自动安装器"""
    
    def __init__(self):
        self.package_name = 'pytubefix'
        
    def ensure_pytubefix(self, force_update=False) -> bool:
        """确保PyTubeFix可用"""
        try:
            # 如果强制更新，跳过可用性检查
            if not force_update:
                # 检查是否已经可用
                if self._check_pytubefix_available():
                    logger.info("✅ PyTubeFix已可用")
                    return True
            else:
                logger.info("🔄 强制更新PyTubeFix...")

            # 使用pip安装/更新
            return self._install_from_pip(force_update)

        except Exception as e:
            logger.error(f"❌ PyTubeFix安装失败: {e}")
            return False

    def update_pytubefix(self) -> bool:
        """更新PyTubeFix到最新版本"""
        return self.ensure_pytubefix(force_update=True)
    
    def _check_pytubefix_available(self) -> bool:
        """检查PyTubeFix是否可用"""
        try:
            import pytubefix
            logger.debug("✅ PyTubeFix模块导入成功")
            return True
        except ImportError:
            logger.debug("⚠️ PyTubeFix模块未找到")
            return False
    
    def _install_from_pip(self, force_update=False) -> bool:
        """使用pip安装"""
        try:
            if force_update:
                logger.info("📦 使用pip强制更新PyTubeFix...")
                cmd = [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-cache-dir",
                    "--upgrade",
                    "--force-reinstall",
                    self.package_name,
                ]
            else:
                logger.info("📦 使用pip安装PyTubeFix...")
                cmd = [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-cache-dir",
                    "--upgrade",
                    self.package_name,
                ]

            # 尝试pip安装
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                logger.info("✅ pip安装成功")
                return self._check_pytubefix_available()
            else:
                logger.error(f"❌ pip安装失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ pip安装异常: {e}")
            return False
    
    def get_pytubefix_info(self) -> Optional[Dict[str, Any]]:
        """获取PyTubeFix信息"""
        try:
            if not self._check_pytubefix_available():
                return None

            import pytubefix

            # 获取版本信息
            version = self._get_pytubefix_version()

            # 获取模块路径
            module_path = getattr(pytubefix, '__file__', 'unknown')

            return {
                'version': version,
                'module_path': module_path,
                'available': True,
                'package_name': self.package_name
            }

        except Exception as e:
            logger.error(f"❌ 获取PyTubeFix信息失败: {e}")
            return None

    def _get_pytubefix_version(self) -> str:
        """获取PyTubeFix版本"""
        try:
            # 方法1: 使用importlib.metadata (推荐的现代方法)
            try:
                import importlib.metadata
                version = importlib.metadata.version(self.package_name)
                if version:
                    logger.debug(f"通过 importlib.metadata 获取版本: {version}")
                    return str(version)
            except:
                pass

            # 方法2: 使用pkg_resources (兼容性备用)
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    import pkg_resources
                    version = pkg_resources.get_distribution(self.package_name).version
                    if version:
                        logger.debug(f"通过 pkg_resources 获取版本: {version}")
                        return str(version)
            except:
                pass

            # 方法3: 执行命令行获取版本
            try:
                import subprocess
                result = subprocess.run(['python', '-c', f'import {self.package_name}; print({self.package_name}.__version__)'],
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    version = result.stdout.strip()
                    logger.debug(f"通过命令行获取版本: {version}")
                    return str(version)
            except:
                pass

            # 方法4: 检查 __version__ 属性
            try:
                import pytubefix
                if hasattr(pytubefix, '__version__'):
                    version = str(pytubefix.__version__)
                    if version and version != 'unknown':
                        logger.debug(f"通过 __version__ 获取版本: {version}")
                        return version
            except:
                pass

            logger.warning("⚠️ 无法获取PyTubeFix版本信息")
            return "已安装 (版本未知)"

        except Exception as e:
            logger.error(f"❌ 获取PyTubeFix版本失败: {e}")
            return "检测失败"
    
    def test_pytubefix(self, test_url: str = "https://www.youtube.com/watch?v=JSuBGTyiJ78") -> bool:
        """测试PyTubeFix功能"""
        try:
            if not self._check_pytubefix_available():
                logger.error("❌ PyTubeFix不可用")
                return False

            from pytubefix import YouTube
            
            logger.info(f"🧪 测试PyTubeFix功能: {test_url}")
            
            # 创建YouTube对象
            yt = YouTube(test_url)
            
            # 获取基本信息
            title = yt.title
            duration = yt.length
            
            if title and duration:
                logger.info(f"✅ PyTubeFix测试成功: {title} ({duration}秒)")
                return True
            else:
                logger.error("❌ PyTubeFix测试失败: 无法获取视频信息")
                return False

        except Exception as e:
            logger.error(f"❌ PyTubeFix测试异常: {e}")
            return False


if __name__ == '__main__':
    # 测试安装器
    logging.basicConfig(level=logging.INFO)
    
    installer = PyTubeFixInstaller()
    
    print("🔧 开始安装PyTubeFix...")
    success = installer.ensure_pytubefix()
    
    if success:
        print("✅ PyTubeFix安装成功")
        info = installer.get_pytubefix_info()
        if info:
            print(f"版本: {info['version']}")
            print(f"路径: {info['module_path']}")
        
        # 测试功能
        print("🧪 测试PyTubeFix功能...")
        test_success = installer.test_pytubefix()
        if test_success:
            print("✅ PyTubeFix功能测试成功")
        else:
            print("❌ PyTubeFix功能测试失败")
    else:
        print("❌ PyTubeFix安装失败")
