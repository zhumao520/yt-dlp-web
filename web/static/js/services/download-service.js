/**
 * 下载服务 - 统一下载相关逻辑
 */
class DownloadService extends BaseService {
    constructor() {
        super();
        this.downloadsCacheKey = 'downloads_list';
        this.videoCacheKey = 'video_info';
        
        // 状态映射
        this.statusMap = {
            'pending': { text: '等待中', class: 'bg-warning' },
            'downloading': { text: '下载中', class: 'bg-primary' },
            'completed': { text: '已完成', class: 'bg-success' },
            'failed': { text: '失败', class: 'bg-danger' },
            'cancelled': { text: '已取消', class: 'bg-secondary' }
        };
    }

    /**
     * 获取视频信息
     */
    async getVideoInfo(url) {
        try {
            if (!url) {
                throw new Error('视频链接不能为空');
            }

            // 检查缓存
            const cacheKey = `${this.videoCacheKey}_${url}`;
            const cached = this.getCache(cacheKey);
            if (cached) {
                return cached;
            }

            const result = await this.apiRequest('/api/video/info', {
                method: 'POST',
                body: JSON.stringify({ url })
            });

            // 缓存视频信息（较短的缓存时间）
            this.cache.set(cacheKey, {
                value: result.video_info,
                timestamp: Date.now()
            });

            return result.video_info;
        } catch (error) {
            this.handleError(error, '获取视频信息');
            throw error;
        }
    }

    /**
     * 开始下载
     */
    async startDownload(url, options = {}) {
        try {
            if (!url) {
                throw new Error('视频链接不能为空');
            }

            const downloadOptions = {
                quality: options.quality || 'high',
                audio_only: options.audio_only || false,
                telegram_push: options.telegram_push || false,
                ...options
            };

            const result = await this.apiRequest('/api/download/start', {
                method: 'POST',
                body: JSON.stringify({
                    url,
                    ...downloadOptions
                })
            });

            // 清除下载列表缓存
            this.clearCache(this.downloadsCacheKey);

            this.showNotification('下载已开始', 'success');
            return result;
        } catch (error) {
            this.handleError(error, '开始下载');
            throw error;
        }
    }

    /**
     * 获取下载列表
     */
    async getDownloads(forceRefresh = false) {
        try {
            if (!forceRefresh) {
                const cached = this.getCache(this.downloadsCacheKey);
                if (cached) {
                    return cached;
                }
            }

            const result = await this.apiRequest('/api/download/list');
            
            // 缓存下载列表（较短的缓存时间）
            this.cache.set(this.downloadsCacheKey, {
                value: result.downloads,
                timestamp: Date.now()
            });

            return result.downloads;
        } catch (error) {
            this.handleError(error, '获取下载列表');
            throw error;
        }
    }

    /**
     * 获取活跃下载
     */
    async getActiveDownloads() {
        try {
            const downloads = await this.getDownloads();
            return downloads.filter(d => 
                ['pending', 'downloading'].includes(d.status)
            );
        } catch (error) {
            this.handleError(error, '获取活跃下载');
            throw error;
        }
    }

    /**
     * 获取最近下载
     */
    async getRecentDownloads(limit = 10) {
        try {
            const downloads = await this.getDownloads();
            return downloads.slice(0, limit);
        } catch (error) {
            this.handleError(error, '获取最近下载');
            throw error;
        }
    }

    /**
     * 取消下载
     */
    async cancelDownload(downloadId) {
        try {
            const result = await this.apiRequest(`/api/download/${downloadId}/cancel`, {
                method: 'POST'
            });

            // 清除缓存
            this.clearCache(this.downloadsCacheKey);

            this.showNotification('下载已取消', 'info');
            return result;
        } catch (error) {
            this.handleError(error, '取消下载');
            throw error;
        }
    }

    /**
     * 删除下载记录
     */
    async deleteDownload(downloadId) {
        try {
            const result = await this.apiRequest(`/api/download/${downloadId}`, {
                method: 'DELETE'
            });

            // 清除缓存
            this.clearCache(this.downloadsCacheKey);

            this.showNotification('下载记录已删除', 'info');
            return result;
        } catch (error) {
            this.handleError(error, '删除下载记录');
            throw error;
        }
    }

    /**
     * 重新下载
     */
    async retryDownload(downloadId) {
        try {
            const result = await this.apiRequest(`/api/download/${downloadId}/retry`, {
                method: 'POST'
            });

            // 清除缓存
            this.clearCache(this.downloadsCacheKey);

            this.showNotification('重新下载已开始', 'success');
            return result;
        } catch (error) {
            this.handleError(error, '重新下载');
            throw error;
        }
    }

    /**
     * 获取下载状态信息
     */
    getStatusInfo(status) {
        return this.statusMap[status] || { text: '未知', class: 'bg-secondary' };
    }

    /**
     * 获取状态文本
     */
    getStatusText(status) {
        return this.getStatusInfo(status).text;
    }

    /**
     * 获取状态样式类
     */
    getStatusClass(status) {
        return this.getStatusInfo(status).class;
    }

    /**
     * 验证URL
     */
    validateUrl(url) {
        if (!url) {
            return { valid: false, message: '链接不能为空' };
        }

        try {
            new URL(url);
            return { valid: true };
        } catch {
            return { valid: false, message: '链接格式不正确' };
        }
    }

    /**
     * 格式化下载进度
     */
    formatProgress(progress) {
        return Math.round(progress || 0);
    }

    /**
     * 格式化下载速度
     */
    formatSpeed(speed) {
        if (!speed) return '';

        const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        let unitIndex = 0;

        while (speed >= 1024 && unitIndex < units.length - 1) {
            speed /= 1024;
            unitIndex++;
        }

        return `${speed.toFixed(1)} ${units[unitIndex]}`;
    }

    /**
     * 估算剩余时间
     */
    formatETA(seconds) {
        if (!seconds || seconds <= 0) return '';

        if (seconds < 60) {
            return `${Math.round(seconds)}秒`;
        } else if (seconds < 3600) {
            return `${Math.round(seconds / 60)}分钟`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.round((seconds % 3600) / 60);
            return `${hours}小时${minutes}分钟`;
        }
    }

    // 继承基础服务的格式化函数
    formatFileSize(bytes) {
        return super.formatFileSize(bytes);
    }

    formatDuration(seconds) {
        return super.formatDuration(seconds);
    }

    formatDate(dateString) {
        return super.formatDate(dateString);
    }

    formatNumber(num) {
        return super.formatNumber(num);
    }

    /**
     * 清除所有缓存
     */
    clearAllCache() {
        this.clearCache(this.downloadsCacheKey);
        // 清除所有视频信息缓存
        for (const [key] of this.cache) {
            if (key.startsWith(this.videoCacheKey)) {
                this.cache.delete(key);
            }
        }
    }
}

// 创建全局实例
window.downloadService = new DownloadService();
