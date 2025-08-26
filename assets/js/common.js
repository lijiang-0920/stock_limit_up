// assets/js/common.js - 通用功能

// 全局变量
let currentImageIndex = 0;
let currentImages = [];

// 通用工具函数
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN');
}

function formatTime(timeStr) {
    return timeStr || '--';
}

function showLoading(container) {
    container.innerHTML = '<div class="loading">加载中...</div>';
}

function showError(container, message) {
    container.innerHTML = `<div class="loading">错误: ${message}</div>`;
}

// 复制到剪贴板
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('复制成功！');
        return true;
    } catch (err) {
        console.error('复制失败:', err);
        // 降级方案
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showToast('复制成功！');
            return true;
        } catch (e) {
            showToast('复制失败，请手动复制');
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

// 显示提示消息
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#48bb78' : '#f56565'};
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// 添加CSS动画
if (!document.querySelector('#toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}

// 加载主页统计数据
async function loadMainPageStats() {
    try {
        // 加载涨停池数据状态
        await loadLimitUpStatus();
        
        // 加载文章数据状态
        await loadArticlesStatus();
        
        // 加载异动解析数据状态
        await loadAnalysisStatus();
        
    } catch (error) {
        console.error('加载统计数据失败:', error);
        const dataStatusEl = document.getElementById('dataStatus');
        if (dataStatusEl) {
            dataStatusEl.textContent = '异常';
        }
    }
}

// 加载涨停池状态
async function loadLimitUpStatus() {
    try {
        const response = await fetch('limitup/index.json');
        if (response.ok) {
            const limitupData = await response.json();
            const dates = Object.keys(limitupData).sort().reverse();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const limitupStatusEl = document.getElementById('limitupStatus');
                if (limitupStatusEl) {
                    limitupStatusEl.textContent = `最新更新: ${latestDate}`;
                }
                
                // 加载最新数据获取股票数量
                const todayLimitUpEl = document.getElementById('todayLimitUp');
                if (todayLimitUpEl && limitupData[latestDate]) {
                    todayLimitUpEl.textContent = `${limitupData[latestDate].total_stocks}只`;
                }
            }
        }
    } catch (error) {
        console.error('加载涨停池状态失败:', error);
        const limitupStatusEl = document.getElementById('limitupStatus');
        if (limitupStatusEl) {
            limitupStatusEl.textContent = '最新更新: 加载失败';
        }
    }
}

// 加载文章状态
async function loadArticlesStatus() {
    try {
        const articlesResponse = await fetch('articles/index.json');
        if (articlesResponse.ok) {
            const articlesData = await articlesResponse.json();
            const dates = Object.keys(articlesData).sort().reverse();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const articlesStatusEl = document.getElementById('articlesStatus');
                if (articlesStatusEl) {
                    articlesStatusEl.textContent = `最新更新: ${latestDate}`;
                }
                
                // 计算本周文章数量
                const weekAgo = new Date();
                weekAgo.setDate(weekAgo.getDate() - 7);
                const weekAgoStr = weekAgo.toISOString().split('T')[0];
                
                let weeklyCount = 0;
                dates.forEach(date => {
                    if (date >= weekAgoStr && articlesData[date].articles) {
                        weeklyCount += articlesData[date].articles.length;
                    }
                });
                const weeklyArticlesEl = document.getElementById('weeklyArticles');
                if (weeklyArticlesEl) {
                    weeklyArticlesEl.textContent = `${weeklyCount}篇`;
                }
            }
        }
    } catch (error) {
        console.error('加载文章状态失败:', error);
        const articlesStatusEl = document.getElementById('articlesStatus');
        if (articlesStatusEl) {
            articlesStatusEl.textContent = '最新更新: 加载失败';
        }
    }
}

// 加载异动解析状态
async function loadAnalysisStatus() {
    try {
        const analysisResponse = await fetch('analysis/index.json');
        if (analysisResponse.ok) {
            const analysisData = await analysisResponse.json();
            const dates = Object.keys(analysisData).sort().reverse();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const analysisStatusEl = document.getElementById('analysisStatus');
                if (analysisStatusEl) {
                    analysisStatusEl.textContent = `最新更新: ${latestDate}`;
                }
            }
        }
    } catch (error) {
        console.error('加载异动解析状态失败:', error);
        const analysisStatusEl = document.getElementById('analysisStatus');
        if (analysisStatusEl) {
            analysisStatusEl.textContent = '最新更新: 加载失败';
        }
    }
}

