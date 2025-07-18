/**
 * 统一的前端工具库
 * 消除重复的JavaScript工具函数
 * 
 * 使用方法:
 * 1. 在HTML中引入: <script src="/static/js/utils/common-utils.js"></script>
 * 2. 使用工具函数: CommonUtils.formatSize(bytes)
 */

class CommonUtils {
    /**
     * 格式化文件大小 - 统一实现
     * @param {number} bytes 字节数
     * @returns {string} 格式化后的大小字符串
     */
    static formatSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        if (i >= sizes.length) {
            return parseFloat((bytes / Math.pow(k, sizes.length - 1)).toFixed(2)) + ' ' + sizes[sizes.length - 1];
        }
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 格式化日期时间 - 统一实现
     * @param {number} timestamp Unix时间戳（秒）
     * @returns {string} 格式化后的日期时间字符串
     */
    static formatDate(timestamp) {
        if (!timestamp) return '';
        
        try {
            return new Date(timestamp * 1000).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        } catch (e) {
            console.warn('日期格式化失败:', e);
            return '';
        }
    }

    /**
     * HTML转义 - 统一实现
     * @param {string} text 需要转义的文本
     * @returns {string} 转义后的HTML安全文本
     */
    static escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 获取文件类型 - 统一实现
     * @param {string} filename 文件名
     * @returns {string} 文件类型描述
     */
    static getFileType(filename) {
        if (!filename) return '未知';
        
        const ext = filename.split('.').pop().toLowerCase();
        
        if (this.isVideoFile(filename)) {
            return `视频 (${ext.toUpperCase()})`;
        }
        
        if (this.isAudioFile(filename)) {
            return `音频 (${ext.toUpperCase()})`;
        }
        
        return `文件 (${ext.toUpperCase()})`;
    }

    /**
     * 获取简单文件类型文本 - 统一实现
     * @param {string} filename 文件名
     * @returns {string} 简单的文件类型
     */
    static getFileTypeText(filename) {
        if (!filename) return '未知';
        
        const ext = filename.split('.').pop().toLowerCase();
        
        if (this.isVideoFile(filename)) return '视频';
        if (this.isAudioFile(filename)) return '音频';
        
        return ext.toUpperCase();
    }

    /**
     * 检查是否为视频文件 - 统一实现
     * @param {string} filename 文件名
     * @returns {boolean} 是否为视频文件
     */
    static isVideoFile(filename) {
        if (!filename) return false;
        
        const videoExts = [
            'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v',
            '3gp', 'mpg', 'mpeg', 'ts', 'vob', 'rm', 'rmvb'
        ];
        
        const ext = filename.split('.').pop().toLowerCase();
        return videoExts.includes(ext);
    }

    /**
     * 检查是否为音频文件 - 统一实现
     * @param {string} filename 文件名
     * @returns {boolean} 是否为音频文件
     */
    static isAudioFile(filename) {
        if (!filename) return false;
        
        const audioExts = [
            'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a',
            'opus', 'ape', 'ac3', 'dts'
        ];
        
        const ext = filename.split('.').pop().toLowerCase();
        return audioExts.includes(ext);
    }

    /**
     * 防抖函数 - 统一实现
     * @param {Function} func 要防抖的函数
     * @param {number} wait 等待时间（毫秒）
     * @returns {Function} 防抖后的函数
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * 节流函数 - 统一实现
     * @param {Function} func 要节流的函数
     * @param {number} limit 限制时间（毫秒）
     * @returns {Function} 节流后的函数
     */
    static throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * 显示通知消息 - 统一实现
     * @param {string} message 消息内容
     * @param {string} type 消息类型 (success, error, warning, info)
     * @param {number} duration 显示时长（毫秒），默认3000
     */
    static showNotification(message, type = 'info', duration = 3000) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            font-size: 14px;
            z-index: 10000;
            max-width: 300px;
            word-wrap: break-word;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transition: all 0.3s ease;
        `;

        // 设置背景色
        const colors = {
            success: '#4CAF50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196F3'
        };
        notification.style.backgroundColor = colors[type] || colors.info;

        notification.textContent = message;

        // 添加到页面
        document.body.appendChild(notification);

        // 自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.opacity = '0';
                notification.style.transform = 'translateX(100%)';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, duration);

        // 点击关闭
        notification.addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }

    /**
     * 复制文本到剪贴板 - 统一实现
     * @param {string} text 要复制的文本
     * @returns {Promise<boolean>} 是否复制成功
     */
    static async copyToClipboard(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return true;
            } else {
                // 备用方案
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                const result = document.execCommand('copy');
                document.body.removeChild(textArea);
                return result;
            }
        } catch (err) {
            console.error('复制失败:', err);
            return false;
        }
    }

    /**
     * 格式化进度百分比 - 统一实现
     * @param {number} current 当前值
     * @param {number} total 总值
     * @returns {number} 百分比（0-100）
     */
    static calculateProgress(current, total) {
        if (!total || total <= 0) return 0;
        return Math.max(0, Math.min(100, Math.round((current / total) * 100)));
    }

    /**
     * 安全的JSON解析 - 统一实现
     * @param {string} jsonString JSON字符串
     * @param {*} defaultValue 解析失败时的默认值
     * @returns {*} 解析结果或默认值
     */
    static safeJsonParse(jsonString, defaultValue = null) {
        try {
            return JSON.parse(jsonString);
        } catch (e) {
            console.warn('JSON解析失败:', e);
            return defaultValue;
        }
    }

    /**
     * 获取URL参数 - 统一实现
     * @param {string} name 参数名
     * @returns {string|null} 参数值
     */
    static getUrlParameter(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    /**
     * 设置URL参数 - 统一实现
     * @param {string} name 参数名
     * @param {string} value 参数值
     * @param {boolean} replaceState 是否替换历史状态
     */
    static setUrlParameter(name, value, replaceState = true) {
        const url = new URL(window.location);
        url.searchParams.set(name, value);
        
        if (replaceState) {
            window.history.replaceState({}, '', url);
        } else {
            window.history.pushState({}, '', url);
        }
    }
}

// 为了向后兼容，也提供全局函数
window.formatSize = CommonUtils.formatSize;
window.formatDate = CommonUtils.formatDate;
window.escapeHtml = CommonUtils.escapeHtml;
window.showNotification = CommonUtils.showNotification;

// 导出到全局
window.CommonUtils = CommonUtils;
