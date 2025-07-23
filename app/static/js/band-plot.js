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
        console.log('正在获取能带数据文件:', filePath);
        const response = await fetch(filePath);

        // 检查HTTP响应状态
        if (!response.ok) {
            console.error(`HTTP错误: ${response.status} ${response.statusText} - ${filePath}`);
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const text = await response.text();
        console.log('文件内容长度:', text.length, '字符');

        const lines = text.trim().split('\n');
        console.log('文件行数:', lines.length);
        
        // 检查文件格式
        if (lines.length < 3) {
            console.error('文件格式错误: 至少需要3行数据');
            throw new Error(`文件格式错误: 只有${lines.length}行，至少需要3行`);
        }

        // 解析高对称点信息
        const kLabels = lines[0].trim().split(/\s+/);  // 第一行：高对称点标签
        const kPositions = lines[1].trim().split(/\s+/).map(Number);  // 第二行：高对称点位置

        console.log('高对称点标签:', kLabels);
        console.log('高对称点位置:', kPositions);

        // 初始化数据数组
        const kpoints = [];
        const bands = [];

        // 获取能带数量（数据行的列数减1，因为第一列是k点）
        const firstDataLine = lines[2].trim().split(/\s+/);
        const numBands = firstDataLine.length - 1;
        console.log('检测到能带数量:', numBands);

        if (numBands <= 0) {
            console.error('数据格式错误: 没有检测到能带数据');
            throw new Error('数据格式错误: 没有检测到能带数据');
        }

        for (let i = 0; i < numBands; i++) {
            bands.push([]);
        }
        
        // 解析能带数据（从第三行开始）
        let validDataLines = 0;
        for (let i = 2; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue; // 跳过空行

            try {
                const values = line.split(/\s+/).map(Number);

                // 检查数据完整性
                if (values.length < numBands + 1) {
                    console.warn(`第${i+1}行数据不完整: 期望${numBands + 1}个值，实际${values.length}个`);
                    continue;
                }

                // 检查是否有NaN值
                if (values.some(isNaN)) {
                    console.warn(`第${i+1}行包含无效数值:`, line);
                    continue;
                }

                kpoints.push(values[0]);
                for (let j = 0; j < numBands; j++) {
                    bands[j].push(values[j + 1]);
                }
                validDataLines++;

            } catch (error) {
                console.warn(`第${i+1}行解析失败:`, error.message);
                continue;
            }
        }

        console.log(`成功解析${validDataLines}行数据，${kpoints.length}个k点`);

        // 检查解析结果
        if (kpoints.length === 0) {
            throw new Error('没有有效的k点数据');
        }

        if (bands.length === 0 || bands[0].length === 0) {
            throw new Error('没有有效的能带数据');
        }

        // 分析能带特性
        const bandAnalysis = analyzeBandStructure(bands);
        console.log('能带分析结果:', bandAnalysis);

        return { kpoints, bands, kLabels, kPositions, bandAnalysis };
    } catch (error) {
        console.error('Error parsing band data:', error);
        throw error;
    }
}