// 显示关于信息
function showAbout() {
    const aboutContent = `
        <div style="text-align: center; padding: 20px;">
            <h2>📊 数据中心</h2>
            <p style="margin: 20px 0; color: #666;">
                这是一个股票数据和研报文章的收集展示平台<br>
                自动收集财联社涨停池数据和韭研公社研报文章
            </p>
            <p style="color: #999; font-size: 0.9rem;">
                数据仅供参考，投资有风险，入市需谨慎
            </p>
        </div>
    `;
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 400px;">
            <div class="modal-header">
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            </div>
            <div class="modal-body">
                ${aboutContent}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 点击外部关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// JSON查看器功能
async function loadJsonViewer() {
    const dataTypeSelect = document.getElementById('dataTypeSelect');
    const dateSelect = document.getElementById('dateSelect');
    const jsonContent = document.getElementById('jsonContent');
    const copyJsonBtn = document.getElementById('copyJsonBtn');
    
    if (!dataTypeSelect || !dateSelect || !jsonContent || !copyJsonBtn) {
        console.error('JSON查看器元素未找到');
        return;
    }
    
    // 加载日期选项
    async function loadDates() {
        const dataType = dataTypeSelect.value;
        dateSelect.innerHTML = '<option value="">选择日期</option>';
        
        try {
            let dates = [];
            if (dataType === 'limitup') {
                const response = await fetch('limitup/index.json');
                if (response.ok) {
                    const limitupData = await response.json();
                    dates = Object.keys(limitupData).sort().reverse();
                }
            } else if (dataType === 'articles') {
                const response = await fetch('articles/index.json');
                if (response.ok) {
                    const articlesData = await response.json();
                    dates = Object.keys(articlesData).sort().reverse();
                }
            }
            else if (dataType === 'analysis') {
                const response = await fetch('analysis/index.json');
                if (response.ok) {
                    const analysisData = await response.json();
                    dates = Object.keys(analysisData).sort().reverse();
                }
            }
            
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = date;
                dateSelect.appendChild(option);
            });
            
            if (dates.length > 0) {
                dateSelect.value = dates[0];
                loadJsonData();
            }
        } catch (error) {
            jsonContent.textContent = '加载日期失败';
        }
    }
    
    // 加载JSON数据
    async function loadJsonData() {
        const dataType = dataTypeSelect.value;
        const date = dateSelect.value;
        
        if (!date) {
            jsonContent.textContent = '请选择日期';
            return;
        }
        
        try {
            let response;
            if (dataType === 'limitup') {
                response = await fetch(`limitup/${date}.json`);
            } else if (dataType === 'articles') {
                response = await fetch('articles/index.json');
            }
            else if (dataType === 'analysis') {
                response = await fetch(`analysis/${date}.json`);
            }
            
            if (response && response.ok) {
                let data = await response.json();
                if (dataType === 'articles') {
                    data = data[date] || {};
                }
                jsonContent.textContent = JSON.stringify(data, null, 2);
            } else {
                jsonContent.textContent = '加载数据失败';
            }
        } catch (error) {
            jsonContent.textContent = `加载失败: ${error.message}`;
        }
    }
    
    // 复制JSON
    copyJsonBtn.addEventListener('click', () => {
        copyToClipboard(jsonContent.textContent);
    });
    
    // 事件监听
    dataTypeSelect.addEventListener('change', loadDates);
    dateSelect.addEventListener('change', loadJsonData);
    
    // 初始加载
    loadDates();
}

// 格式化数字
function formatNumber(num) {
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    return num.toString();
}

// 获取URL参数
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

// 防抖函数
function debounce(func, wait) {
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

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}