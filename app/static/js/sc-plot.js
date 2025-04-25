/**
 * SC绘图函数 - 用于绘制SC数据的交互式图表
 * 使用plotly.js实现学术风格图表
 */

function plotSCStructure(containerId, dataUrl) {
    // 获取容器元素
    const container = document.getElementById(containerId);
    
    // 检查是否存在容器
    if (!container) {
        console.error(`容器元素 ${containerId} 不存在`);
        return;
    }
    
    // 设置加载提示
    container.innerHTML = '<div style="text-align:center;padding:50px;">正在加载SC数据...</div>';
    
    // 获取数据文件
    fetch(dataUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('数据文件获取失败');
            }
            return response.text();
        })
        .then(data => {
            // 解析数据
            parseAndPlotSCData(data, container);
        })
        .catch(error => {
            console.error('SC数据加载失败:', error);
            container.innerHTML = `<div style="text-align:center;padding:50px;color:#e53e3e;">
                <i class="fas fa-exclamation-circle"></i> SC数据加载失败: ${error.message}
            </div>`;
        });
}

// 解析SC数据并找出曲线之间的关系
function analyzeCurveRelationships(data, traceNames) {
    // 提取所有曲线的数据
    const curveData = {};
    traceNames.forEach(trace => {
        const yValues = data.map(row => row[trace.index]);
        curveData[trace.name] = yValues;
    });
    
    // 对所有曲线数据取绝对值用于分组
    const absData = {};
    const isZeroCurve = {};
    Object.keys(curveData).forEach(name => {
        // 计算平均绝对值，用于判断是否为接近零的曲线
        const avgAbs = curveData[name].reduce((sum, val) => sum + Math.abs(val), 0) / curveData[name].length;
        isZeroCurve[name] = avgAbs < 0.1; // 扩大零值判定范围到0.1
        
        absData[name] = curveData[name].map(val => Math.abs(val));
    });
    
    // 找出具有相同数据模式的曲线组
    const groups = [];
    const processed = new Set();
    
    // 首先处理所有接近零的曲线
    const zeroCurves = Object.keys(isZeroCurve).filter(name => isZeroCurve[name]);
    if (zeroCurves.length > 0) {
        groups.push({
            curves: zeroCurves,
            relations: zeroCurves.map(name => `${name}=0`)
        });
        zeroCurves.forEach(name => processed.add(name));
    }
    
    // 按绝对值相似性对非零曲线进行分组
    const similarityGroups = {};
    const similarityThreshold = 0.01; // 增大相似性阈值，从0.001提高到0.01，更宽松地判断绝对值相似性
    
    // 第一步：找出具有相似绝对值的曲线组
    Object.keys(curveData).forEach(name1 => {
        if (processed.has(name1)) return;
        
        if (!similarityGroups[name1]) {
            similarityGroups[name1] = [name1];
        }
        
        Object.keys(curveData).forEach(name2 => {
            if (processed.has(name2) || name1 === name2) return;
            
            // 比较两条曲线的绝对值是否一致
            const absValues1 = absData[name1];
            const absValues2 = absData[name2];
            
            let diffSum = 0;
            for (let i = 0; i < absValues1.length; i++) {
                diffSum += Math.abs(absValues1[i] - absValues2[i]);
            }
            
            const avgDiff = diffSum / absValues1.length;
            
            if (avgDiff < similarityThreshold) {
                similarityGroups[name1].push(name2);
            }
        });
    });
    
    // 第二步：合并具有共同曲线的组
    const finalGroups = [];
    const groupProcessed = new Set();
    
    Object.keys(similarityGroups).forEach(key => {
        if (groupProcessed.has(key)) return;
        
        const group = [...similarityGroups[key]];
        groupProcessed.add(key);
        
        // 检查组是否有共同曲线，如果有则合并
        let i = 0;
        while (i < Object.keys(similarityGroups).length) {
            const otherKey = Object.keys(similarityGroups)[i];
            if (!groupProcessed.has(otherKey)) {
                const hasCommon = similarityGroups[otherKey].some(curve => group.includes(curve));
                
                if (hasCommon) {
                    // 合并组并去重
                    similarityGroups[otherKey].forEach(curve => {
                        if (!group.includes(curve)) {
                            group.push(curve);
                        }
                    });
                    groupProcessed.add(otherKey);
                }
            }
            i++;
        }
        
        if (group.length > 0) {
            finalGroups.push(group);
        }
    });
    
    // 第三步：确定每组内曲线之间的符号关系，构建关系表达式
    const relationGroups = [];
    
    finalGroups.forEach(curves => {
        if (curves.length === 0) return;
        
        // 所有曲线都已处理
        curves.forEach(curve => processed.add(curve));
        
        // 如果只有一条曲线，单独处理
        if (curves.length === 1) {
            relationGroups.push({
                curves: curves,
                relation: curves[0]
            });
            return;
        }
        
        // 用第一条曲线作为参考
        const referenceCurve = curves[0];
        const refValues = curveData[referenceCurve];
        
        // 确定每条曲线相对于参考曲线的符号关系
        const signRelations = {};
        curves.forEach(curve => {
            if (curve === referenceCurve) {
                signRelations[curve] = 1; // 参考曲线自身
                return;
            }
            
            const values = curveData[curve];
            let sameSignCount = 0;
            let oppositeSignCount = 0;
            
            // 比较非零值点的符号
            for (let i = 0; i < refValues.length; i++) {
                if (Math.abs(refValues[i]) < 0.0001 || Math.abs(values[i]) < 0.0001) continue;
                
                const sameSign = (refValues[i] > 0 && values[i] > 0) || (refValues[i] < 0 && values[i] < 0);
                
                if (sameSign) {
                    sameSignCount++;
                } else {
                    oppositeSignCount++;
                }
            }
            
            signRelations[curve] = (sameSignCount > oppositeSignCount) ? 1 : -1;
        });
        
        // 构建连续的等式关系表达式：a=b=-c=-d
        let relationExpression = referenceCurve;
        
        // 对曲线按符号关系排序，便于构建表达式
        const sameCurves = [referenceCurve]; // 与参考曲线符号相同的曲线
        const oppositeCurves = []; // 与参考曲线符号相反的曲线
        
        // 将曲线分为符号相同和符号相反两组
        curves.forEach(curve => {
            if (curve === referenceCurve) return;
            
            const signRelation = signRelations[curve];
            if (signRelation > 0) {
                sameCurves.push(curve);
            } else {
                oppositeCurves.push(curve);
            }
        });
        
        // 构建等式表达式，先添加符号相同的曲线
        for (let i = 1; i < sameCurves.length; i++) {
            relationExpression += "=" + sameCurves[i];
        }
        
        // 再添加符号相反的曲线，每个都带负号
        if (oppositeCurves.length > 0) {
            relationExpression += "=-" + oppositeCurves[0];
            
            for (let i = 1; i < oppositeCurves.length; i++) {
                relationExpression += "=-" + oppositeCurves[i];
            }
        }
        
        relationGroups.push({
            curves: curves,
            relation: relationExpression
        });
    });
    
    // 组合零曲线组和正常关系组
    const allGroups = [];
    
    // 添加零曲线组
    if (zeroCurves.length > 0) {
        allGroups.push({
            type: 'zero',
            curves: zeroCurves,
            relation: zeroCurves.join("=0, ") + "=0"
        });
    }
    
    // 添加其他关系组
    relationGroups.forEach(group => {
        allGroups.push({
            type: 'relation',
            curves: group.curves,
            relation: group.relation
        });
    });
    
    return allGroups;
}