// 分析能带结构特性
function analyzeBandStructure(bands) {
    if (!bands || bands.length === 0) {
        return null;
    }

    // 找到所有能量值
    const allEnergies = bands.flat();

    // 找到费米能级附近的能带（假设费米能级为0）
    const fermiLevel = 0;
    const tolerance = 0.1; // 容差值，用于判断能带是否跨越费米能级

    // 分离价带和导带
    const valenceBands = [];
    const conductionBands = [];

    bands.forEach((band, bandIndex) => {
        const maxEnergy = Math.max(...band);
        const minEnergy = Math.min(...band);

        if (maxEnergy < fermiLevel - tolerance) {
            // 完全在费米能级以下的能带 - 价带
            valenceBands.push({ index: bandIndex, energies: band });
        } else if (minEnergy > fermiLevel + tolerance) {
            // 完全在费米能级以上的能带 - 导带
            conductionBands.push({ index: bandIndex, energies: band });
        }
        // 跨越费米能级的能带可能表示金属性
    });

    // 计算带隙
    let bandGap = null;
    let vbmEnergy = null;
    let cbmEnergy = null;
    let vbmCoordinates = "Not available";
    let cbmCoordinates = "Not available";
    let materialType = "Unknown";

    if (valenceBands.length > 0 && conductionBands.length > 0) {
        // 找到价带顶 (VBM - Valence Band Maximum)
        let vbmValue = -Infinity;
        let vbmBandIndex = -1;
        let vbmKIndex = -1;

        valenceBands.forEach(band => {
            band.energies.forEach((energy, kIndex) => {
                if (energy > vbmValue) {
                    vbmValue = energy;
                    vbmBandIndex = band.index;
                    vbmKIndex = kIndex;
                }
            });
        });

        // 找到导带底 (CBM - Conduction Band Minimum)
        let cbmValue = Infinity;
        let cbmBandIndex = -1;
        let cbmKIndex = -1;

        conductionBands.forEach(band => {
            band.energies.forEach((energy, kIndex) => {
                if (energy < cbmValue) {
                    cbmValue = energy;
                    cbmBandIndex = band.index;
                    cbmKIndex = kIndex;
                }
            });
        });

        vbmEnergy = vbmValue;
        cbmEnergy = cbmValue;
        bandGap = cbmValue - vbmValue;

        // 简化的坐标表示（使用k点索引）
        vbmCoordinates = `k-point ${vbmKIndex}`;
        cbmCoordinates = `k-point ${cbmKIndex}`;

        // 判断材料类型
        if (bandGap > 3.0) {
            materialType = "Insulator";
        } else if (bandGap > 0.1) {
            materialType = "Semiconductor";
        } else {
            materialType = "Metal";
        }
    } else {
        // 没有明显的价带导带分离，可能是金属
        materialType = "Metal";
        bandGap = 0;
    }

    return {
        bandGap: bandGap,
        vbmEnergy: vbmEnergy,
        cbmEnergy: cbmEnergy,
        vbmCoordinates: vbmCoordinates,
        cbmCoordinates: cbmCoordinates,
        materialType: materialType,
        valenceBandCount: valenceBands.length,
        conductionBandCount: conductionBands.length
    };
}

// 绘制能带图
async function plotBandStructure(containerId, bandDataPath) {
    let isExample = false;
    let bandData = null;

    console.log('开始绘制能带图，容器ID:', containerId, '数据路径:', bandDataPath);

    try {
        await loadPlotly();
        console.log('Plotly库加载成功');

        try {
            bandData = await parseBandData(bandDataPath);
            console.log('能带数据解析成功');
        } catch (error) {
            console.error('能带数据解析失败:', error);
            throw error;
        }

        // 详细验证数据完整性
        const validationErrors = [];

        if (!bandData) {
            validationErrors.push('bandData为空');
        } else {
            if (!bandData.kpoints || bandData.kpoints.length === 0) {
                validationErrors.push('k点数据缺失或为空');
            }
            if (!bandData.bands || bandData.bands.length === 0) {
                validationErrors.push('能带数据缺失或为空');
            }
            if (!bandData.kLabels || bandData.kLabels.length === 0) {
                validationErrors.push('高对称点标签缺失或为空');
            }
            if (!bandData.kPositions || bandData.kPositions.length === 0) {
                validationErrors.push('高对称点位置缺失或为空');
            }
        }

        if (validationErrors.length > 0) {
            console.error('数据验证失败:', validationErrors);
            throw new Error('数据验证失败: ' + validationErrors.join(', '));
        }

        // 数据验证通过，开始绘图
        console.log('数据验证通过，开始绘制能带图');
        const { kpoints, bands, kLabels, kPositions, bandAnalysis } = bandData;
        
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

        // 更新页面上的能带信息
        if (bandAnalysis) {
            updateBandStructureInfo(bandAnalysis);
        }

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
        console.error('绘制能带图时发生错误:', error);

        // 显示详细的错误信息在容器中
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `<div style="
                min-height: 220px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                background: linear-gradient(90deg,#fff,#f3f4f6 60%,#fff);
                border-radius: 12px;
                margin: 24px 0;
                box-shadow:0 2px 8px #e5e7eb;">
                <div style="font-size: 2rem; font-weight: bold; color: #dc2626; margin-bottom: 12px; letter-spacing:1px;">Band structure data not found</div>
                <div style="font-size: 1rem; color: #666; max-width: 480px; margin: 0 auto; line-height: 1.7; text-align: center;">
                    Sorry, the band structure data for this material is currently unavailable.<br>
                    Error: ${error.message}<br>
                    This may be due to missing or incorrectly formatted data files.<br>
                    Please check the browser console for more details.
                </div>
            </div>`;
        }
    }
}

