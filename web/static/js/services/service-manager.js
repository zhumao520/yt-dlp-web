/**
 * 服务管理器 - 统一管理所有服务
 */
class ServiceManager {
    constructor() {
        this.services = new Map();
        this.initialized = false;
    }

    /**
     * 初始化所有服务
     */
    async init() {
        if (this.initialized) return;

        try {
            // 注册服务
            this.registerService('telegram', window.telegramService);
            this.registerService('download', window.downloadService);

            console.log('✅ 服务管理器初始化完成');
            this.initialized = true;
        } catch (error) {
            console.error('❌ 服务管理器初始化失败:', error);
            throw error;
        }
    }

    /**
     * 注册服务
     */
    registerService(name, service) {
        if (!(service instanceof BaseService)) {
            throw new Error(`服务 ${name} 必须继承自 BaseService`);
        }

        this.services.set(name, service);
        console.log(`📝 注册服务: ${name}`);
    }

    /**
     * 获取服务
     */
    getService(name) {
        const service = this.services.get(name);
        if (!service) {
            throw new Error(`服务 ${name} 未注册`);
        }
        return service;
    }

    /**
     * 获取Telegram服务
     */
    get telegram() {
        return this.getService('telegram');
    }

    /**
     * 获取下载服务
     */
    get download() {
        return this.getService('download');
    }

    /**
     * 清除所有服务缓存
     */
    clearAllCache() {
        for (const service of this.services.values()) {
            if (typeof service.clearAllCache === 'function') {
                service.clearAllCache();
            }
        }
        console.log('🧹 已清除所有服务缓存');
    }

    /**
     * 获取所有服务状态
     */
    getServicesStatus() {
        const status = {};
        for (const [name, service] of this.services) {
            status[name] = {
                initialized: !!service,
                cacheSize: service.cache ? service.cache.size : 0
            };
        }
        return status;
    }

    /**
     * 销毁所有服务
     */
    destroy() {
        for (const service of this.services.values()) {
            if (typeof service.destroy === 'function') {
                service.destroy();
            }
        }
        this.services.clear();
        this.initialized = false;
        console.log('🗑️ 服务管理器已销毁');
    }
}

/**
 * 应用管理器 - 统一管理应用状态和服务
 */
class AppManager {
    constructor() {
        this.serviceManager = new ServiceManager();
        this.currentPage = null;
        this.initialized = false;
    }

    /**
     * 初始化应用
     */
    async init() {
        if (this.initialized) return;

        try {
            // 初始化服务管理器
            await this.serviceManager.init();

            // 检测当前页面
            this.detectCurrentPage();

            console.log('🚀 应用管理器初始化完成');
            this.initialized = true;
        } catch (error) {
            console.error('❌ 应用管理器初始化失败:', error);
            throw error;
        }
    }

    /**
     * 检测当前页面
     */
    detectCurrentPage() {
        const path = window.location.pathname;
        
        if (path === '/' || path === '/download') {
            this.currentPage = 'download';
        } else if (path === '/telegram') {
            this.currentPage = 'telegram';
        } else if (path === '/files') {
            this.currentPage = 'files';
        } else if (path === '/history') {
            this.currentPage = 'history';
        } else {
            this.currentPage = 'unknown';
        }

        console.log(`📍 当前页面: ${this.currentPage}`);
    }

    /**
     * 获取服务管理器
     */
    get services() {
        return this.serviceManager;
    }

    /**
     * 页面切换处理
     */
    onPageChange(newPage) {
        const oldPage = this.currentPage;
        this.currentPage = newPage;

        console.log(`🔄 页面切换: ${oldPage} -> ${newPage}`);

        // 可以在这里添加页面切换的逻辑
        // 比如清除特定缓存、停止轮询等
    }

    /**
     * 全局错误处理
     */
    handleGlobalError(error, context = '') {
        console.error(`❌ 全局错误 [${context}]:`, error);
        
        // 可以在这里添加全局错误处理逻辑
        // 比如错误上报、用户通知等
        if (typeof window.showNotification === 'function') {
            window.showNotification('系统错误，请刷新页面重试', 'danger');
        }
    }

    /**
     * 应用状态检查
     */
    checkAppHealth() {
        const health = {
            initialized: this.initialized,
            currentPage: this.currentPage,
            services: this.serviceManager.getServicesStatus(),
            timestamp: new Date().toISOString()
        };

        console.log('🏥 应用健康状态:', health);
        return health;
    }

    /**
     * 销毁应用
     */
    destroy() {
        this.serviceManager.destroy();
        this.initialized = false;
        console.log('🗑️ 应用管理器已销毁');
    }
}

// 创建全局应用管理器实例
window.appManager = new AppManager();

// 延迟初始化，确保在其他DOMContentLoaded事件之后
setTimeout(async function() {
    try {
        await window.appManager.init();
        console.log('🎉 应用启动完成');
    } catch (error) {
        console.error('💥 应用启动失败:', error);
        window.appManager.handleGlobalError(error, '应用启动');
    }
}, 100);

// 页面卸载时清理
window.addEventListener('beforeunload', function() {
    if (window.appManager) {
        window.appManager.destroy();
    }
});

// 全局错误捕获
window.addEventListener('error', function(event) {
    if (window.appManager) {
        window.appManager.handleGlobalError(event.error, '全局异常');
    }
});

// 未处理的Promise错误捕获
window.addEventListener('unhandledrejection', function(event) {
    if (window.appManager) {
        window.appManager.handleGlobalError(event.reason, 'Promise异常');
    }
});
