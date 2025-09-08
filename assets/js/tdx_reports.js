// assets/js/tdx_reports.js - 通达信研报页面功能

let currentReportsData = null;
let currentDetailReport = null;

document.addEventListener('DOMContentLoaded', function() {
    initTdxReportsPage();
});

async function initTdxReportsPage() {
    await loadTdxReportsDateOptions();
    setupTdxReportsEventListeners();
}

// 加载日期选项
// 加载日期选项
async function loadTdxReportsDateOptions() {
    try {
        const response = await fetch('tdx_value/index.json');
        if (!response.ok) throw new Error('无法加载通达信研报日期数据');
        
        const indexData = await response.json();
        
        // 过滤掉 _summary 字段，只保留日期键
        const dates = Object.keys(indexData)
            .filter(key => key !== '_summary')  // 过滤掉 _summary
            .sort()
            .reverse();
            
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
        
        // 默认选择最新日期
        if (dates.length > 0) {
            dateFilter.value = dates[0];
            await loadTdxReportsData(dates[0]);
        }
    } catch (error) {
        console.error('加载通达信研报日期选项失败:', error);
        const container = document.getElementById('reportsContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}


// 设置事件监听器
function setupTdxReportsEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const searchInput = document.getElementById('searchInput');
    const ratingFilter = document.getElementById('ratingFilter');
    const institutionFilter = document.getElementById('institutionFilter');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadTdxReportsData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterReports, 300));
    }
    
    if (ratingFilter) {
        ratingFilter.addEventListener('change', filterReports);
    }
    
    if (institutionFilter) {
        institutionFilter.addEventListener('change', filterReports);
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyTdxReportsData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewTdxReportsJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载通达信研报数据
async function loadTdxReportsData(date) {
    const container = document.getElementById('reportsContainer');
    const dataInfo = document.getElementById('dataInfo');
    const statsPanel = document.getElementById('statsPanel');
    
    if (!container) {
        console.error('reportsContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) dataInfo.style.display = 'none';
    if (statsPanel) statsPanel.style.display = 'none';
    
    try {
        // 构建文件路径
        const yearMonth = date.substring(0, 7); // 2025-01
        const response = await fetch(`tdx_value/${yearMonth}/${date}.json`);
        if (!response.ok) throw new Error('通达信研报数据加载失败');
        
        currentReportsData = await response.json();
        
        // 更新数据信息
        updateDataInfo(currentReportsData);
        
        // 更新机构筛选选项
        updateInstitutionFilter(currentReportsData.研报数据);
        
        // 更新统计面板
        updateRatingStats(currentReportsData.研报数据);
        
        // 渲染研报表格
        renderReportsTable(currentReportsData.研报数据);
        
        // 显示数据区域
        if (dataInfo) dataInfo.style.display = 'flex';
        if (statsPanel) statsPanel.style.display = 'block';
        
    } catch (error) {
        console.error('加载通达信研报数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 更新数据信息
function updateDataInfo(data) {
    const updateTimeEl = document.getElementById('updateTime');
    const reportCountEl = document.getElementById('reportCount');
    const stockCountEl = document.getElementById('stockCount');
    const institutionCountEl = document.getElementById('institutionCount');
    
    if (updateTimeEl) {
        updateTimeEl.textContent = data.获取时间 || '--';
    }
    if (reportCountEl) {
        reportCountEl.textContent = data.数据条数 + '条' || '--';
    }
    if (stockCountEl) {
        const uniqueStocks = new Set(data.研报数据.map(r => r.证券代码)).size;
        stockCountEl.textContent = uniqueStocks + '只';
    }
    if (institutionCountEl) {
        const uniqueInstitutions = new Set(data.研报数据.map(r => r.研究机构)).size;
        institutionCountEl.textContent = uniqueInstitutions + '家';
    }
}

// 更新机构筛选选项
function updateInstitutionFilter(reports) {
    const institutionFilter = document.getElementById('institutionFilter');
    if (!institutionFilter) return;
    
    const institutions = [...new Set(reports.map(r => r.研究机构))].sort();
    
    institutionFilter.innerHTML = '<option value="">全部机构</option>';
    institutions.forEach(institution => {
        const option = document.createElement('option');
        option.value = institution;
        option.textContent = institution;
        institutionFilter.appendChild(option);
    });
}

// 更新评级统计
function updateRatingStats(reports) {
    const ratingStatsGrid = document.getElementById('ratingStatsGrid');
    if (!ratingStatsGrid) return;
    
    const ratingCounts = {};
    reports.forEach(report => {
        const rating = report.评级.split('(')[0]; // 去掉括号内容，如"买入(维持)" -> "买入"
        ratingCounts[rating] = (ratingCounts[rating] || 0) + 1;
    });
    
    const statsHtml = Object.entries(ratingCounts).map(([rating, count]) => {
        const colorClass = getRatingColorClass(rating);
        return `<div class="stat-item ${colorClass}">
            <span class="stat-label">${rating}</span>
            <span class="stat-value">${count}只</span>
        </div>`;
    }).join('');
    
    ratingStatsGrid.innerHTML = statsHtml;
}

// 获取评级颜色样式类
function getRatingColorClass(rating) {
    if (rating.includes('买入')) return 'rating-buy';
    if (rating.includes('增持')) return 'rating-hold';
    if (rating.includes('中性')) return 'rating-neutral';
    if (rating.includes('减持')) return 'rating-sell';
    return '';
}

// 渲染研报表格
function renderReportsTable(reports) {
    const container = document.getElementById('reportsContainer');
    
    if (!container) {
        console.error('reportsContainer元素未找到');
        return;
    }
    
    if (!reports || reports.length === 0) {
        container.innerHTML = '<div class="loading">暂无研报数据</div>';
        return;
    }
    
    const tableHtml = `
        <table class="reports-table">
            <thead>
                <tr class="header-row-1">
                    <th rowspan="2">序号</th>
                    <th rowspan="2">报告日期</th>
                    <th rowspan="2">证券代码</th>
                    <th rowspan="2">证券简称</th>
                    <th rowspan="2">研究机构</th>
                    <th rowspan="2">投资评级</th>
                    <th rowspan="2">目标价</th>
                    <th rowspan="2">T年度</th>
                    <th rowspan="2">EPS实际值(元)</th>
                    <th colspan="3">EPS预测</th>
                    <th rowspan="2">操作</th>
                </tr>
                <tr class="header-row-2">
                    <th>T年</th>
                    <th>T+1年</th>
                    <th>T+2年</th>
                </tr>
            </thead>
            <tbody>
                ${reports.map(report => `
                    <tr class="report-row" data-code="${report.证券代码}" data-name="${report.证券简称}" data-institution="${report.研究机构}" data-rating="${report.评级}">
                        <td class="report-index">${report.序号}</td>
                        <td>${report.报告日期}</td>
                        <td class="stock-code">${report.证券代码}</td>
                        <td class="stock-name">${report.证券简称}</td>
                        <td class="institution">${report.研究机构}</td>
                        <td class="rating ${getRatingColorClass(report.评级)}">${report.评级}</td>
                        <td class="target-price">${report.目标价}</td>
                        <td class="t-year">${report.T年度}</td>
                        <td class="eps-actual">${report['EPS实际值(元)']}</td>
                        <td class="eps-t">${report.EPS预测.T年}</td>
                        <td class="eps-t1">${report.EPS预测['T+1年']}</td>
                        <td class="eps-t2">${report.EPS预测['T+2年']}</td>
                        <td class="actions">
                            <button onclick="viewReportDetail('${report.证券代码}', ${report.序号})" class="action-btn-sm">📖 详情</button>
                            <button onclick="copyReportData('${report.证券代码}', ${report.序号})" class="action-btn-sm">📋 复制</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    
    container.innerHTML = tableHtml;
}

// 筛选研报
function filterReports() {
    const searchInput = document.getElementById('searchInput');
    const ratingFilter = document.getElementById('ratingFilter');
    const institutionFilter = document.getElementById('institutionFilter');
    
    if (!searchInput || !ratingFilter || !institutionFilter) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const ratingValue = ratingFilter.value;
    const institutionValue = institutionFilter.value;
    
    const reportRows = document.querySelectorAll('.report-row');
    
    reportRows.forEach(row => {
        const code = row.dataset.code.toLowerCase();
        const name = row.dataset.name.toLowerCase();
        const rating = row.dataset.rating;
        const institution = row.dataset.institution;
        
        const matchesSearch = !searchTerm || code.includes(searchTerm) || name.includes(searchTerm);
        const matchesRating = !ratingValue || rating.includes(ratingValue);
        const matchesInstitution = !institutionValue || institution === institutionValue;
        
        if (matchesSearch && matchesRating && matchesInstitution) {
            row.style.display = 'table-row';
        } else {
            row.style.display = 'none';
        }
    });
}

// 查看研报详情
function viewReportDetail(stockCode, reportIndex) {
    if (!currentReportsData || !currentReportsData.研报数据) {
        showToast('研报数据未找到', 'error');
        return;
    }
    
    const report = currentReportsData.研报数据.find(r => r.证券代码 === stockCode && r.序号 === reportIndex);
    if (!report) {
        showToast('研报详情未找到', 'error');
        return;
    }
    
    currentDetailReport = report;
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const reportDetailContent = document.getElementById('reportDetailContent');
    const modal = document.getElementById('reportDetailModal');
    
    if (!modalTitle || !reportDetailContent || !modal) {
        console.error('详情模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = `${report.证券简称} (${report.证券代码}) - 研报详情`;
    
    // 生成详情内容
    const detailHtml = generateReportDetailContent(report);
    reportDetailContent.innerHTML = detailHtml;
    
    // 显示模态框
    modal.style.display = 'block';
}

// 生成研报详情内容
function generateReportDetailContent(report) {
    return `
        <div class="report-detail-section">
            <h4>📊 基本信息</h4>
            <div class="detail-info-grid">
                <div class="info-pair"><span>证券代码:</span><span>${report.证券代码}</span></div>
                <div class="info-pair"><span>证券简称:</span><span>${report.证券简称}</span></div>
                <div class="info-pair"><span>研究机构:</span><span>${report.研究机构}</span></div>
                <div class="info-pair"><span>报告日期:</span><span>${report.报告日期}</span></div>
                <div class="info-pair"><span>投资评级:</span><span class="rating ${getRatingColorClass(report.评级)}">${report.评级}</span></div>
                <div class="info-pair"><span>评级变化:</span><span>${report.评级变化}</span></div>
                <div class="info-pair"><span>目标价格:</span><span>${report.目标价}</span></div>
                <div class="info-pair"><span>T年度:</span><span>${report.T年度}</span></div>
            </div>
        </div>
        
        <div class="report-detail-section">
            <h4>💰 盈利预测</h4>
            <div class="eps-info-grid">
                <div class="eps-item">
                    <span class="eps-label">EPS实际值:</span>
                    <span class="eps-value">${report['EPS实际值(元)']}</span>
                </div>
                <div class="eps-item">
                    <span class="eps-label">T年预测:</span>
                    <span class="eps-value">${report.EPS预测.T年}元 (${report.T年度})</span>
                </div>
                <div class="eps-item">
                    <span class="eps-label">T+1年预测:</span>
                    <span class="eps-value">${report.EPS预测['T+1年']}元 (${parseInt(report.T年度) + 1})</span>
                </div>
                <div class="eps-item">
                    <span class="eps-label">T+2年预测:</span>
                    <span class="eps-value">${report.EPS预测['T+2年']}元 (${parseInt(report.T年度) + 2})</span>
                </div>
            </div>
        </div>
        
        <div class="report-detail-section">
            <h4>📰 研报标题</h4>
            <div class="report-title-content">
                ${report.标题}
            </div>
        </div>
    `;
}

// 关闭研报详情模态框
function closeReportDetailModal() {
    const modal = document.getElementById('reportDetailModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentDetailReport = null;
}

// 复制研报详情
function copyReportDetail(type) {
    if (!currentDetailReport) {
        showToast('未选择研报', 'error');
        return;
    }
    
    let content = '';
    
    switch (type) {
        case 'full':
            content = generateReportTextContent(currentDetailReport);
            break;
        case 'basic':
            content = generateBasicReportTextContent(currentDetailReport);
            break;
        default:
            content = generateReportTextContent(currentDetailReport);
    }
    
    copyToClipboard(content);
}

// 生成研报文本内容
function generateReportTextContent(report) {
    let content = `${report.证券简称} (${report.证券代码}) - 投资评级研报\n\n`;
    content += `研究机构: ${report.研究机构}\n`;
    content += `报告日期: ${report.报告日期}\n`;
    content += `投资评级: ${report.评级}\n`;
    content += `评级变化: ${report.评级变化}\n`;
    content += `目标价格: ${report.目标价}\n`;
    content += `T年度: ${report.T年度}\n\n`;
    
    content += `=== 盈利预测 ===\n`;
    content += `EPS实际值: ${report['EPS实际值(元)']}\n`;
    content += `T年预测: ${report.EPS预测.T年}元 (${report.T年度})\n`;
    content += `T+1年预测: ${report.EPS预测['T+1年']}元 (${parseInt(report.T年度) + 1})\n`;
    content += `T+2年预测: ${report.EPS预测['T+2年']}元 (${parseInt(report.T年度) + 2})\n\n`;
    
    content += `=== 研报标题 ===\n`;
    content += `${report.标题}\n`;
    
    return content;
}

// 生成基本信息文本内容
function generateBasicReportTextContent(report) {
    return `${report.证券简称} (${report.证券代码})\n` +
           `机构: ${report.研究机构}\n` +
           `评级: ${report.评级}\n` +
           `目标价: ${report.目标价}\n` +
           `EPS预测: ${report.EPS预测.T年}/${report.EPS预测['T+1年']}/${report.EPS预测['T+2年']}`;
}

// 下载研报详情
function downloadReportDetail() {
    if (!currentDetailReport) {
        showToast('未选择研报', 'error');
        return;
    }
    
    const content = generateReportTextContent(currentDetailReport);
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `研报详情_${currentDetailReport.证券代码}_${currentDetailReport.证券简称}_${currentDetailReport.报告日期}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    showToast('详情下载中...');
}

// 复制单个研报数据
function copyReportData(stockCode, reportIndex) {
    if (!currentReportsData || !currentReportsData.研报数据) {
        showToast('研报数据未找到', 'error');
        return;
    }
    
    const report = currentReportsData.研报数据.find(r => r.证券代码 === stockCode && r.序号 === reportIndex);
    if (!report) {
        showToast('研报数据未找到', 'error');
        return;
    }
    
    const content = generateBasicReportTextContent(report);
    copyToClipboard(content);
}

// 复制通达信研报数据
function copyTdxReportsData() {
    if (!currentReportsData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    // 生成表格格式数据
    let textData = '序号\t报告日期\t证券代码\t证券简称\t研究机构\t投资评级\t目标价\tT年度\tEPS实际值\tT年EPS\tT+1年EPS\tT+2年EPS\t标题\n';
    
    currentReportsData.研报数据.forEach(report => {
        textData += `${report.序号}\t`;
        textData += `${report.报告日期}\t`;
        textData += `${report.证券代码}\t`;
        textData += `${report.证券简称}\t`;
        textData += `${report.研究机构}\t`;
        textData += `${report.评级}\t`;
        textData += `${report.目标价}\t`;
        textData += `${report.T年度}\t`;
        textData += `${report['EPS实际值(元)']}\t`;
        textData += `${report.EPS预测.T年}\t`;
        textData += `${report.EPS预测['T+1年']}\t`;
        textData += `${report.EPS预测['T+2年']}\t`;
        textData += `${report.标题}\n`;
    });
    
    copyToClipboard(textData);
}

// 查看JSON数据
function viewTdxReportsJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open(`json_viewer.html?type=tdx_reports&date=${date}`, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 模态框外部点击关闭
document.addEventListener('click', (e) => {
    const modal = document.getElementById('reportDetailModal');
    if (modal && e.target === modal) {
        closeReportDetailModal();
    }
});

// 键盘事件
document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('reportDetailModal');
    if (modal && modal.style.display === 'block' && e.key === 'Escape') {
        closeReportDetailModal();
    }
});
