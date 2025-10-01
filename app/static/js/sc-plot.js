/**
 * sc-plot.js
 * SC绘图函数 - 用于绘制SC数据的交互式图表
 * 使用plotly.js实现学术风格图表
 */

/**
 * 绘制SC结构图表的主函数
 * @param {string} containerId - 用于放置图表的HTML容器元素ID
 * @param {string} dataUrl - SC数据文件的URL地址
 * 
 * 函数功能:
 * 1. 检查并获取容器元素
 * 2. 显示加载提示
 * 3. 尝试加载主数据文件
 * 4. 如果主文件加载失败,则加载示例数据
 * 5. 解析数据并绘制图表
 * 6. 处理错误情况并显示相应提示
 */
function plotSCStructure(containerId, dataUrl) {
    console.log('SC dataUrl:', dataUrl);
    // 获取并验证容器元素
    const container = document.getElementById(containerId);
    
    // 如果找不到容器元素,输出错误并退出
    if (!container) {
        console.error(`容器元素 ${containerId} 不存在`);
        return;
    }
    
    // 显示数据加载中的提示信息
    container.innerHTML = '<div style="text-align:center;padding:50px;">正在加载SC数据...</div>';
    
    // 首先尝试加载用户指定的数据文件
    fetch(dataUrl)
        .then(response => {
            // 检查响应状态
            if (!response.ok) throw new Error('not found');
            return response.text();
        })
        .then(data => {
            // 成功获取数据后,解析并绘制图表
            parseAndPlotSCData(data, container);
        })
        .catch(() => {
            // 主数据文件加载失败,直接显示无数据提示，不再加载示例数据
            container.innerHTML = `<div style=\"padding: 48px 16px; text-align: center; background: linear-gradient(90deg,#fff,#f3f4f6 60%,#fff); border-radius: 12px; margin: 24px 0; box-shadow:0 2px 8px #e5e7eb;\">
                <div style=\"font-size: 2rem; font-weight: bold; color: #dc2626; margin-bottom: 12px; letter-spacing:1px;\">SC data not found</div>
                <div style=\"font-size: 1rem; color: #666; max-width: 480px; margin: 0 auto; line-height: 1.7;\">
                    Sorry, the SC data for this material is currently unavailable.<br>
                    This may be due to missing or incorrectly formatted data files.<br>
                    Our development team is actively working to improve this feature.<br>
                    If you have any questions or suggestions, please contact us via <a href='mailto:your_email@example.com' style='color:#2563eb;text-decoration:underline;'>email</a> or submit a <a href='https://github.com/yourrepo/issues' target='_blank' style='color:#2563eb;text-decoration:underline;'>GitHub Issue</a>.
                </div>
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
    
    // 计算所有曲线的平均绝对值
    const avgAbsValues = {};
    Object.keys(curveData).forEach(name => {
        const avgAbs = curveData[name].reduce((sum, val) => sum + Math.abs(val), 0) / curveData[name].length;
        avgAbsValues[name] = avgAbs;
    });
    
    // 找出最大平均绝对值，用于确定数量级
    const maxAvgAbs = Math.max(...Object.values(avgAbsValues));
    console.log(`最大曲线平均绝对值: ${maxAvgAbs}`);
    
    // 确定零曲线阈值 - 使用相对数量级判断
    // 如果最大值很小(小于0.01)，使用更低的相对阈值
    let zeroThreshold;
    if (maxAvgAbs < 0.01) {
        // 取最大值的1/1000作为阈值
        zeroThreshold = maxAvgAbs / 1000;
        console.log(`使用小曲线相对阈值: ${zeroThreshold}`);
    } else if (maxAvgAbs < 0.1) {
        // 取最大值的1/100作为阈值
        zeroThreshold = maxAvgAbs / 100;
        console.log(`使用中等曲线相对阈值: ${zeroThreshold}`);
    } else {
        // 取最大值的1/50或固定值0.02，取较大者
        zeroThreshold = Math.max(maxAvgAbs / 50, 0.02);
        console.log(`使用大曲线相对阈值: ${zeroThreshold}`);
    }
    
    // 动态确定曲线相似性阈值 - 基于相同的数量级逻辑
    let similarityThreshold;
    if (maxAvgAbs < 0.01) {
        // 对于整体很小的曲线，使用较小的相似性阈值
        similarityThreshold = maxAvgAbs / 100; // 相对于最大值的1%
        console.log(`使用小曲线相对相似性阈值: ${similarityThreshold}`);
    } else if (maxAvgAbs < 0.1) {
        // 中等数量级使用中等阈值
        similarityThreshold = maxAvgAbs / 50; // 相对于最大值的2%
        console.log(`使用中等曲线相对相似性阈值: ${similarityThreshold}`);
    } else {
        // 大数量级使用更宽松的阈值
        similarityThreshold = maxAvgAbs / 20; // 相对于最大值的5%
        console.log(`使用大曲线相对相似性阈值: ${similarityThreshold}`);
    }
    
    // 对所有曲线数据取绝对值用于分组
    const absData = {};
    const isZeroCurve = {};
    Object.keys(curveData).forEach(name => {
        // 基于动态阈值判断是否为零曲线
        isZeroCurve[name] = avgAbsValues[name] < zeroThreshold;
        console.log(`曲线 ${name}: 平均绝对值=${avgAbsValues[name]}, 是否为零曲线=${isZeroCurve[name]}`);
        
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
            
            // 计算两曲线差值的标准差，以更好地评估整体相似性
            let sumDiff = 0;
            let sumSqDiff = 0;
            let maxDiff = 0;
            
            for (let i = 0; i < absValues1.length; i++) {
                const diff = Math.abs(absValues1[i] - absValues2[i]);
                sumDiff += diff;
                sumSqDiff += diff * diff;
                maxDiff = Math.max(maxDiff, diff); // 记录最大差异
            }
            
            const avgDiff = sumDiff / absValues1.length;
            // 计算标准差
            const stdDev = Math.sqrt(sumSqDiff / absValues1.length - (avgDiff * avgDiff));
            
            // 在控制台输出详细的比较结果
            console.log(`比较曲线 ${name1} 和 ${name2}: 平均差异=${avgDiff.toExponential(3)}, 标准差=${stdDev.toExponential(3)}, 最大差异=${maxDiff.toExponential(3)}, 相似性阈值=${similarityThreshold.toExponential(3)}`);
            
            // 综合考虑平均差异和标准差，使判断更稳健
            if (avgDiff < similarityThreshold && stdDev < similarityThreshold * 2) {
                similarityGroups[name1].push(name2);
                console.log(`=> 曲线 ${name1} 和 ${name2} 被判定为相似`);
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
        <div class="relations-legend" style="display:flex; gap:12px; align-items:center; margin:8px 8px 6px;">
            <span class="same-relation"><span style="font-weight:700">●</span> Same sign</span>
            <span class="opposite-relation"><span style="font-weight:700">●</span> Opposite sign</span>
            <span class="zero-group"><span style="font-weight:700">●</span> Zero group</span>
        </div>
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
            // 相反关系统一使用红色样式（opposite-relation）
            styleClass = 'opposite-relation';
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
        container.innerHTML = `<div style="padding: 48px 16px; text-align: center; background: linear-gradient(90deg,#fff,#f3f4f6 60%,#fff); border-radius: 12px; margin: 24px 0; box-shadow:0 2px 8px #e5e7eb;">
            <div style="font-size: 2rem; font-weight: bold; color: #dc2626; margin-bottom: 12px; letter-spacing:1px;">SC data not found</div>
            <div style="font-size: 1rem; color: #666; max-width: 480px; margin: 0 auto; line-height: 1.7;">
                Sorry, the SC data for this material is currently unavailable.<br>
                This may be due to missing or incorrectly formatted data files.<br>
                Our development team is actively working to improve this feature.<br>
                If you have any questions or suggestions, please contact us via <a href='mailto:your_email@example.com' style='color:#2563eb;text-decoration:underline;'>email</a> or submit a <a href='https://github.com/yourrepo/issues' target='_blank' style='color:#2563eb;text-decoration:underline;'>GitHub Issue</a>.
            </div>
        </div>`;
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
                },
                visible: true  // 明确设置初始状态为可见
            });
        }
    });
    
    // 创建控制面板容器
    const controlPanelHtml = `
        <div class="sc-control-panel">
            <div class="sc-control-tip">
                <i class="fas fa-info-circle"></i> <span class="control-tip-text">Single-click to toggle curves, double-click to isolate (hide all others).</span>
            </div>
            <div class="sc-control-item">
                <button id="resetBtn" class="sc-control-btn btn btn--secondary btn--sm">Reset Chart</button>
            </div>
            <div class="sc-control-status">
                <span class="visible-count-text">Visible: <span id="visibleCount">${traces.length}</span>/${traces.length} curves</span>
            </div>
        </div>
    `;
    
    // 清空容器并添加控制面板
    container.innerHTML = controlPanelHtml + '<div id="sc-plot" style="width:100%;"></div>';
    
    // ====== 动态计算Plotly绘图区域的高度和宽度 ======
    function getPlotSize() {
        // 获取父容器（#scStructure）
        const parent = container;
        // 获取控制面板和示例提示
        const controlPanel = parent.querySelector('.sc-control-panel');
        const tip = parent.querySelector('.sc-example-tip');
        // 容器总高度
        let availableHeight = parent.getBoundingClientRect().height;
        // 减去控制面板高度
        if (controlPanel) availableHeight -= controlPanel.getBoundingClientRect().height;
        // 减去示例提示高度
        if (tip) availableHeight -= tip.getBoundingClientRect().height;
        // 兜底最小高度
        if (availableHeight < 300) availableHeight = 300;
        // 宽度直接取父容器宽度
        let availableWidth = parent.getBoundingClientRect().width;
        if (availableWidth < 300) availableWidth = 300;
        return {height: availableHeight, width: availableWidth};
    }

    // 获取动态尺寸
    const plotElement = document.getElementById('sc-plot');

    // === 关键：等浏览器完成一帧布局后再绘图，确保高度准确，减少回弹 ===
    requestAnimationFrame(() => {
        const plotSize = getPlotSize();
        // 明确设置绘图容器尺寸，避免因父容器未定高导致 0 高度
        if (plotElement && plotSize) {
            plotElement.style.height = plotSize.height + 'px';
            plotElement.style.width = plotSize.width + 'px';
        }
        const layout = {
            // 图表标题配置
            title: {
                text: 'Shift Current', // 标题文本
                font: {
                    family: 'system-ui, -apple-system, sans-serif',
                    size: 20
                },
                y: 0.97,
                x: 0.5,
                xanchor: 'center',
                yanchor: 'top'
            },
            // X轴配置
            xaxis: {
                title: {
                    text: 'Energy (eV)', // X轴标题文本
                    font: {
                        size: 16, // 减小X轴标题字体大小
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
                    size: 12, // 减小刻度字体大小
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
                        size: 16, // 减小Y轴标题字体大小
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
                    size: 12, // 减小刻度字体大小
                    family: 'Arial, sans-serif',
                    color: '#4b5563'
                },
                mirror: 'ticks' // 显示对称刻度线
            },
            hovermode: 'closest', // 悬停模式设为最近点
            // 图例配置
            legend: {
                orientation: 'h', // 水平方向排列
                xanchor: 'center', // 中心对齐
                x: 0.5, // 居中放置
                yanchor: 'top', // 顶部对齐
                y: -0.25, // 放在图表下方，增加与x轴的距离
                font: { // 图例字体设置
                    size: 14, // 增大图例字体大小
                    family: 'Arial, sans-serif'
                },
                tracegroupgap: 8, // 减小图例组间距
                bgcolor: '#ffffff', // 白色背景
                bordercolor: '#e2e8f0',
                borderwidth: 1,
                itemsizing: 'constant',
                itemwidth: 40 // 图例项宽度
            },
            // 图表边距设置
            margin: {
                t: 50, // 顶部边距
                r: 30, // 右侧边距
                b: 120, // 显著增加底部边距，为图例留出更多空间
                l: 80 // 左侧边距
            },
            autosize: false, // 关闭Plotly自动尺寸，采用自定义
            height: plotSize.height,
            width: plotSize.width,
            paper_bgcolor: '#ffffff',
            plot_bgcolor: '#ffffff',
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
        
        // 绘制图表（加载页改为全站触发，不在模块内控制）
        console.log(`SC图表: 准备绘制 ${traces.length} 条曲线，实现完整的交互逻辑`);
        Plotly.newPlot(plotElement, traces, layout, config)
          .catch(err => { console.error('SC 绘制失败:', err); });

        // 状态管理变量
        const curveVisibility = new Array(traces.length).fill(true); // 跟踪每条曲线的可见性

        // 双击检测变量
        let lastClickTime = 0;
        let lastClickCurve = -1;
        const DOUBLE_CLICK_THRESHOLD = 400; // 400ms内的两次点击视为双击

        // 初始化完成后立即更新计数显示
        setTimeout(() => {
            console.log('SC图表: 初始化完成，更新曲线计数');
            updateVisibleCount();
        }, 200);

        // 监听图表重新布局事件，确保计数同步
        plotElement.on('plotly_relayout', function() {
            requestAnimationFrame(() => {
                updateVisibleCount();
            });
        });
        
        // 增大图例中的线条显示
        requestAnimationFrame(() => {
            const legendLines = document.querySelectorAll('.legendlines path');
            legendLines.forEach(line => {
                line.setAttribute('stroke-width', '4'); // 增加线宽
                line.setAttribute('d', line.getAttribute('d').replace(/5\.0/g, '15\.0')); // 增加线长
            });
            // 去除图例滚动提示与运行时样式注入，避免布局回弹
        }, 300);
        
        
        
        // 更新可见曲线计数
        function updateVisibleCount() {
            // 直接从Plotly图表中获取当前可见的曲线数量
            let visible = 0;
            try {
                const plotData = plotElement.data;
                if (plotData && Array.isArray(plotData)) {
                    visible = plotData.filter(trace => trace.visible !== false && trace.visible !== 'legendonly').length;
                    console.log(`SC图表: 当前可见曲线数量 ${visible}/${plotData.length}`);
                }
            } catch (e) {
                // 如果无法获取Plotly数据，则使用内部状态作为备用方案
                visible = curveVisibility.filter(v => v).length;
                console.log(`SC图表: 使用备用计数方法，可见曲线数量 ${visible}/${curveVisibility.length}`);
            }

            document.getElementById('visibleCount').textContent = visible;
            return visible;
        }



        // 应用曲线可见性状态到Plotly图表
        function applyCurveVisibility() {
            const visibilityUpdate = curveVisibility.map(visible => visible ? true : 'legendonly');
            const visibleCount = curveVisibility.filter(v => v).length;
            console.log(`SC图表: 应用可见性更新，可见曲线: ${visibleCount}/${curveVisibility.length}`);
            console.log('SC图表: 可见性状态:', curveVisibility.map((v, i) => `${i}:${v}`).join(', '));

            Plotly.restyle(plotElement, {visible: visibilityUpdate});
            setTimeout(() => {
                updateVisibleCount();
            }, 100);
        }
        
        // 重置图表按钮
        document.getElementById('resetBtn').addEventListener('click', function() {
            console.log('SC图表: 重置按钮被点击');

            // 重置状态：显示所有曲线
            curveVisibility.fill(true);

            // 应用到图表
            applyCurveVisibility();

            // 添加视觉反馈
            this.classList.add('active');
            setTimeout(() => this.classList.remove('active'), 200);

            // 显示重置通知
            const notification = document.createElement('div');
            notification.className = 'sc-notification';
            notification.innerHTML = `<i class="fas fa-refresh"></i> All ${traces.length} curves are now visible`;

            document.querySelector('.sc-control-panel').appendChild(notification);

            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 500);
            }, 1500);
        });
        
        // 处理单击逻辑的函数
        function handleSingleClick(curveIndex) {
            console.log(`SC图表: 处理单击曲线 ${curveIndex}`);

            // 简单逻辑：切换曲线可见性
            curveVisibility[curveIndex] = !curveVisibility[curveIndex];
            console.log(`SC图表: 曲线 ${curveIndex} 可见性切换为: ${curveVisibility[curveIndex]}`);

            // 应用可见性变化
            applyCurveVisibility();
        }

        // 处理双击逻辑的函数
        function handleDoubleClick(curveIndex) {
            console.log(`SC图表: 处理双击曲线 ${curveIndex}，强制隔离显示`);

            // 双击强制隔离：隐藏所有其他曲线，只显示被双击的曲线
            curveVisibility.fill(false);
            curveVisibility[curveIndex] = true;

            // 应用可见性变化
            applyCurveVisibility();

            const traceName = traces[curveIndex].name;

            const notification = document.createElement('div');
            notification.className = 'sc-notification';
            notification.innerHTML = `<i class="fas fa-eye"></i> Isolated: Only showing "${traceName}" curve`;

            document.querySelector('.sc-control-panel').appendChild(notification);

            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 500);
            }, 1500);
        }

        // 监听图例点击（统一处理单击和双击）
        plotElement.on('plotly_legendclick', function(data) {
            if (data && data.curveNumber !== undefined) {
                const curveIndex = data.curveNumber;
                const currentTime = Date.now();

                console.log(`SC图表: 检测到点击事件，曲线 ${curveIndex}，时间间隔: ${currentTime - lastClickTime}ms`);

                // 检查是否为双击（同一曲线，时间间隔小于阈值）
                const isDoubleClick = (curveIndex === lastClickCurve) &&
                                    (currentTime - lastClickTime < DOUBLE_CLICK_THRESHOLD);

                console.log(`SC图表: 双击检测 - 同一曲线: ${curveIndex === lastClickCurve}, 时间间隔: ${currentTime - lastClickTime}ms < ${DOUBLE_CLICK_THRESHOLD}ms: ${currentTime - lastClickTime < DOUBLE_CLICK_THRESHOLD}`);

                if (isDoubleClick) {
                    console.log('SC图表: ✅ 检测到双击，执行双击逻辑');
                    handleDoubleClick(curveIndex);
                } else {
                    console.log('SC图表: 📱 执行单击逻辑');
                    handleSingleClick(curveIndex);

                    // 添加点击动画反馈
                    const legendItems = document.querySelectorAll('.traces');
                    if (legendItems && legendItems.length > 0 && curveIndex < legendItems.length) {
                        const item = legendItems[curveIndex];
                        item.classList.add('active');
                        setTimeout(() => item.classList.remove('active'), 300);
                    }
                }

                // 更新最后点击信息
                lastClickTime = currentTime;
                lastClickCurve = curveIndex;

                // 阻止Plotly的默认图例点击行为
                return false;
            }
        });
        
        // 注意：双击检测现在在单击事件中统一处理，不再需要单独的双击监听器
        
        // 初始添加图例项鼠标悬停提示
        setTimeout(() => {
            const legendItems = document.querySelectorAll('.legendtext');
            legendItems.forEach(item => {
                item.setAttribute('data-tooltip', 'Click: toggle | Double-click: isolate');
                item.setAttribute('title', 'Click: toggle | Double-click: isolate');
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
        
        // 响应窗口和容器变化，动态调整Plotly尺寸
        function handleResize() {
            const plotSize = getPlotSize();
            Plotly.relayout('sc-plot', {
                height: plotSize.height,
                width: plotSize.width,
                autosize: false
            });
        }
        window.addEventListener('resize', handleResize);

        // 卡片展开/折叠时也触发（重构后不再有 .viewer-container，改为定位最近的 #sc-card / .detail-card）
        const cardRoot = container.closest('#sc-card') || container.closest('.detail-card');
        const cardHeader = cardRoot ? cardRoot.querySelector('.card-header') : null;
        if (cardHeader) {
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        const isCollapsed = cardHeader.classList.contains('collapsed');
                        if (!isCollapsed) {
                            setTimeout(handleResize, 300);
                        }
                    }
                });
            });
            observer.observe(cardHeader, { attributes: true });
        }
        
        // 获取重置按钮并添加点击事件
        const resetBtn = document.getElementById('resetBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                Plotly.restyle('sc-plot', 'visible', true);
                updateVisibleCount();
            });
        }
    }, 0); // 0ms延迟，等DOM渲染
} 