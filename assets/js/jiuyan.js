// assets/js/jiuyan.js - 韭研公社文章页面功能

let currentArticlesData = {};

document.addEventListener('DOMContentLoaded', function() {
    console.log('韭研公社页面初始化...');
    initJiuyanPage();
});

async function initJiuyanPage() {
    await loadArticlesData();
    setupEventListeners();
}

// 加载文章数据
async function loadArticlesData() {
    try {
        console.log('正在加载文章数据...');
        const response = await fetch('articles/index.json');
        if (!response.ok) throw new Error('无法加载文章数据');
        
        currentArticlesData = await response.json();
        console.log('文章数据:', currentArticlesData);
        
        // 填充日期选项
        const dates = Object.keys(currentArticlesData).sort().reverse();
        const dateFilter = document.getElementById('dateFilter');
        
        if (!dateFilter) {
            console.error('dateFilter元素未找到');
            return;
        }
        
        dateFilter.innerHTML = '<option value="">选择日期</option>';
        dates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            dateFilter.appendChild(option);
        });
        
        // 默认加载最新日期
        if (dates.length > 0) {
            dateFilter.value = dates[0];
            filterAndRenderArticles();
        }
        
    } catch (error) {
        console.error('加载文章数据失败:', error);
        const container = document.getElementById('articlesContainer');
        if (container) {
            showError(container, '加载文章数据失败');
        }
    }
}

// 设置事件监听器
function setupEventListeners() {
    const authorFilter = document.getElementById('authorFilter');
    const dateFilter = document.getElementById('dateFilter');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (authorFilter) {
        authorFilter.addEventListener('change', filterAndRenderArticles);
    }
    
    if (dateFilter) {
        dateFilter.addEventListener('change', filterAndRenderArticles);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 筛选并渲染文章
function filterAndRenderArticles() {
    const authorFilter = document.getElementById('authorFilter');
    const dateFilter = document.getElementById('dateFilter');
    const container = document.getElementById('articlesContainer');
    
    if (!authorFilter || !dateFilter || !container) {
        console.error('筛选元素未找到');
        return;
    }
    
    const authorValue = authorFilter.value;
    const dateValue = dateFilter.value;
    
    let articles = [];
    
    // 根据日期筛选
    if (dateValue && currentArticlesData[dateValue]) {
        articles = currentArticlesData[dateValue].articles || [];
    } else {
        // 显示所有文章
        Object.values(currentArticlesData).forEach(dayData => {
            if (dayData.articles) {
                articles = articles.concat(dayData.articles);
            }
        });
    }
    
    // 根据作者筛选
    if (authorValue) {
        articles = articles.filter(article => article.author === authorValue);
    }
    
    // 按日期排序（最新在前）
    articles.sort((a, b) => new Date(b.date) - new Date(a.date));
    
    renderArticles(articles);
}

// 渲染文章列表
function renderArticles(articles) {
    const container = document.getElementById('articlesContainer');
    
    if (!container) {
        console.error('articlesContainer元素未找到');
        return;
    }
    
    if (!articles || articles.length === 0) {
        container.innerHTML = '<div class="loading">暂无文章数据</div>';
        return;
    }
    
    const articlesHtml = articles.map((article, index) => `
        <div class="article-card">
            <div class="article-header">
                <h3 class="article-title">${article.title}</h3>
                <div class="article-meta">
                    <span>📝 ${article.author}</span>
                    <span>📅 ${article.date} ${article.publish_time}</span>
                </div>
            </div>
            <div class="article-preview">
                ${getArticlePreview(article.content)}
            </div>
            <div class="article-stats">
                <span>📊 ${article.word_count || 0}字</span>
                <span>📷 ${article.image_count || 0}张图片</span>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = articlesHtml;
}

// 获取文章预览
function getArticlePreview(content, maxLength = 200) {
    if (!content) return '暂无预览';
    
    // 移除图片占位符
    const textOnly = content.replace(/\[图片:[^\]]+\]/g, '');
    
    if (textOnly.length <= maxLength) {
        return textOnly;
    }
    
    return textOnly.substring(0, maxLength) + '...';
}