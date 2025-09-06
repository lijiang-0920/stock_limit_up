// assets/js/jiuyan.js - 韭研公社文章页面功能

let currentArticlesData = {};
let currentArticle = null;

document.addEventListener('DOMContentLoaded', function() {
    initJiuyanPage();
});

async function initJiuyanPage() {
    await loadArticlesData();
    setupEventListeners();
}

// 加载文章数据
async function loadArticlesData() {
    try {
        const response = await fetch('articles/index.json');
        if (!response.ok) throw new Error('无法加载文章数据');
        
        currentArticlesData = await response.json();
        
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
                <span>💾 ${article.files && article.files.docx ? '可下载' : '仅文本'}</span>
            </div>
            <div class="article-actions">
                <button class="article-btn primary" onclick="viewArticle('${article.date}', '${article.author}')">
                    📖 查看全文
                </button>
                <button class="article-btn" onclick="copyArticleText('${article.date}', '${article.author}')">
                    📋 复制内容
                </button>
                <button class="article-btn" onclick="downloadArticleFile('${article.date}', '${article.author}')">
                    💾 下载文件
                </button>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = articlesHtml;
}

// 获取文章预览
function getArticlePreview(content, maxLength = 200) {
    if (!content) return '暂无预览';
    
    // 移除图片占位符 - 使用正确的正则表达式
    const imgRegex = new RegExp('\\[图片:[^\\]]+\\]', 'g');
    const textOnly = content.replace(imgRegex, '');
    
    if (textOnly.length <= maxLength) {
        return textOnly;
    }
    
    return textOnly.substring(0, maxLength) + '...';
}

// 查看文章详情
function viewArticle(date, author) {
    const article = findArticle(date, author);
    if (!article) {
        showToast('文章未找到', 'error');
        return;
    }
    
    currentArticle = article;
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const articleMeta = document.getElementById('articleMeta');
    const articleContent = document.getElementById('articleContent');
    const modal = document.getElementById('articleModal');
    
    if (!modalTitle || !articleMeta || !articleContent || !modal) {
        console.error('模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = article.title;
    articleMeta.innerHTML = `
        <div style="display: flex; gap: 20px; margin-bottom: 20px; font-size: 0.9rem; color: #666;">
            <span>📅 ${article.date} ${article.publish_time}</span>
            <span>👤 ${article.author}</span>
            <span>📊 ${article.word_count}字</span>
            <span>📷 ${article.image_count}图</span>
        </div>
    `;
    
    // 处理文章内容（包含图片）
    const processedContent = processArticleContent(article);
    articleContent.innerHTML = processedContent;
    
    // 显示模态框
    modal.style.display = 'block';
    
    // 设置图片点击事件
    setupImageViewer(article.images || []);
}

// 处理文章内容
function processArticleContent(article) {
    let content = article.content;
    
    // 替换图片占位符为实际图片
    if (article.images && article.images.length > 0) {
        article.images.forEach((image, index) => {
            const placeholder = image.placeholder;
            const imgHtml = `
                <div style="text-align: center; margin: 20px 0;">
                    <img src="${image.src}" 
                         alt="${image.alt}" 
                         class="article-image" 
                         data-index="${index}"
                         style="max-width: 100%; height: auto; border-radius: 8px; cursor: pointer;"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div style="display: none; padding: 20px; background: #f5f5f5; border-radius: 8px; color: #666;">
                        图片加载失败: ${image.filename}
                    </div>
                    ${image.caption ? `<div class="image-caption">${image.caption}</div>` : ''}
                </div>
            `;
            content = content.replace(placeholder, imgHtml);
        });
    }
    
    // 处理段落
    const lines = content.split('\n');
    const processedLines = lines.map(line => {
        if (line.trim()) {
            return `<p>${line}</p>`;
        }
        return '';
    });
    
    return processedLines.join('');
}

// 设置图片查看器
function setupImageViewer(images) {
    currentImages = images;
    
    // 移除之前的事件监听器
    document.querySelectorAll('.article-image').forEach(img => {
        img.removeEventListener('click', handleImageClick);
        img.addEventListener('click', handleImageClick);
    });
}

function handleImageClick(e) {
    const index = parseInt(e.target.dataset.index);
    openImageViewer(index);
}

// 打开图片查看器
function openImageViewer(index) {
    if (!currentImages || currentImages.length === 0) return;
    
    currentImageIndex = index;
    const image = currentImages[index];
    
    const viewerImage = document.getElementById('viewerImage');
    const viewerInfo = document.getElementById('viewerInfo');
    const imageViewer = document.getElementById('imageViewer');
    
    if (!viewerImage || !viewerInfo || !imageViewer) {
        console.error('图片查看器元素未找到');
        return;
    }
    
    viewerImage.src = image.src;
    viewerInfo.textContent = `图片 ${index + 1} / ${currentImages.length}`;
    imageViewer.style.display = 'block';
}

// 关闭图片查看器
function closeImageViewer() {
    const imageViewer = document.getElementById('imageViewer');
    if (imageViewer) {
        imageViewer.style.display = 'none';
    }
}

// 上一张图片
function prevImage() {
    if (currentImageIndex > 0) {
        openImageViewer(currentImageIndex - 1);
    }
}

// 下一张图片
function nextImage() {
    if (currentImageIndex < currentImages.length - 1) {
        openImageViewer(currentImageIndex + 1);
    }
}

// 下载当前图片
function downloadCurrentImage() {
    if (currentImages && currentImages[currentImageIndex]) {
        const image = currentImages[currentImageIndex];
        const link = document.createElement('a');
        link.href = image.src;
        link.download = image.filename || `image_${currentImageIndex + 1}.jpg`;
        link.click();
        showToast('图片下载中...');
    }
}

// 关闭文章模态框
function closeArticleModal() {
    const modal = document.getElementById('articleModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentArticle = null;
}

// 复制文章内容
function copyArticleContent(type) {
    if (!currentArticle) {
        showToast('未选择文章', 'error');
        return;
    }
    
    let content = '';
    
    switch (type) {
        case 'full':
            // 包含格式的完整内容
            content = `${currentArticle.title}\n\n`;
            content += `作者: ${currentArticle.author}\n`;
            content += `时间: ${currentArticle.date} ${currentArticle.publish_time}\n\n`;
            content += currentArticle.content;
            break;
        case 'text':
            // 纯文本（移除图片占位符）
            const imgRegex = new RegExp('\\[图片:[^\\]]+\\]', 'g');
            content = currentArticle.content.replace(imgRegex, '');
            break;
        case 'html':
            // HTML格式
            content = processArticleContent(currentArticle);
            break;
        case 'markdown':
            // Markdown格式
            content = convertToMarkdown(currentArticle);
            break;
        default:
            content = currentArticle.content;
    }
    
    copyToClipboard(content);
}

// 转换为Markdown格式
function convertToMarkdown(article) {
    let content = `# ${article.title}\n\n`;
    content += `**作者**: ${article.author}  \n`;
    content += `**时间**: ${article.date} ${article.publish_time}\n\n`;
    
    let articleContent = article.content;
    
    // 替换图片占位符为Markdown图片语法
    if (article.images && article.images.length > 0) {
        article.images.forEach((image, index) => {
            const placeholder = image.placeholder;
            const markdownImg = `![${image.alt}](${image.src})`;
            articleContent = articleContent.replace(placeholder, markdownImg);
        });
    }
    
    // 处理段落
    const lines = articleContent.split('\n');
    const processedLines = lines.map(line => {
        if (line.trim()) {
            return line;
        }
        return '';
    });
    const finalContent = processedLines.join('\n\n');
    
    content += finalContent;
    return content;
}

// 复制文章文本（从列表调用）
function copyArticleText(date, author) {
    const article = findArticle(date, author);
    if (article) {
        const imgRegex = new RegExp('\\[图片:[^\\]]+\\]', 'g');
        const content = article.content.replace(imgRegex, '');
        copyToClipboard(content);
    } else {
        showToast('文章未找到', 'error');
    }
}

// 下载文章文件
function downloadArticle() {
    if (!currentArticle) {
        showToast('未选择文章', 'error');
        return;
    }
    
    if (!currentArticle.files || !currentArticle.files.txt) {
        showToast('文件不可用', 'error');
        return;
    }
    
    const link = document.createElement('a');
    link.href = currentArticle.files.txt;
    link.download = `${currentArticle.title}.txt`;
    link.click();
    showToast('文件下载中...');
}

// 下载文章文件（从列表调用）
function downloadArticleFile(date, author) {
    const article = findArticle(date, author);
    if (article && article.files && article.files.txt) {
        const link = document.createElement('a');
        link.href = article.files.txt;
        link.download = `${article.title}.txt`;
        link.click();
        showToast('文件下载中...');
    } else {
        showToast('文件不可用', 'error');
    }
}

// 查找文章
function findArticle(date, author) {
    if (currentArticlesData[date] && currentArticlesData[date].articles) {
        return currentArticlesData[date].articles.find(article => article.author === author);
    }
    return null;
}

// 批量下载文章
function batchDownloadArticles() {
    const authorFilter = document.getElementById('authorFilter');
    const dateFilter = document.getElementById('dateFilter');
    
    if (!authorFilter || !dateFilter) return;
    
    const authorValue = authorFilter.value;
    const dateValue = dateFilter.value;
    
    let articles = [];
    
    // 根据筛选条件获取文章
    if (dateValue && currentArticlesData[dateValue]) {
        articles = currentArticlesData[dateValue].articles || [];
    } else {
        Object.values(currentArticlesData).forEach(dayData => {
            if (dayData.articles) {
                articles = articles.concat(dayData.articles);
            }
        });
    }
    
    if (authorValue) {
        articles = articles.filter(article => article.author === authorValue);
    }
    
    if (articles.length === 0) {
        showToast('没有可下载的文章', 'error');
        return;
    }
    
    // 创建批量下载内容
    let batchContent = '';
    articles.forEach((article, index) => {
        batchContent += `\n${'='.repeat(50)}\n`;
        batchContent += `文章 ${index + 1}: ${article.title}\n`;
        batchContent += `作者: ${article.author}\n`;
        batchContent += `时间: ${article.date} ${article.publish_time}\n`;
        batchContent += `${'='.repeat(50)}\n\n`;
        const imgRegex = new RegExp('\\[图片:[^\\]]+\\]', 'g');
        batchContent += article.content.replace(imgRegex, '[图片]');
        batchContent += '\n\n';
    });
    
    // 创建下载链接
    const blob = new Blob([batchContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `批量文章_${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    
    showToast(`已下载 ${articles.length} 篇文章`);
}

// 搜索文章
function searchArticles(keyword) {
    if (!keyword.trim()) {
        filterAndRenderArticles();
        return;
    }
    
    let allArticles = [];
    Object.values(currentArticlesData).forEach(dayData => {
        if (dayData.articles) {
            allArticles = allArticles.concat(dayData.articles);
        }
    });
    
    const filteredArticles = allArticles.filter(article => {
        return article.title.toLowerCase().includes(keyword.toLowerCase()) ||
               article.content.toLowerCase().includes(keyword.toLowerCase()) ||
               article.author.toLowerCase().includes(keyword.toLowerCase());
    });
    
    renderArticles(filteredArticles);
    showToast(`找到 ${filteredArticles.length} 篇相关文章`);
}

// 模态框外部点击关闭
document.addEventListener('click', (e) => {
    const modal = document.getElementById('articleModal');
    const imageViewer = document.getElementById('imageViewer');
    
    if (modal && e.target === modal) {
        closeArticleModal();
    }
    
    if (imageViewer && e.target === imageViewer) {
        closeImageViewer();
    }
});

// 键盘事件
document.addEventListener('keydown', (e) => {
    const imageViewer = document.getElementById('imageViewer');
    const modal = document.getElementById('articleModal');
    
    if (imageViewer && imageViewer.style.display === 'block') {
        switch (e.key) {
            case 'Escape':
                closeImageViewer();
                break;
            case 'ArrowLeft':
                prevImage();
                break;
            case 'ArrowRight':
                nextImage();
                break;
            case ' ':
                e.preventDefault();
                nextImage();
                break;
        }
    }
    
    if (modal && modal.style.display === 'block' && e.key === 'Escape') {
        closeArticleModal();
    }
});

// 添加搜索功能到页面
function addSearchFeature() {
    const controlsPanel = document.querySelector('.controls-panel .filter-section');
    if (controlsPanel) {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = '搜索文章标题或内容...';
        searchInput.className = 'search-input';
        searchInput.style.flex = '1';
        searchInput.style.minWidth = '200px';
        
        searchInput.addEventListener('input', debounce((e) => {
            searchArticles(e.target.value);
        }, 500));
        
        controlsPanel.appendChild(searchInput);
    }
}

// 初始化时添加搜索功能
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(addSearchFeature, 100);
});

// 文章统计功能
function getArticleStats() {
    let totalArticles = 0;
    let totalWords = 0;
    let totalImages = 0;
    const authorStats = {};
    
    Object.values(currentArticlesData).forEach(dayData => {
        if (dayData.articles) {
            dayData.articles.forEach(article => {
                totalArticles++;
                totalWords += article.word_count || 0;
                totalImages += article.image_count || 0;
                
                if (!authorStats[article.author]) {
                    authorStats[article.author] = 0;
                }
                authorStats[article.author]++;
            });
        }
    });
    
    return {
        totalArticles,
        totalWords,
        totalImages,
        authorStats
    };
}

// 显示统计信息
function showStats() {
    const stats = getArticleStats();
    const statsContent = `
        <div style="padding: 20px;">
            <h3>📊 文章统计</h3>
            <div style="margin: 20px 0;">
                <p><strong>总文章数:</strong> ${stats.totalArticles} 篇</p>
                <p><strong>总字数:</strong> ${formatNumber(stats.totalWords)} 字</p>
                <p><strong>总图片数:</strong> ${stats.totalImages} 张</p>
            </div>
            <h4>📝 作者统计:</h4>
            <div style="margin: 10px 0;">
                ${Object.entries(stats.authorStats).map(([author, count]) => 
                    `<p><strong>${author}:</strong> ${count} 篇</p>`
                ).join('')}
            </div>
        </div>
    `;
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 400px;">
            <div class="modal-header">
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                <h2>统计信息</h2>
            </div>
            <div class="modal-body">
                ${statsContent}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}