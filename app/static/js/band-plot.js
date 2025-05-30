/**
 * band-plot.js
 * 能带图绘制函数 - 用于绘制能带图
 * 使用plotly.js实现学术风格图表
 */
// 加载plotly.js库
function loadPlotly() {
    return new Promise((resolve, reject) => {
        if (window.Plotly) {
            resolve(window.Plotly);
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://cdn.plot.ly/plotly-2.24.1.min.js';
        script.onload = () => resolve(window.Plotly);
        script.onerror = () => reject(new Error('Failed to load Plotly'));
        document.head.appendChild(script);
    });
}

// 解析能带数据文件
async function parseBandData(filePath) {
    try {
        const response = await fetch(filePath);
        const text = await response.text();
        const lines = text.trim().split('\n');
        
        // 解析高对称点信息
        const kLabels = lines[0].trim().split(/\s+/);  // 第一行：高对称点标签
        const kPositions = lines[1].trim().split(/\s+/).map(Number);  // 第二行：高对称点位置
        
        // 初始化数据数组
        const kpoints = [];
        const bands = [];
        
        // 获取能带数量（数据行的列数减1，因为第一列是k点）
        const numBands = lines[2].trim().split(/\s+/).length - 1;
        for (let i = 0; i < numBands; i++) {
            bands.push([]);
        }
        
        // 解析能带数据（从第三行开始）
        for (let i = 2; i < lines.length; i++) {
            const values = lines[i].trim().split(/\s+/).map(Number);
            kpoints.push(values[0]);
            for (let j = 0; j < numBands; j++) {
                bands[j].push(values[j + 1]);
            }
        }
        
        return { kpoints, bands, kLabels, kPositions };
    } catch (error) {
        console.error('Error parsing band data:', error);
        throw error;
    }
}

// 绘制能带图
async function plotBandStructure(containerId, bandDataPath) {
    let isExample = false;
    let exampleBandPath = '/static/materials/example_band.dat';
    let bandData = null;
    let errorMsg = '';
    try {
        await loadPlotly();
        try {
            bandData = await parseBandData(bandDataPath);
        } catch (error) {
            errorMsg = 'No data';
        }
        if (!bandData ||
            !bandData.kpoints || bandData.kpoints.length === 0 ||
            !bandData.bands || bandData.bands.length === 0 ||
            !bandData.kLabels || bandData.kLabels.length === 0 ||
            !bandData.kPositions || bandData.kPositions.length === 0
        ) {
            // 显示无数据提示
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = `<div style=\"padding: 48px 16px; text-align: center; background: linear-gradient(90deg,#fff,#f3f4f6 60%,#fff); border-radius: 12px; margin: 24px 0; box-shadow:0 2px 8px #e5e7eb;\">
                    <div style=\"font-size: 2rem; font-weight: bold; color: #dc2626; margin-bottom: 12px; letter-spacing:1px;\">Band structure data not found</div>
                    <div style=\"font-size: 1rem; color: #666; max-width: 480px; margin: 0 auto; line-height: 1.7;\">
                        Sorry, the band structure data for this material is currently unavailable.<br>
                        This may be due to missing or incorrectly formatted data files.<br>
                        Our development team is actively working to improve this feature.<br>
                        If you have any questions or suggestions, please contact us via <a href='mailto:your_email@example.com' style='color:#2563eb;text-decoration:underline;'>email</a> or submit a <a href='https://github.com/yourrepo/issues' target='_blank' style='color:#2563eb;text-decoration:underline;'>GitHub Issue</a>.
                    </div>
                </div>`;
            }
            return;
        }
        const { kpoints, bands, kLabels, kPositions } = bandData;
        
        // 准备绘图数据
        const traces = [];
        
        // 添加能带曲线
        bands.forEach((bandEnergies, index) => {
            traces.push({
                x: kpoints,
                y: bandEnergies,
                mode: 'lines',
                name: `Band ${index + 1}`,
                line: { width: 2.5 },  // 增加线宽使能带曲线更明显
                hoverinfo: 'y',        // 添加悬停信息显示能量值
                showlegend: false
            });
        });
        
        // 添加费米能级虚线（E = 0）
        traces.push({
            x: [Math.min(...kpoints), Math.max(...kpoints)],
            y: [0, 0],
            mode: 'lines',
            name: 'Fermi Level',
            line: {
                color: 'black',
                width: 1.5,  // 增加线宽使费米能级更明显
                dash: 'dash'
            },
            showlegend: false
        });
        
        // 添加高对称点垂直虚线
        kPositions.forEach((pos, index) => {
            traces.push({
                x: [pos, pos],
                y: [Math.min(...bands.flat()), Math.max(...bands.flat())],
                mode: 'lines',
                name: `${kLabels[index]} line`,
                line: {
                    color: 'gray',
                    width: 1,
                    dash: 'dash'
                },
                showlegend: false
            });
        });
        
        // 绘图布局
        const layout = {
            title: {
                text: isExample ? 'Band Structure (Example)' : 'Band Structure',
                font: {
                    family: 'system-ui, -apple-system, sans-serif',
                    size: 20
                },
                y: 0.97,
                x: 0.5,
                xanchor: 'center',
                yanchor: 'top'
            },
            // 设置图表尺寸
            autosize: true,  // 启用自动尺寸调整
            // 移除固定高度以实现完全自适应
            xaxis: {
                title: {
                    text: 'High Symmetry Path',
                    font: {
                        family: 'system-ui, -apple-system, sans-serif',
                        size: 16,
                    },
                    standoff: 15, // 增加标题与坐标轴的距离
                    x: 0.5,      // 标题水平居中对齐
                    xanchor: 'center', // 锚点居中对齐
                    y: -0.15,    // 向下移动标题
                    yanchor: 'middle', // 垂直居中对齐
                },
                showgrid: false,
                zeroline: false,
                ticktext: kLabels,
                tickvals: kPositions,
                tickmode: 'array',
                showticklabels: true,
                showline: true,
                linewidth: 1.5,
                linecolor: 'black',
                mirror: true,
                tickformat: '',
                ticks: 'inside',
                showticknumber: false,
                tickfont: {
                    family: 'system-ui, -apple-system, sans-serif',
                    size: 14
                }
            },
            yaxis: {
                title: {
                    text: 'Energy (eV)',
                    font: {
                        family: 'system-ui, -apple-system, sans-serif',
                        size: 16
                    },
                    standoff: 0, // 增加标题与坐标轴的距离
                },
                showgrid: true,
                gridwidth: 1,
                gridcolor: '#E5E5E5',
                zeroline: false,
                showline: true,
                linewidth: 1.5,
                linecolor: 'black',
                mirror: true,
                ticks: 'inside',
                tickfont: {
                    family: 'system-ui, -apple-system, sans-serif',
                    size: 14
                }
            },
            showlegend: false,
            hovermode: 'closest',
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            // 调整边距，确保在小尺寸下也能正常显示
            margin: {l: 70, r: 30, t: 50, b: 90},
            font: {
                family: 'system-ui, -apple-system, sans-serif'
            }
        };
        
        // 绘图配置
        const config = {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            toImageButtonOptions: {
                format: 'png',  // 导出图像格式
                filename: 'band_structure',
                scale: 2       // 提高导出图像质量
            },
            modeBarButtonsToAdd: [
                'drawline',
                'drawopenpath',
                'eraseshape'   // 添加绘图工具
            ]
        };
        
        // 创建图表
        await Plotly.newPlot(containerId, traces, layout, config);
        
        // 添加窗口大小调整监听器，以确保图表自适应容器大小
        const resizeGraph = () => {
            Plotly.relayout(containerId, {
                autosize: true
            });
        };
        
        // 确保图表在窗口大小变化时保持自适应
        window.addEventListener('resize', resizeGraph);
        
        // 清理函数，当组件卸载时移除事件监听器
        const container = document.getElementById(containerId);
        if (container) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.removedNodes.contains(container)) {
                        window.removeEventListener('resize', resizeGraph);
                        observer.disconnect();
                    }
                });
            });
            
            observer.observe(container.parentNode, { childList: true });
        }
        
        // 插入英文红色提示（只插入一次）
        if (isExample && container && !container.parentNode.querySelector('.band-example-tip')) {
            let tip = document.createElement('div');
            tip.className = 'band-example-tip';
            tip.style = 'color:#b91c1c;font-size:16px;text-align:center;margin-bottom:8px;';
            tip.innerText = 'Example band structure is shown. Original data file not found.';
            container.parentNode.insertBefore(tip, container);
        }
        
    } catch (error) {
        console.error('Error plotting band structure:', error);
        // 显示错误信息在容器中
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `<div style="color: #666; padding: 50px; text-align: center; font-size: 18px; background: #f9f9f9; border-radius: 8px; margin: 20px 0;">
                <p>No data</p>
            </div>`;
        }
    }
}