# -*- coding: utf-8 -*-
"""
文件名处理模块

智能文件名生成、清理和管理
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import unicodedata

logger = logging.getLogger(__name__)


class FilenameProcessor:
    """文件名处理器"""
    
    def __init__(self):
        # 文件名清理规则
        self.invalid_chars = r'[<>:"/\\|?*]'
        self.reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        
        # 语言代码映射
        self.language_codes = {
            'zh': '中文', 'zh-CN': '简体中文', 'zh-TW': '繁体中文',
            'en': 'English', 'ja': '日本語', 'ko': '한국어',
            'es': 'Español', 'fr': 'Français', 'de': 'Deutsch',
            'ru': 'Русский', 'ar': 'العربية', 'hi': 'हिन्दी'
        }
        
        # 文件类型映射
        self.file_type_map = {
            'video': ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm'],
            'audio': ['mp3', 'aac', 'wav', 'flac', 'ogg', 'm4a'],
            'subtitle': ['srt', 'vtt', 'ass', 'ssa', 'sub'],
            'thumbnail': ['jpg', 'jpeg', 'png', 'webp'],
            'info': ['json', 'txt', 'xml']
        }
    
    def sanitize_filename(self, filename: str, max_length: int = 80) -> str:
        """清理文件名，确保跨平台兼容"""
        try:
            # 1. Unicode标准化
            filename = unicodedata.normalize('NFKC', filename)
            
            # 2. 移除或替换无效字符
            filename = re.sub(self.invalid_chars, '_', filename)
            
            # 3. 移除控制字符
            filename = ''.join(char for char in filename if ord(char) >= 32)
            
            # 4. 处理连续的空格和下划线
            filename = re.sub(r'[\s_]+', '_', filename)
            
            # 5. 移除开头和结尾的特殊字符
            filename = filename.strip('._- ')
            
            # 6. 检查保留名称
            name_without_ext = Path(filename).stem.upper()
            if name_without_ext in self.reserved_names:
                filename = f"_{filename}"
            
            # 7. 限制长度
            if len(filename) > max_length:
                name = Path(filename).stem
                ext = Path(filename).suffix
                max_name_length = max_length - len(ext)
                if max_name_length > 0:
                    filename = name[:max_name_length] + ext
                else:
                    filename = filename[:max_length]
            
            # 8. 确保不为空
            if not filename or filename in ['.', '..']:
                filename = 'untitled'
            
            return filename
            
        except Exception as e:
            logger.error(f"❌ 文件名清理失败: {e}")
            return 'untitled'
    
    def generate_smart_filename(self, title: str, ext: str, options: Dict[str, Any] = None) -> str:
        """生成智能文件名"""
        try:
            options = options or {}
            
            # 1. 清理标题
            clean_title = self.sanitize_filename(title)
            
            # 2. 添加质量信息
            if options.get('quality'):
                quality = options['quality']
                if quality not in clean_title:
                    clean_title = f"{clean_title}_{quality}"
            
            # 3. 添加语言信息
            if options.get('language'):
                lang = options['language']
                lang_name = self.language_codes.get(lang, lang)
                clean_title = f"{clean_title}_{lang_name}"
            
            # 4. 添加日期（如果需要）
            if options.get('add_date'):
                from datetime import datetime
                date_str = datetime.now().strftime('%Y%m%d')
                clean_title = f"{clean_title}_{date_str}"
            
            # 5. 确保扩展名
            if not ext.startswith('.'):
                ext = f'.{ext}'
            
            filename = f"{clean_title}{ext}"
            
            # 6. 最终清理
            return self.sanitize_filename(filename)
            
        except Exception as e:
            logger.error(f"❌ 智能文件名生成失败: {e}")
            return f"untitled{ext}"
    
    def apply_custom_filename(self, current_file: str, custom_filename: str) -> str:
        """应用自定义文件名"""
        try:
            current_path = Path(current_file)
            
            # 清理自定义文件名
            clean_custom = self.sanitize_filename(custom_filename)
            
            # 如果自定义文件名没有扩展名，使用原文件的扩展名
            if not Path(clean_custom).suffix:
                clean_custom = f"{clean_custom}{current_path.suffix}"
            
            # 构建新路径
            new_path = current_path.parent / clean_custom
            
            # 重命名文件
            if current_path.exists():
                current_path.rename(new_path)
                logger.info(f"✅ 文件重命名: {current_path.name} -> {new_path.name}")
                return str(new_path)
            else:
                logger.warning(f"⚠️ 源文件不存在: {current_file}")
                return current_file
                
        except Exception as e:
            logger.error(f"❌ 应用自定义文件名失败: {e}")
            return current_file
    
    def classify_files(self, files: List[Path]) -> Dict[str, List[Path]]:
        """分类文件"""
        classified = {
            'video': [],
            'audio': [],
            'subtitle': [],
            'thumbnail': [],
            'info': [],
            'other': []
        }
        
        try:
            for file_path in files:
                ext = file_path.suffix.lower().lstrip('.')
                
                # 查找文件类型
                file_type = 'other'
                for type_name, extensions in self.file_type_map.items():
                    if ext in extensions:
                        file_type = type_name
                        break
                
                classified[file_type].append(file_path)
            
            return classified
            
        except Exception as e:
            logger.error(f"❌ 文件分类失败: {e}")
            return classified
    
    def generate_specific_filename(self, base_filename: str, file_path: Path, file_type: str) -> str:
        """为特定类型文件生成文件名"""
        try:
            base_name = Path(base_filename).stem
            original_ext = file_path.suffix
            
            # 根据文件类型添加后缀
            if file_type == 'subtitle':
                # 尝试提取语言代码
                lang_code = self._extract_language_code_from_filename(file_path.name)
                if lang_code:
                    lang_name = self.language_codes.get(lang_code, lang_code)
                    new_name = f"{base_name}.{lang_name}{original_ext}"
                else:
                    new_name = f"{base_name}.subtitle{original_ext}"
            
            elif file_type == 'thumbnail':
                new_name = f"{base_name}.thumbnail{original_ext}"
            
            elif file_type == 'info':
                if original_ext.lower() == '.json':
                    new_name = f"{base_name}.info.json"
                else:
                    new_name = f"{base_name}.info{original_ext}"
            
            elif file_type == 'audio':
                new_name = f"{base_name}.audio{original_ext}"
            
            else:
                new_name = f"{base_name}{original_ext}"
            
            return self.sanitize_filename(new_name)
            
        except Exception as e:
            logger.error(f"❌ 生成特定文件名失败: {e}")
            return file_path.name
    
    def _extract_language_code_from_filename(self, filename: str) -> Optional[str]:
        """从文件名提取语言代码"""
        try:
            # 常见的语言代码模式
            patterns = [
                r'\.([a-z]{2})\.', # .en.
                r'\.([a-z]{2}-[A-Z]{2})\.', # .zh-CN.
                r'_([a-z]{2})_', # _en_
                r'_([a-z]{2}-[A-Z]{2})_', # _zh-CN_
                r'\[([a-z]{2})\]', # [en]
                r'\[([a-z]{2}-[A-Z]{2})\]', # [zh-CN]
            ]
            
            for pattern in patterns:
                match = re.search(pattern, filename, re.IGNORECASE)
                if match:
                    lang_code = match.group(1).lower()
                    # 验证是否是已知的语言代码
                    if lang_code in self.language_codes:
                        return lang_code
            
            return None
            
        except Exception as e:
            logger.debug(f"🔍 语言代码提取失败: {e}")
            return None
    
    def find_related_files(self, download_id: str, base_dir: Path) -> List[Path]:
        """查找相关文件"""
        try:
            related_files = []
            
            # 查找以download_id开头的所有文件
            for file_path in base_dir.glob(f"{download_id}*"):
                if file_path.is_file():
                    related_files.append(file_path)
            
            return related_files
            
        except Exception as e:
            logger.error(f"❌ 查找相关文件失败: {e}")
            return []
    
    def apply_smart_filename_to_all(self, download_id: str, title: str, base_dir: Path) -> Optional[str]:
        """为所有相关文件应用智能文件名"""
        try:
            # 查找所有相关文件
            related_files = self.find_related_files(download_id, base_dir)
            
            if not related_files:
                logger.warning(f"⚠️ 未找到相关文件: {download_id}")
                return None
            
            # 分类文件
            classified = self.classify_files(related_files)
            
            # 生成基础文件名
            base_filename = self.sanitize_filename(title)
            main_file = None
            
            # 处理各类文件
            for file_type, files in classified.items():
                for file_path in files:
                    try:
                        if file_type == 'video' and not main_file:
                            # 主视频文件
                            new_name = f"{base_filename}{file_path.suffix}"
                            new_path = file_path.parent / new_name
                            file_path.rename(new_path)
                            main_file = str(new_path)
                            logger.info(f"✅ 主文件重命名: {file_path.name} -> {new_name}")
                        
                        else:
                            # 其他文件
                            new_name = self.generate_specific_filename(base_filename, file_path, file_type)
                            new_path = file_path.parent / new_name
                            file_path.rename(new_path)
                            logger.info(f"✅ 文件重命名: {file_path.name} -> {new_name}")
                    
                    except Exception as e:
                        logger.error(f"❌ 重命名文件失败 {file_path}: {e}")
                        continue
            
            return main_file
            
        except Exception as e:
            logger.error(f"❌ 批量重命名失败: {e}")
            return None
    
    def get_safe_filename_length(self, directory: str) -> int:
        """获取安全的文件名长度限制"""
        try:
            # 不同文件系统的限制
            import os
            
            # 尝试检测文件系统类型
            if os.name == 'nt':  # Windows
                return 200  # Windows路径限制更严格
            else:  # Unix-like
                return 255  # 大多数Unix文件系统支持255字符
                
        except Exception:
            return 80  # 保守的默认值
    
    def validate_filename(self, filename: str) -> Dict[str, Any]:
        """验证文件名"""
        result = {
            'valid': True,
            'issues': [],
            'suggestions': []
        }
        
        try:
            # 检查长度
            if len(filename) > 255:
                result['valid'] = False
                result['issues'].append('文件名过长')
                result['suggestions'].append('缩短文件名')
            
            # 检查无效字符
            if re.search(self.invalid_chars, filename):
                result['valid'] = False
                result['issues'].append('包含无效字符')
                result['suggestions'].append('移除特殊字符')
            
            # 检查保留名称
            name_without_ext = Path(filename).stem.upper()
            if name_without_ext in self.reserved_names:
                result['valid'] = False
                result['issues'].append('使用了系统保留名称')
                result['suggestions'].append('更改文件名')
            
            # 检查空文件名
            if not filename.strip():
                result['valid'] = False
                result['issues'].append('文件名为空')
                result['suggestions'].append('提供有效的文件名')
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 文件名验证失败: {e}")
            return {
                'valid': False,
                'issues': ['验证过程出错'],
                'suggestions': ['使用默认文件名']
            }