// 更新页面上的能带结构信息
function updateBandStructureInfo(bandAnalysis) {
    try {
        console.log('Updating band structure info:', bandAnalysis);

        // 更新带隙信息
        const bandGapElement = document.querySelector('#band-gap .property-value');
        if (bandGapElement) {
            if (bandAnalysis.bandGap !== null && bandAnalysis.bandGap !== undefined) {
                const newValue = `${bandAnalysis.bandGap.toFixed(4)} eV`;
                const oldValue = bandGapElement.textContent;

                // 只有当值发生变化时才更新并添加视觉反馈
                if (oldValue !== newValue) {
                    bandGapElement.textContent = newValue;

                    // 添加更新动画效果
                    bandGapElement.style.backgroundColor = '#e8f5e8';
                    bandGapElement.style.transition = 'background-color 0.5s';

                    setTimeout(() => {
                        bandGapElement.style.backgroundColor = '';
                    }, 2000);

                    console.log(`Band Gap updated from "${oldValue}" to "${newValue}"`);
                }
            } else {
                bandGapElement.textContent = 'N/A';
            }
        }

        // 更新VBM能量
        const vbmEnergyElement = document.querySelector('#vbm-energy .property-value');
        if (vbmEnergyElement) {
            if (bandAnalysis.vbmEnergy !== null && bandAnalysis.vbmEnergy !== undefined) {
                vbmEnergyElement.textContent = `${bandAnalysis.vbmEnergy.toFixed(4)} eV`;
            } else {
                vbmEnergyElement.textContent = 'N/A';
            }
        }

        // 更新CBM能量
        const cbmEnergyElement = document.querySelector('#cbm-energy .property-value');
        if (cbmEnergyElement) {
            if (bandAnalysis.cbmEnergy !== null && bandAnalysis.cbmEnergy !== undefined) {
                cbmEnergyElement.textContent = `${bandAnalysis.cbmEnergy.toFixed(4)} eV`;
            } else {
                cbmEnergyElement.textContent = 'N/A';
            }
        }

        // 更新VBM坐标
        const vbmCoordElement = document.querySelector('#vbm-coordinates .property-value');
        if (vbmCoordElement) {
            vbmCoordElement.textContent = bandAnalysis.vbmCoordinates || 'Not available';
        }

        // 更新CBM坐标
        const cbmCoordElement = document.querySelector('#cbm-coordinates .property-value');
        if (cbmCoordElement) {
            cbmCoordElement.textContent = bandAnalysis.cbmCoordinates || 'Not available';
        }

        // 更新材料类型（Materials Type字段）
        const materialTypeElement = document.querySelector('#material-type .property-value');
        if (materialTypeElement) {
            materialTypeElement.textContent = bandAnalysis.materialType || 'Unknown';
        }

        // 尝试更新数据库中的metal_type字段
        if (bandAnalysis.materialType) {
            updateMaterialTypeInDatabase(bandAnalysis.materialType);
        }

        // 获取Max SC数据
        const maxSCData = getMaxSCFromDatabase();

        // 保存Band Gap到数据库
        saveBandGapToDatabase(getMaterialIdFromUrl(), bandAnalysis.bandGap);

        // 触发全局事件，通知其他页面数据已更新
        window.dispatchEvent(new CustomEvent('materialDataUpdated', {
            detail: {
                materialId: getMaterialIdFromUrl(),
                bandGap: bandAnalysis.bandGap,
                maxSC: maxSCData
            }
        }));

        console.log('Band structure info updated successfully');

    } catch (error) {
        console.error('Error updating band structure info:', error);
    }
}

