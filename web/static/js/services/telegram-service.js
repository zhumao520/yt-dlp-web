/**
 * Telegram服务 - 与后端Telegram服务层对应
 */
class TelegramService extends BaseService {
    constructor() {
        super();
        this.configCacheKey = 'telegram_config';
        this.statusCacheKey = 'telegram_status';
        
        // 配置验证规则
        this.configRules = {
            bot_token: {
                required: true,
                label: 'Bot Token',
                pattern: /^\d+:[A-Za-z0-9_-]+$/,
                message: 'Bot Token格式不正确'
            },
            chat_id: {
                required: true,
                label: 'Chat ID',
                pattern: /^-?\d+$/,
                message: 'Chat ID必须是数字'
            },
            api_id: {
                required: false,
                label: 'API ID',
                custom: (value, config) => {
                    if (value && !config.api_hash) {
                        return '提供API ID时必须同时提供API Hash';
                    }
                    if (value && !/^\d+$/.test(value)) {
                        return 'API ID必须是数字';
                    }
                    return null;
                }
            },
            api_hash: {
                required: false,
                label: 'API Hash',
                custom: (value, config) => {
                    if (value && !config.api_id) {
                        return '提供API Hash时必须同时提供API ID';
                    }
                    if (value && !/^[a-f0-9]{32}$/.test(value)) {
                        return 'API Hash格式不正确（32位十六进制）';
                    }
                    return null;
                }
            },
            file_size_limit: {
                required: false,
                label: '文件大小限制',
                custom: (value) => {
                    const num = parseInt(value);
                    if (isNaN(num) || num <= 0) {
                        return '文件大小限制必须是正数';
                    }
                    return null;
                }
            }
        };
    }

    /**
     * 获取配置
     */
    async getConfig() {
        try {
            // 先检查缓存
            const cached = this.getCache(this.configCacheKey);
            if (cached) {
                return cached;
            }

            const config = await this.apiRequest('/api/telegram/config');
            
            // 处理布尔值
            const processedConfig = {
                ...config,
                enabled: Boolean(config.enabled),
                auto_download: Boolean(config.auto_download)
            };

            // 缓存配置
            this.setCache(this.configCacheKey, processedConfig);
            
            return processedConfig;
        } catch (error) {
            this.handleError(error, '获取Telegram配置');
            throw error;
        }
    }

    /**
     * 保存配置
     */
    async saveConfig(config) {
        try {
            // 验证配置
            const errors = this.validateConfig(config, this.configRules);
            if (Object.keys(errors).length > 0) {
                const errorMessage = Object.values(errors)[0];
                throw new Error(errorMessage);
            }

            const result = await this.apiRequest('/api/telegram/config', {
                method: 'POST',
                body: JSON.stringify(config)
            });

            // 清除缓存
            this.clearCache(this.configCacheKey);
            this.clearCache(this.statusCacheKey);

            this.showNotification('配置保存成功', 'success');
            return result;
        } catch (error) {
            this.handleError(error, '保存Telegram配置');
            throw error;
        }
    }

    /**
     * 测试连接
     */
    async testConnection() {
        try {
            const result = await this.apiRequest('/api/telegram/test', {
                method: 'POST'
            });

            // 缓存状态
            this.setCache(this.statusCacheKey, result);

            if (result.success) {
                this.showNotification('连接测试成功', 'success');
            } else {
                this.showNotification(result.error || '连接测试失败', 'danger');
            }

            return result;
        } catch (error) {
            this.handleError(error, '测试Telegram连接');
            throw error;
        }
    }

    /**
     * 获取连接状态
     */
    async getConnectionStatus() {
        try {
            // 先检查缓存
            const cached = this.getCache(this.statusCacheKey);
            if (cached) {
                return cached;
            }

            // 静默测试连接
            return await this.testConnection();
        } catch (error) {
            return {
                success: false,
                bot_api: false,
                pyrogrammod: false,
                error: error.message
            };
        }
    }

    /**
     * Webhook管理
     */
    async setupWebhook(webhookUrl = null) {
        try {
            const result = await this.apiRequest('/telegram/api/setup-webhook', {
                method: 'POST',
                body: JSON.stringify({
                    webhook_url: webhookUrl
                })
            });

            this.showNotification(`Webhook设置成功: ${result.webhook_url}`, 'success');
            return result;
        } catch (error) {
            this.handleError(error, '设置Webhook');
            throw error;
        }
    }

    async deleteWebhook() {
        try {
            const result = await this.apiRequest('/telegram/api/delete-webhook', {
                method: 'POST'
            });

            this.showNotification('Webhook已删除', 'success');
            return result;
        } catch (error) {
            this.handleError(error, '删除Webhook');
            throw error;
        }
    }

    async getWebhookInfo() {
        try {
            const result = await this.apiRequest('/telegram/api/webhook-info');
            return result.webhook_info;
        } catch (error) {
            this.handleError(error, '获取Webhook信息');
            throw error;
        }
    }

    /**
     * 生成默认Webhook URL
     */
    generateDefaultWebhookUrl() {
        return window.location.origin + '/telegram/webhook';
    }

    /**
     * 验证Webhook URL
     */
    validateWebhookUrl(url) {
        if (!url) {
            return { valid: false, message: 'Webhook URL不能为空' };
        }

        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            return { valid: false, message: 'Webhook URL必须以http://或https://开头' };
        }

        if (url.startsWith('http://')) {
            return { 
                valid: true, 
                warning: 'Telegram要求使用HTTPS，HTTP可能无法正常工作' 
            };
        }

        return { valid: true };
    }

    /**
     * 清除所有缓存
     */
    clearAllCache() {
        this.clearCache(this.configCacheKey);
        this.clearCache(this.statusCacheKey);
    }

    /**
     * 获取状态文本
     */
    getStatusText(status) {
        if (status === null) return '未检测';
        return status ? '正常' : '异常';
    }

    /**
     * 获取状态图标类
     */
    getStatusIconClass(status) {
        if (status === null) return 'bi bi-clock text-muted';
        return status ? 'bi bi-check-circle text-success' : 'bi bi-x-circle text-danger';
    }

    /**
     * 获取状态样式类
     */
    getStatusClass(status) {
        if (status === null) return 'text-muted';
        return status ? 'text-success' : 'text-danger';
    }
}

// 创建全局实例
window.telegramService = new TelegramService();
