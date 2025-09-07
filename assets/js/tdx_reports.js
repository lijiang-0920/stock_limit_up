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
async function loadTdxReportsDateOptions() {
    try {
        const response = await fetch('tdx_value/index.json');
        if (!response.ok) throw new Error('无法加载通达信研报日期数据');
        
        const indexData = await response.json();
        const dates = Object.keys(indexData).sort().reverse();
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
    
    container