// 获取当前页面的材料ID
function getMaterialIdFromUrl() {
    const materialIdMatch = window.location.pathname.match(/\/materials\/(\d+)/);
    return materialIdMatch ? materialIdMatch[1] : null;
}

// 从页面获取Max SC数据
function getMaxSCFromDatabase() {
    try {
        // 从Shift Current Properties卡片中读取Max SC值
        const maxSCElements = document.querySelectorAll('#shift-current-properties .property-value');
        for (let element of maxSCElements) {
            const text = element.textContent.trim();
            if (text.includes('μA/V²')) {
                // 提取数值部分
                const match = text.match(/([\d.]+)\s*μA\/V²/);
                if (match) {
                    return parseFloat(match[1]);
                }
            }
        }

        // 如果没有找到，尝试从模板变量中获取（如果页面刚加载）
        const materialData = window.materialData;
        if (materialData && materialData.max_sc !== undefined && materialData.max_sc !== null) {
            return materialData.max_sc;
        }

        return null;
    } catch (error) {
        console.error('Error getting Max SC data:', error);
        return null;
    }
}

// 更新数据库中的材料类型
function updateMaterialTypeInDatabase(materialType) {
    try {
        // 获取材料ID
        const materialId = getMaterialIdFromUrl();
        if (!materialId) {
            console.log('Could not extract material ID from URL');
            return;
        }

        // 发送更新请求到后端
        fetch(`/api/materials/${materialId}/update-metal-type`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                metal_type: materialType.toLowerCase()
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Material type updated in database:', materialType);

                // 保存更新信息到localStorage，以便index页面使用
                const maxSC = getMaxSCFromDatabase();
                saveMaterialDataUpdate(materialId, bandAnalysis.bandGap, maxSC);

            } else {
                console.log('Failed to update material type in database:', data.error);
            }
        })
        .catch(error => {
            console.log('Error updating material type in database:', error);
        });

    } catch (error) {
        console.error('Error in updateMaterialTypeInDatabase:', error);
    }
}

// 保存材料数据更新信息到localStorage
function saveMaterialDataUpdate(materialId, bandGap, maxSC) {
    try {
        // 获取现有的更新记录
        let updatedData = localStorage.getItem('updatedMaterialData');
        let updates = updatedData ? JSON.parse(updatedData) : [];

        // 检查是否已经有该材料的更新记录
        const existingIndex = updates.findIndex(update => update.materialId === materialId);

        const updateInfo = {
            materialId: materialId,
            bandGap: bandGap,
            maxSC: maxSC,
            timestamp: new Date().toISOString()
        };

        if (existingIndex >= 0) {
            // 更新现有记录
            updates[existingIndex] = updateInfo;
        } else {
            // 添加新记录
            updates.push(updateInfo);
        }

        // 保存到localStorage
        localStorage.setItem('updatedMaterialData', JSON.stringify(updates));

        console.log('Material data update saved to localStorage:', updateInfo);

    } catch (error) {
        console.error('Error saving material data update:', error);
    }
}

// 保存Band Gap到数据库
function saveBandGapToDatabase(materialId, bandGap) {
    if (bandGap === null || bandGap === undefined) {
        console.log('Band Gap is null, skipping database update');
        return;
    }

    try {
        fetch('/api/materials/update-band-gap', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                material_id: materialId,
                band_gap: bandGap
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Band Gap ${bandGap.toFixed(4)} eV saved to database for material ${materialId}`);
            } else {
                console.error('Failed to save Band Gap to database:', data.error);
            }
        })
        .catch(error => {
            console.error('Error saving Band Gap to database:', error);
        });
    } catch (error) {
        console.error('Error in saveBandGapToDatabase:', error);
    }
}