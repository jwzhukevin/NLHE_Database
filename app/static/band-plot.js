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
    try {
        // 加载Plotly
        await loadPlotly();
        
        // 解析数据
        const { kpoints, bands, kLabels, kPositions } = await parseBandData(bandDataPath);
        
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
                text: 'Band Structure',
                font: {
                    family: 'Times New Roman',
                    size: 24
                }
            },
            // 设置图表尺寸
            width: 800,  // 恢复原始宽度
            height: 400, // 恢复原始高度
            xaxis: {
                title: {
                    text: 'High Symmetry Path',
                    font: {
                        family: 'Times New Roman',
                        size: 20
                    }
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
                ticks: 'outside',
                showticknumber: false,
                tickfont: {
                    family: 'Times New Roman',
                    size: 16
                }
            },
            yaxis: {
                title: {
                    text: 'Energy (eV)',
                    font: {
                        family: 'Times New Roman',
                        size: 20
                    }
                },
                showgrid: true,
                gridwidth: 1,
                gridcolor: '#E5E5E5',
                zeroline: false,
                showline: true,
                linewidth: 1.5,
                linecolor: 'black',
                mirror: true,
                ticks: 'outside',
                tickfont: {
                    family: 'Times New Roman',
                    size: 16
                }
            },
            showlegend: false,
            hovermode: 'closest',
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            // 调整边距，优化显示空间
            margin: {l: 60, r: 30, t: 50, b: 50},
            font: {
                family: 'Times New Roman'
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
                height: 700,
                width: 900,
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
        
    } catch (error) {
        console.error('Error plotting band structure:', error);
        throw error;
    }
}