// 生成元素关系的HTML表格
function generateRelationsTable(groups) {
    let html = `
        <div class="relations-table">
            <table>
                <thead>
                    <tr>
                        <th>Group</th>
                        <th>Relations</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    groups.forEach((group, index) => {
        // 确定每个组的行样式类和图标
        let styleClass = '';
        let iconClass = '';
        
        if (group.type === 'zero') {
            styleClass = 'zero-group';
            iconClass = 'zero-indicator';
        } else if (group.relation.includes('-')) {
            styleClass = 'mixed-relation';
            iconClass = 'opposite-indicator';
        } else {
            styleClass = 'same-relation';
            iconClass = 'same-indicator';
        }
        
        html += `
            <tr>
                <td>${index + 1}</td>
                <td class="${styleClass}">
                    <span class="${iconClass}">●</span> ${group.relation}
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    return html;
}

function parseAndPlotSCData(dataText, container) {
    // 按行分割数据
    const lines = dataText.trim().split('\n');
    
    // 解析注释行中的列名
    let header = lines[0];
    if (header.startsWith('#')) {
        header = header.substring(1).trim();
    }
    
    // 获取列名
    const headerParts = header.split(' ');
    
    // 提取所有曲线的名称
    const traceNames = [];
    for (let i = 1; i < headerParts.length; i++) {
        if (headerParts[i].match(/\d+-[a-z]{3}/)) {
            const nameParts = headerParts[i].split('-');
            if (nameParts.length === 2) {
                traceNames.push({
                    index: parseInt(nameParts[0]) - 1, // 调整索引以匹配数据列（从0开始）
                    name: nameParts[1]
                });
            }
        }
    }
    
    // 解析数据行
    const data = [];
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line && !line.startsWith('#')) {
            const values = line.split(/\s+/).map(Number);
            data.push(values);
        }
    }
    
    // 如果没有数据，显示错误消息
    if (data.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:50px;color:#e53e3e;">没有找到有效的SC数据</div>';
        return;
    }
    
    // 提取横坐标数据
    const xValues = data.map(row => row[0]);
    
    // 准备绘图数据
    const traces = [];
    
    // 创建每条曲线的trace，基础颜色设置更适合学术图表
    const colors = [
        // 主要色彩（高饱和度）
        '#FF3333', '#0066FF', '#33CC33', '#9900CC', '#FF9900', 
        '#00CCCC', '#FF3399', '#3366FF', '#99CC00', '#FF6600',
        // 次要色彩（中等饱和度）
        '#8B0000', '#006400', '#00008B', '#8B008B', '#FF4500',
        '#2F4F4F', '#696969', '#556B2F', '#800000', '#191970',
        // 补充色彩（确保27种不同颜色）
        '#20B2AA', '#9370DB', '#00CED1', '#FF1493', '#00FF7F',
        '#4682B4', '#DAA520'
    ];
    
    traceNames.forEach((traceName, i) => {
        // 确保索引在有效范围内
        if (traceName.index < data[0].length) {
            const yValues = data.map(row => row[traceName.index]);
            
            traces.push({
                x: xValues,
                y: yValues,
                type: 'scatter',
                mode: 'lines',
                name: traceName.name,
                hovertemplate: `Energy: %{x} eV<br>Sigma: %{y} uA/V²<extra>${traceName.name}</extra>`,
                line: {
                    width: 1.5,
                    color: colors[i % colors.length]
                }
            });
        }
    });
    
    // 创建控制面板容器
    const controlPanelHtml = `
        <div class="sc-control-panel">
            <div class="sc-control-tip">
                <i class="fas fa-info-circle"></i> <span class="control-tip-text">Double-click on legend items to isolate specific curves. Click "Reset" to show all curves.</span>
            </div>
            <div class="sc-control-item">
                <button id="resetBtn" class="sc-control-btn">Reset Chart</button>
            </div>
            <div class="sc-control-status">
                <span class="visible-count-text">Visible: <span id="visibleCount">${traces.length}</span>/${traces.length} curves</span>
            </div>
        </div>
    `;
    
    // 清空容器并添加控制面板
    container.innerHTML = controlPanelHtml + '<div id="sc-plot" style="width:100%;height:700px;"></div>';
    
    // 布局配置 - 学术风格的图表布局设置
    const layout = {
        // 图表标题配置
        title: {
            text: 'SC Structure', // 标题文本
            font: {
                size: 24, // 标题字体大小
                family: 'Arial, sans-serif', // 标题字体
                color: '#1f2937' // 标题颜色
            }
        },
        // X轴配置
        xaxis: {
            title: {
                text: 'Energy (eV)', // X轴标题文本
                font: {
                    size: 18, // X轴标题字体大小
                    family: 'Arial, sans-serif', // X轴标题字体
                    color: '#1f2937' // X轴标题颜色
                }
            },
            showgrid: true, // 显示网格线
            gridcolor: '#e5e7eb', // 网格线颜色
            gridwidth: 1, // 网格线宽度
            zeroline: true, // 显示零线
            zerolinecolor: '#6b7280', // 零线颜色
            zerolinewidth: 1.5, // 零线宽度
            showline: true, // 显示轴线
            linecolor: '#374151', // 轴线颜色
            linewidth: 2, // 轴线宽度
            tickfont: { // 刻度标签字体设置
                size: 14,
                family: 'Arial, sans-serif',
                color: '#4b5563'
            },
            mirror: true // 在对面也显示轴线
        },
        // Y轴配置，与X轴类似
        yaxis: {
            title: {
                text: 'Sigma (uA/V²)', // Y轴标题文本
                font: {
                    size: 18,
                    family: 'Arial, sans-serif',
                    color: '#1f2937'
                }
            },
            showgrid: true,
            gridcolor: '#e5e7eb',
            gridwidth: 1,
            zeroline: true,
            zerolinecolor: '#6b7280',
            zerolinewidth: 1.5,
            showline: true,
            linecolor: '#374151',
            linewidth: 2,
            tickfont: {
                size: 14,
                family: 'Arial, sans-serif',
                color: '#4b5563'
            },
            mirror: 'ticks' // 显示对称刻度线
        },
        hovermode: 'closest', // 悬停模式设为最近点
        // 图例配置
        legend: {
            orientation: 'v', // 垂直方向排列
            xanchor: 'left', // 左侧对齐
            x: 1.05, // X位置（图表右侧）
            yanchor: 'top', // 顶部对齐
            y: 1, // Y位置
            font: { // 图例字体设置
                size: 18,
                family: 'Arial, sans-serif'
            },
            tracegroupgap: 16,
            bgcolor: '#f8fafc',
            bordercolor: '#e2e8f0',
            borderwidth: 2,
            itemsizing: 'constant',
            itemwidth: 45
        },
        // 图表边距设置
        margin: {
            t: 80, // 顶部边距
            r: 200, // 右侧边距（为图例留出空间）
            b: 100, // 底部边距
            l: 100 // 左侧边距
        },
        autosize: true, // 自动调整大小
        paper_bgcolor: '#ffffff', // 画布背景色
        plot_bgcolor: '#ffffff', // 绘图区背景色
        // 添加形状（用于绘制边框）
        shapes: [
            {
                type: 'rect', // 矩形形状
                xref: 'paper', // 相对于画布的X参考
                yref: 'paper', // 相对于画布的Y参考
                x0: 0, // 起始X坐标
                y0: 0, // 起始Y坐标
                x1: 1, // 结束X坐标
                y1: 1, // 结束Y坐标
                line: {
                    width: 2, // 边框线宽
                    color: '#374151' // 边框颜色
                },
                fillcolor: 'rgba(0,0,0,0)' // 填充色（透明）
            }
        ]
    };
    
    // Plotly配置中添加自定义图例样式插件
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        toImageButtonOptions: {
            format: 'png',
            filename: 'sc_structure',
            height: 800,
            width: 1200,
            scale: 2
        }
    };
    
    // 修改曲线样式，增强显示效果
    traces.forEach(trace => {
        trace.line.width = 2.5; // 线宽适中，避免过粗
        trace.hoverlabel = {
            bgcolor: '#f8fafc',
            bordercolor: trace.line.color,
            font: {
                size: 14, // 适中的悬停标签字体
                family: 'Arial, sans-serif'
            }
        };
    });
    
    // 绘制图表
    const plotElement = document.getElementById('sc-plot');
    Plotly.newPlot(plotElement, traces, layout, config);
    
    // 跟踪每条曲线的点击次数
    const curveClickCounts = new Array(traces.length).fill(0);
    
    // 增大图例中的线条显示
    setTimeout(() => {
        const legendLines = document.querySelectorAll('.legendlines path');
        legendLines.forEach(line => {
            line.setAttribute('stroke-width', '3'); 
            line.setAttribute('d', line.getAttribute('d').replace(/5\.0/g, '10.0')); 
        });
        
        // 增强图例滚动交互
        const legendEl = document.querySelector('.legend');
        if (legendEl) {
            // 为图例添加滚动提示
            const observer = new MutationObserver((mutations) => {
                const legendRect = legendEl.getBoundingClientRect();
                const contentHeight = legendEl.scrollHeight;
                
                // 如果内容高度超过可见高度，添加滚动提示
                if (contentHeight > legendRect.height && !legendEl.classList.contains('scrollable')) {
                    legendEl.classList.add('scrollable');
                    
                    // 添加滚动提示样式
                    const scrollStyle = document.createElement('style');
                    scrollStyle.textContent = `
                        .scrollable::after {
                            content: '';
                            position: absolute;
                            bottom: 5px;
                            left: 50%;
                            transform: translateX(-50%);
                            width: 30px;
                            height: 4px;
                            background-color: #0047AB;
                            border-radius: 2px;
                            opacity: 0.7;
                            animation: scrollPulse 1.5s infinite;
                        }
                        @keyframes scrollPulse {
                            0% { opacity: 0.7; }
                            50% { opacity: 0.3; }
                            100% { opacity: 0.7; }
                        }
                    `;
                    document.head.appendChild(scrollStyle);
                }
            });
            
            observer.observe(legendEl, { childList: true, subtree: true });
        }
    }, 300);
    
    // 添加自定义样式
    const style = document.createElement('style');
    style.textContent = `
        /* 样式已移动到detail.html中定义 */
    `;
    document.head.appendChild(style);
    
    // 更新可见曲线计数
    function updateVisibleCount() {
        // 使用点击次数判断曲线可见性
        // 偶数次点击表示显示，奇数次点击表示隐藏
        let visible = 0;
        for (let i = 0; i < curveClickCounts.length; i++) {
            // 如果点击次数为偶数(包括0)，曲线可见
            if (curveClickCounts[i] % 2 === 0) {
                visible++;
            }
        }
        
        document.getElementById('visibleCount').textContent = visible;
        return visible;
    }
    
    // 重置图表按钮
    document.getElementById('resetBtn').addEventListener('click', function() {
        const update = {visible: true};
        Plotly.restyle(plotElement, update);
        
        // 重置所有曲线的点击计数
        curveClickCounts.fill(0);
        updateVisibleCount();
        
        // 添加视觉反馈
        this.classList.add('active');
        setTimeout(() => this.classList.remove('active'), 200);
    });
    
    // 监听图例点击，更新可见曲线计数
    plotElement.on('plotly_legendclick', function(data) {
        if (data && data.curveNumber !== undefined) {
            // 更新点击次数
            curveClickCounts[data.curveNumber]++;
            
            // 立即更新计数
            updateVisibleCount();
        
        // 添加点击动画反馈
        const legendItems = document.querySelectorAll('.traces');
        if (legendItems && legendItems.length > 0 && data.curveNumber < legendItems.length) {
            const item = legendItems[data.curveNumber];
            item.classList.add('active');
            setTimeout(() => item.classList.remove('active'), 300);
            }
        }
    });
    
    // 监听双击图例，保持监视更新计数
    plotElement.on('plotly_legenddoubleclick', function(data) {
        if (data && data.curveNumber !== undefined) {
            // 双击时重置所有曲线的点击次数，除了当前曲线
            for (let i = 0; i < curveClickCounts.length; i++) {
                if (i !== data.curveNumber) {
                    // 设为1表示隐藏
                    curveClickCounts[i] = 1;
                } else {
                    // 当前曲线设为0表示显示
                    curveClickCounts[i] = 0;
                }
            }
            
            // 立即更新计数
            updateVisibleCount();
            
            const traceName = traces[data.curveNumber].name;
            
            const notification = document.createElement('div');
            notification.className = 'sc-notification';
            notification.innerHTML = `<i class="fas fa-eye"></i> Only showing "${traceName}" curve`;
            
            document.querySelector('.sc-control-panel').appendChild(notification);
            
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 500);
            }, 2000);
        }
    });
    
    // 初始添加图例项鼠标悬停提示
    setTimeout(() => {
        const legendItems = document.querySelectorAll('.legendtext');
        legendItems.forEach(item => {
            item.setAttribute('data-tooltip', 'Click to toggle visibility, Double-click to isolate');
            item.setAttribute('title', 'Click to toggle visibility, Double-click to isolate');
        });
    }, 500);
    
    // 在分析数据后添加关系分析
    const relationships = analyzeCurveRelationships(data, traceNames);
    const relationsTableHtml = generateRelationsTable(relationships);
    
    // 发送关系表到Element Relations卡片
    setTimeout(() => {
        const relationsTableContainer = document.getElementById('relations-table-container');
        if (relationsTableContainer) {
            relationsTableContainer.innerHTML = relationsTableHtml;
        }
    }, 500);
} 