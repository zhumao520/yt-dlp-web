// ==UserScript==
// @name         智能视频下载助手 - YT-DLP Web (全网支持)
// @namespace    http://tampermonkey.net/
// @version      3.3.0
// @description  智能识别网站类型：支持平台直接发送URL，其他网站提取真实视频文件地址。支持无认证SSE实时进度跟踪，修复TrustedHTML问题，支持全网视频下载。
// @author       YT-DLP Web Team
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      localhost
// @connect      127.0.0.1
// @connect      192.168.*
// @connect      10.*
// @connect      172.16.*
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // 🛡️ 防止在iframe或广告页面中运行
    if (window.top !== window.self) {
        console.log('🚫 检测到iframe环境，跳过脚本执行');
        return;
    }

    // 🛡️ 检查URL，跳过广告相关页面
    const currentUrl = window.location.href.toLowerCase();
    const skipPatterns = [
        'ads', 'advertisement', 'banner', 'popup', 'promo',
        'google.com/ads', 'doubleclick', 'googlesyndication'
    ];

    if (skipPatterns.some(pattern => currentUrl.includes(pattern))) {
        console.log('🚫 检测到广告相关页面，跳过脚本执行');
        return;
    }

    // 🔄 允许重复加载以便更新和调试
    if (window.smartVideoDownloaderLoaded) {
        console.log('🔄 智能视频下载助手重新加载，应用最新更新');
    }
    window.smartVideoDownloaderLoaded = true;

    console.log('🎬 智能全网视频下载助手开始加载');

    // 配置 - 服务器地址现在通过设置动态获取

    // 支持YT-DLP直接解析的平台
    const SUPPORTED_PLATFORMS = [
        'youtube.com', 'youtu.be', 'bilibili.com', 'tiktok.com',
        'douyin.com', 'v.douyin.com', 'xiaohongshu.com', 'xhslink.com',
        'kuaishou.com', 'v.kuaishou.com', 'twitter.com', 'x.com',
        'instagram.com', 'facebook.com', 'vimeo.com', 'dailymotion.com'
    ];

    // 全局变量
    let extractedVideos = [];

    // 🔧 智能SSE管理器 - 实现精准推送 + 页面刷新恢复
    class SmartSSEManager {
        constructor() {
            this.activeDownloads = new Map(); // download_id -> client_id
            this.eventSource = null;
            this.progressCallbacks = new Map(); // download_id -> callback
            this.isConnected = false;

            // 🔧 尝试恢复持久化的客户端ID
            this.clientId = this.restoreOrGenerateClientId();

            // 🔧 页面加载时尝试恢复活跃任务
            setTimeout(() => this.restoreActiveDownloads(), 1000);
        }

        restoreOrGenerateClientId() {
            // 尝试从存储中恢复客户端ID
            const savedClientId = GM_getValue('persistent_client_id');
            if (savedClientId) {
                console.log('🔄 恢复持久化客户端ID:', savedClientId);
                return savedClientId;
            }

            // 生成新的客户端ID并保存
            const newClientId = this.generateClientId();
            GM_setValue('persistent_client_id', newClientId);
            console.log('🆕 生成新的客户端ID:', newClientId);
            return newClientId;
        }

        generateClientId() {
            return `client_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        }

        // 🔧 恢复活跃任务
        async restoreActiveDownloads() {
            try {
                // 防止重复恢复
                if (this.isRestoring) {
                    console.log('⏳ 恢复任务正在进行中，跳过...');
                    return;
                }
                this.isRestoring = true;

                const serverUrl = GM_getValue('serverUrl', 'http://localhost:8090');
                console.log('🔄 尝试恢复活跃任务...');
                console.log('🌐 使用服务器地址:', serverUrl);

                // 保存this上下文
                const self = this;

                // 使用现有的/list端点查询服务器上的活跃任务
                const serverApiKey = GM_getValue('serverApiKey', '');
                const headers = {
                    'Content-Type': 'application/json'
                };
                if (serverApiKey) {
                    headers['X-API-Key'] = serverApiKey;
                }

                GM_xmlhttpRequest({
                    method: 'GET',
                    url: `${serverUrl}/download/list`,
                    headers: headers,
                    onload: (response) => {
                        try {
                            if (response.status === 200) {
                                const data = JSON.parse(response.responseText);
                                // /list端点返回的是downloads数组，需要过滤活跃任务
                                const allDownloads = data.downloads || data || [];
                                const activeDownloads = allDownloads.filter(download =>
                                    download.status === 'downloading' || download.status === 'pending'
                                );

                                if (activeDownloads.length > 0) {
                                    console.log(`🔄 发现 ${activeDownloads.length} 个活跃任务，开始恢复...`);
                                    console.log('📊 活跃任务详情:', activeDownloads);

                                    // 建立SSE连接
                                    self.connectSSE(serverUrl);

                                    // 显示恢复通知
                                    self.showRestoreNotification(activeDownloads.length);

                                    // 🔧 可选：为每个活跃任务创建浮动进度跟踪器
                                    activeDownloads.forEach(download => {
                                        console.log('🔧 处理单个任务:', download);
                                        console.log('🔧 任务字段:', Object.keys(download));
                                        console.log('🔧 可能的ID字段:', {
                                            id: download.id,
                                            download_id: download.download_id,
                                            task_id: download.task_id,
                                            _id: download._id
                                        });
                                        console.log('🔧 可能的标题字段:', {
                                            title: download.title,
                                            name: download.name,
                                            filename: download.filename,
                                            url: download.url
                                        });
                                        self.createFloatingProgressTracker(download);
                                    });

                                } else {
                                    console.log('✅ 没有发现活跃任务');
                                }
                            } else {
                                console.log('❌ 查询活跃任务失败:', response.status, response.statusText);
                            }
                        } catch (e) {
                            console.error('❌ 解析响应失败:', e);
                        }
                    },
                    onerror: (error) => {
                        console.error('❌ 网络请求失败:', error);
                    }
                });
            } catch (e) {
                console.log('❌ 恢复活跃任务失败:', e);
            } finally {
                this.isRestoring = false;
            }
        }

        // 🔧 显示恢复通知
        showRestoreNotification(taskCount) {
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed; top: 20px; right: 20px; z-index: 10000;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 15px 20px; border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                font-family: Arial, sans-serif; font-size: 14px;
                max-width: 300px; cursor: pointer;
                transition: all 0.3s ease;
            `;

            // 🛡️ 修复 TrustedHTML 问题 - 使用 DOM 操作而不是 innerHTML
            const titleDiv = document.createElement('div');
            titleDiv.style.cssText = 'font-weight: bold; margin-bottom: 5px;';
            titleDiv.textContent = '🔄 发现活跃下载任务';

            const contentDiv = document.createElement('div');
            contentDiv.style.cssText = 'font-size: 12px; opacity: 0.9;';

            // 🛡️ 完全避免 innerHTML，使用纯 DOM 操作
            const line1 = document.createTextNode(`检测到 ${taskCount} 个正在进行的下载任务`);
            const br = document.createElement('br');
            const line2 = document.createTextNode('SSE连接已自动恢复，可接收进度更新');

            contentDiv.appendChild(line1);
            contentDiv.appendChild(br);
            contentDiv.appendChild(line2);

            notification.appendChild(titleDiv);
            notification.appendChild(contentDiv);

            document.body.appendChild(notification);

            // 3秒后自动消失
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }, 3000);

            // 点击立即消失
            notification.onclick = () => {
                notification.style.opacity = '0';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            };
        }

        // 建立全局SSE连接（复用现有服务器代码）
        connectSSE(serverUrl) {
            if (this.eventSource && this.isConnected) {
                return; // 已经连接
            }

            // 🛡️ 检查HTTPS混合内容问题
            if (window.location.protocol === 'https:' && serverUrl.startsWith('http:')) {
                console.warn('⚠️ HTTPS页面无法连接HTTP服务器，SSE连接将被跳过');
                console.warn('💡 建议：配置HTTPS服务器或使用HTTP页面访问');
                console.warn('🔄 将启用轮询模式作为备用方案');
                this.startGlobalPolling(serverUrl);
                return;
            }

            console.log('🔗 建立智能SSE连接，客户端ID:', this.clientId);
            this.eventSource = new EventSource(`${serverUrl}/api/events/public?client_id=${this.clientId}`);

            this.eventSource.onopen = () => {
                console.log('✅ SSE连接已建立');
                this.isConnected = true;
            };

            this.eventSource.addEventListener('download_progress', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleProgressMessage(data);
                } catch (e) {
                    console.error('❌ SSE进度消息解析失败:', e);
                }
            });

            this.eventSource.addEventListener('download_completed', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleCompletedMessage(data);
                } catch (e) {
                    console.error('❌ SSE完成消息解析失败:', e);
                }
            });

            this.eventSource.addEventListener('download_failed', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleFailedMessage(data);
                } catch (e) {
                    console.error('❌ SSE失败消息解析失败:', e);
                }
            });

            this.eventSource.onerror = (error) => {
                console.error('❌ SSE连接错误:', error);
                this.isConnected = false;
            };
        }

        // 智能过滤进度消息
        handleProgressMessage(data) {
            const downloadId = data.download_id;
            const messageClientId = data.client_id;

            // 🔧 检查是否有注册的回调（包括恢复的任务）
            const callback = this.progressCallbacks.get(downloadId);
            if (callback) {
                if (messageClientId === this.clientId) {
                    console.log('📨 接收到自己的进度更新:', downloadId, data.progress + '%');
                } else {
                    console.log('🔄 恢复任务进度更新:', downloadId, data.progress + '%');
                }
                callback(data.progress, data.status, data);
            } else {
                console.debug('🔇 忽略其他客户端的进度:', downloadId);
            }
        }

        // 处理完成消息
        handleCompletedMessage(data) {
            const downloadId = data.download_id;
            const messageClientId = data.client_id;

            if (messageClientId === this.clientId) {
                console.log('📨 接收到下载完成:', downloadId);

                const callback = this.progressCallbacks.get(downloadId);
                if (callback) {
                    callback(100, 'completed', data);
                }

                // 清理完成的任务
                this.unregisterDownload(downloadId);
            }
        }

        // 处理失败消息
        handleFailedMessage(data) {
            const downloadId = data.download_id;
            const messageClientId = data.client_id;

            if (messageClientId === this.clientId) {
                console.log('📨 接收到下载失败:', downloadId);

                const callback = this.progressCallbacks.get(downloadId);
                if (callback) {
                    callback(0, 'failed', data);
                }

                // 清理失败的任务
                this.unregisterDownload(downloadId);
            }
        }

        // 注册下载任务
        registerDownload(downloadId, progressCallback) {
            this.activeDownloads.set(downloadId, this.clientId);
            this.progressCallbacks.set(downloadId, progressCallback);
            console.log('📝 注册下载任务:', downloadId, '客户端:', this.clientId);
        }

        // 清理下载任务
        unregisterDownload(downloadId) {
            this.activeDownloads.delete(downloadId);
            this.progressCallbacks.delete(downloadId);
            console.log('🗑️ 清理下载任务:', downloadId);
        }

        // 获取客户端ID
        getClientId() {
            return this.clientId;
        }

        // 关闭连接
        disconnect() {
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
                this.isConnected = false;
                console.log('🔌 SSE连接已关闭');
            }
            this.stopGlobalPolling();
        }

        // 🔄 全局轮询模式 - HTTPS环境下的备用方案
        startGlobalPolling(serverUrl) {
            if (this.pollingInterval) {
                return; // 已经在轮询
            }

            // 🛡️ 检查HTTPS混合内容问题
            if (window.location.protocol === 'https:' && serverUrl.startsWith('http:')) {
                console.warn('⚠️ HTTPS环境下无法进行轮询请求，将使用本地状态管理');
                console.warn('💡 建议：配置HTTPS服务器或使用HTTP页面访问以获得实时进度更新');
                this.startLocalStatusPolling();
                return;
            }

            console.log('🔄 启动全局轮询模式...');

            this.pollingInterval = setInterval(async () => {
                try {
                    // 获取所有活跃任务的状态
                    const response = await fetch(`${serverUrl}/api/downloads/active`, {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });

                    if (response.ok) {
                        const activeDownloads = await response.json();

                        // 更新每个已注册任务的进度
                        activeDownloads.forEach(download => {
                            const taskId = download.id || download.task_id || download.download_id;
                            if (taskId && this.progressCallbacks.has(taskId)) {
                                const callback = this.progressCallbacks.get(taskId);
                                if (callback) {
                                    callback(download.progress || 0, download.status || 'downloading', download);
                                }
                            }
                        });
                    }
                } catch (error) {
                    console.log('🔄 轮询请求失败:', error.message);
                }
            }, 2000); // 每2秒轮询一次

            console.log('✅ 全局轮询已启动，间隔2秒');
        }

        // 🔄 本地状态轮询 - HTTPS环境下的最后备用方案
        startLocalStatusPolling() {
            if (this.localPollingInterval) {
                return;
            }

            console.log('🔄 启动本地状态轮询模式...');
            console.log('💡 此模式下进度更新依赖页面刷新或手动检查');

            // 每10秒提醒用户刷新页面获取最新状态
            this.localPollingInterval = setInterval(() => {
                const activeCallbacks = this.progressCallbacks.size;
                if (activeCallbacks > 0) {
                    console.log(`🔄 检测到 ${activeCallbacks} 个活跃任务，建议刷新页面获取最新进度`);

                    // 显示刷新提示（可选）
                    this.showRefreshHint();
                }
            }, 10000); // 每10秒检查一次

            console.log('✅ 本地状态轮询已启动');
        }

        // 显示刷新提示
        showRefreshHint() {
            // 避免重复显示提示
            if (document.getElementById('refresh-hint')) {
                return;
            }

            const hint = document.createElement('div');
            hint.id = 'refresh-hint';
            hint.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                background: #ff9800;
                color: white;
                padding: 10px 15px;
                border-radius: 8px;
                font-size: 12px;
                z-index: 10001;
                cursor: pointer;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                animation: pulse 2s infinite;
            `;

            hint.innerHTML = `
                🔄 点击刷新获取最新进度<br>
                <small>HTTPS环境限制实时更新</small>
            `;

            hint.onclick = () => {
                window.location.reload();
            };

            // 添加脉冲动画
            const style = document.createElement('style');
            style.textContent = `
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.7; }
                    100% { opacity: 1; }
                }
            `;
            document.head.appendChild(style);

            document.body.appendChild(hint);

            // 10秒后自动移除
            setTimeout(() => {
                if (hint.parentNode) {
                    hint.parentNode.removeChild(hint);
                }
                if (style.parentNode) {
                    style.parentNode.removeChild(style);
                }
            }, 10000);
        }

        // 停止全局轮询
        stopGlobalPolling() {
            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
                console.log('🛑 全局轮询已停止');
            }
            if (this.localPollingInterval) {
                clearInterval(this.localPollingInterval);
                this.localPollingInterval = null;
                console.log('🛑 本地状态轮询已停止');
            }
        }

        // 🔧 为恢复的任务创建浮动进度跟踪器
        createFloatingProgressTracker(download) {
            try {
                // 🔧 尝试多种可能的ID字段
                const taskId = download.download_id || download.id || download.task_id || download._id;
                const title = download.title || download.name || download.filename || download.url || 'Unknown';

                const progress = download.progress || 0;
                const status = download.status || 'pending';

                console.log('🔧 解析任务数据:', {
                    taskId: taskId,
                    title: title,
                    progress: progress,
                    status: status
                });

                console.log(`🔧 为恢复任务创建浮动跟踪器: ${taskId} - ${title}`);

                // 创建浮动进度显示器
                const progressContainer = this.createFloatingProgressDisplay(taskId, title, progress, status);
                document.body.appendChild(progressContainer);

                // 注册SSE回调
                this.registerDownload(taskId, (progress, status) => {
                    this.updateFloatingProgress(progressContainer, progress, status);
                });

                return progressContainer;

            } catch (e) {
                console.error('❌ 创建浮动进度跟踪器失败:', e);
            }
        }

        // 🔧 创建圆形浮球进度显示器
        createFloatingProgressDisplay(taskId, title, initialProgress = 0, initialStatus = 'pending') {
            const container = document.createElement('div');
            container.id = `floating-progress-${taskId}`;

            // 计算位置（垂直堆叠）
            const existingBalls = document.querySelectorAll('[id^="floating-progress-"]');
            const topOffset = 20 + (existingBalls.length * 110); // 每个球间隔110px

            container.style.cssText = `
                position: fixed; top: ${topOffset}px; right: 20px; z-index: 10000;
                width: 90px; height: 90px; cursor: move;
                transition: none; user-select: none;
            `;

            // 创建SVG环形进度
            const svgSize = 90;
            const strokeWidth = 8;
            const radius = (svgSize - strokeWidth) / 2;
            const circumference = radius * 2 * Math.PI;

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', svgSize);
            svg.setAttribute('height', svgSize);
            svg.style.cssText = 'position: absolute; top: 0; left: 0; transform: rotate(-90deg);';

            // 创建渐变定义
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            const progressGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
            progressGradient.setAttribute('id', `progressGradient_${taskId}`);
            progressGradient.setAttribute('x1', '0%');
            progressGradient.setAttribute('y1', '0%');
            progressGradient.setAttribute('x2', '100%');
            progressGradient.setAttribute('y2', '100%');

            const progressStop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            progressStop1.setAttribute('offset', '0%');
            progressStop1.setAttribute('stop-color', '#ff8c00');
            const progressStop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
            progressStop2.setAttribute('offset', '100%');
            progressStop2.setAttribute('stop-color', '#00cc44');
            progressGradient.appendChild(progressStop1);
            progressGradient.appendChild(progressStop2);
            defs.appendChild(progressGradient);

            // 背景圆圈
            const bgCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            bgCircle.setAttribute('cx', svgSize / 2);
            bgCircle.setAttribute('cy', svgSize / 2);
            bgCircle.setAttribute('r', radius);
            bgCircle.setAttribute('stroke', '#e8e8e8');
            bgCircle.setAttribute('stroke-width', strokeWidth);
            bgCircle.setAttribute('fill', 'transparent');

            // 进度圆圈
            const progressCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            progressCircle.setAttribute('cx', svgSize / 2);
            progressCircle.setAttribute('cy', svgSize / 2);
            progressCircle.setAttribute('r', radius);
            progressCircle.setAttribute('stroke', `url(#progressGradient_${taskId})`);
            progressCircle.setAttribute('stroke-width', strokeWidth);
            progressCircle.setAttribute('fill', 'transparent');
            progressCircle.setAttribute('stroke-dasharray', circumference);
            progressCircle.setAttribute('stroke-dashoffset', circumference - (initialProgress / 100) * circumference);
            progressCircle.setAttribute('stroke-linecap', 'round');

            svg.appendChild(defs);
            svg.appendChild(bgCircle);
            svg.appendChild(progressCircle);

            // 中心圆圈
            const centerCircle = document.createElement('div');
            centerCircle.style.cssText = `
                width: 74px; height: 74px; border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex; align-items: center; justify-content: center;
                color: white; font-size: 12px; font-weight: bold;
                position: absolute; top: 8px; left: 8px; z-index: 1;
                text-align: center; line-height: 1.2;
            `;
            // 🛡️ 使用安全的 DOM 操作设置内容
            this.setCenterContent(centerCircle, initialStatus, initialProgress);

            // 标题提示（悬停显示）
            container.title = title;

            // 关闭按钮
            const closeButton = document.createElement('div');
            closeButton.style.cssText = `
                position: absolute; top: -5px; right: -5px;
                width: 20px; height: 20px; border-radius: 50%;
                background: #ff4444; color: white; font-size: 12px;
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; opacity: 0; transition: opacity 0.3s ease;
            `;
            closeButton.textContent = '×';
            closeButton.onclick = (e) => {
                e.stopPropagation();
                container.remove();
                this.unregisterDownload(taskId);
            };

            // 悬停显示关闭按钮
            container.onmouseenter = () => closeButton.style.opacity = '1';
            container.onmouseleave = () => closeButton.style.opacity = '0';

            container.appendChild(svg);
            container.appendChild(centerCircle);
            container.appendChild(closeButton);

            // 🔧 添加拖动功能
            this.makeDraggable(container);

            // 存储元素引用
            container.progressCircle = progressCircle;
            container.centerCircle = centerCircle;
            container.circumference = circumference;
            container.taskId = taskId;

            return container;
        }

        // 🔧 使浮球可拖动（复用现有拖动逻辑）
        makeDraggable(element) {
            // 复用现有的拖动代码逻辑
            makeElementDraggable(element, {
                excludeSelector: '×', // 排除关闭按钮
                onDragStart: () => {
                    element.style.opacity = '0.8';
                    element.style.transform = 'scale(1.05)';
                },
                onDragEnd: () => {
                    element.style.opacity = '1';
                    element.style.transform = 'scale(1)';
                },
                bounds: {
                    minLeft: 0,
                    minTop: 0,
                    maxLeft: window.innerWidth - 90,
                    maxTop: window.innerHeight - 90
                }
            });
        }

        // 🔧 更新圆形浮球进度
        updateFloatingProgress(container, progress, status) {
            if (!container || !container.progressCircle) return;

            const validProgress = Math.max(0, Math.min(100, progress || 0));

            // 更新环形进度
            const offset = container.circumference - (validProgress / 100) * container.circumference;
            container.progressCircle.setAttribute('stroke-dashoffset', offset);

            // 更新中心内容 - 🛡️ 使用安全的 DOM 操作
            this.setCenterContent(container.centerCircle, status, validProgress);

            // 根据状态更新发光效果
            if (status === 'completed') {
                container.progressCircle.style.filter = 'drop-shadow(0 0 8px rgba(0, 204, 68, 0.8))';

                // 3秒后自动关闭
                setTimeout(() => {
                    if (container.parentNode) {
                        container.remove();
                        this.unregisterDownload(container.taskId);
                    }
                }, 3000);

            } else if (status === 'failed') {
                container.progressCircle.style.filter = 'drop-shadow(0 0 8px rgba(255, 51, 51, 0.8))';

                // 5秒后自动关闭
                setTimeout(() => {
                    if (container.parentNode) {
                        container.remove();
                        this.unregisterDownload(container.taskId);
                    }
                }, 3000);

            } else if (status === 'downloading') {
                // 动态发光颜色（橙色到绿色）
                const orangeR = 255, orangeG = 140, orangeB = 0;
                const greenR = 0, greenG = 204, greenB = 68;
                const ratio = validProgress / 100;
                const currentR = Math.round(orangeR + (greenR - orangeR) * ratio);
                const currentG = Math.round(orangeG + (greenG - orangeG) * ratio);
                const currentB = Math.round(orangeB + (greenB - orangeB) * ratio);

                container.progressCircle.style.filter = `drop-shadow(0 0 8px rgba(${currentR}, ${currentG}, ${currentB}, 0.8))`;
            }
        }



        // 🛡️ 设置中心圆圈内容 - 避免 innerHTML，使用 DOM 操作
        setCenterContent(element, status, progress) {
            // 🛡️ 安全地清空现有内容 - 避免 innerHTML
            while (element.firstChild) {
                element.removeChild(element.firstChild);
            }

            let icon, text;
            switch (status) {
                case 'pending':
                    icon = '⏳';
                    text = '等待';
                    break;
                case 'downloading':
                    icon = progress > 50 ? '📥' : '⬇️';
                    text = `${progress}%`;
                    break;
                case 'completed':
                    icon = '✅';
                    text = '完成';
                    break;
                case 'failed':
                    icon = '❌';
                    text = '失败';
                    break;
                default:
                    icon = '📊';
                    text = `${progress}%`;
                    break;
            }

            // 创建图标元素
            const iconElement = document.createTextNode(icon);
            element.appendChild(iconElement);

            // 创建换行
            const br = document.createElement('br');
            element.appendChild(br);

            // 创建小文字元素
            const small = document.createElement('small');
            small.textContent = text;
            element.appendChild(small);
        }

        // 🔧 获取状态文字
        getStatusText(status, progress) {
            switch (status) {
                case 'pending': return '⏳ 等待中...';
                case 'downloading': return `📥 下载中... ${progress}%`;
                case 'completed': return '✅ 下载完成';
                case 'failed': return '❌ 下载失败';
                default: return `📊 ${progress}%`;
            }
        }
    }

    // 全局SSE管理器实例
    const sseManager = new SmartSSEManager();

    // 样式常量
    const MODAL_STYLES = {
        overlay: `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background: rgba(0,0,0,0.7) !important;
            z-index: 999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        `,
        dialog: `
            background: white !important;
            padding: 30px !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
            min-width: 500px !important;
            max-width: 80vw !important;
            font-family: Arial, sans-serif !important;
            color: #333 !important;
        `,
        errorStatus: 'background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 10px; border-radius: 5px; margin-bottom: 15px; text-align: center;',
        successStatus: 'background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 10px; border-radius: 5px; margin-bottom: 15px; text-align: center;'
    };

    // 常量定义
    const CONSTANTS = {
        TIMEOUTS: {
            INIT_RETRY: 200,
            AUTO_DETECT: 2000,
            REQUEST_TIMEOUT: 5000
        },
        ENDPOINTS: {
            SHORTCUTS: '/api/shortcuts/download',
            DOWNLOAD: '/download/start',  // 🔧 修正：使用正确的路径前缀
            HEALTH: '/api/health'
        },
        MESSAGES: {
            SUCCESS: '✅ 下载请求已发送',
            ERROR_CONNECTION: '❌ 所有下载端点都无法连接',
            ERROR_SERVER: '❌ 服务器错误'
        }
    };



    // FetchV 精准过滤配置（完全复制FetchV的过滤逻辑）
    const MEDIA_CONFIG = {
        // FetchV支持的格式（完全一致）
        formats: ['m3u8', 'm3u', 'mp4', '3gp', 'flv', 'mov', 'avi', 'wmv', 'webm', 'f4v', 'acc', 'mkv', 'mp3', 'wav', 'ogg'],
        mimeTypes: {
            'application/vnd.apple.mpegurl': 'm3u8',
            'application/x-mpegurl': 'm3u8',
            'application/vnd.americandynamics.acc': 'acc',
            'application/vnd.rn-realmedia-vbr': 'rmvb',
            'video/mp4': 'mp4',
            'video/3gpp': '3gp',
            'video/x-flv': 'flv',
            'video/quicktime': 'mov',
            'video/x-msvideo': 'avi',
            'video/x-ms-wmv': 'wmv',
            'video/webm': 'webm',
            'video/ogg': 'ogg',
            'video/x-f4v': 'f4v',
            'video/x-matroska': 'mkv',
            'video/iso.segment': 'm4s',
            'audio/mpeg': 'mp3',
            'audio/wav': 'wav',
            'audio/ogg': 'ogg'
        },
        // FetchV的默认大小限制：最小500KB
        minSize: 500 * 1024, // 500KB，与FetchV完全一致
        maxSize: 0, // 0表示无限制
        // FetchV的屏蔽域名（完全一致）
        blockedDomains: ['doppiocdn', 'adtng', 'afcdn', 'sacdnssedge'],
        // FetchV屏蔽的特定平台
        blockedPlatforms: ['youtube.com', 'globo.com']
    };

    // 🛡️ 通用URL验证函数 - 修复URL解析失败问题
    function isValidUrl(url) {
        try {
            if (!url || typeof url !== 'string' || url.trim() === '') {
                return false;
            }

            // 确保URL是完整的HTTP/HTTPS URL
            let validUrl = url.trim();
            if (!validUrl.startsWith('http://') && !validUrl.startsWith('https://')) {
                if (validUrl.startsWith('//')) {
                    validUrl = window.location.protocol + validUrl;
                } else if (validUrl.startsWith('/')) {
                    validUrl = window.location.origin + validUrl;
                } else {
                    return false;
                }
            }

            // 尝试构造URL对象
            new URL(validUrl);
            return true;
        } catch (e) {
            return false;
        }
    }

    // 🎯 通用M3U8处理函数 - 避免重复代码
    function processM3U8Detection(url, source) {
        let mediaType = getVideoType(url);
        let title = getVideoFileName(url) || '网络请求媒体';

        if (url.includes('.m3u8')) {
            if (url.includes('master')) {
                title = 'M3U8主播放列表';
                mediaType = 'm3u8_master';
            } else {
                title = 'M3U8播放列表';
                mediaType = 'm3u8';
            }
            console.log(`🎯 ${source}捕获M3U8文件:`, url);
            return { title, mediaType, isM3U8: true };
        } else {
            console.log(`🌐 ${source}捕获有效媒体:`, url);
            return { title, mediaType, isM3U8: false };
        }
    }

    // 🎯 通用网络请求结果添加函数 - 避免重复代码
    function addNetworkRequestResult(url, source, contentLength, headers) {
        const { title, mediaType } = processM3U8Detection(url, source);

        addVideoResult({
            title: title,
            url: url,
            type: mediaType,
            source: `${source}请求`,
            size: contentLength,
            headers: headers
        });
    }

    // 🎯 通用请求数据构建函数 - 避免重复代码
    function buildRequestData(url, quality, audioOnly, customFilename, source) {
        // 🔧 确保URL格式正确，去除转义字符
        const cleanUrl = url.replace(/\\\//g, '/');

        // 🔧 如果没有自定义文件名，尝试从URL中提取
        let finalCustomFilename = customFilename || '';
        if (!finalCustomFilename) {
            finalCustomFilename = extractFilenameFromUrl(url) || '';
        }

        return {
            url: cleanUrl,
            quality: quality || 'high',
            audio_only: audioOnly || false,
            custom_filename: finalCustomFilename,
            source: source,
            smart_filename: true,
            client_id: sseManager.getClientId()
        };
    }

    // 🎯 通用API密钥处理函数 - 避免重复代码
    function addApiKeyToRequest(requestData, headers) {
        const serverApiKey = GM_getValue('serverApiKey', '');

        if (serverApiKey) {
            headers['X-API-Key'] = serverApiKey;
            requestData.api_key = serverApiKey;
            console.log('✅ 已添加API密钥认证');
        } else {
            console.log('❌ 未找到API密钥');
        }

        return serverApiKey;
    }

    // 🎯 FetchV风格MediaSource Hook - 基于成功测试的技术
    function setupMediaSourceHook() {
        console.log('🎯 设置FetchV风格MediaSource Hook...');

        if (!window.MediaSource) {
            console.log('⚠️ MediaSource API 不可用');
            return;
        }

        // 保存原始MediaSource
        const OriginalMediaSource = window.MediaSource;

        // 创建FetchV风格的MediaSource代理
        window.MediaSource = new Proxy(OriginalMediaSource, {
            construct(target, args) {
                console.log('🎯 FetchV风格: MediaSource实例创建');
                const mediaSource = new target(...args);
                const sourceId = Math.floor(Math.random() * (200000000 - 1000 + 1)) + 1000;
                let isLive = false;

                // Hook addSourceBuffer方法
                const originalAddSourceBuffer = mediaSource.addSourceBuffer;
                mediaSource.addSourceBuffer = function(mimeType) {
                    console.log('🎯 FetchV风格: addSourceBuffer调用, mimeType:', mimeType);
                    const sourceBuffer = originalAddSourceBuffer.call(this, mimeType);
                    const bufferId = Math.floor(Math.random() * (200000000 - 1000 + 1)) + 1000;

                    // Hook appendBuffer方法
                    const originalAppendBuffer = sourceBuffer.appendBuffer;
                    sourceBuffer.appendBuffer = function(buffer) {
                        if (buffer && (buffer.length > 0 || buffer.byteLength > 0)) {
                            const bufferSize = buffer.byteLength || buffer.length;

                            // 创建Blob URL (模拟FetchV)
                            const blob = new Blob([buffer]);
                            const blobUrl = URL.createObjectURL(blob);

                            isLive = mediaSource.duration === Infinity;

                            console.log('🎯 FetchV风格: 捕获媒体数据', {
                                url: blobUrl.substring(0, 50) + '...',
                                mime: mimeType,
                                sourceId: sourceId,
                                bufferId: bufferId,
                                size: bufferSize,
                                live: isLive
                            });

                            // 添加到结果中
                            addVideoResult({
                                title: `MediaSource流 (${mimeType})`,
                                url: blobUrl,
                                type: mimeType.includes('video') ? 'video_stream' : 'media_stream',
                                source: 'MediaSource Hook',
                                size: bufferSize,
                                mimeType: mimeType
                            });

                            // 延迟清理URL (模拟FetchV的10秒清理)
                            setTimeout(() => {
                                URL.revokeObjectURL(blobUrl);
                            }, 10000);
                        }

                        return originalAppendBuffer.call(this, buffer);
                    };

                    return sourceBuffer;
                };

                // 监听sourceended事件
                mediaSource.addEventListener('sourceended', () => {
                    setTimeout(() => {
                        console.log('🎯 FetchV风格: MediaSource结束', { sourceId, live: isLive });
                    }, 5000);
                });

                return mediaSource;
            }
        });

        console.log('✅ FetchV风格MediaSource Hook已安装');
    }

    // 高级网络请求监听 - 集成FetchV的智能过滤技术
    function setupAdvancedNetworkMonitoring() {
        console.log('🌐 设置高级网络请求监听...');

        // FetchV 精准过滤函数（完全复制FetchV的过滤逻辑）
        function isValidMediaResource(url, headers, size) {
            filterStats.totalChecked++;

            try {
                // 🛡️ 增强URL验证 - 修复URL解析失败问题
                if (!url || typeof url !== 'string' || url.trim() === '') {
                    filterStats.filteredByFormat++;
                    console.log('🚫 无效URL: 空或非字符串');
                    return false;
                }

                // 确保URL是完整的HTTP/HTTPS URL
                let validUrl = url.trim();
                if (!validUrl.startsWith('http://') && !validUrl.startsWith('https://')) {
                    if (validUrl.startsWith('//')) {
                        validUrl = window.location.protocol + validUrl;
                    } else if (validUrl.startsWith('/')) {
                        validUrl = window.location.origin + validUrl;
                    } else {
                        filterStats.filteredByFormat++;
                        console.log('🚫 无效URL协议:', validUrl.substring(0, 50));
                        return false;
                    }
                }

                const urlObj = new URL(validUrl);
                const hostname = urlObj.hostname;
                const pathname = urlObj.pathname.toLowerCase();
                const contentType = headers['content-type'] || headers['Content-Type'] || '';

                // 1. FetchV的域名屏蔽检查
                if (MEDIA_CONFIG.blockedDomains.some(domain => hostname.includes(domain))) {
                    filterStats.filteredByDomain++;
                    console.log('🚫 FetchV域名过滤:', hostname);
                    return false;
                }

                // 2. FetchV的平台屏蔽检查
                if (MEDIA_CONFIG.blockedPlatforms.some(platform => hostname.includes(platform))) {
                    filterStats.filteredByDomain++;
                    console.log('🚫 FetchV平台过滤:', hostname);
                    return false;
                }

                // 3. FetchV的文件大小检查 - 必须有大小且符合要求
                if (!size || size <= 0) {
                    filterStats.filteredBySize++;
                    console.log('🚫 无文件大小信息:', url.substring(0, 50));
                    return false;
                }

                // 4. FetchV的大小限制检查
                if (MEDIA_CONFIG.minSize && size < MEDIA_CONFIG.minSize) {
                    filterStats.filteredBySize++;
                    console.log('🚫 文件过小:', size, 'bytes <', MEDIA_CONFIG.minSize);
                    return false;
                }

                if (MEDIA_CONFIG.maxSize && size > MEDIA_CONFIG.maxSize) {
                    filterStats.filteredBySize++;
                    console.log('🚫 文件过大:', size, 'bytes >', MEDIA_CONFIG.maxSize);
                    return false;
                }

                // 5. FetchV的格式检查 - 必须在支持列表中
                let detectedFormat = null;

                // 5a. 检查文件扩展名
                for (const format of MEDIA_CONFIG.formats) {
                    if (pathname.includes(`.${format}`)) {
                        detectedFormat = format;
                        break;
                    }
                }

                // 5b. 检查MIME类型
                if (!detectedFormat && contentType && MEDIA_CONFIG.mimeTypes[contentType]) {
                    detectedFormat = MEDIA_CONFIG.mimeTypes[contentType];
                }

                // 5c. 特殊处理：master.txt文件（FetchV逻辑）
                if (!detectedFormat && pathname.includes('master.txt') && contentType.startsWith('text/plain')) {
                    detectedFormat = 'm3u8';
                }

                if (!detectedFormat) {
                    filterStats.filteredByFormat++;
                    console.log('🚫 不支持的格式:', pathname, contentType);
                    return false;
                }

                // 6. FetchV的M3U8特殊处理 - M3U8不需要大小检查
                if (detectedFormat === 'm3u8' || detectedFormat === 'm3u') {
                    filterStats.passed++;
                    console.log('✅ FetchV M3U8通过:', url.substring(0, 50));
                    return true;
                }

                filterStats.passed++;
                console.log('✅ FetchV过滤通过:', detectedFormat, `${(size/1024).toFixed(0)}KB`);
                return true;

            } catch (e) {
                filterStats.filteredByFormat++;
                console.log('🚫 URL解析失败:', e.message);
                return false;
            }
        }

        // 升级XMLHttpRequest监听
        const originalXHROpen = XMLHttpRequest.prototype.open;
        const originalXHRSend = XMLHttpRequest.prototype.send;

        XMLHttpRequest.prototype.open = function(method, url, ...args) {
            this._url = url;
            this._method = method;

            // 🔍 M3U8预检查
            if (url && typeof url === 'string' && url.includes('.m3u8')) {
                console.log('🎯 XHR检测到M3U8请求:', url);

                if (url.includes('master')) {
                    console.log('🎯 发现master.m3u8文件！');
                }
            }

            return originalXHROpen.apply(this, [method, url, ...args]);
        };

        XMLHttpRequest.prototype.send = function(...args) {
            const xhr = this;

            xhr.addEventListener('load', function() {
                try {
                    if (xhr._url && xhr.status >= 200 && xhr.status < 300) {
                        // 🛡️ 增强URL验证
                        if (!xhr._url || typeof xhr._url !== 'string' || xhr._url.trim() === '') {
                            return;
                        }

                        const headers = {};
                        const headerStr = xhr.getAllResponseHeaders();
                        if (headerStr) {
                            headerStr.split('\r\n').forEach(line => {
                                const [key, value] = line.split(': ');
                                if (key && value) headers[key] = value;
                            });
                        }

                        const contentLength = parseInt(headers['content-length'] || headers['Content-Length'] || '0');

                        // 🎯 M3U8文件特殊处理
                        if (xhr._url.includes('.m3u8')) {
                            console.log('🎯 XHR响应M3U8:', {
                                url: xhr._url.substring(0, 80) + '...',
                                contentType: headers['content-type'],
                                contentLength: contentLength
                            });

                            // 直接添加M3U8文件到结果
                            addM3U8ToResults(xhr._url, headers, contentLength, 'XHR');

                            // 如果有响应文本，进行内容分析
                            if (xhr.responseText) {
                                const analysis = analyzeM3U8Content(xhr.responseText);
                                console.log('🎯 XHR M3U8内容分析:', analysis);
                            }
                        } else if (isValidMediaResource(xhr._url, headers, contentLength)) {
                            // 🎯 其他媒体文件使用通用处理
                            addNetworkRequestResult(xhr._url, 'XHR', contentLength, headers);
                        }
                    }
                } catch (e) {
                    console.log('🚫 XHR处理错误:', e.message);
                }
            });

            return originalXHRSend.apply(this, args);
        };

        // 🎯 FetchV风格增强Fetch监听 - 专门检测M3U8
        const originalFetch = window.fetch;
        window.fetch = function(url, ...args) {
            // 🔍 M3U8预检查和特殊处理
            if (url && typeof url === 'string' && url.includes('.m3u8')) {
                console.log('🎯 Fetch检测到M3U8请求:', url);

                if (url.includes('master')) {
                    console.log('🎯 发现master.m3u8文件！');
                }

                // 立即尝试获取M3U8内容进行分析
                setTimeout(() => {
                    fetchAndAnalyzeM3U8(url, 'Fetch');
                }, 100);
            }

            return originalFetch.apply(this, arguments).then(response => {
                try {
                    if (response.ok) {
                        // 🛡️ 增强URL验证
                        if (!url || typeof url !== 'string' || url.trim() === '') {
                            return response;
                        }

                        const headers = {};
                        response.headers.forEach((value, key) => {
                            headers[key] = value;
                        });

                        const contentLength = parseInt(headers['content-length'] || '0');

                        // 🎯 M3U8文件特殊处理
                        if (url.includes('.m3u8')) {
                            console.log('🎯 Fetch响应M3U8:', {
                                url: url.substring(0, 80) + '...',
                                contentType: headers['content-type'],
                                contentLength: contentLength
                            });

                            // 直接添加M3U8文件到结果
                            addM3U8ToResults(url, headers, contentLength, 'Fetch');
                        } else if (isValidMediaResource(url, headers, contentLength)) {
                            // 🎯 其他媒体文件使用通用处理
                            addNetworkRequestResult(url, 'Fetch', contentLength, headers);
                        }
                    }
                } catch (e) {
                    console.log('🚫 Fetch处理错误:', e.message);
                }
                return response;
            });
        };

        console.log('✅ 高级网络请求监听已设置');
    }

    // 🎯 Video元素监听 - 检测动态加载的视频源
    function setupVideoElementMonitoring() {
        console.log('📺 设置Video元素监听...');

        // 监听现有video元素
        function monitorVideoElement(video) {
            const videoId = video.id || `video-${Date.now()}`;
            console.log('📺 开始监听video元素:', videoId);

            // 检查当前src
            if (video.src && video.src.startsWith('blob:')) {
                console.log('🎯 检测到Blob视频源:', video.src);
                addVideoResult({
                    title: 'Blob视频源',
                    url: video.src,
                    type: 'blob_video',
                    source: 'Video元素监听',
                    element: videoId
                });
            }

            // 监听src属性变化
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
                        const newSrc = video.src;
                        if (newSrc && newSrc.startsWith('blob:')) {
                            console.log('🎯 Video src变化为Blob:', newSrc);
                            addVideoResult({
                                title: 'Blob视频源 (动态)',
                                url: newSrc,
                                type: 'blob_video',
                                source: 'Video元素监听',
                                element: videoId
                            });
                        }
                    }
                });
            });

            observer.observe(video, {
                attributes: true,
                attributeFilter: ['src']
            });

            // 监听loadstart事件
            video.addEventListener('loadstart', () => {
                if (video.src && video.src.startsWith('blob:')) {
                    console.log('🎯 Video loadstart事件 - Blob源:', video.src);
                    addVideoResult({
                        title: 'Blob视频源 (loadstart)',
                        url: video.src,
                        type: 'blob_video',
                        source: 'Video元素监听',
                        element: videoId
                    });
                }
            });
        }

        // 监听现有的video元素
        document.querySelectorAll('video').forEach(monitorVideoElement);

        // 监听新添加的video元素
        const domObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        if (node.tagName === 'VIDEO') {
                            monitorVideoElement(node);
                        } else {
                            // 检查子元素中的video
                            const videos = node.querySelectorAll && node.querySelectorAll('video');
                            if (videos) {
                                videos.forEach(monitorVideoElement);
                            }
                        }
                    }
                });
            });
        });

        domObserver.observe(document.body, {
            childList: true,
            subtree: true
        });

        console.log('✅ Video元素监听已设置');
    }

    // 智能JavaScript脚本扫描 (优化版)
    function scanJavaScriptSources() {
        console.log('📜 智能扫描JavaScript源码...');
        const scripts = document.querySelectorAll('script[src], script:not([src])');

        scripts.forEach(script => {
            if (script.textContent) {
                // 只扫描包含明显媒体关键词的脚本
                const content = script.textContent;
                if (!/(?:video|audio|stream|m3u8|mp4|src|url)/i.test(content)) {
                    return; // 跳过不相关的脚本
                }

                // 🔍 增强的正则表达式模式 - 特别针对M3U8
                const patterns = [
                    // 直接的URL赋值
                    /(?:src|url|videoUrl|streamUrl)["'\s]*[:=]["'\s]*["']([^"']+\.(?:mp4|m3u8|webm|mkv|avi|mov|flv)(?:\?[^"']*)?)/gi,
                    // JSON对象中的URL
                    /["'](?:src|url|file)["']:\s*["']([^"']+\.(?:mp4|m3u8|webm|mkv|avi|mov|flv)(?:\?[^"']*)?)/gi,
                    // 🆕 M3U8专用模式 - 检测所有.m3u8链接
                    /(https?:\/\/[^"'\s<>]+\.m3u8(?:\?[^"'\s<>]*)?)/gi,
                    // 🆕 HLS流媒体模式 - 检测HLS相关URL
                    /(?:hls|stream|playlist)["'\s]*[:=]["'\s]*["']([^"']+\.m3u8(?:\?[^"']*)?)/gi,
                    // 🆕 成人网站特定模式
                    /(https?:\/\/[^"'\s<>]*(?:phncdn|xvideos|pornhub|xhamster)[^"'\s<>]*\.m3u8(?:\?[^"'\s<>]*)?)/gi
                ];

                patterns.forEach(pattern => {
                    let match;
                    while ((match = pattern.exec(content)) !== null) {
                        const url = match[1];
                        // 🛡️ 使用通用URL验证函数
                        if (url && isValidUrl(url)) {
                            console.log('📜 脚本中发现媒体URL:', url);
                            addVideoResult({
                                title: getVideoFileName(url) || 'JavaScript媒体',
                                url: url,
                                type: getVideoType(url),
                                source: 'JavaScript源码'
                            });
                        }
                    }
                });
            }
        });
    }

    // 显示详细的过滤统计
    function showDetailedFilterStats() {
        const total = filterStats.totalChecked;
        const passed = filterStats.passed;
        const filtered = total - passed;
        const passRate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0';

        const statsMessage = `📊 FetchV过滤统计:
总检查: ${total} 个
✅ 通过: ${passed} 个 (${passRate}%)
🚫 过滤: ${filtered} 个
   - 大小不符: ${filterStats.filteredBySize}
   - 域名屏蔽: ${filterStats.filteredByDomain}
   - 格式不支持: ${filterStats.filteredByFormat}`;

        showNotification(statsMessage, 'info', 8000);
        console.log('📊 详细过滤统计:', filterStats);
    }

    // 重置过滤统计
    function resetFilterStats() {
        filterStats.totalChecked = 0;
        filterStats.passed = 0;
        filterStats.filteredBySize = 0;
        filterStats.filteredByDomain = 0;
        filterStats.filteredByFormat = 0;
        updatePanelStatus(extractedVideos.length);
        showNotification('🔄 过滤统计已重置', 'info');
    }

    // 过滤统计数据
    const filterStats = {
        totalChecked: 0,
        passed: 0,
        filteredBySize: 0,
        filteredByDomain: 0,
        filteredByFormat: 0
    };

    // 实时状态更新函数
    function updatePanelStatus(capturedCount) {
        const panel = document.getElementById('smart-video-panel');
        if (panel) {
            const statusElement = panel.querySelector('.panel-status');
            if (statusElement) {
                const platformType = isSupportedPlatform() ? '支持平台' : '提取模式';
                const filterRate = filterStats.totalChecked > 0 ?
                    ((filterStats.passed / filterStats.totalChecked) * 100).toFixed(1) : '0';
                statusElement.textContent = `智能下载助手 (${platformType}) - 已捕获: ${capturedCount} | 过滤率: ${filterRate}%`;
            }
        }
    }

    // 判断是否为支持的平台
    function isSupportedPlatform() {
        const hostname = window.location.hostname.toLowerCase();
        return SUPPORTED_PLATFORMS.some(platform => hostname.includes(platform));
    }

    // 判断是否为视频文件
    function isVideoFile(url) {
        const videoExtensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.m3u8', '.mpd'];
        return videoExtensions.some(ext => url.toLowerCase().includes(ext));
    }

    // 获取视频类型
    function getVideoType(url) {
        const urlLower = url.toLowerCase();
        if (urlLower.includes('.m3u8')) return 'm3u8';
        if (urlLower.includes('.mpd')) return 'mpd';
        if (urlLower.includes('.mp4')) return 'mp4';
        if (urlLower.includes('.mkv')) return 'mkv';
        if (urlLower.includes('.webm')) return 'webm';
        return 'video';
    }

    // 获取文件名
    function getVideoFileName(url) {
        try {
            const urlObj = new URL(url);
            const pathname = urlObj.pathname;
            const filename = pathname.split('/').pop();
            return filename || 'video';
        } catch {
            return 'video';
        }
    }

    // 获取页面标题
    function getPageTitle() {
        let title = document.title || 'video';
        return title.replace(/[<>:"/\\|?*]/g, '_')
                   .replace(/ - YouTube$/, '')
                   .replace(/ - 哔哩哔哩$/, '')
                   .replace(/ - bilibili$/, '')
                   .replace(/ \| TikTok$/, '')
                   .replace(/ - 抖音$/, '')
                   .replace(/ - 小红书$/, '')
                   .replace(/ - 快手$/, '')
                   .replace(/ - Twitter$/, '')
                   .replace(/ - X$/, '')
                   .replace(/ - Instagram$/, '')
                   .replace(/ - Facebook$/, '')
                   .replace(/\s+/g, ' ')
                   .trim()
                   .substring(0, 100);
    }

    // 智能提取视频标题
    function getSmartVideoTitle() {
        console.log('🎯 开始智能提取视频标题...');

        // 优先级1: 视频特定的标题元素
        const videoTitleSelectors = [
            'h1[class*="title"]',
            'h1[class*="video"]',
            '.video-title',
            '.title',
            'h1.title',
            'h2.title',
            '[data-title]',
            '.video-info h1',
            '.video-info h2',
            '.content-title',
            '.main-title',
            '#video-title',
            '.video-name',
            '.media-title'
        ];

        for (const selector of videoTitleSelectors) {
            const element = document.querySelector(selector);
            if (element && element.textContent.trim()) {
                let title = element.textContent.trim();
                if (title.length > 10) { // 确保标题有意义
                    console.log(`🎯 从选择器 ${selector} 提取到标题:`, title);
                    return cleanTitle(title);
                }
            }
        }

        // 优先级2: meta标签
        const metaTitle = document.querySelector('meta[property="og:title"]') ||
                         document.querySelector('meta[name="twitter:title"]');
        if (metaTitle && metaTitle.content.trim()) {
            console.log('🎯 从meta标签提取到标题:', metaTitle.content.trim());
            return cleanTitle(metaTitle.content.trim());
        }

        // 优先级3: 页面标题
        console.log('🎯 使用页面标题:', document.title);
        return getPageTitle();
    }

    // 清理标题 (与服务器端保持一致)
    function cleanTitle(title) {
        try {
            // 1. 移除或替换无效字符 (与服务器端 invalid_chars 一致)
            let cleaned = title.replace(/[<>:"/\\|?*]/g, '_');

            // 2. 移除控制字符
            cleaned = cleaned.replace(/[\x00-\x1F\x7F]/g, '');

            // 3. 智能处理空格和下划线
            cleaned = cleaned.replace(/\s{2,}/g, ' ');  // 多个空格变成单个空格
            cleaned = cleaned.replace(/_{2,}/g, '_');   // 多个下划线变成单个下划线
            cleaned = cleaned.replace(/\s*_\s*/g, '_'); // 空格+下划线+空格 -> 下划线

            // 4. 移除开头和结尾的特殊字符
            cleaned = cleaned.replace(/^[._\-\s]+|[._\-\s]+$/g, '');

            // 5. 限制长度 (留出扩展名空间)
            if (cleaned.length > 200) {
                cleaned = cleaned.substring(0, 200);
            }

            // 6. 确保不为空
            if (!cleaned || cleaned === '.' || cleaned === '..') {
                cleaned = 'untitled';
            }

            return cleaned;

        } catch (e) {
            console.log('❌ 文件名清理失败:', e);
            return 'untitled';
        }
    }

    // 工具函数
    function createModalDialog(title, content) {
        const overlay = document.createElement('div');
        overlay.style.cssText = MODAL_STYLES.overlay;

        const dialog = document.createElement('div');
        dialog.style.cssText = MODAL_STYLES.dialog;

        if (title) {
            const titleElement = document.createElement('h3');
            titleElement.style.cssText = 'margin: 0 0 20px 0; text-align: center; color: #667eea;';
            titleElement.textContent = title;
            dialog.appendChild(titleElement);
        }

        if (content) {
            dialog.appendChild(content);
        }

        overlay.appendChild(dialog);

        // 通用事件绑定
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        });

        dialog.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        return { overlay, dialog };
    }

    // 🎯 通用模态对话框事件绑定函数 - 避免重复代码
    function bindModalEvents(overlay, dialog, closeCallback) {
        // 点击背景关闭
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                if (closeCallback) closeCallback();
                else overlay.remove();
            }
        });

        // 阻止对话框内点击冒泡
        dialog.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    // 🎯 通用按钮创建函数 - 避免重复代码
    function createButton(text, color, clickHandler) {
        const button = document.createElement('button');
        button.style.cssText = `
            padding: 8px 16px;
            background: ${color};
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            margin: 0 5px;
        `;
        button.textContent = text;
        if (clickHandler) {
            button.addEventListener('click', clickHandler);
        }
        return button;
    }

    // 🎯 通用输入框创建函数 - 避免重复代码
    function createInput(type, placeholder, value, width = '100%') {
        const input = document.createElement('input');
        input.type = type;
        input.placeholder = placeholder || '';
        input.value = value || '';
        input.style.cssText = `
            width: ${width};
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        `;
        return input;
    }

    // 🎯 M3U8内容获取和分析函数 - 基于成功测试的技术
    async function fetchAndAnalyzeM3U8(url, source) {
        try {
            console.log(`🎯 ${source}获取M3U8内容:`, url.substring(0, 80) + '...');

            const response = await fetch(url);
            if (response.ok) {
                const content = await response.text();
                console.log(`🎯 ${source}获取M3U8内容成功:`, {
                    url: url.substring(0, 80) + '...',
                    size: content.length,
                    lines: content.split('\n').length
                });

                // 分析M3U8内容
                const analysis = analyzeM3U8Content(content);
                console.log(`🎯 M3U8分析结果:`, {
                    url: url.substring(0, 50) + '...',
                    ...analysis
                });

                // 添加到结果
                addM3U8ToResults(url, { 'content-type': 'application/x-mpegurl' }, content.length, source + '(内容分析)', analysis);

                return { content, analysis };
            }
        } catch (error) {
            console.log(`❌ ${source}获取M3U8内容失败:`, error.message);
        }
        return null;
    }

    // 🎯 M3U8内容分析函数
    function analyzeM3U8Content(content) {
        const lines = content.split('\n');
        let isPlaylist = false;
        let isMaster = false;
        let segmentCount = 0;
        let streams = [];

        lines.forEach(line => {
            line = line.trim();
            if (line.startsWith('#EXTM3U')) {
                isPlaylist = true;
            } else if (line.startsWith('#EXT-X-STREAM-INF')) {
                isMaster = true;
                // 解析流信息
                const resolution = line.match(/RESOLUTION=(\d+x\d+)/);
                const bandwidth = line.match(/BANDWIDTH=(\d+)/);
                const frameRate = line.match(/FRAME-RATE=([\d.]+)/);

                streams.push({
                    resolution: resolution ? resolution[1] : 'unknown',
                    bandwidth: bandwidth ? parseInt(bandwidth[1]) : 0,
                    frameRate: frameRate ? parseFloat(frameRate[1]) : 0
                });
            } else if (line.endsWith('.ts')) {
                segmentCount++;
            }
        });

        return {
            isPlaylist,
            isMaster,
            segmentCount,
            streams,
            type: isMaster ? 'Master Playlist' : 'Media Playlist'
        };
    }

    // 🎯 M3U8文件添加到结果函数
    function addM3U8ToResults(url, headers, size, source, analysis = null) {
        let title = 'M3U8播放列表';
        let type = 'm3u8';

        if (url.includes('master') || (analysis && analysis.isMaster)) {
            title = '🎯 M3U8主播放列表';
            type = 'm3u8_master';
        }

        if (analysis && analysis.streams.length > 0) {
            const bestStream = analysis.streams.reduce((best, current) =>
                current.bandwidth > best.bandwidth ? current : best
            );
            title += ` (${bestStream.resolution})`;
        }

        console.log('✅ 添加M3U8文件:', {
            title,
            url: url.substring(0, 80) + '...',
            type,
            source
        });

        addVideoResult({
            title: title,
            url: url,
            type: type,
            source: source,
            size: size,
            headers: headers,
            analysis: analysis
        });
    }

    // 通用下载重试函数
    function createDownloadRetryFunction(requestData, statusElement, endpoints, logPrefix = '') {
        let currentEndpoint = 0;

        function tryNextEndpoint() {
            if (currentEndpoint >= endpoints.length) {
                statusElement.style.cssText = MODAL_STYLES.errorStatus;
                statusElement.textContent = CONSTANTS.MESSAGES.ERROR_CONNECTION;
                showNotification(CONSTANTS.MESSAGES.ERROR_CONNECTION, 'error');
                return;
            }

            const endpoint = endpoints[currentEndpoint];
            console.log(`📤 ${logPrefix}尝试端点: ${endpoint}`);

            const serverApiKey = GM_getValue('serverApiKey', '');
            const headers = { 'Content-Type': 'application/json' };

            if (serverApiKey) {
                headers['X-API-Key'] = serverApiKey;
                requestData.api_key = serverApiKey;
            }

            // 🔍 发送前最终检查
            console.log('🚀 即将发送到服务器的数据:');
            console.log('   endpoint:', endpoint);
            console.log('   method: POST');
            console.log('   headers:', headers);
            console.log('   requestData.custom_filename:', `"${requestData.custom_filename}"`);
            console.log('   requestData.custom_filename长度:', requestData.custom_filename ? requestData.custom_filename.length : 'null/undefined');
            console.log('   完整JSON:', JSON.stringify(requestData, null, 2));

            GM_xmlhttpRequest({
                method: 'POST',
                url: endpoint,
                headers: headers,
                data: JSON.stringify(requestData),
                onload: function(response) {
                    if (response.status === 200) {
                        try {
                            const result = JSON.parse(response.responseText);
                            if (result.success) {
                                statusElement.style.cssText = MODAL_STYLES.successStatus;

                                // 🔧 使用现有的进度跟踪器 + 智能SSE管理器
                                const serverUrl = GM_getValue('serverUrl', 'http://localhost:8090');
                                const taskId = result.download_id;

                                // 创建进度跟踪器（使用现有函数）
                                // 🔧 SSE注册将在startFillProgressTracking中进行，避免重复注册
                                const progressTracker = createFillProgressTracker(taskId, serverUrl);

                                // 🛡️ 安全地清空状态元素
                                while (statusElement.firstChild) {
                                    statusElement.removeChild(statusElement.firstChild);
                                }
                                statusElement.appendChild(progressTracker);

                                showNotification(`✅ 下载任务已创建: ${taskId}`, 'success');
                            } else {
                                statusElement.style.cssText = MODAL_STYLES.errorStatus;
                                statusElement.textContent = `❌ 下载失败: ${result.error}`;
                                showNotification(`❌ 下载失败: ${result.error}`, 'error');
                            }
                        } catch (e) {
                            statusElement.style.cssText = MODAL_STYLES.successStatus;
                            statusElement.textContent = CONSTANTS.MESSAGES.SUCCESS;
                            showNotification(CONSTANTS.MESSAGES.SUCCESS, 'success');
                        }
                    } else if (response.status === 404) {
                        currentEndpoint++;
                        tryNextEndpoint();
                    } else {
                        // 🔍 详细错误信息
                        console.error(`❌ HTTP ${response.status} 错误详情:`, {
                            status: response.status,
                            statusText: response.statusText,
                            url: endpoint,
                            headers: headers,
                            requestData: requestData,
                            responseText: response.responseText
                        });

                        statusElement.style.cssText = MODAL_STYLES.errorStatus;
                        statusElement.textContent = `${CONSTANTS.MESSAGES.ERROR_SERVER}: HTTP ${response.status}`;
                        showNotification(`${CONSTANTS.MESSAGES.ERROR_SERVER}: HTTP ${response.status}`, 'error');

                        // 尝试下一个端点
                        currentEndpoint++;
                        setTimeout(tryNextEndpoint, 1000);
                    }
                },
                onerror: function() {
                    currentEndpoint++;
                    tryNextEndpoint();
                }
            });
        }

        return tryNextEndpoint;
    }

    // 显示通知
    function showNotification(message, type = 'info') {
        const colors = { success: '#2ecc71', error: '#e74c3c', info: '#3498db' };

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed; top: 80px; right: 20px; z-index: 10002;
            background: ${colors[type]}; color: white; padding: 15px 20px;
            border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px; max-width: 350px;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => notification.remove(), 3000);
    }

    // 提取页面中的视频文件
    function extractVideosFromPage() {
        extractedVideos = [];
        console.log('🔍 开始提取页面视频文件...');

        // 提取方法1: video标签
        const videoTags = document.querySelectorAll('video');
        console.log(`📹 找到 ${videoTags.length} 个video标签`);

        videoTags.forEach(video => {
            // 🔧 优先检查video标签的src属性
            if (video.src && isVideoFile(video.src)) {
                console.log('✅ video标签src:', video.src);
                addVideoResult({
                    title: video.title || getVideoFileName(video.src),
                    url: video.src,
                    type: getVideoType(video.src),
                    source: 'video标签'
                });
            } else {
                // 🔧 只有当video标签没有src时，才检查source子标签
                const sources = video.querySelectorAll('source');
                sources.forEach(source => {
                    if (source.src && isVideoFile(source.src)) {
                        console.log('✅ source标签src:', source.src);
                        addVideoResult({
                            title: getVideoFileName(source.src),
                            url: source.src,
                            type: getVideoType(source.src),
                            source: 'source标签'
                        });
                    }
                });
            }
        });

        // 🔍 增强M3U8播放列表检测 - 包含更多模式
        const pageText = document.documentElement.innerHTML;

        // 1. 高质量M3U8播放列表检测（原有逻辑）
        const highQualityM3u8Pattern = /https?:\/\/[^"\s<>]+(?:playlist|index|master|main)\.m3u8(?:\?[^"\s<>]*)?/gi;
        let m3u8Matches = pageText.match(highQualityM3u8Pattern);

        // 2. 🆕 通用M3U8文件检测 - 检测所有.m3u8文件
        const generalM3u8Pattern = /https?:\/\/[^"\s<>]+\.m3u8(?:\?[^"\s<>]*)?/gi;
        let generalM3u8Matches = pageText.match(generalM3u8Pattern);

        // 3. 🆕 特定域名M3U8检测 - 针对phncdn等成人网站
        const adultSiteM3u8Pattern = /https?:\/\/[^"\s<>]*(?:phncdn|xvideos|pornhub|xhamster)[^"\s<>]*\.m3u8(?:\?[^"\s<>]*)?/gi;
        let adultM3u8Matches = pageText.match(adultSiteM3u8Pattern);

        // 合并所有匹配结果
        const allM3u8Matches = [
            ...(m3u8Matches || []),
            ...(generalM3u8Matches || []),
            ...(adultM3u8Matches || [])
        ];

        if (allM3u8Matches.length > 0) {
            const uniqueM3u8 = [...new Set(allM3u8Matches)];
            console.log(`📺 找到 ${uniqueM3u8.length} 个M3U8播放列表`);

            uniqueM3u8.forEach(url => {
                // 判断M3U8类型
                let m3u8Type = 'M3U8播放列表';
                if (url.includes('master')) {
                    m3u8Type = 'M3U8主播放列表';
                } else if (url.includes('playlist') || url.includes('index')) {
                    m3u8Type = 'M3U8索引列表';
                }

                console.log('✅ M3U8检测:', url.substring(0, 80) + '...');
                addVideoResult({
                    title: getVideoFileName(url) || m3u8Type,
                    url: url,
                    type: 'm3u8',
                    source: 'HTML内容扫描'
                });
            });
        }
        // 提取方法3: 智能JavaScript脚本扫描 (优化版)
        scanJavaScriptSources();

        // 🔧 最终去重检查 - 确保没有重复的URL
        const uniqueVideos = [];
        const seenUrls = new Set();

        extractedVideos.forEach(video => {
            try {
                const url = new URL(video.url);
                const baseUrl = `${url.origin}${url.pathname}`;

                if (!seenUrls.has(baseUrl)) {
                    seenUrls.add(baseUrl);
                    uniqueVideos.push(video);
                } else {
                    console.log('🔄 最终去重过滤:', video.title, '来源:', video.source);
                }
            } catch (e) {
                // URL解析失败，使用完整URL作为标识
                if (!seenUrls.has(video.url)) {
                    seenUrls.add(video.url);
                    uniqueVideos.push(video);
                } else {
                    console.log('🔄 最终去重过滤:', video.title, '来源:', video.source);
                }
            }
        });

        extractedVideos = uniqueVideos;
        console.log(`🎉 提取完成，总共找到 ${extractedVideos.length} 个唯一视频文件`);
        extractedVideos.forEach((video, index) => {
            console.log(`${index + 1}. [${video.type.toUpperCase()}] ${video.title} - ${video.source}`);
        });

        return extractedVideos;
    }

    function addVideoResult(video) {
        // 🔧 智能去重逻辑 - 处理URL参数差异和路径相似性
        const exists = extractedVideos.some(v => {
            // 1. 完全相同的URL
            if (v.url === video.url) {
                return true;
            }

            // 2. 去除查询参数后比较主要路径
            try {
                const existingUrl = new URL(v.url);
                const newUrl = new URL(video.url);

                // 比较域名和路径（忽略查询参数）
                const existingBase = `${existingUrl.origin}${existingUrl.pathname}`;
                const newBase = `${newUrl.origin}${newUrl.pathname}`;

                if (existingBase === newBase) {
                    console.log('🔄 检测到相似URL，已去重:', newBase);
                    return true;
                }

                // 3. 检查文件名相似性（针对动态URL）
                const existingFilename = existingUrl.pathname.split('/').pop();
                const newFilename = newUrl.pathname.split('/').pop();

                if (existingFilename && newFilename &&
                    existingFilename === newFilename &&
                    existingUrl.hostname === newUrl.hostname) {
                    console.log('🔄 检测到相同文件名，已去重:', newFilename);
                    return true;
                }

            } catch (e) {
                // URL解析失败，使用简单字符串比较
                console.log('⚠️ URL解析失败，使用简单比较');
            }

            return false;
        });

        if (!exists) {
            extractedVideos.push(video);
            console.log('✅ 新增视频:', video.title, '来源:', video.source);

            // 🎯 实时更新面板显示
            updatePanelStatus(extractedVideos.length);
            addVideoToPanel(video);

            // 显示捕获通知（避免通知过多）
            if (extractedVideos.length <= 5) {
                showNotification(`🎬 发现${video.type.toUpperCase()}：${video.title}`, 'success');
            }
        } else {
            console.log('🔄 重复视频已过滤:', video.title, '来源:', video.source);
        }
    }

    // 🎯 添加视频到面板显示
    function addVideoToPanel(video) {
        const panel = document.getElementById('smart-video-panel');
        if (!panel) return;

        const videoList = panel.querySelector('.video-list');
        if (!videoList) return;

        // 显示视频列表容器
        videoList.style.display = 'block';

        // 创建视频项目
        const videoItem = document.createElement('div');
        videoItem.className = 'video-item';

        // 🎯 M3U8文件特殊样式
        const isM3U8 = video.type === 'm3u8' || video.type === 'm3u8_master' || video.url.includes('.m3u8');
        const borderColor = isM3U8 ? '#e74c3c' : '#3498db';
        const bgColor = isM3U8 ? 'linear-gradient(135deg, #fff5f5, #ffe6e6)' : '#f8f9fa';

        videoItem.style.cssText = `
            padding: 8px;
            margin: 5px 0;
            border: 2px solid ${borderColor};
            border-radius: 6px;
            background: ${bgColor};
            font-size: 12px;
        `;

        // 标题
        const title = document.createElement('div');
        title.className = 'video-title';
        title.textContent = video.title;
        title.style.cssText = `
            font-weight: bold;
            color: ${isM3U8 ? '#e74c3c' : '#2c3e50'};
            margin-bottom: 3px;
            font-size: 11px;
        `;

        // URL
        const url = document.createElement('div');
        url.className = 'video-url';
        url.textContent = video.url;
        url.style.cssText = `
            color: #7f8c8d;
            font-size: 10px;
            word-break: break-all;
            margin-bottom: 3px;
        `;

        // 信息
        const info = document.createElement('div');
        info.textContent = `类型: ${video.type} | 来源: ${video.source}`;
        info.style.cssText = `
            color: #95a5a6;
            font-size: 9px;
            margin-bottom: 5px;
        `;

        // 按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 3px;';

        // 下载按钮
        const downloadBtn = createButton('📤', '#2ecc71', () => {
            if (isSupportedPlatform()) {
                showSupportedPlatformDialog(video.url);
            } else {
                showExtractVideoDownloadDialog(video);
            }
        });
        downloadBtn.style.fontSize = '10px';
        downloadBtn.style.padding = '4px 8px';

        // 复制按钮
        const copyBtn = createButton('📋', '#3498db', () => {
            navigator.clipboard.writeText(video.url).then(() => {
                copyBtn.textContent = '✅';
                setTimeout(() => copyBtn.textContent = '📋', 2000);
            });
        });
        copyBtn.style.fontSize = '10px';
        copyBtn.style.padding = '4px 8px';

        buttonContainer.appendChild(downloadBtn);
        buttonContainer.appendChild(copyBtn);

        videoItem.appendChild(title);
        videoItem.appendChild(url);
        videoItem.appendChild(info);
        videoItem.appendChild(buttonContainer);

        // 🎯 M3U8文件添加到顶部，其他文件添加到底部
        if (isM3U8) {
            videoList.insertBefore(videoItem, videoList.firstChild);
        } else {
            videoList.appendChild(videoItem);
        }
    }

    // 创建可拖拽的圆形面板
    function createDraggablePanel() {
        // 检查是否已经存在面板，避免重复创建
        const existingPanel = document.getElementById('smart-video-panel');
        if (existingPanel) {
            console.log('⚠️ 面板已存在，不重复创建');
            return existingPanel;
        }

        const panel = document.createElement('div');
        panel.id = 'smart-video-panel';

        const platformType = isSupportedPlatform() ? '支持平台' : '提取模式';
        const buttonText = isSupportedPlatform() ? '📥' : '🔍';
        const buttonTitle = isSupportedPlatform() ? '下载视频' : '提取视频';

        // 安全的DOM创建方式（避免TrustedHTML问题）
        const header = document.createElement('div');
        header.className = 'panel-header';
        header.title = buttonTitle;

        const icon = document.createElement('span');
        icon.className = 'panel-icon';
        icon.textContent = buttonText;
        header.appendChild(icon);

        const content = document.createElement('div');
        content.className = 'panel-content';

        const buttons = document.createElement('div');
        buttons.className = 'panel-buttons';

        const primaryBtn = document.createElement('button');
        primaryBtn.className = 'panel-btn primary';
        primaryBtn.textContent = `${buttonText} ${buttonTitle}`;

        const secondaryBtn = document.createElement('button');
        secondaryBtn.className = 'panel-btn secondary';
        secondaryBtn.textContent = '⚙️ 设置';

        buttons.appendChild(primaryBtn);
        buttons.appendChild(secondaryBtn);

        const status = document.createElement('div');
        status.className = 'panel-status';
        status.textContent = `智能下载助手 (${platformType})`;

        // 🎯 添加视频列表容器
        const videoList = document.createElement('div');
        videoList.className = 'video-list';
        videoList.style.cssText = `
            max-height: 300px;
            overflow-y: auto;
            margin-top: 10px;
            display: none;
        `;

        content.appendChild(buttons);
        content.appendChild(status);
        content.appendChild(videoList);

        panel.appendChild(header);
        panel.appendChild(content);

        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            #smart-video-panel {
                position: fixed;
                top: 20px;
                right: 20px;
                width: 300px;
                background: #2c3e50;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                z-index: 10000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                color: white;
                font-size: 14px;
                transition: all 0.3s ease;
                user-select: none;
            }

            #smart-video-panel.collapsed {
                width: 60px !important;
                height: 60px !important;
                border-radius: 50% !important;
                overflow: hidden;
                cursor: move !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
            }

            #smart-video-panel.collapsed .panel-content {
                display: none;
            }

            #smart-video-panel.collapsed .panel-header {
                justify-content: center !important;
                padding: 0 !important;
                border-radius: 50% !important;
                cursor: move !important;
                width: 60px !important;
                height: 60px !important;
                display: flex !important;
                align-items: center !important;
                position: absolute !important;
                top: 0 !important;
                left: 0 !important;
                background: linear-gradient(45deg, #ff6b6b, #4ecdc4) !important;
            }

            #smart-video-panel.collapsed .panel-icon {
                font-size: 24px !important;
                display: block !important;
            }

            .panel-header {
                background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                padding: 12px 15px;
                border-radius: 10px 10px 0 0;
                display: flex;
                justify-content: center;
                align-items: center;
                cursor: move;
                font-weight: bold;
            }

            .panel-content {
                padding: 15px;
            }

            .panel-buttons {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin-bottom: 10px;
            }

            .panel-btn {
                padding: 8px 12px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 12px;
                font-weight: bold;
                transition: all 0.2s ease;
            }

            .panel-btn.primary {
                background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
                color: white;
            }

            .panel-btn.primary:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            }

            .panel-btn.secondary {
                background: #95a5a6;
                color: white;
            }

            .panel-btn.secondary:hover {
                background: #7f8c8d;
            }

            .panel-status {
                font-size: 11px;
                opacity: 0.8;
                text-align: center;
            }

            .panel-icon {
                font-size: 16px;
            }
        `;
        document.head.appendChild(style);

        // 添加拖拽功能
        let isDragging = false;
        let dragOffset = { x: 0, y: 0 };

        panel.querySelector('.panel-header').addEventListener('mousedown', (e) => {
            isDragging = true;
            dragOffset.x = e.clientX - panel.offsetLeft;
            dragOffset.y = e.clientY - panel.offsetTop;
            panel.style.cursor = 'grabbing';
        });

        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                // 计算新位置
                let newLeft = e.clientX - dragOffset.x;
                let newTop = e.clientY - dragOffset.y;

                // 获取面板尺寸
                const panelRect = panel.getBoundingClientRect();
                const panelWidth = panelRect.width;

                // 获取视窗尺寸
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;

                // 边界限制 - 确保面板不会完全移出视窗
                const minLeft = -panelWidth + 50; // 允许大部分隐藏，但保留50px可见
                const maxLeft = viewportWidth - 50; // 右边界保留50px可见
                const minTop = 0; // 顶部不能超出
                const maxTop = viewportHeight - 50; // 底部保留50px可见

                // 应用边界限制
                newLeft = Math.max(minLeft, Math.min(maxLeft, newLeft));
                newTop = Math.max(minTop, Math.min(maxTop, newTop));

                // 设置新位置
                panel.style.left = newLeft + 'px';
                panel.style.top = newTop + 'px';
                panel.style.right = 'auto';
            }
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                panel.style.cursor = 'move';

                // 保存位置到本地存储
                if (typeof GM_setValue === 'function') {
                    try {
                        GM_setValue('panelPosition', {
                            left: panel.style.left,
                            top: panel.style.top
                        });
                    } catch (e) {
                        console.log('保存面板位置失败:', e);
                    }
                }
            }
        });

        // 双击重置位置
        panel.addEventListener('dblclick', () => {
            panel.style.left = 'auto';
            panel.style.top = '20px';
            panel.style.right = '20px';

            // 清除保存的位置
            if (typeof GM_setValue === 'function') {
                try {
                    GM_setValue('panelPosition', null);
                } catch (e) {
                    console.log('清除面板位置失败:', e);
                }
            }

            console.log('🔄 面板位置已重置');
            showNotification('🔄 面板位置已重置', 'info');
        });

        // 点击事件处理
        primaryBtn.addEventListener('click', () => {
            if (isSupportedPlatform()) {
                showSupportedPlatformDialog();
            } else {
                showExtractModeDialog();
            }
        });

        secondaryBtn.addEventListener('click', () => {
            showSettings();
        });

        // 面板收缩/展开功能
        let autoCollapseTimer = null;

        function startAutoCollapse() {
            if (autoCollapseTimer) clearTimeout(autoCollapseTimer);
            autoCollapseTimer = setTimeout(() => {
                if (!panel.classList.contains('collapsed')) {
                    panel.classList.add('collapsed');
                }
            }, 5000);
        }

        // 鼠标悬停时暂停自动收缩
        panel.addEventListener('mouseenter', () => {
            if (autoCollapseTimer) clearTimeout(autoCollapseTimer);
        });

        panel.addEventListener('mouseleave', () => {
            startAutoCollapse();
        });

        // 点击切换展开/收缩
        panel.addEventListener('click', (e) => {
            if (!isDragging) {
                if (panel.classList.contains('collapsed')) {
                    // 收缩状态：点击展开
                    panel.classList.remove('collapsed');
                    startAutoCollapse();
                } else {
                    // 展开状态：点击非按钮区域收缩
                    if (!e.target.classList.contains('panel-btn')) {
                        panel.classList.add('collapsed');
                        if (autoCollapseTimer) clearTimeout(autoCollapseTimer);
                    }
                }
            }
        });

        // 启动自动收缩
        startAutoCollapse();

        // 恢复保存的位置
        if (typeof GM_getValue === 'function') {
            try {
                const savedPosition = GM_getValue('panelPosition', null);
                if (savedPosition && savedPosition.left && savedPosition.top) {
                    panel.style.left = savedPosition.left;
                    panel.style.top = savedPosition.top;
                    panel.style.right = 'auto';
                    console.log('✅ 已恢复面板位置:', savedPosition);
                }
            } catch (e) {
                console.log('恢复面板位置失败:', e);
            }
        }

        return panel;
    }

    // 显示支持平台下载对话框
    function showSupportedPlatformDialog() {
        // 创建对话框内容
        const content = document.createElement('div');

        // URL输入
        const urlLabel = document.createElement('label');
        urlLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold;';
        urlLabel.textContent = '视频链接:';

        const urlInput = createInput('text', '', window.location.href);
        urlInput.style.cssText += `
            padding: 10px !important;
            border: 2px solid #ddd !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            margin-bottom: 15px !important;
            background: white !important;
            color: #333 !important;
        `;

        // 文件名输入
        const nameLabel = document.createElement('label');
        nameLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold;';
        nameLabel.textContent = '自定义文件名 (已自动提取):';

        const nameContainer = document.createElement('div');
        nameContainer.style.cssText = 'display: flex; gap: 8px; margin-bottom: 15px;';

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.placeholder = '留空使用页面标题';
        nameInput.value = getSmartVideoTitle(); // 自动填入智能提取的标题
        nameInput.style.cssText = `
            flex: 1 !important;
            padding: 10px !important;
            border: 2px solid #ddd !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            font-size: 14px !important;
            background: white !important;
            color: #333 !important;
        `;

        const refreshTitleBtn = document.createElement('button');
        refreshTitleBtn.type = 'button';
        refreshTitleBtn.textContent = '🔄';
        refreshTitleBtn.title = '重新提取标题';
        refreshTitleBtn.style.cssText = `
            padding: 10px 12px !important;
            border: 2px solid #ddd !important;
            background: #f8f9fa !important;
            border-radius: 5px !important;
            cursor: pointer !important;
            font-size: 14px !important;
        `;

        nameContainer.appendChild(nameInput);
        nameContainer.appendChild(refreshTitleBtn);

        // 质量选择
        const qualityLabel = document.createElement('label');
        qualityLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold;';
        qualityLabel.textContent = '质量选择:';

        const qualitySelect = document.createElement('select');
        qualitySelect.style.cssText = 'width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 8px; margin-bottom: 15px;';

        const qualities = [
            { value: 'best', text: '最佳质量' },
            { value: '720p', text: '720p' },
            { value: '1080p', text: '1080p' },
            { value: '1440p', text: '1440p' },
            { value: '2160p', text: '4K' }
        ];

        qualities.forEach(q => {
            const option = document.createElement('option');
            option.value = q.value;
            option.textContent = q.text;
            qualitySelect.appendChild(option);
        });

        // 音频选项
        const audioContainer = document.createElement('label');
        audioContainer.style.cssText = 'display: flex; align-items: center; cursor: pointer; margin-bottom: 20px;';

        const audioCheckbox = document.createElement('input');
        audioCheckbox.type = 'checkbox';
        audioCheckbox.style.marginRight = '8px';

        const audioText = document.createTextNode('仅下载音频');
        audioContainer.appendChild(audioCheckbox);
        audioContainer.appendChild(audioText);

        // 设置按钮 (单独一行)
        const settingsBtn = document.createElement('button');
        settingsBtn.textContent = '⚙️ 设置';
        settingsBtn.style.cssText = 'width: 100%; padding: 10px; margin-bottom: 15px; background: #6c757d; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold;';

        // 按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 10px; justify-content: flex-end;';

        const cancelBtn = createButton('取消', '#6c757d', () => overlay.remove());

        const downloadBtn = createButton('开始下载', '#667eea', null);

        buttonContainer.appendChild(cancelBtn);
        buttonContainer.appendChild(downloadBtn);

        // 添加所有元素到内容容器
        content.appendChild(urlLabel);
        content.appendChild(urlInput);
        content.appendChild(nameLabel);
        content.appendChild(nameContainer);
        content.appendChild(qualityLabel);
        content.appendChild(qualitySelect);
        content.appendChild(audioContainer);
        content.appendChild(settingsBtn);
        content.appendChild(buttonContainer);

        // 使用新的模态对话框工具
        const { overlay } = createModalDialog('🎬 下载视频', content);
        document.body.appendChild(overlay);

        // 绑定事件
        refreshTitleBtn.addEventListener('click', () => {
            console.log('🔄 用户点击刷新标题');
            const newTitle = getSmartVideoTitle();
            nameInput.value = newTitle;
            showNotification('✅ 标题已刷新', 'success');
        });

        settingsBtn.addEventListener('click', () => {
            overlay.remove();
            setTimeout(showSettings, 100);
        });

        cancelBtn.addEventListener('click', () => overlay.remove());

        // 自动聚焦第一个输入框
        setTimeout(() => {
            urlInput.focus();
            urlInput.select();
        }, 100);

        downloadBtn.addEventListener('click', () => {
            const url = urlInput.value.trim();
            const customName = nameInput.value.trim();
            const quality = qualitySelect.value;
            const audioOnly = audioCheckbox.checked;

            // 🔍 调试日志
            console.log('🔍 支持平台模式下载:', { url, customName, quality, audioOnly });

            if (!url) {
                console.log('❌ URL为空，显示错误提示');
                showNotification('请输入视频链接', 'error');
                return;
            }

            // 获取并清理文件名
            const rawFilename = customName || getPageTitle();
            const cleanedFilename = cleanTitle(rawFilename);

            if (!cleanedFilename || cleanedFilename === 'untitled') {
                showNotification('文件名包含无效字符，已使用默认名称', 'warning');
                cleanedFilename = 'video_download';
            }

            // 🔧 直接发送原始URL和自定义文件名，适应服务器API
            sendToServerWithFilename(url, quality, audioOnly, cleanedFilename);
            overlay.remove();
        });
    }

    // 显示提取模式对话框
    function showExtractModeDialog() {
        // 🎯 合并页面提取和网络监听检测到的视频
        const pageVideos = extractVideosFromPage();

        // 🎯 获取当前所有检测到的视频（包括网络监听检测到的M3U8）
        const allVideos = [...extractedVideos];

        console.log(`📊 提取模式统计: 页面提取${pageVideos.length}个, 总计${allVideos.length}个`);

        if (allVideos.length === 0) {
            showNotification('未在当前页面找到视频文件。请尝试播放视频后再次提取，或检查控制台日志。', 'error');
            return;
        }

        // 使用所有检测到的视频
        const videos = allVideos;

        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background: rgba(0,0,0,0.7) !important;
            z-index: 999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white !important;
            padding: 30px !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
            min-width: 500px !important;
            max-width: 80vw !important;
            max-height: 80vh !important;
            overflow-y: auto !important;
            font-family: Arial, sans-serif !important;
            color: #333 !important;
        `;

        // 标题
        const title = document.createElement('h3');
        title.style.cssText = 'margin: 0 0 20px 0; text-align: center; color: #667eea;';
        title.textContent = `🔍 找到 ${videos.length} 个视频文件`;

        // 视频列表容器
        const videoList = document.createElement('div');
        videoList.style.cssText = 'margin-bottom: 20px; max-height: 400px; overflow-y: auto;';

        videos.forEach((video) => {
            const videoItem = document.createElement('div');
            videoItem.style.cssText = `
                border: 2px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 10px;
                background: #f9f9f9;
            `;

            // 视频头部
            const header = document.createElement('div');
            header.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;';

            const typeSpan = document.createElement('span');
            typeSpan.style.cssText = 'background: #667eea; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;';
            typeSpan.textContent = video.type.toUpperCase();

            const sourceSpan = document.createElement('span');
            sourceSpan.style.cssText = 'font-size: 11px; color: #666;';
            sourceSpan.textContent = video.source;

            header.appendChild(typeSpan);
            header.appendChild(sourceSpan);

            // 视频标题
            const titleDiv = document.createElement('div');
            titleDiv.style.cssText = 'font-weight: bold; margin-bottom: 5px; color: #333;';
            titleDiv.textContent = video.title;

            // 视频URL
            const urlDiv = document.createElement('div');
            urlDiv.style.cssText = 'font-size: 12px; color: #666; margin-bottom: 10px; word-break: break-all;';
            urlDiv.textContent = video.url.length > 80 ? video.url.substring(0, 80) + '...' : video.url;

            // 操作按钮
            const actions = document.createElement('div');
            actions.style.cssText = 'display: flex; gap: 8px;';

            const downloadBtn = createButton('📤 下载', '#2ecc71', () => showExtractVideoDownloadDialog(video));
            const copyBtn = createButton('📋 复制', '#3498db', () => copyVideoUrl(video.url));
            const testBtn = createButton('🔗 测试', '#f39c12', () => testVideoUrl(video.url));

            actions.appendChild(downloadBtn);
            actions.appendChild(copyBtn);
            actions.appendChild(testBtn);

            videoItem.appendChild(header);
            videoItem.appendChild(titleDiv);
            videoItem.appendChild(urlDiv);
            videoItem.appendChild(actions);

            videoList.appendChild(videoItem);
        });

        // 按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 10px; margin-top: 15px;';

        // 🎯 使用通用按钮创建函数
        const refreshBtn = createButton('🔄 重新扫描', '#3498db', null);
        const settingsBtn2 = createButton('⚙️ 设置', '#6c757d', null);
        const closeBtn = createButton('关闭', '#95a5a6', null);

        // 设置flex样式
        [refreshBtn, settingsBtn2, closeBtn].forEach(btn => {
            btn.style.flex = '1';
            btn.style.padding = '12px';
            btn.style.fontWeight = 'bold';
        });

        buttonContainer.appendChild(refreshBtn);
        buttonContainer.appendChild(settingsBtn2);
        buttonContainer.appendChild(closeBtn);

        dialog.appendChild(title);
        dialog.appendChild(videoList);
        dialog.appendChild(buttonContainer);

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // 绑定事件
        refreshBtn.addEventListener('click', () => {
            console.log('🔄 用户点击重新扫描');
            closeDialog();
            // 延迟一下再重新扫描
            setTimeout(() => {
                showExtractModeDialog();
            }, 500);
        });

        settingsBtn2.addEventListener('click', () => {
            closeDialog();
            setTimeout(showSettings, 100);
        });

        closeBtn.addEventListener('click', closeDialog);

        // 🎯 使用通用模态对话框事件绑定
        bindModalEvents(overlay, dialog, closeDialog);

        function closeDialog() {
            overlay.remove();
        }
    }

    // 显示提取视频的下载确认对话框
    function showExtractVideoDownloadDialog(video) {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background: rgba(0,0,0,0.7) !important;
            z-index: 999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white !important;
            padding: 30px !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
            min-width: 500px !important;
            max-width: 80vw !important;
            font-family: Arial, sans-serif !important;
            color: #333 !important;
        `;

        // 标题
        const title = document.createElement('h3');
        title.style.cssText = 'margin: 0 0 20px 0; text-align: center; color: #667eea;';
        title.textContent = '📥 确认下载提取的视频';

        // 视频信息显示
        const videoInfo = document.createElement('div');
        videoInfo.style.cssText = 'background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-size: 14px;';
        // 安全的DOM创建
        const infoTitle = document.createElement('div');
        infoTitle.style.cssText = 'font-weight: bold; margin-bottom: 8px; color: #495057;';
        infoTitle.textContent = '📺 视频信息:';

        const urlInfo = document.createElement('div');
        urlInfo.style.marginBottom = '5px';
        const urlLabel = document.createElement('strong');
        urlLabel.textContent = '链接:';
        urlInfo.appendChild(urlLabel);
        urlInfo.appendChild(document.createTextNode(' ' + video.url));

        const typeInfo = document.createElement('div');
        typeInfo.style.marginBottom = '5px';
        const typeLabel = document.createElement('strong');
        typeLabel.textContent = '类型:';
        typeInfo.appendChild(typeLabel);
        typeInfo.appendChild(document.createTextNode(' ' + video.type.toUpperCase()));

        const sourceInfo = document.createElement('div');
        sourceInfo.style.marginBottom = '5px';
        const sourceLabel = document.createElement('strong');
        sourceLabel.textContent = '来源:';
        sourceInfo.appendChild(sourceLabel);
        sourceInfo.appendChild(document.createTextNode(' ' + video.source));

        videoInfo.appendChild(infoTitle);
        videoInfo.appendChild(urlInfo);
        videoInfo.appendChild(typeInfo);
        videoInfo.appendChild(sourceInfo);

        // 文件名输入
        const nameLabel = document.createElement('label');
        nameLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold;';
        nameLabel.textContent = '自定义文件名:';

        const nameContainer = document.createElement('div');
        nameContainer.style.cssText = 'display: flex; gap: 8px; margin-bottom: 15px;';

        // 智能提取文件名
        let smartTitle = video.title || '';
        if (smartTitle.includes('.m3u8') || smartTitle.includes('video') || smartTitle.length < 10) {
            smartTitle = getSmartVideoTitle();
        }

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = smartTitle;
        nameInput.placeholder = '输入自定义文件名';
        nameInput.style.cssText = `
            flex: 1 !important;
            padding: 10px !important;
            border: 2px solid #ddd !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            font-size: 14px !important;
            background: white !important;
            color: #333 !important;
        `;

        const refreshTitleBtn = document.createElement('button');
        refreshTitleBtn.type = 'button';
        refreshTitleBtn.textContent = '🔄';
        refreshTitleBtn.title = '重新提取标题';
        refreshTitleBtn.style.cssText = `
            padding: 10px 12px !important;
            border: 2px solid #ddd !important;
            background: #f8f9fa !important;
            border-radius: 5px !important;
            cursor: pointer !important;
            font-size: 14px !important;
        `;

        nameContainer.appendChild(nameInput);
        nameContainer.appendChild(refreshTitleBtn);

        // 文件名预览
        const namePreview = document.createElement('div');
        namePreview.style.cssText = 'font-size: 12px; color: #6c757d; margin-bottom: 15px; padding: 8px; background: #f8f9fa; border-radius: 4px; border: 1px solid #e9ecef;';

        function updateNamePreview() {
            const rawName = nameInput.value.trim();
            if (rawName) {
                const cleanedName = cleanTitle(rawName);
                if (cleanedName && cleanedName !== 'untitled') {
                    namePreview.textContent = '📝 清理后的文件名: ';
                    const strong = document.createElement('strong');
                    strong.textContent = cleanedName;
                    namePreview.appendChild(strong);
                    namePreview.style.color = '#28a745';
                } else {
                    namePreview.textContent = '⚠️ 文件名包含无效字符，请重新输入';
                    namePreview.style.color = '#dc3545';
                }
            } else {
                namePreview.textContent = '💡 提示: 文件名将自动清理特殊字符';
                namePreview.style.color = '#6c757d';
            }
        }

        // 初始化预览
        updateNamePreview();

        // 绑定输入事件
        nameInput.addEventListener('input', updateNamePreview);

        // 质量选择
        const qualityLabel = document.createElement('label');
        qualityLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold;';
        qualityLabel.textContent = '下载质量:';

        const qualitySelect = document.createElement('select');
        qualitySelect.style.cssText = `
            width: 100% !important;
            padding: 10px !important;
            border: 2px solid #ddd !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            margin-bottom: 15px !important;
            font-size: 14px !important;
            background: white !important;
            color: #333 !important;
        `;

        const qualityOptions = [
            { value: 'high', text: '高质量' },
            { value: 'medium', text: '中等质量' },
            { value: 'low', text: '低质量' }
        ];

        qualityOptions.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option.value;
            optionElement.textContent = option.text;
            if (option.value === 'high') {
                optionElement.selected = true;
            }
            qualitySelect.appendChild(optionElement);
        });

        // 音频选项
        const audioContainer = document.createElement('div');
        audioContainer.style.cssText = 'margin-bottom: 20px;';

        const audioCheckbox = document.createElement('input');
        audioCheckbox.type = 'checkbox';
        audioCheckbox.id = 'extractAudioOnly';
        audioCheckbox.style.cssText = 'margin-right: 8px;';

        const audioLabel = document.createElement('label');
        audioLabel.htmlFor = 'extractAudioOnly';
        audioLabel.style.cssText = 'font-weight: bold; cursor: pointer;';
        audioLabel.textContent = '仅下载音频';

        audioContainer.appendChild(audioCheckbox);
        audioContainer.appendChild(audioLabel);

        // 按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 10px; justify-content: flex-end;';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '取消';
        cancelBtn.style.cssText = 'padding: 12px 24px; border: 2px solid #ddd; background: white; border-radius: 8px; cursor: pointer; font-weight: bold;';

        const downloadBtn = document.createElement('button');
        downloadBtn.textContent = '📥 开始下载';
        downloadBtn.style.cssText = 'padding: 12px 24px; border: none; background: #28a745; color: white; border-radius: 8px; cursor: pointer; font-weight: bold;';

        buttonContainer.appendChild(cancelBtn);
        buttonContainer.appendChild(downloadBtn);

        // 组装对话框
        dialog.appendChild(title);
        dialog.appendChild(videoInfo);
        dialog.appendChild(nameLabel);
        dialog.appendChild(nameContainer);
        dialog.appendChild(namePreview);
        dialog.appendChild(qualityLabel);
        dialog.appendChild(qualitySelect);
        dialog.appendChild(audioContainer);
        dialog.appendChild(buttonContainer);

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // 绑定事件
        refreshTitleBtn.addEventListener('click', () => {
            const newTitle = getSmartVideoTitle();
            nameInput.value = newTitle;
            updateNamePreview();  // 更新预览
            showNotification('✅ 标题已刷新', 'success');
        });

        cancelBtn.addEventListener('click', closeDialog);

        downloadBtn.addEventListener('click', () => {
            const rawFilename = nameInput.value.trim();
            const quality = qualitySelect.value;
            const audioOnly = audioCheckbox.checked;

            // 🔍 调试日志
            console.log('🔍 提取模式下载:', { rawFilename, quality, audioOnly });

            if (!rawFilename) {
                console.log('❌ 文件名为空，显示错误提示');
                showNotification('请输入文件名', 'error');
                return;
            }

            // 清理文件名，确保符合服务器要求
            const customFilename = cleanTitle(rawFilename);
            console.log('🧹 文件名清理详情:');
            console.log('   输入:', `"${rawFilename}"`);
            console.log('   输出:', `"${customFilename}"`);
            console.log('   输出长度:', customFilename.length);
            console.log('   是否为untitled:', customFilename === 'untitled');

            if (!customFilename || customFilename === 'untitled') {
                console.log('❌ 清理后文件名无效，显示错误提示');
                showNotification('文件名包含无效字符，请重新输入', 'error');
                return;
            }

            console.log('✅ 文件名验证通过，开始下载');
            console.log('📤 即将发送的参数:');
            console.log('   video.url:', video.url);
            console.log('   customFilename:', `"${customFilename}"`);
            console.log('   quality:', quality);
            console.log('   audioOnly:', audioOnly);

            // 关闭对话框并开始下载
            closeDialog();
            downloadExtractedVideo(video, customFilename, quality, audioOnly);
        });

        // 🎯 使用通用模态对话框事件绑定
        bindModalEvents(overlay, dialog, closeDialog);

        // 自动聚焦文件名输入框
        setTimeout(() => {
            nameInput.focus();
            nameInput.select();
        }, 100);

        function closeDialog() {
            overlay.remove();
        }
    }

    // 下载提取的视频 (修改为接收用户确认的参数)
    function downloadExtractedVideo(video, customFilename, quality, audioOnly) {
        const currentServerUrl = GM_getValue('serverUrl', 'http://localhost:8090');

        // 🔍 调试日志
        console.log('🚀 downloadExtractedVideo:', { url: video.url, customFilename, quality, audioOnly });

        // 🎯 使用通用请求数据构建函数
        const requestData = buildRequestData(video.url, quality, audioOnly, customFilename, 'extracted_video_v3.2.0');

        // 显示发送详情对话框
        const statusElement = showSendDetails(requestData, currentServerUrl);

        // 🎯 使用通用API密钥处理函数
        const headers = { 'Content-Type': 'application/json' };
        addApiKeyToRequest(requestData, headers);

        // 🔧 临时修复：强制使用通用端点避免405错误
        const hasCustomFilename = customFilename && customFilename.length > 0;
        const downloadEndpoints = [
            `${currentServerUrl}${CONSTANTS.ENDPOINTS.DOWNLOAD}`,    // 通用端点，支持自定义文件名
            `${currentServerUrl}${CONSTANTS.ENDPOINTS.SHORTCUTS}`   // iOS端点作为备用（暂时跳过）
        ];

        console.log('🔧 提取模式端点选择策略（临时修复405错误）:');
        console.log('   hasCustomFilename:', hasCustomFilename);
        console.log('   customFilename:', `"${customFilename}"`);
        console.log('   强制使用通用端点:', downloadEndpoints[0]);

        // 使用通用重试函数
        const tryDownload = createDownloadRetryFunction(requestData, statusElement, downloadEndpoints, '提取模式 - ');
        tryDownload();
    }

    // 复制视频URL
    function copyVideoUrl(url) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(() => {
                showNotification('✅ URL已复制到剪贴板', 'success');
            }).catch(() => {
                showManualCopyDialog(url);
            });
        } else {
            showManualCopyDialog(url);
        }
    }

    // 显示手动复制对话框
    function showManualCopyDialog(url) {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background: rgba(0,0,0,0.7) !important;
            z-index: 999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white !important;
            padding: 30px !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
            min-width: 400px !important;
            font-family: Arial, sans-serif !important;
            color: #333 !important;
        `;

        const title = document.createElement('h3');
        title.style.cssText = 'margin: 0 0 15px 0; text-align: center; color: #e74c3c;';
        title.textContent = '📋 手动复制URL';

        const description = document.createElement('p');
        description.style.cssText = 'margin-bottom: 15px; color: #666;';
        description.textContent = '自动复制失败，请手动复制以下URL:';

        const textarea = document.createElement('textarea');
        textarea.value = url;
        textarea.readOnly = true;
        textarea.style.cssText = `
            width: 100% !important;
            height: 80px !important;
            padding: 10px !important;
            border: 2px solid #ddd !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            margin-bottom: 15px !important;
            font-size: 12px !important;
            background: white !important;
            color: #333 !important;
            font-family: monospace !important;
            resize: vertical !important;
        `;

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '关闭';
        closeBtn.style.cssText = 'width: 100%; padding: 12px; background: #95a5a6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold;';

        dialog.appendChild(title);
        dialog.appendChild(description);
        dialog.appendChild(textarea);
        dialog.appendChild(closeBtn);

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // 自动选中文本
        setTimeout(() => {
            textarea.select();
            textarea.focus();
        }, 100);

        closeBtn.addEventListener('click', () => {
            overlay.remove();
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        });

        // 阻止对话框内点击冒泡
        dialog.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    // 测试视频URL
    function testVideoUrl(url) {
        window.open(url, '_blank');
        showNotification('🔗 已在新标签页打开视频链接', 'info');
    }

    // 显示设置对话框
    function showSettings() {
        // 创建设置内容
        const content = document.createElement('div');

        // 服务器地址设置
        const serverLabel = document.createElement('label');
        serverLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold;';
        serverLabel.textContent = '服务器地址:';

        const serverInput = document.createElement('input');
        serverInput.type = 'text';
        serverInput.value = GM_getValue('serverUrl', 'http://localhost:8090');
        serverInput.placeholder = 'http://localhost:8090';
        serverInput.style.cssText = `
            width: 100% !important;
            padding: 10px !important;
            border: 2px solid #ddd !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            margin-bottom: 15px !important;
            font-size: 14px !important;
            background: white !important;
            color: #333 !important;
        `;

        // 服务器API密钥配置
        const apiSection = document.createElement('div');
        apiSection.style.cssText = 'background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 8px; margin-bottom: 15px;';

        const apiTitle = document.createElement('div');
        apiTitle.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #856404;';
        apiTitle.textContent = '🔑 服务器API密钥 (必需):';

        const apiWarning = document.createElement('div');
        apiWarning.style.cssText = 'background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 8px; border-radius: 4px; margin-bottom: 10px; font-size: 12px;';
        apiWarning.textContent = '⚠️ 没有API密钥，服务器将拒绝执行下载请求！';

        // 服务器API密钥
        const apiKeyLabel = document.createElement('label');
        apiKeyLabel.style.cssText = 'display: block; margin-bottom: 5px; font-weight: bold; font-size: 13px;';
        apiKeyLabel.textContent = 'API密钥:';

        const apiKeyInput = document.createElement('input');
        apiKeyInput.type = 'password';
        apiKeyInput.value = GM_getValue('serverApiKey', '');
        apiKeyInput.placeholder = '输入服务器API密钥';
        apiKeyInput.style.cssText = `
            width: 100% !important;
            padding: 10px !important;
            border: 2px solid #ffc107 !important;
            border-radius: 5px !important;
            box-sizing: border-box !important;
            margin-bottom: 10px !important;
            font-size: 14px !important;
            background: white !important;
            color: #333 !important;
        `;

        // 显示/隐藏密钥按钮
        const toggleContainer = document.createElement('div');
        toggleContainer.style.cssText = 'display: flex; align-items: center; margin-bottom: 10px;';

        const showApiKeyBtn = document.createElement('button');
        showApiKeyBtn.type = 'button';
        showApiKeyBtn.textContent = '👁️ 显示密钥';
        showApiKeyBtn.style.cssText = `
            padding: 6px 12px !important;
            border: 1px solid #ddd !important;
            background: #f8f9fa !important;
            border-radius: 4px !important;
            cursor: pointer !important;
            font-size: 12px !important;
            margin-right: 10px !important;
        `;

        const apiKeyStatus = document.createElement('span');
        apiKeyStatus.style.cssText = 'font-size: 12px; color: #6c757d;';

        toggleContainer.appendChild(showApiKeyBtn);
        toggleContainer.appendChild(apiKeyStatus);

        apiSection.appendChild(apiTitle);
        apiSection.appendChild(apiWarning);
        apiSection.appendChild(apiKeyLabel);
        apiSection.appendChild(apiKeyInput);
        apiSection.appendChild(toggleContainer);

        // 当前设置显示
        const currentSettings = document.createElement('div');
        currentSettings.style.cssText = 'background: #e8f5e8; padding: 15px; border-radius: 8px; margin-bottom: 15px; font-size: 13px;';

        const settingsContent = document.createElement('div');
        const serverApiKey = GM_getValue('serverApiKey', '');

        // 安全的DOM创建
        const settingsTitle = document.createElement('div');
        settingsTitle.style.cssText = 'font-weight: bold; margin-bottom: 8px; color: #495057;';
        settingsTitle.textContent = '📋 当前设置:';

        const serverDiv = document.createElement('div');
        serverDiv.textContent = `🌐 服务器地址: ${GM_getValue('serverUrl', 'http://localhost:8090')}`;

        const apiDiv = document.createElement('div');
        apiDiv.textContent = `🔑 API密钥: ${serverApiKey ? '✅ 已配置' : '❌ 未配置'}`;

        const versionDiv = document.createElement('div');
        versionDiv.textContent = '📊 脚本版本: 3.2.0';

        const platformDiv = document.createElement('div');
        platformDiv.textContent = `🎯 支持平台: ${SUPPORTED_PLATFORMS.length} 个`;

        settingsContent.appendChild(settingsTitle);
        settingsContent.appendChild(serverDiv);
        settingsContent.appendChild(apiDiv);
        settingsContent.appendChild(versionDiv);
        settingsContent.appendChild(platformDiv);
        currentSettings.appendChild(settingsContent);

        // 过滤统计按钮
        const statsBtn = document.createElement('button');
        statsBtn.textContent = '📊 查看过滤统计';
        statsBtn.style.cssText = 'width: 100%; padding: 10px; margin-bottom: 10px; background: #6f42c1; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;';

        // 重置统计按钮
        const resetStatsBtn = document.createElement('button');
        resetStatsBtn.textContent = '🔄 重置统计';
        resetStatsBtn.style.cssText = 'width: 100%; padding: 10px; margin-bottom: 15px; background: #fd7e14; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;';

        // 测试连接按钮
        const testBtn = document.createElement('button');
        testBtn.textContent = '🔗 测试连接';
        testBtn.style.cssText = 'width: 100%; padding: 10px; margin-bottom: 15px; background: #17a2b8; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;';

        // 按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 10px; justify-content: flex-end;';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '取消';
        cancelBtn.style.cssText = 'padding: 12px 24px; border: 2px solid #ddd; background: white; border-radius: 5px; cursor: pointer; font-weight: bold;';

        const saveBtn = document.createElement('button');
        saveBtn.textContent = '保存设置';
        saveBtn.style.cssText = 'padding: 12px 24px; border: none; background: #28a745; color: white; border-radius: 5px; cursor: pointer; font-weight: bold;';

        buttonContainer.appendChild(cancelBtn);
        buttonContainer.appendChild(saveBtn);

        // 添加所有元素到内容容器
        content.appendChild(serverLabel);
        content.appendChild(serverInput);
        content.appendChild(apiSection);
        content.appendChild(currentSettings);
        content.appendChild(statsBtn);
        content.appendChild(resetStatsBtn);
        content.appendChild(testBtn);
        content.appendChild(buttonContainer);

        // 使用新的模态对话框工具
        const { overlay } = createModalDialog('⚙️ 下载助手设置', content);
        document.body.appendChild(overlay);

        // 更新API密钥状态显示
        function updateApiKeyStatus() {
            const keyValue = apiKeyInput.value.trim();
            if (keyValue) {
                apiKeyStatus.textContent = `长度: ${keyValue.length} 字符`;
                apiKeyStatus.style.color = '#28a745';
            } else {
                apiKeyStatus.textContent = '未输入API密钥';
                apiKeyStatus.style.color = '#dc3545';
            }
        }

        // 初始化状态
        updateApiKeyStatus();

        // 绑定事件
        apiKeyInput.addEventListener('input', updateApiKeyStatus);

        showApiKeyBtn.addEventListener('click', () => {
            if (apiKeyInput.type === 'password') {
                apiKeyInput.type = 'text';
                showApiKeyBtn.textContent = '🙈 隐藏密钥';
            } else {
                apiKeyInput.type = 'password';
                showApiKeyBtn.textContent = '👁️ 显示密钥';
            }
        });

        // 过滤统计按钮事件
        statsBtn.addEventListener('click', () => {
            showDetailedFilterStats();
        });

        // 重置统计按钮事件
        resetStatsBtn.addEventListener('click', () => {
            resetFilterStats();
        });

        testBtn.addEventListener('click', () => {
            const testUrl = serverInput.value.trim();
            const testApiKey = apiKeyInput.value.trim();

            if (!testUrl) {
                showNotification('请输入服务器地址', 'error');
                return;
            }

            if (!testApiKey) {
                showNotification('请输入API密钥', 'error');
                return;
            }

            testBtn.textContent = '🔄 测试中...';
            testBtn.disabled = true;

            // 使用项目中实际的API端点
            const healthEndpoints = [
                `${testUrl}/api/health`,  // 项目中的健康检查端点
                `${testUrl}/api/info`     // 备用端点
            ];

            let currentEndpoint = 0;

            function tryNextEndpoint() {
                if (currentEndpoint >= healthEndpoints.length) {
                    testBtn.textContent = '🔗 测试连接';
                    testBtn.disabled = false;
                    showNotification('❌ 所有端点都无法连接', 'error');
                    return;
                }

                const endpoint = healthEndpoints[currentEndpoint];
                console.log(`🔗 测试端点: ${endpoint}`);

                GM_xmlhttpRequest({
                    method: 'GET',
                    url: endpoint,
                    headers: {
                        'X-API-Key': testApiKey
                    },
                    timeout: 5000,
                    onload: function(response) {
                        if (response.status === 200) {
                            testBtn.textContent = '🔗 测试连接';
                            testBtn.disabled = false;
                            showNotification(`✅ 服务器连接成功: ${endpoint}`, 'success');
                        } else if (response.status === 401) {
                            testBtn.textContent = '🔗 测试连接';
                            testBtn.disabled = false;
                            showNotification('❌ API密钥无效', 'error');
                        } else if (response.status === 404) {
                            // 404错误，尝试下一个端点
                            currentEndpoint++;
                            tryNextEndpoint();
                        } else {
                            testBtn.textContent = '🔗 测试连接';
                            testBtn.disabled = false;
                            showNotification(`❌ 服务器响应错误: HTTP ${response.status}`, 'error');
                        }
                    },
                    onerror: function() {
                        // 连接错误，尝试下一个端点
                        currentEndpoint++;
                        tryNextEndpoint();
                    },
                    ontimeout: function() {
                        // 超时，尝试下一个端点
                        currentEndpoint++;
                        tryNextEndpoint();
                    }
                });
            }

            // 开始测试第一个端点
            tryNextEndpoint();
        });

        saveBtn.addEventListener('click', () => {
            const newUrl = serverInput.value.trim();
            const newApiKey = apiKeyInput.value.trim();

            if (!newUrl) {
                showNotification('请输入服务器地址', 'error');
                return;
            }

            if (!newApiKey) {
                showNotification('请输入API密钥', 'error');
                return;
            }

            // 验证URL格式
            try {
                new URL(newUrl);
            } catch (e) {
                showNotification('请输入有效的URL格式', 'error');
                return;
            }

            // 保存服务器地址和API密钥
            GM_setValue('serverUrl', newUrl);
            GM_setValue('serverApiKey', newApiKey);

            showNotification('✅ 设置已保存', 'success');
            overlay.remove();
        });

        cancelBtn.addEventListener('click', () => overlay.remove());

        // 自动聚焦服务器地址输入框
        setTimeout(() => {
            serverInput.focus();
            serverInput.select();
        }, 100);
    }

    // 显示发送详情对话框
    function showSendDetails(requestData, serverUrl) {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background: rgba(0,0,0,0.7) !important;
            z-index: 999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: white !important;
            padding: 30px !important;
            border-radius: 10px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3) !important;
            min-width: 500px !important;
            max-width: 80vw !important;
            font-family: Arial, sans-serif !important;
            color: #333 !important;
        `;

        // 标题
        const title = document.createElement('h3');
        title.style.cssText = 'margin: 0 0 20px 0; text-align: center; color: #28a745;';
        title.textContent = '📤 发送到服务器的详细信息';

        // 请求信息
        const requestInfo = document.createElement('div');
        requestInfo.style.cssText = 'background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; font-family: monospace; font-size: 13px;';

        const infoContent = document.createElement('div');
        const serverApiKey = GM_getValue('serverApiKey', '');

        // 安全的DOM创建
        const requestTitle = document.createElement('div');
        requestTitle.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #495057;';
        requestTitle.textContent = '🌐 请求信息:';

        const serverInfo = createLabelDiv('服务器地址:');
        serverInfo.appendChild(document.createTextNode(' ' + serverUrl));

        const methodInfo = createInfoLine('请求方法:', 'POST');

        const pathInfo = createInfoLine('请求路径:', '/api/shortcuts/download');

        const contentInfo = createInfoLine('内容类型:', 'application/json');

        const authInfo = createInfoLine('认证方式:', 'X-API-Key头 + 请求体');

        const apiInfo = createLabelDiv('API密钥:', 'margin-bottom: 15px;');
        apiInfo.appendChild(document.createTextNode(' ' + (serverApiKey ? '✅ 已配置' : '❌ 未配置')));

        const dataTitle = document.createElement('div');
        dataTitle.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #495057;';
        dataTitle.textContent = '📋 请求数据:';

        const urlData = createLabelDiv('视频链接:');
        urlData.appendChild(document.createTextNode(' ' + requestData.url));

        const qualityData = createInfoLine('视频质量:', requestData.quality || 'high');

        const audioData = createInfoLine('仅音频:', requestData.audio_only ? '是' : '否');

        const filenameData = createInfoLine('自定义文件名:', requestData.custom_filename || '使用默认');

        const sourceData = createInfoLine('来源:', requestData.source);

        infoContent.appendChild(requestTitle);
        infoContent.appendChild(serverInfo);
        infoContent.appendChild(methodInfo);
        infoContent.appendChild(pathInfo);
        infoContent.appendChild(contentInfo);
        infoContent.appendChild(authInfo);
        infoContent.appendChild(apiInfo);
        infoContent.appendChild(dataTitle);
        infoContent.appendChild(urlData);
        infoContent.appendChild(qualityData);
        infoContent.appendChild(audioData);
        infoContent.appendChild(filenameData);
        infoContent.appendChild(sourceData);
        requestInfo.appendChild(infoContent);

        // JSON数据显示
        const jsonData = document.createElement('div');
        jsonData.style.cssText = 'background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 8px; margin-bottom: 15px; font-family: monospace; font-size: 12px; overflow-x: auto;';

        const jsonTitle = document.createElement('div');
        jsonTitle.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #3498db;';
        jsonTitle.textContent = '📄 JSON请求体:';

        const jsonContent = document.createElement('pre');
        jsonContent.style.cssText = 'margin: 0; white-space: pre-wrap; word-wrap: break-word;';
        jsonContent.textContent = JSON.stringify(requestData, null, 2);

        jsonData.appendChild(jsonTitle);
        jsonData.appendChild(jsonContent);

        // 状态显示
        const statusDiv = document.createElement('div');
        statusDiv.id = 'send-status';
        statusDiv.style.cssText = 'background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; padding: 10px; border-radius: 5px; margin-bottom: 15px; text-align: center;';
        statusDiv.textContent = '⏳ 正在发送请求...';

        // 按钮
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '关闭';
        closeBtn.style.cssText = 'width: 100%; padding: 12px; background: #95a5a6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold;';

        // 组装对话框
        dialog.appendChild(title);
        dialog.appendChild(requestInfo);
        dialog.appendChild(jsonData);
        dialog.appendChild(statusDiv);
        dialog.appendChild(closeBtn);

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        // 绑定事件
        closeBtn.addEventListener('click', () => {
            overlay.remove();
        });

        // 🎯 使用通用模态对话框事件绑定
        bindModalEvents(overlay, dialog);

        return statusDiv; // 返回状态元素用于更新
    }

    // 发送到服务器 (带文件名)
    function sendToServerWithFilename(url, quality, audioOnly, filename) {
        const currentServerUrl = GM_getValue('serverUrl', 'http://localhost:8090');

        // 🔍 调试日志
        console.log('🚀 sendToServerWithFilename:', { url, filename, quality, audioOnly });

        // 🔧 如果没有自定义文件名，尝试从URL中提取
        let finalCustomFilename = filename || '';
        if (!finalCustomFilename) {
            finalCustomFilename = extractFilenameFromUrl(url) || '';
            if (finalCustomFilename) {
                console.log('🔧 从URL提取自定义文件名:', finalCustomFilename);
            }
        }

        // 🔧 SSE连接将在进度跟踪器中建立，避免重复连接

        // 🎯 使用通用请求数据构建函数
        const requestData = buildRequestData(url, quality, audioOnly, finalCustomFilename, 'smart_video_downloader_v3.2.0');

        // 显示发送详情对话框
        const statusElement = showSendDetails(requestData, currentServerUrl);

        // 🎯 使用通用API密钥处理函数
        const headers = { 'Content-Type': 'application/json' };
        addApiKeyToRequest(requestData, headers);

        // 🔧 临时修复：强制使用通用端点避免405错误
        const hasCustomFilename = finalCustomFilename && finalCustomFilename.length > 0;
        const downloadEndpoints = [
            `${currentServerUrl}${CONSTANTS.ENDPOINTS.DOWNLOAD}`,    // 通用端点，支持自定义文件名
            `${currentServerUrl}${CONSTANTS.ENDPOINTS.SHORTCUTS}`   // iOS端点作为备用（暂时跳过）
        ];

        console.log('🔧 支持平台端点选择策略（临时修复405错误）:');
        console.log('   hasCustomFilename:', hasCustomFilename);
        console.log('   finalCustomFilename:', `"${finalCustomFilename}"`);
        console.log('   强制使用通用端点:', downloadEndpoints[0]);

        // 使用通用重试函数
        const tryDownload = createDownloadRetryFunction(requestData, statusElement, downloadEndpoints, '支持平台 - ');
        tryDownload();
    }



    // ==================== 工具函数 ====================

    // 🔧 通用拖动功能（复用现有逻辑）
    function makeElementDraggable(element, options = {}) {
        let isDragging = false;
        let dragOffset = { x: 0, y: 0 };

        const {
            excludeSelector = null,
            onDragStart = null,
            onDragEnd = null,
            bounds = null
        } = options;

        element.addEventListener('mousedown', (e) => {
            // 检查是否点击了排除的元素
            if (excludeSelector && e.target.textContent === excludeSelector) return;

            isDragging = true;
            dragOffset.x = e.clientX - element.offsetLeft;
            dragOffset.y = e.clientY - element.offsetTop;
            element.style.cursor = 'grabbing';

            if (onDragStart) onDragStart();
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            let newLeft = e.clientX - dragOffset.x;
            let newTop = e.clientY - dragOffset.y;

            // 应用边界限制
            if (bounds) {
                newLeft = Math.max(bounds.minLeft || 0, Math.min(bounds.maxLeft || window.innerWidth, newLeft));
                newTop = Math.max(bounds.minTop || 0, Math.min(bounds.maxTop || window.innerHeight, newTop));
            }

            element.style.left = newLeft + 'px';
            element.style.top = newTop + 'px';
            element.style.right = 'auto';
        });

        document.addEventListener('mouseup', () => {
            if (!isDragging) return;

            isDragging = false;
            element.style.cursor = 'move';

            if (onDragEnd) onDragEnd();
        });
    }

    // 🔧 从URL中提取自定义文件名参数
    function extractFilenameFromUrl(url) {
        try {
            const urlObj = new URL(url);
            const params = urlObj.searchParams;

            // 支持的文件名参数（按优先级排序）
            const filenameParams = [
                'download_filename',  // 最高优先级
                'filename',
                'name',
                'title',
                'custom_filename',
                'file_name',
                'video_name'
            ];

            for (const param of filenameParams) {
                const value = params.get(param);
                if (value && value.trim()) {
                    let cleanFilename = value.trim();

                    // 移除常见的视频扩展名（系统会自动添加）
                    const videoExtensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'];
                    for (const ext of videoExtensions) {
                        if (cleanFilename.toLowerCase().endsWith(ext)) {
                            cleanFilename = cleanFilename.slice(0, -ext.length);
                            break;
                        }
                    }

                    // 移除不安全的字符
                    const unsafeChars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/'];
                    for (const char of unsafeChars) {
                        cleanFilename = cleanFilename.replace(new RegExp('\\' + char, 'g'), '_');
                    }

                    // 移除多余的空格和下划线
                    cleanFilename = cleanFilename.replace(/\s+/g, ' ').replace(/_+/g, '_').trim();

                    if (cleanFilename) {
                        console.log('🔧 从URL提取自定义文件名:', value, '->', cleanFilename);
                        return cleanFilename;
                    }
                }
            }

            return '';
        } catch (e) {
            console.debug('🔍 URL文件名提取失败:', e);
            return '';
        }
    }

    // 创建填充式圆圈进度跟踪器
    function createFillProgressTracker(taskId, serverUrl) {
        const container = document.createElement('div');
        container.style.cssText = 'text-align: center; padding: 20px;';

        // 创建圆圈容器
        const circleContainer = document.createElement('div');
        circleContainer.style.cssText = 'position: relative; display: inline-block; margin-bottom: 15px;';

        // 创建SVG填充式进度环
        const svgSize = 90;
        const strokeWidth = 8;
        const radius = (svgSize - strokeWidth) / 2;
        const circumference = radius * 2 * Math.PI;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', svgSize);
        svg.setAttribute('height', svgSize);
        svg.style.cssText = 'position: absolute; top: -5px; left: -5px; transform: rotate(-90deg);';

        // 背景圆圈 - 浅灰色轨道
        const bgCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        bgCircle.setAttribute('cx', svgSize / 2);
        bgCircle.setAttribute('cy', svgSize / 2);
        bgCircle.setAttribute('r', radius);
        bgCircle.setAttribute('stroke', '#e8e8e8');
        bgCircle.setAttribute('stroke-width', strokeWidth);
        bgCircle.setAttribute('fill', 'transparent');

        // 创建渐变定义
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');

        // 动态进度渐变 (橙色到绿色)
        const progressGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        progressGradient.setAttribute('id', 'progressGradient');
        progressGradient.setAttribute('x1', '0%');
        progressGradient.setAttribute('y1', '0%');
        progressGradient.setAttribute('x2', '100%');
        progressGradient.setAttribute('y2', '100%');
        const progressStop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        progressStop1.setAttribute('offset', '0%');
        progressStop1.setAttribute('stop-color', '#ff8c00'); // 橙色起始
        const progressStop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        progressStop2.setAttribute('offset', '100%');
        progressStop2.setAttribute('stop-color', '#00cc44'); // 绿色结束
        progressGradient.appendChild(progressStop1);
        progressGradient.appendChild(progressStop2);

        // 等待状态渐变 (黄色)
        const pendingGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        pendingGradient.setAttribute('id', 'pendingGradient');
        pendingGradient.setAttribute('x1', '0%');
        pendingGradient.setAttribute('y1', '0%');
        pendingGradient.setAttribute('x2', '100%');
        pendingGradient.setAttribute('y2', '100%');
        const pendingStop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        pendingStop1.setAttribute('offset', '0%');
        pendingStop1.setAttribute('stop-color', '#ffd700');
        const pendingStop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        pendingStop2.setAttribute('offset', '100%');
        pendingStop2.setAttribute('stop-color', '#ffaa00');
        pendingGradient.appendChild(pendingStop1);
        pendingGradient.appendChild(pendingStop2);

        // 失败状态渐变 (红色)
        const failedGradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        failedGradient.setAttribute('id', 'failedGradient');
        failedGradient.setAttribute('x1', '0%');
        failedGradient.setAttribute('y1', '0%');
        failedGradient.setAttribute('x2', '100%');
        failedGradient.setAttribute('y2', '100%');
        const failedStop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        failedStop1.setAttribute('offset', '0%');
        failedStop1.setAttribute('stop-color', '#dc3545');
        const failedStop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        failedStop2.setAttribute('offset', '100%');
        failedStop2.setAttribute('stop-color', '#ff3333');
        failedGradient.appendChild(failedStop1);
        failedGradient.appendChild(failedStop2);

        defs.appendChild(progressGradient);
        defs.appendChild(pendingGradient);
        defs.appendChild(failedGradient);

        // 进度圆圈 - 使用橙色到绿色渐变
        const progressCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        progressCircle.setAttribute('cx', svgSize / 2);
        progressCircle.setAttribute('cy', svgSize / 2);
        progressCircle.setAttribute('r', radius);
        progressCircle.setAttribute('stroke', 'url(#progressGradient)'); // 使用橙色到绿色渐变
        progressCircle.setAttribute('stroke-width', strokeWidth);
        progressCircle.setAttribute('fill', 'transparent');
        progressCircle.setAttribute('stroke-dasharray', circumference);
        progressCircle.setAttribute('stroke-dashoffset', circumference); // 初始为0%
        progressCircle.setAttribute('stroke-linecap', 'round');
        progressCircle.style.transition = 'stroke-dashoffset 0.2s ease, stroke 0.3s ease';
        progressCircle.style.filter = 'drop-shadow(0 0 6px rgba(255, 140, 0, 0.8))';

        svg.appendChild(defs);
        svg.appendChild(bgCircle);
        svg.appendChild(progressCircle);

        // 中心圆圈（浮球本身）- 增强版
        const centerCircle = document.createElement('div');
        centerCircle.style.cssText = `
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 24px;
            position: relative;
            z-index: 2;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            transition: all 0.3s ease;
        `;
        centerCircle.textContent = '📥';

        // 进度百分比显示（在浮球内部）
        const progressPercent = document.createElement('div');
        progressPercent.style.cssText = `
            position: absolute;
            bottom: 2px;
            right: 2px;
            font-size: 8px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
            background: rgba(0, 0, 0, 0.3);
            padding: 1px 3px;
            border-radius: 3px;
            z-index: 3;
            display: none;
        `;
        progressPercent.textContent = '0%';

        centerCircle.appendChild(progressPercent);
        circleContainer.appendChild(centerCircle);
        circleContainer.appendChild(svg);

        // 完成后的链接容器
        const linksContainer = document.createElement('div');
        linksContainer.style.cssText = 'display: none; background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 15px;';

        container.appendChild(circleContainer);
        container.appendChild(linksContainer);

        // 开始进度跟踪
        startFillProgressTracking(taskId, serverUrl, progressCircle, centerCircle, linksContainer, circumference, progressPercent);

        return container;
    }

    // 🔧 删除了重复的进度跟踪器，使用现有的createFillProgressTracker

    // 开始填充式进度跟踪 - 使用智能SSE管理器
    function startFillProgressTracking(taskId, serverUrl, progressCircle, centerCircle, linksContainer, circumference, progressPercent) {
        let fallbackTimer = null;

        // 更新进度的统一函数
        function updateProgress(progress, status) {
            const validProgress = Math.max(0, Math.min(100, parseInt(progress) || 0));

            // 更新填充式进度环
            const offset = circumference - (validProgress / 100) * circumference;
            progressCircle.setAttribute('stroke-dashoffset', offset);

            // 根据状态更新浮球样式 - 橙色到绿色渐变进度
            if (status === 'completed') {
                progressCircle.setAttribute('stroke', 'url(#progressGradient)'); // 保持橙绿渐变
                progressCircle.style.filter = 'drop-shadow(0 0 8px rgba(0, 204, 68, 0.8))'; // 绿色发光
                centerCircle.textContent = '✅';
                // 保持原始蓝色渐变背景
                centerCircle.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                if (progressPercent) progressPercent.style.display = 'none';

            } else if (status === 'failed') {
                progressCircle.setAttribute('stroke', 'url(#failedGradient)'); // 红色渐变外环
                progressCircle.style.filter = 'drop-shadow(0 0 8px rgba(255, 51, 51, 0.8))';
                centerCircle.textContent = '❌';
                // 保持原始蓝色渐变背景
                centerCircle.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                if (progressPercent) progressPercent.style.display = 'none';

            } else if (status === 'downloading') {
                progressCircle.setAttribute('stroke', 'url(#progressGradient)'); // 橙绿渐变外环

                // 根据进度动态调整发光颜色 (橙色到绿色)
                const orangeR = 255, orangeG = 140, orangeB = 0;
                const greenR = 0, greenG = 204, greenB = 68;
                const ratio = validProgress / 100;
                const currentR = Math.round(orangeR + (greenR - orangeR) * ratio);
                const currentG = Math.round(orangeG + (greenG - orangeG) * ratio);
                const currentB = Math.round(orangeB + (greenB - orangeB) * ratio);

                progressCircle.style.filter = `drop-shadow(0 0 8px rgba(${currentR}, ${currentG}, ${currentB}, 0.8))`;
                centerCircle.textContent = validProgress > 50 ? '📥' : '⬇️';
                // 保持原始蓝色渐变背景
                centerCircle.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

                // 显示进度百分比
                if (progressPercent && validProgress > 0) {
                    progressPercent.style.display = 'block';
                    progressPercent.textContent = `${validProgress}%`;
                } else if (progressPercent) {
                    progressPercent.style.display = 'none';
                }

            } else if (status === 'pending') {
                progressCircle.setAttribute('stroke', 'url(#pendingGradient)'); // 黄色渐变外环
                progressCircle.style.filter = 'drop-shadow(0 0 8px rgba(255, 170, 0, 0.8))';
                centerCircle.textContent = '⏳';
                // 保持原始蓝色渐变背景
                centerCircle.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                if (progressPercent) progressPercent.style.display = 'none';
            }

            // 处理完成和失败状态
            if (status === 'completed') {
                showCompletedLinks(linksContainer, serverUrl);
                cleanup();
                return true; // 完成
            } else if (status === 'failed') {
                cleanup();
                return true; // 失败
            }

            return false; // 继续
        }

        // 清理资源
        function cleanup() {
            if (fallbackTimer) {
                clearTimeout(fallbackTimer);
                fallbackTimer = null;
            }
            // 🔧 从SSE管理器中注销任务
            sseManager.unregisterDownload(taskId);
        }

        // 🔧 使用智能SSE管理器进行精准推送
        function trySmartSSE() {
            try {
                // 🛡️ 检查HTTPS混合内容问题
                if (window.location.protocol === 'https:' && serverUrl.startsWith('http:')) {
                    console.log('⚠️ HTTPS环境下无法使用SSE，直接启动轮询模式');
                    startPolling();
                    return;
                }

                // 确保SSE连接已建立
                sseManager.connectSSE(serverUrl);

                // 注册进度回调
                sseManager.registerDownload(taskId, (progress, status) => {
                    console.log(`📊 智能SSE进度更新: ${taskId} - ${progress}% (${status})`);
                    updateProgress(progress, status);
                });

                console.log('✅ 智能SSE跟踪已启动');

                // 5秒后如果没有收到任何进度，降级到轮询
                fallbackTimer = setTimeout(() => {
                    console.log('⏰ SSE超时，降级到轮询模式');
                    startPolling();
                }, 5000);

                eventSource.addEventListener('download_completed', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.download_id === taskId) {
                            console.log('📡 SSE下载完成');
                            updateProgress(100, 'completed');
                        }
                    } catch (e) {
                        console.log('SSE完成事件解析失败:', e);
                    }
                });

                eventSource.addEventListener('download_failed', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.download_id === taskId) {
                            console.log('📡 SSE下载失败');
                            updateProgress(0, 'failed');
                        }
                    } catch (e) {
                        console.log('SSE失败事件解析失败:', e);
                    }
                });

                eventSource.onerror = () => {
                    console.log('❌ SSE连接错误，降级到轮询模式');
                    cleanup();
                    startPolling();
                };

                // 5秒后如果没有收到任何进度，降级到轮询
                fallbackTimer = setTimeout(() => {
                    console.log('⏰ SSE超时，降级到轮询模式');
                    cleanup();
                    startPolling();
                }, 5000);

            } catch (error) {
                console.log('❌ SSE初始化失败，使用轮询模式');
                startPolling();
            }
        }

        // 轮询模式 (备用方案)
        function startPolling() {
            let pollCount = 0;
            const maxPolls = 300;

            const pollProgress = () => {
                // 🔧 使用GM_xmlhttpRequest绕过CSP限制
                GM_xmlhttpRequest({
                    method: 'GET',
                    url: `${serverUrl}/download/status/${taskId}`,
                    headers: { 'Content-Type': 'application/json' },
                    onload: (response) => {
                        try {
                            if (response.status === 200) {
                                const data = JSON.parse(response.responseText);
                                const isComplete = updateProgress(data.progress, data.status);

                                if (!isComplete && pollCount < maxPolls) {
                                    pollCount++;
                                    setTimeout(pollProgress, 1000);
                                } else if (pollCount >= maxPolls) {
                                    centerCircle.textContent = '⏰';
                                    progressCircle.setAttribute('stroke', '#6c757d');
                                }
                            } else {
                                throw new Error(`HTTP ${response.status}`);
                            }
                        } catch (error) {
                            console.log('轮询解析失败:', error);
                            centerCircle.textContent = '❌';
                            progressCircle.setAttribute('stroke', '#ff3333');
                        }
                    },
                    onerror: (error) => {
                        console.log('轮询网络失败:', error);
                        centerCircle.textContent = '❌';
                        progressCircle.setAttribute('stroke', '#ff3333');
                    }
                });
            };

            setTimeout(pollProgress, 1000);
        }

        // 🔧 优先尝试智能SSE，失败则降级到轮询
        trySmartSSE();
    }

    // 显示完成后的链接
    function showCompletedLinks(container, serverUrl) {
        container.style.display = 'block';

        const title = document.createElement('div');
        title.style.cssText = 'font-weight: bold; margin-bottom: 10px; color: #28a745;';
        title.textContent = '🎉 下载完成！';

        const links = [
            {
                icon: '📁',
                text: '文件管理器',
                url: `${serverUrl}/files`,
                description: '浏览所有文件'
            },
            {
                icon: '🎬',
                text: '在线预览',
                url: `${serverUrl}/files`,
                description: '在线播放'
            },
            {
                icon: '📥',
                text: '直接下载',
                url: `${serverUrl}/files`,
                description: '下载到本地'
            }
        ];

        container.appendChild(title);

        links.forEach(link => {
            const linkDiv = document.createElement('div');
            linkDiv.style.cssText = 'margin: 8px 0;';

            // 🛡️ 使用 DOM 操作替代 innerHTML
            const linkElement = document.createElement('a');
            linkElement.href = link.url;
            linkElement.target = '_blank';
            linkElement.style.cssText = `
                color: #007bff;
                text-decoration: none;
                font-size: 13px;
                display: inline-block;
                padding: 5px 10px;
                border: 1px solid #007bff;
                border-radius: 4px;
                transition: all 0.2s ease;
            `;
            linkElement.textContent = `${link.icon} ${link.text}`;

            // 添加悬停效果
            linkElement.onmouseover = function() {
                this.style.background = '#007bff';
                this.style.color = 'white';
            };
            linkElement.onmouseout = function() {
                this.style.background = 'transparent';
                this.style.color = '#007bff';
            };

            const descriptionElement = document.createElement('small');
            descriptionElement.style.cssText = 'color: #666; margin-left: 10px;';
            descriptionElement.textContent = link.description;

            linkDiv.appendChild(linkElement);
            linkDiv.appendChild(descriptionElement);
            container.appendChild(linkDiv);
        });
    }

    // 创建带标签的信息行（避免TrustedHTML问题）
    function createInfoLine(label, value, style = 'margin-bottom: 5px;') {
        const div = document.createElement('div');
        div.style.cssText = style;

        const strong = document.createElement('strong');
        strong.textContent = label;
        div.appendChild(strong);

        if (value) {
            div.appendChild(document.createTextNode(' ' + value));
        }

        return div;
    }

    // 创建带标签的信息行（只有标签，后续可添加内容）
    function createLabelDiv(label, style = 'margin-bottom: 5px;') {
        const div = document.createElement('div');
        div.style.cssText = style;

        const strong = document.createElement('strong');
        strong.textContent = label;
        div.appendChild(strong);

        return div;
    }

    // 初始化
    function init() {
        if (!document.body) {
            setTimeout(init, CONSTANTS.TIMEOUTS.INIT_RETRY);
            return;
        }

        // 检查是否为有效的网页（排除一些特殊页面）
        const hostname = window.location.hostname.toLowerCase();
        const invalidHosts = ['localhost', '127.0.0.1', 'about:', 'chrome:', 'moz-extension:', 'chrome-extension:'];

        if (invalidHosts.some(invalid => hostname.includes(invalid)) ||
            hostname === '' ||
            window.location.protocol === 'file:') {
            console.log('🚫 跳过特殊页面:', hostname);
            return;
        }

        // 启用FetchV精准过滤模式
        setupMediaSourceHook();
        setupAdvancedNetworkMonitoring();
        setupVideoElementMonitoring();

        console.log('✅ FetchV精准过滤模式已启用');
        console.log(`📊 过滤标准: 最小${MEDIA_CONFIG.minSize/1024}KB, 支持${MEDIA_CONFIG.formats.length}种格式`);
        console.log(`🚫 屏蔽域名: ${MEDIA_CONFIG.blockedDomains.join(', ')}`);
        console.log(`🚫 屏蔽平台: ${MEDIA_CONFIG.blockedPlatforms.join(', ')}`);

        const panel = createDraggablePanel();
        document.body.appendChild(panel);

        const platformType = isSupportedPlatform() ? '支持平台' : '提取模式';
        console.log(`🎬 智能全网视频下载助手已加载 - ${platformType}`);

        // 🔧 设置加载完成标记
        window.smartVideoDownloaderLoaded = true;

        // 如果是提取模式，可以自动检测一次
        if (!isSupportedPlatform()) {
            setTimeout(() => {
                const videos = extractVideosFromPage();
                if (videos.length > 0) {
                    showNotification(`🔍 检测到 ${videos.length} 个视频文件`, 'info');
                }
            }, CONSTANTS.TIMEOUTS.AUTO_DETECT);
        }
    }

    // 🔧 调试：暴露函数到全局作用域 (仅用于调试)
    if (typeof window !== 'undefined') {
        window.debugVideoDownloader = {
            cleanTitle: cleanTitle,
            showExtractVideoDownloadDialog: showExtractVideoDownloadDialog,
            showSupportedPlatformDialog: showSupportedPlatformDialog,
            downloadExtractedVideo: downloadExtractedVideo,
            sendToServerWithFilename: sendToServerWithFilename,
            extractVideosFromPage: extractVideosFromPage,
            isSupportedPlatform: isSupportedPlatform,
            // 新增：过滤统计功能
            showFilterStats: showDetailedFilterStats,
            resetFilterStats: resetFilterStats,
            getFilterStats: () => filterStats,
            version: '3.3.0'
        };
        console.log('🔧 调试函数已暴露到 window.debugVideoDownloader');
        console.log('📊 过滤统计功能: debugVideoDownloader.showFilterStats(), debugVideoDownloader.resetFilterStats()');
    }

    // 等待页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // 页面已经加载完成
        init();
    }

})();
