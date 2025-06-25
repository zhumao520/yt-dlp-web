/**
 * 基础服务类 - 提供通用功能
 */
class BaseService {
    constructor() {
        this.cache = new Map();
        this.cacheTTL = 5 * 60 * 1000; // 5分钟缓存
    }

    /**
     * 统一API请求方法
     */
    async apiRequest(url, options = {}) {
        try {
            // 使用全局apiRequest函数，如果不存在则回退到fetch
            let response;
            if (typeof window.apiRequest === 'function') {
                response = await window.apiRequest(url, options);
            } else {
                // 回退实现
                const token = localStorage.getItem('auth_token');
                const defaultOptions = {
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        ...(token && { 'Authorization': `Bearer ${token}` })
                    }
                };
                response = await fetch(url, { ...defaultOptions, ...options });
            }

            // 如果response为空（401重定向情况），直接返回
            if (!response) {
                return null;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.error || errorData.message || `HTTP ${response.status}`;

                // 根据状态码提供更友好的错误信息
                let userMessage = errorMessage;
                if (response.status === 403) {
                    userMessage = '权限不足，无法访问此资源';
                } else if (response.status === 404) {
                    userMessage = '请求的资源不存在';
                } else if (response.status >= 500) {
                    userMessage = '服务器内部错误，请稍后重试';
                }

                throw new Error(userMessage);
            }

            return await response.json();
        } catch (error) {
            console.error(`❌ API请求失败 [${url}]:`, error);

            // 如果有全局通知函数，显示用户友好的错误信息
            if (typeof window.showNotification === 'function' && !error.message.includes('权限') && !error.message.includes('不存在')) {
                window.showNotification(`请求失败: ${error.message}`, 'danger');
            }

            throw error;
        }
    }

    /**
     * 缓存管理
     */
    setCache(key, value) {
        this.cache.set(key, {
            value,
            timestamp: Date.now()
        });
    }

    getCache(key) {
        const cached = this.cache.get(key);
        if (!cached) return null;

        // 检查是否过期
        if (Date.now() - cached.timestamp > this.cacheTTL) {
            this.cache.delete(key);
            return null;
        }

        return cached.value;
    }

    clearCache(key = null) {
        if (key) {
            this.cache.delete(key);
        } else {
            this.cache.clear();
        }
    }

    /**
     * 错误处理
     */
    handleError(error, context = '') {
        const message = error.message || '未知错误';
        console.error(`❌ ${context}失败:`, error);
        
        // 根据错误类型显示不同的通知
        if (message.includes('网络') || message.includes('fetch')) {
            this.showNotification('网络连接错误，请检查网络', 'danger');
        } else if (message.includes('401') || message.includes('认证')) {
            this.showNotification('认证失败，请重新登录', 'warning');
            // 可以在这里处理重新登录逻辑
        } else {
            this.showNotification(message, 'danger');
        }
    }

    /**
     * 显示通知（统一接口）
     */
    showNotification(message, type = 'info') {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    /**
     * 验证配置
     */
    validateConfig(config, rules) {
        const errors = {};

        for (const [field, rule] of Object.entries(rules)) {
            const value = config[field];

            if (rule.required && (!value || value === '')) {
                errors[field] = `${rule.label || field}不能为空`;
                continue;
            }

            if (value && rule.pattern && !rule.pattern.test(value)) {
                errors[field] = rule.message || `${rule.label || field}格式不正确`;
            }

            if (value && rule.minLength && value.length < rule.minLength) {
                errors[field] = `${rule.label || field}长度不能少于${rule.minLength}个字符`;
            }

            if (value && rule.maxLength && value.length > rule.maxLength) {
                errors[field] = `${rule.label || field}长度不能超过${rule.maxLength}个字符`;
            }

            if (rule.custom && typeof rule.custom === 'function') {
                const customError = rule.custom(value, config);
                if (customError) {
                    errors[field] = customError;
                }
            }
        }

        return errors;
    }

    /**
     * 防抖函数
     */
    debounce(func, wait) {
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
     * 节流函数
     */
    throttle(func, limit) {
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
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 格式化时间
     */
    formatDuration(seconds) {
        if (!seconds) return '';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * 格式化日期
     */
    formatDate(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleString('zh-CN');
    }

    /**
     * 格式化数字
     */
    formatNumber(num) {
        if (!num) return '';
        return num.toLocaleString();
    }
}
