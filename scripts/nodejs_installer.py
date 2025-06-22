#!/usr/bin/env python3
"""
Node.js自动安装脚本
用于在没有Node.js的环境中自动安装Node.js，以支持PO Token自动生成功能
"""

import os
import sys
import subprocess
import platform
import logging
import tempfile
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

class NodeJSInstaller:
    """Node.js自动安装器"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        self.is_docker = os.environ.get('DOCKER_CONTAINER') == '1'
        
    def is_nodejs_available(self) -> bool:
        """检查Node.js是否已安装"""
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"✅ 检测到Node.js: {version}")
                return True
            return False
        except Exception:
            return False
    
    def install_nodejs(self, caller_name: str = "Unknown") -> bool:
        """
        自动安装Node.js
        
        Args:
            caller_name: 调用者名称
            
        Returns:
            是否安装成功
        """
        try:
            logger.info(f"🚀 {caller_name} 开始自动安装Node.js")
            
            if self.is_nodejs_available():
                logger.info(f"✅ {caller_name} Node.js已存在，跳过安装")
                return True
            
            if self.system == 'linux':
                return self._install_linux(caller_name)
            elif self.system == 'windows':
                return self._install_windows(caller_name)
            elif self.system == 'darwin':  # macOS
                return self._install_macos(caller_name)
            else:
                logger.error(f"❌ {caller_name} 不支持的操作系统: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"❌ {caller_name} Node.js安装失败: {e}")
            return False
    
    def _install_linux(self, caller_name: str) -> bool:
        """在Linux系统上安装Node.js"""
        try:
            logger.info(f"🐧 {caller_name} 在Linux系统上安装Node.js")
            
            # 检查是否有root权限
            if os.geteuid() != 0 and not self.is_docker:
                logger.warning(f"⚠️ {caller_name} 需要root权限安装Node.js")
                return self._install_nodejs_portable(caller_name)
            
            # 检测Linux发行版
            if self._has_command('apt-get'):
                return self._install_debian_ubuntu(caller_name)
            elif self._has_command('yum') or self._has_command('dnf'):
                return self._install_redhat_centos(caller_name)
            elif self._has_command('pacman'):
                return self._install_arch(caller_name)
            else:
                logger.warning(f"⚠️ {caller_name} 未知Linux发行版，尝试便携式安装")
                return self._install_nodejs_portable(caller_name)
                
        except Exception as e:
            logger.error(f"❌ {caller_name} Linux Node.js安装失败: {e}")
            return False
    
    def _install_debian_ubuntu(self, caller_name: str) -> bool:
        """在Debian/Ubuntu上安装Node.js"""
        try:
            logger.info(f"📦 {caller_name} 使用apt安装Node.js")
            
            # 添加NodeSource仓库
            commands = [
                ['curl', '-fsSL', 'https://deb.nodesource.com/setup_lts.x', '-o', '/tmp/nodesource_setup.sh'],
                ['bash', '/tmp/nodesource_setup.sh'],
                ['apt-get', 'update'],
                ['apt-get', 'install', '-y', 'nodejs']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    logger.error(f"❌ {caller_name} 命令失败: {' '.join(cmd)}")
                    logger.error(f"   错误: {result.stderr}")
                    return False
            
            # 验证安装
            if self.is_nodejs_available():
                logger.info(f"✅ {caller_name} Node.js安装成功")
                return True
            else:
                logger.error(f"❌ {caller_name} Node.js安装验证失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ {caller_name} Debian/Ubuntu Node.js安装失败: {e}")
            return False
    
    def _install_redhat_centos(self, caller_name: str) -> bool:
        """在RedHat/CentOS上安装Node.js"""
        try:
            logger.info(f"📦 {caller_name} 使用yum/dnf安装Node.js")
            
            # 选择包管理器
            pkg_manager = 'dnf' if self._has_command('dnf') else 'yum'
            
            commands = [
                ['curl', '-fsSL', 'https://rpm.nodesource.com/setup_lts.x', '-o', '/tmp/nodesource_setup.sh'],
                ['bash', '/tmp/nodesource_setup.sh'],
                [pkg_manager, 'install', '-y', 'nodejs', 'npm']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    logger.error(f"❌ {caller_name} 命令失败: {' '.join(cmd)}")
                    return False
            
            return self.is_nodejs_available()
            
        except Exception as e:
            logger.error(f"❌ {caller_name} RedHat/CentOS Node.js安装失败: {e}")
            return False
    
    def _install_arch(self, caller_name: str) -> bool:
        """在Arch Linux上安装Node.js"""
        try:
            logger.info(f"📦 {caller_name} 使用pacman安装Node.js")
            
            commands = [
                ['pacman', '-Sy', '--noconfirm', 'nodejs', 'npm']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    logger.error(f"❌ {caller_name} 命令失败: {' '.join(cmd)}")
                    return False
            
            return self.is_nodejs_available()
            
        except Exception as e:
            logger.error(f"❌ {caller_name} Arch Linux Node.js安装失败: {e}")
            return False
    
    def _install_nodejs_portable(self, caller_name: str) -> bool:
        """便携式Node.js安装（无需root权限）"""
        try:
            logger.info(f"📁 {caller_name} 便携式安装Node.js")
            
            # 确定架构
            if self.arch in ['x86_64', 'amd64']:
                arch = 'x64'
            elif self.arch in ['aarch64', 'arm64']:
                arch = 'arm64'
            else:
                logger.error(f"❌ {caller_name} 不支持的架构: {self.arch}")
                return False
            
            # 下载Node.js
            version = "v18.19.0"  # LTS版本
            filename = f"node-{version}-linux-{arch}.tar.xz"
            url = f"https://nodejs.org/dist/{version}/{filename}"
            
            # 创建安装目录
            install_dir = Path.home() / '.local' / 'nodejs'
            install_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载和解压
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = Path(temp_dir) / filename
                
                logger.info(f"📥 {caller_name} 下载Node.js: {url}")
                result = subprocess.run(['curl', '-L', '-o', str(temp_file), url], 
                                      capture_output=True, text=True, timeout=600)
                
                if result.returncode != 0:
                    logger.error(f"❌ {caller_name} 下载失败: {result.stderr}")
                    return False
                
                logger.info(f"📦 {caller_name} 解压Node.js到: {install_dir}")
                result = subprocess.run(['tar', '-xf', str(temp_file), '-C', str(install_dir), '--strip-components=1'],
                                      capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    logger.error(f"❌ {caller_name} 解压失败: {result.stderr}")
                    return False
            
            # 添加到PATH
            node_bin = install_dir / 'bin'
            current_path = os.environ.get('PATH', '')
            if str(node_bin) not in current_path:
                os.environ['PATH'] = f"{node_bin}:{current_path}"
                logger.info(f"✅ {caller_name} 已添加Node.js到PATH: {node_bin}")
            
            return self.is_nodejs_available()
            
        except Exception as e:
            logger.error(f"❌ {caller_name} 便携式Node.js安装失败: {e}")
            return False
    
    def _install_windows(self, caller_name: str) -> bool:
        """在Windows上安装Node.js"""
        logger.warning(f"⚠️ {caller_name} Windows自动安装暂未实现")
        logger.info(f"💡 {caller_name} 请手动下载安装: https://nodejs.org/")
        return False
    
    def _install_macos(self, caller_name: str) -> bool:
        """在macOS上安装Node.js"""
        logger.warning(f"⚠️ {caller_name} macOS自动安装暂未实现")
        logger.info(f"💡 {caller_name} 请使用Homebrew: brew install node")
        return False
    
    def _has_command(self, command: str) -> bool:
        """检查命令是否存在"""
        return shutil.which(command) is not None

# 便捷函数
def install_nodejs_if_needed(caller_name: str = "Unknown") -> bool:
    """如果需要则安装Node.js的便捷函数"""
    installer = NodeJSInstaller()
    
    if installer.is_nodejs_available():
        return True
    
    logger.info(f"🔧 {caller_name} Node.js不可用，尝试自动安装...")
    return installer.install_nodejs(caller_name)

def check_nodejs_status() -> dict:
    """检查Node.js状态"""
    installer = NodeJSInstaller()
    
    status = {
        'available': installer.is_nodejs_available(),
        'system': installer.system,
        'arch': installer.arch,
        'is_docker': installer.is_docker
    }
    
    if status['available']:
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            status['version'] = result.stdout.strip()
        except:
            status['version'] = 'unknown'
    
    return status

if __name__ == "__main__":
    # 测试脚本
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🧪 Node.js安装器测试")
    status = check_nodejs_status()
    print(f"状态: {status}")
    
    if not status['available']:
        print("🚀 尝试安装Node.js...")
        success = install_nodejs_if_needed("TestScript")
        print(f"安装结果: {'成功' if success else '失败'}")
    else:
        print("✅ Node.js已可用")
