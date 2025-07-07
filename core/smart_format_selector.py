#!/usr/bin/env python3
"""
智能格式选择器
将用户的简单质量选择（4K、1080p、720p）映射到具体的格式ID
实现动态格式检测和智能降级机制
"""

import logging
from typing import Dict, List, Optional, Tuple
import yt_dlp

logger = logging.getLogger(__name__)

class SmartFormatSelector:
    """智能格式选择器"""
    
    def __init__(self):
        # 编解码器质量评分 (分数越高越好)
        self.codec_scores = {
            # 视频编解码器评分
            'av01': 100,      # AV1 - 最新最高效
            'vp9.2': 90,      # VP9.2 HDR - 高质量HDR
            'vp9': 85,        # VP9 - 高效现代编解码器
            'avc1': 70,       # H.264 - 兼容性好但效率较低
            'vp09': 95,       # VP9变种 - 高质量

            # 音频编解码器评分
            'opus': 95,       # Opus - 最高效音频编解码器
            'mp4a.40.2': 80,  # AAC - 广泛兼容
            'mp4a': 80,       # AAC变种
        }

        # 容器格式评分
        self.container_scores = {
            'mp4': 90,        # MP4 - 最佳兼容性
            'webm': 85,       # WebM - 现代高效
            'm4a': 80,        # M4A - 音频容器
        }

        # 用户友好的质量级别配置（移除固定优先级，改为动态选择）
        self.quality_mappings = {
            '4k': {
                'description': '4K (2160p)',
                'min_height': 2160,
                'prefer_codecs': ['av01', 'vp9', 'vp09'],  # 优选编解码器
                'prefer_containers': ['mp4', 'webm']       # 优选容器
            },
            '1080p': {
                'description': '1080p Full HD',
                'min_height': 1080,
                'prefer_codecs': ['av01', 'vp9', 'avc1'],
                'prefer_containers': ['mp4', 'webm']
            },
            '720p': {
                'description': '720p HD',
                'min_height': 720,
                'prefer_codecs': ['av01', 'vp9', 'avc1'],
                'prefer_containers': ['mp4', 'webm']
            },
            '480p': {
                'description': '480p',
                'min_height': 480,
                'prefer_codecs': ['avc1', 'vp9'],
                'prefer_containers': ['mp4', 'webm']
            },
            '360p': {
                'description': '360p',
                'min_height': 360,
                'prefer_codecs': ['avc1'],
                'prefer_containers': ['mp4']
            },
            'best': {
                'description': '最佳质量',
                'min_height': 0,
                'prefer_codecs': ['av01', 'vp9', 'avc1'],
                'prefer_containers': ['mp4', 'webm']
            }
        }

        # 降级顺序
        self.fallback_order = ['4k', '1080p', '720p', '480p', '360p']
    
    def get_available_formats(self, url: str, proxy: str = None) -> Dict:
        """获取视频的可用格式列表"""
        try:
            # 配置yt-dlp只获取格式信息
            opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            if proxy:
                opts['proxy'] = proxy
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    formats = info.get('formats', [])
                    
                    # 解析格式信息
                    parsed_formats = self._parse_formats(formats)
                    
                    logger.info(f"📊 解析到 {len(formats)} 个格式")
                    logger.debug(f"   4K格式: {len(parsed_formats['4k'])} 个")
                    logger.debug(f"   1080p格式: {len(parsed_formats['1080p'])} 个")
                    logger.debug(f"   720p格式: {len(parsed_formats['720p'])} 个")
                    
                    return {
                        'success': True,
                        'formats': parsed_formats,
                        'total_count': len(formats)
                    }
                else:
                    return {'success': False, 'error': '无法获取视频信息'}
                    
        except Exception as e:
            logger.error(f"❌ 获取格式列表失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _parse_formats(self, formats: List[Dict]) -> Dict:
        """解析格式列表，按质量分类"""
        parsed = {
            '4k': [],
            '1080p': [],
            '720p': [],
            '480p': [],
            '360p': [],
            'audio': []
        }
        
        for fmt in formats:
            format_id = fmt.get('format_id', '')
            height = fmt.get('height', 0)
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            ext = fmt.get('ext', '')
            filesize = fmt.get('filesize', 0)
            
            format_info = {
                'id': format_id,
                'height': height,
                'ext': ext,
                'vcodec': vcodec,
                'acodec': acodec,
                'filesize': filesize,
                'note': fmt.get('format_note', '')
            }
            
            # 分类格式
            if vcodec != 'none' and height > 0:  # 视频格式
                if height >= 2160:
                    parsed['4k'].append(format_info)
                elif height >= 1080:
                    parsed['1080p'].append(format_info)
                elif height >= 720:
                    parsed['720p'].append(format_info)
                elif height >= 480:
                    parsed['480p'].append(format_info)
                elif height >= 360:
                    parsed['360p'].append(format_info)
            elif acodec != 'none':  # 音频格式
                parsed['audio'].append(format_info)
        
        return parsed
    
    def select_best_format(self, user_quality: str, available_formats: Dict) -> Tuple[str, str]:
        """
        根据用户选择的质量和可用格式，选择最佳格式ID
        
        Args:
            user_quality: 用户选择的质量 ('4k', '1080p', '720p', etc.)
            available_formats: 可用格式字典
            
        Returns:
            Tuple[format_id, reason]: (格式ID, 选择原因)
        """
        try:
            # 标准化用户输入
            normalized_quality = self._normalize_quality(user_quality)
            
            logger.info(f"🎯 用户选择质量: {user_quality} -> {normalized_quality}")
            
            # 首先尝试用户请求的质量
            format_id, reason = self._try_quality_level(normalized_quality, available_formats)
            if format_id:
                return format_id, reason
            
            # 如果用户请求的质量不可用，实施智能降级
            logger.info(f"🔄 {normalized_quality} 不可用，开始智能降级")
            
            # 找到用户请求质量在降级顺序中的位置
            try:
                start_index = self.fallback_order.index(normalized_quality)
            except ValueError:
                start_index = 0  # 如果不在列表中，从最高质量开始
            
            # 从用户请求的质量开始向下降级
            for quality in self.fallback_order[start_index + 1:]:
                format_id, reason = self._try_quality_level(quality, available_formats)
                if format_id:
                    return format_id, f"降级到{quality}: {reason}"
            
            # 如果所有降级都失败，使用平台无关的通用格式选择器
            logger.warning(f"⚠️ 所有质量级别都不可用，使用通用格式选择器")
            return 'best/worst', '降级到通用格式选择器'

        except Exception as e:
            logger.error(f"❌ 格式选择失败: {e}")
            return 'best/worst', f'错误降级，使用通用格式: {str(e)}'
    
    def _normalize_quality(self, user_quality: str) -> str:
        """标准化用户输入的质量选择"""
        quality_lower = user_quality.lower().strip()
        
        # 处理各种用户输入
        quality_map = {
            '4k': '4k',
            '2160p': '4k',
            '2160': '4k',
            'uhd': '4k',
            'ultra': '4k',
            
            '1080p': '1080p',
            '1080': '1080p',
            'fhd': '1080p',
            'full': '1080p',
            'high': '1080p',
            
            '720p': '720p',
            '720': '720p',
            'hd': '720p',
            'medium': '720p',
            
            '480p': '480p',
            '480': '480p',
            'sd': '480p',
            
            '360p': '360p',
            '360': '360p',
            'low': '360p',
            
            'best': 'best',
            'worst': '360p',
            'auto': 'best'
        }
        
        return quality_map.get(quality_lower, '720p')  # 默认720p
    
    def _try_quality_level(self, quality: str, available_formats: Dict) -> Tuple[Optional[str], str]:
        """尝试特定质量级别的格式，使用智能评分选择最佳格式"""
        if quality not in self.quality_mappings:
            return None, f"不支持的质量级别: {quality}"

        quality_config = self.quality_mappings[quality]

        # 获取该质量级别的可用格式
        available_in_quality = available_formats['formats'].get(quality, [])

        if not available_in_quality:
            return None, f"{quality_config['description']} 格式不可用"

        # 智能选择最佳格式
        best_format = self._select_best_format(available_in_quality, available_formats['formats'].get('audio', []), quality_config)

        if best_format:
            return best_format['format_id'], f"{quality_config['description']} - 最佳格式: {best_format['format_id']} (评分: {best_format['score']:.1f})"

        return None, f"{quality_config['description']} 无可用格式"

    def _select_best_format(self, video_formats: List[Dict], audio_formats: List[Dict], quality_config: Dict) -> Optional[Dict]:
        """智能选择最佳格式组合"""
        best_combination = None
        best_score = 0

        logger.debug(f"🔍 评估 {len(video_formats)} 个视频格式")

        for video_fmt in video_formats:
            # 评估视频格式
            video_score = self._evaluate_video_format(video_fmt, quality_config)

            # 如果是组合格式（已包含音频），直接评估
            if video_fmt.get('acodec', 'none') != 'none':
                total_score = video_score
                format_id = video_fmt['id']

                logger.debug(f"   组合格式 {format_id}: 评分 {total_score:.1f}")

                if total_score > best_score:
                    best_score = total_score
                    best_combination = {
                        'format_id': format_id,
                        'score': total_score,
                        'type': 'combined'
                    }
            else:
                # 纯视频格式，需要配对音频
                for audio_fmt in audio_formats:
                    audio_score = self._evaluate_audio_format(audio_fmt)
                    total_score = video_score + audio_score
                    format_id = f"{video_fmt['id']}+{audio_fmt['id']}"

                    logger.debug(f"   组合 {format_id}: 视频{video_score:.1f} + 音频{audio_score:.1f} = {total_score:.1f}")

                    if total_score > best_score:
                        best_score = total_score
                        best_combination = {
                            'format_id': format_id,
                            'score': total_score,
                            'type': 'video+audio'
                        }

        if best_combination:
            logger.info(f"🏆 最佳格式选择: {best_combination['format_id']} (评分: {best_combination['score']:.1f})")

        return best_combination

    def _evaluate_video_format(self, video_fmt: Dict, quality_config: Dict) -> float:
        """评估视频格式质量"""
        score = 0.0

        # 1. 编解码器评分 (40%)
        vcodec = video_fmt.get('vcodec', '').lower()
        codec_score = 0
        for codec, codec_score_val in self.codec_scores.items():
            if codec in vcodec:
                codec_score = codec_score_val
                break
        score += codec_score * 0.4

        # 2. 容器格式评分 (20%)
        ext = video_fmt.get('ext', '').lower()
        container_score = self.container_scores.get(ext, 50)
        score += container_score * 0.2

        # 3. 文件大小评分 (20%) - 适中的文件大小更好
        filesize = video_fmt.get('filesize', 0)
        if filesize > 0:
            # 根据分辨率调整期望文件大小
            height = video_fmt.get('height', 720)
            expected_size = height * height * 0.001  # 简单的大小估算
            size_ratio = filesize / (expected_size * 1024 * 1024)  # 转换为MB

            # 文件大小在0.5-2倍期望大小之间得分最高
            if 0.5 <= size_ratio <= 2.0:
                size_score = 100
            elif size_ratio < 0.5:
                size_score = size_ratio * 200  # 太小扣分
            else:
                size_score = max(0, 100 - (size_ratio - 2) * 20)  # 太大扣分
        else:
            size_score = 50  # 未知大小给中等分数
        score += size_score * 0.2

        # 4. 帧率评分 (10%)
        fps = video_fmt.get('fps', 30)
        if fps >= 60:
            fps_score = 100
        elif fps >= 30:
            fps_score = 80
        else:
            fps_score = 60
        score += fps_score * 0.1

        # 5. 偏好编解码器加分 (10%)
        prefer_codecs = quality_config.get('prefer_codecs', [])
        preference_score = 0
        for i, preferred_codec in enumerate(prefer_codecs):
            if preferred_codec in vcodec:
                preference_score = 100 - i * 10  # 越靠前分数越高
                break
        score += preference_score * 0.1

        logger.debug(f"      视频格式 {video_fmt['id']}: 编解码器{codec_score} 容器{container_score} 大小{size_score:.1f} 帧率{fps_score} 偏好{preference_score} = {score:.1f}")

        return score

    def _evaluate_audio_format(self, audio_fmt: Dict) -> float:
        """评估音频格式质量"""
        score = 0.0

        # 1. 音频编解码器评分 (60%)
        acodec = audio_fmt.get('acodec', '').lower()
        codec_score = 0
        for codec, codec_score_val in self.codec_scores.items():
            if codec in acodec:
                codec_score = codec_score_val
                break
        score += codec_score * 0.6

        # 2. 容器格式评分 (20%)
        ext = audio_fmt.get('ext', '').lower()
        container_score = self.container_scores.get(ext, 50)
        score += container_score * 0.2

        # 3. 比特率评分 (20%)
        tbr = audio_fmt.get('tbr', 0)
        if tbr >= 128:
            bitrate_score = 100
        elif tbr >= 96:
            bitrate_score = 80
        elif tbr >= 64:
            bitrate_score = 60
        else:
            bitrate_score = 40
        score += bitrate_score * 0.2

        logger.debug(f"      音频格式 {audio_fmt['id']}: 编解码器{codec_score} 容器{container_score} 比特率{bitrate_score} = {score:.1f}")

        return score
    
    def _is_format_available(self, format_id: str, available_formats: List[Dict]) -> bool:
        """检查格式ID是否在可用格式中"""
        if '+' in format_id:
            # 组合格式，检查视频和音频部分
            video_id, audio_id = format_id.split('+', 1)
            
            # 检查视频部分
            video_available = any(fmt['id'] == video_id for fmt in available_formats)
            
            # 检查音频部分（在所有格式中查找）
            # 这里简化处理，假设常见音频格式可用
            common_audio = ['140', '251', '249', '250']
            audio_available = audio_id in common_audio
            
            return video_available and audio_available
        else:
            # 单一格式
            return any(fmt['id'] == format_id for fmt in available_formats)
    
    def get_format_info(self, format_id: str) -> Dict:
        """获取格式ID的详细信息"""
        # 解析格式ID
        if '+' in format_id:
            video_id, audio_id = format_id.split('+', 1)
            return {
                'type': 'combined',
                'video_id': video_id,
                'audio_id': audio_id,
                'description': f"视频格式{video_id} + 音频格式{audio_id}"
            }
        else:
            return {
                'type': 'single',
                'format_id': format_id,
                'description': f"单一格式{format_id}"
            }

# 全局实例
_smart_format_selector = None

def get_smart_format_selector() -> SmartFormatSelector:
    """获取智能格式选择器实例"""
    global _smart_format_selector
    if _smart_format_selector is None:
        _smart_format_selector = SmartFormatSelector()
    return _smart_format_selector

def select_format_for_user(user_quality: str, url: str, proxy: str = None) -> Tuple[str, str, Dict]:
    """
    为用户选择最佳格式的便捷函数

    Args:
        user_quality: 用户选择的质量 ('4K', '1080p', '720p', etc.)
        url: 视频URL
        proxy: 代理配置

    Returns:
        Tuple[format_selector, reason, info]: (格式选择器表达式, 选择原因, 详细信息)
    """
    try:
        # 首先尝试使用平台特定的格式选择器
        platform_selector = _get_platform_format_selector(url, user_quality)
        if platform_selector:
            return platform_selector, f"使用{_get_platform_name(url)}平台专用格式选择器", {}

        # 如果平台选择器不可用，使用智能选择器
        selector = get_smart_format_selector()

        # 获取可用格式
        logger.info(f"🔍 获取视频格式列表: {url}")
        format_result = selector.get_available_formats(url, proxy)

        if not format_result['success']:
            return _get_fallback_format_selector(user_quality), f"格式检测失败，使用通用格式: {format_result.get('error', '')}", {}

        # 选择最佳格式
        format_id, reason = selector.select_best_format(user_quality, format_result)

        # 如果选择的是格式选择器表达式，直接返回
        if '/' in format_id or format_id in ['best', 'worst']:
            return format_id, reason, {
                'total_formats': format_result['total_count'],
                'available_qualities': list(format_result['formats'].keys())
            }

        # 获取格式详细信息
        format_info = selector.get_format_info(format_id)

        logger.info(f"✅ 为用户质量 '{user_quality}' 选择格式: {format_id}")
        logger.info(f"   选择原因: {reason}")

        return format_id, reason, {
            'format_info': format_info,
            'total_formats': format_result['total_count'],
            'available_qualities': list(format_result['formats'].keys())
        }

    except Exception as e:
        logger.error(f"❌ 智能格式选择失败: {e}")
        return _get_fallback_format_selector(user_quality), f"选择失败，使用通用格式: {str(e)}", {}


def _get_platform_format_selector(url: str, quality: str) -> str:
    """获取平台特定的格式选择器"""
    try:
        from modules.downloader.platforms import get_platform_for_url
        platform = get_platform_for_url(url)
        return platform.get_format_selector(quality, url)
    except Exception as e:
        logger.debug(f"获取平台格式选择器失败: {e}")
        return None


def _get_platform_name(url: str) -> str:
    """获取平台名称"""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url.lower()).netloc
        if 'twitter.com' in domain or 'x.com' in domain:
            return 'Twitter'
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            return 'YouTube'
        elif 'bilibili.com' in domain:
            return 'Bilibili'
        elif 'tiktok.com' in domain:
            return 'TikTok'
        elif 'instagram.com' in domain:
            return 'Instagram'
        elif 'facebook.com' in domain:
            return 'Facebook'
        else:
            return '通用'
    except:
        return '未知'


def _get_fallback_format_selector(quality: str) -> str:
    """获取降级格式选择器"""
    quality_lower = quality.lower().strip()

    if quality_lower in ['high', '1080p', '1080', 'fhd', 'full']:
        return 'best[height<=1080]/best[ext=mp4]/best/worst'
    elif quality_lower in ['medium', '720p', '720', 'hd']:
        return 'best[height<=720]/best[ext=mp4]/best/worst'
    elif quality_lower in ['low', '480p', '480', 'sd']:
        return 'best[height<=480]/best[ext=mp4]/best/worst'
    elif quality_lower in ['worst', '360p', '360']:
        return 'worst[ext=mp4]/worst/best[height<=360]/best'
    else:
        return 'best/worst'
