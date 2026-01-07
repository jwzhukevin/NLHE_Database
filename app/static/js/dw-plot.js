/**
 * DW 九曲线绘制与本征矩阵渲染
 * 约定：
 * - 目录下存在固定命名的九个文件：D_xx.dat, D_xy.dat, ..., D_zz.dat
 * - matrix.dat（可选）：取倒数三行、每行三列，组成 3x3 矩阵
 * - 单位：曲线 y 轴 s^-1；矩阵元素 s^-1
 */

(function(){
    // 数值格式化：区间 [1e-3, 1e3) 用普通小数，否则科学计数法
    function formatValue(v) {
        if (v === null || Number.isNaN(v)) return '-';
        if (v === 0) return '0';
        try {
            const n = Number(v);
            const absn = Math.abs(n);
            if (absn >= 1e-3 && absn < 1e3) {
                let s = n.toFixed(6);
                s = s.replace(/\.0+$/, '').replace(/(\.\d*?[1-9])0+$/, '$1');
                return s;
            }
            return n.toExponential(3);
        } catch (e) {
            return String(v);
        }
    }
    function fetchText(url) {
        return fetch(url, { cache: 'no-cache' }).then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status} @ ${url}`);
            return res.text();
        });
    }

    function parseTwoCols(text) {
        const xs = [], ys = [];
        const lines = text.split(/\r?\n/);
        for (const line of lines) {
            const s = line.trim();
            if (!s || s.startsWith('#')) continue;
            const parts = s.split(/\s+/);
            if (parts.length >= 2) {
                const x = parseFloat(parts[0]);
                const y = parseFloat(parts[1]);
                if (!Number.isNaN(x) && !Number.isNaN(y)) {
                    xs.push(x);
                    ys.push(y);
                }
            }
        }
        return { x: xs, y: ys };
    }

    const components = [
        'xx','xy','xz',
        'yx','yy','yz',
        'zx','zy','zz'
    ];

    function makeLabel(comp){
        return `D${comp}`;
    }

    function renderMatrix(matrixContainerId, matrix, unitLabel) {
        if (!matrix || matrix.length !== 3) return;
        const el = document.getElementById(matrixContainerId);
        if (!el) return;
        let html = '<table class="prop-table"><thead><tr>' +
                   '<th>i\\j</th><th>x</th><th>y</th><th>z</th></tr></thead><tbody>';
        const axis = ['x','y','z'];
        for (let i=0;i<3;i++){
            html += `<tr><th>${axis[i]}</th>`;
            for (let j=0;j<3;j++){
                const v = matrix[i][j];
                const text = formatValue(v);
                html += `<td>${text}</td>`;
            }
            html += '</tr>';
        }
        html += `</tbody></table><div class="property-note">Unit: ${unitLabel}</div>`;
        el.innerHTML = html;
    }

    function parseMatrixFromText(text) {
        const lines = text.split(/\r?\n/).filter(l => l.trim().length>0);
        if (lines.length < 3) return null;
        const last3 = lines.slice(-3);
        const mat = [];
        for (const line of last3) {
            const parts = line.trim().split(/\s+/);
            if (parts.length < 3) return null;
            const row = parts.slice(0,3).map(v => {
                const n = parseFloat(v);
                return Number.isNaN(n) ? null : +n;
            });
            mat.push(row);
        }
        return mat;
    }

    function plotDW(containerId, dirUrl, matrixFileUrl) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn('DW 容器未找到:', containerId);
            return;
        }
        if (!dirUrl) {
            container.innerHTML = '<div class="error">DW 数据目录未提供</div>';
            return;
        }

        const fileUrls = components.map(c => `${dirUrl}/D_${c}.dat`);
        const fetches = fileUrls.map(url => fetchText(url).then(txt => ({ url, txt })).catch(err => ({ url, err })));

        Promise.all(fetches).then(results => {
            const traces = [];
            const failures = [];
            results.forEach((res, idx) => {
                const comp = components[idx];
                if (res.err) {
                    failures.push({ comp, url: res.url, error: res.err.message || String(res.err) });
                    return;
                }
                const parsed = parseTwoCols(res.txt);
                if (parsed.x.length === 0) {
                    failures.push({ comp, url: res.url, error: 'empty or unparsable' });
                    return;
                }
                const yText = parsed.y.map(formatValue);
                traces.push({
                    x: parsed.x,
                    y: parsed.y,
                    text: yText,
                    type: 'scatter',
                    mode: 'lines',
                    name: makeLabel(comp),
                    hovertemplate: `Energy: %{x} eV<br>D: %{text} s^-1<extra>${makeLabel(comp)}</extra>`,
                    line: { width: 1.5 }
                });
            });

            // 控制面板 + 内部绘图容器（与 SC 保持一致风格）
            const controlPanelHtml = `
                <div class="sc-control-panel">
                    <div class="sc-control-tip">
                        <i class="fas fa-info-circle"></i> <span class="control-tip-text">Single-click to toggle curves, double-click to isolate (hide all others).</span>
                    </div>
                    <div class="sc-control-item">
                        <button id="dwResetBtn" class="button-tool-small">Reset Chart</button>
                    </div>
                    <div class="sc-control-status">
                        <span class="visible-count-text">Visible: <span id="dwVisibleCount">${traces.length}</span>/${traces.length} curves</span>
                    </div>
                </div>
            `;
            container.innerHTML = controlPanelHtml + '<div id="dw-plot" style="width:100%;"></div>';
            const plotElement = document.getElementById('dw-plot');
            // 明确设置绘图容器尺寸，避免因父容器未定高导致 0 高度
            try {
                const size = getPlotSize();
                if (plotElement && size) {
                    plotElement.style.height = size.height + 'px';
                    plotElement.style.width = size.width + 'px';
                }
            } catch (_) {}

            // 色板与 hover 样式
            const colors = [
                '#FF3333', '#0066FF', '#33CC33', '#9900CC', '#FF9900',
                '#00CCCC', '#FF3399', '#3366FF', '#99CC00', '#FF6600',
                '#8B0000', '#006400', '#00008B', '#8B008B', '#FF4500',
                '#2F4F4F', '#696969', '#556B2F', '#800000', '#191970',
                '#20B2AA', '#9370DB', '#00CED1', '#FF1493', '#00FF7F',
                '#4682B4', '#DAA520'
            ];
            traces.forEach((t, i) => {
                t.line = t.line || {};
                t.line.width = 2.5;
                t.line.color = colors[i % colors.length];
                t.hoverlabel = {
                    bgcolor: '#f8fafc',
                    bordercolor: t.line.color,
                    font: { size: 14, family: 'Arial, sans-serif' }
                };
            });

            // 尺寸计算
            function getPlotSize() {
                const parent = container;
                const controlPanel = parent.querySelector('.sc-control-panel');
                const tip = parent.querySelector('.sc-example-tip');
                let availableHeight = parent.getBoundingClientRect().height;
                if (controlPanel) availableHeight -= controlPanel.getBoundingClientRect().height;
                if (tip) availableHeight -= tip.getBoundingClientRect().height;
                if (availableHeight < 300) availableHeight = 300;
                let availableWidth = parent.getBoundingClientRect().width;
                if (availableWidth < 300) availableWidth = 300;
                return { height: availableHeight, width: availableWidth };
            }

            // layout/config 与 SC 对齐
            const plotSize = getPlotSize();
            const layout = {
                title: { text: 'Drude Weight', font: { family: 'system-ui, -apple-system, sans-serif', size: 20 }, y: 0.97, x: 0.5, xanchor: 'center', yanchor: 'top' },
                xaxis: { title: { text: 'Energy (eV)', font: { size: 16, family: 'Arial, sans-serif', color: '#1f2937' } },
                         showgrid: true, gridcolor: '#e5e7eb', gridwidth: 1, zeroline: true, zerolinecolor: '#6b7280', zerolinewidth: 1.5,
                         showline: true, linecolor: '#374151', linewidth: 2, tickfont: { size: 12, family: 'Arial, sans-serif', color: '#4b5563' }, mirror: true },
                yaxis: { title: { text: 'D (s^-1)', font: { size: 16, family: 'Arial, sans-serif', color: '#1f2937' } },
                         showgrid: true, gridcolor: '#e5e7eb', gridwidth: 1, zeroline: true, zerolinecolor: '#6b7280', zerolinewidth: 1.5,
                         showline: true, linecolor: '#374151', linewidth: 2, tickfont: { size: 12, family: 'Arial, sans-serif', color: '#4b5563' }, mirror: 'ticks' },
                hovermode: 'closest',
                legend: { orientation: 'h', xanchor: 'center', x: 0.5, yanchor: 'top', y: -0.25, font: { size: 14, family: 'Arial, sans-serif' }, tracegroupgap: 8,
                          bgcolor: '#ffffff', bordercolor: '#e2e8f0', borderwidth: 1, itemsizing: 'constant', itemwidth: 40 },
                margin: { t: 50, r: 30, b: 120, l: 80 },
                autosize: false, height: plotSize.height, width: plotSize.width,
                paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff',
                shapes: [{ type: 'rect', xref: 'paper', yref: 'paper', x0: 0, y0: 0, x1: 1, y1: 1, line: { width: 2, color: '#374151' }, fillcolor: 'rgba(0,0,0,0)' }]
            };
            const config = { responsive: true, displayModeBar: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                             toImageButtonOptions: { format: 'png', filename: 'dw_structure', height: 800, width: 1200, scale: 2 } };

            if (traces.length > 0 && window.Plotly) {
                Plotly.newPlot(plotElement, traces, layout, config)
                  .catch(err => { console.error('DW 绘制失败:', err); });

                // 状态管理与交互
                const curveVisibility = new Array(traces.length).fill(true);
                let lastClickTime = 0;
                let lastClickCurve = -1;
                const DOUBLE_CLICK_THRESHOLD = 400;

                function updateVisibleCount() {
                    let visible = 0;
                    try {
                        const plotData = plotElement.data;
                        if (plotData && Array.isArray(plotData)) {
                            visible = plotData.filter(t => t.visible !== false && t.visible !== 'legendonly').length;
                        }
                    } catch (_) {
                        visible = curveVisibility.filter(v => v).length;
                    }
                    const el = document.getElementById('dwVisibleCount');
                    if (el) el.textContent = visible;
                    return visible;
                }

                function applyCurveVisibility() {
                    const visibilityUpdate = curveVisibility.map(v => v ? true : 'legendonly');
                    Plotly.restyle(plotElement, { visible: visibilityUpdate });
                    setTimeout(updateVisibleCount, 100);
                }

                function showNotification(html) {
                    const notification = document.createElement('div');
                    notification.className = 'sc-notification';
                    notification.innerHTML = html;
                    const panel = container.querySelector('.sc-control-panel');
                    if (panel) panel.appendChild(notification);
                    setTimeout(() => { notification.style.opacity = '0'; setTimeout(() => notification.remove(), 500); }, 1500);
                }

                function handleSingleClick(curveIndex) {
                    curveVisibility[curveIndex] = !curveVisibility[curveIndex];
                    applyCurveVisibility();
                }

                function handleDoubleClick(curveIndex) {
                    curveVisibility.fill(false);
                    curveVisibility[curveIndex] = true;
                    applyCurveVisibility();
                }

                // 图例点击：单击切换，双击隔离
                plotElement.on('plotly_legendclick', function(data) {
                    if (data && data.curveNumber !== undefined) {
                        const curveIndex = data.curveNumber;
                        const now = Date.now();
                        const isDouble = (curveIndex === lastClickCurve) && (now - lastClickTime < DOUBLE_CLICK_THRESHOLD);
                        if (isDouble) {
                            handleDoubleClick(curveIndex);
                        } else {
                            handleSingleClick(curveIndex);
                            const items = container.querySelectorAll('.traces');
                            if (items && items.length > curveIndex) {
                                items[curveIndex].classList.add('active');
                                setTimeout(() => items[curveIndex].classList.remove('active'), 300);
                            }
                        }
                        lastClickTime = now;
                        lastClickCurve = curveIndex;
                        return false;
                    }
                });

                // 初始化可见计数与 relayout 监听
                setTimeout(updateVisibleCount, 200);
                plotElement.on('plotly_relayout', () => setTimeout(updateVisibleCount, 50));

                // Reset 按钮
                const resetBtn = document.getElementById('dwResetBtn');
                if (resetBtn) {
                    resetBtn.addEventListener('click', function() {
                        curveVisibility.fill(true);
                        applyCurveVisibility();
                        this.classList.add('active');
                        setTimeout(() => this.classList.remove('active'), 200);
                        showNotification(`<i class=\"fas fa-refresh\"></i> All ${traces.length} curves are now visible`);
                    });
                }

                // 增强 legend 外观
                setTimeout(() => {
                    const legendLines = document.querySelectorAll('.legendlines path');
                    legendLines.forEach(line => {
                        line.setAttribute('stroke-width', '4');
                        const d = line.getAttribute('d');
                        if (d) line.setAttribute('d', d.replace(/5\.0/g, '15.0'));
                    });
                    const legendItems = document.querySelectorAll('.legendtext');
                    legendItems.forEach(item => {
                        item.setAttribute('data-tooltip', 'Click: toggle | Double-click: isolate');
                        item.setAttribute('title', 'Click: toggle | Double-click: isolate');
                    });
                }, 300);

                // 尺寸自适应
                function handleResize() {
                    const size = getPlotSize();
                    Plotly.relayout(plotElement, { height: size.height, width: size.width, autosize: false });
                }
                window.addEventListener('resize', handleResize);

            } else {
                container.innerHTML = '<div class="error">未能加载任何 DW 分量曲线</div>';
            }

            // 缺失分量提示
            if (failures.length) {
                console.warn('DW 加载失败项:', failures);
                const notice = document.getElementById('dwNotice');
                if (notice) {
                    const list = failures.map(f => `D_${f.comp}.dat`).join('，');
                    notice.textContent = `缺失或解析失败的分量：${list}`;
                    notice.style.display = '';
                }
            }
        }).catch(err => {
            console.error('DW 绘制异常:', err);
            container.innerHTML = '<div class="error">DW 数据加载异常</div>';
        });

        if (matrixFileUrl) {
            fetchText(matrixFileUrl).then(text => {
                const mat = parseMatrixFromText(text);
                if (!mat) {
                    console.warn('DW 矩阵解析失败');
                    return;
                }
                renderMatrix('dwEigenMatrix', mat, 's^-1');
                // 已移除复制矩阵按钮逻辑
            }).catch(err => {
                console.warn('读取 DW 矩阵失败:', err);
            });
        }

        window.addEventListener('resize', () => {
            if (window.Plotly && container && container.data) {
                Plotly.Plots.resize(container);
            }
        });
    }

    window.plotDW = plotDW;
})();
