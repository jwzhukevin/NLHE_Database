/**
 * 材料详情页面的JavaScript逻辑
 * 负责处理3D晶体结构查看器、能带图、SC图等功能
 * 
 * 作用：
 * 1. 初始化页面各种组件（3D查看器、图表等）
 * 2. 处理页面导航和滚动效果
 * 3. 管理卡片的折叠/展开功能
 * 4. 加载和显示晶体结构数据
 * 5. 处理原子坐标的显示切换
 */

// 全局变量：存储材料数据，从JSON script标签中读取
window.materialData = null;

/**
 * 从HTML页面的JSON script标签中读取材料数据
 * 这种方法避免了在JavaScript代码中使用模板语法，IDE不会报错
 * @returns {Object|null} 材料数据对象，如果读取失败则返回null
 */
function loadMaterialDataFromPage() {
    try {
        // 查找包含材料数据的JSON script标签
        const dataScript = document.getElementById('material-data');
        if (!dataScript) {
            console.error('未找到材料数据script标签');
            return null;
        }
        // 解析JSON数据
        const materialData = JSON.parse(dataScript.textContent);
        console.log('材料数据已从页面加载:', materialData);
        return materialData;
    } catch (error) {
        console.error('解析材料数据时出错:', error);
        return null;
    }
}

/**
 * 通用顶部 Tabs 组件
 * container_selector: 包含 .tab-header 与多个 .tab-content 的容器选择器
 * storage_key: localStorage 记忆当前激活 tab 的 key（可为空）
 */
function setup_tabs(container_selector, storage_key) {
    const root = document.querySelector(container_selector);
    if (!root) return;

    const btns = root.querySelectorAll('.tab-header [role="tab"]');
    const panels = root.querySelectorAll('.tab-content[role="tabpanel"], .tab-content');
    if (!btns.length || !panels.length) return;

    const tabByBtn = new Map();
    btns.forEach(btn => tabByBtn.set(btn, btn.getAttribute('data-tab')));

    const panelByKey = {};
    panels.forEach(p => {
        // 面板 id 形如 panel-xxx 或自定义，优先通过 data-tab 映射
        const labelled = p.getAttribute('aria-labelledby');
        if (labelled) {
            const btn = root.querySelector(`#${labelled}`);
            if (btn) {
                const key = btn.getAttribute('data-tab');
                if (key) panelByKey[key] = p;
            }
        }
    });

    function activate(key, remember) {
        btns.forEach(btn => {
            const k = tabByBtn.get(btn);
            const isActive = k === key;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
            btn.setAttribute('tabindex', isActive ? '0' : '-1');
        });

        Object.entries(panelByKey).forEach(([k, panel]) => {
            const isActive = k === key;
            if (isActive) {
                panel.classList.add('active');
                panel.removeAttribute('hidden');
            } else {
                panel.classList.remove('active');
                panel.setAttribute('hidden', '');
            }
        });

        // SC 情况：当前左侧绘图固定显示，但右侧面板切换可能影响整体宽度/滚动条，适当触发自适应
        if ((key === 'overview' || key === 'properties' || key === 'plot') && window.Plotly && document.getElementById('sc-plot')) {
            setTimeout(() => Plotly.relayout('sc-plot', { autosize: true }), 150);
        }

        if (remember && storage_key) {
            localStorage.setItem(storage_key, key);
        }
    }

    // 初始激活
    const saved = storage_key ? (localStorage.getItem(storage_key) || '') : '';
    const defaultKey = saved || (btns[0] && btns[0].getAttribute('data-tab')) || '';
    if (defaultKey) activate(defaultKey, false);

    // 事件绑定
    btns.forEach((btn, idx) => {
        btn.addEventListener('click', () => activate(tabByBtn.get(btn), true));
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                e.preventDefault();
                const next = (idx + (e.key === 'ArrowRight' ? 1 : -1) + btns.length) % btns.length;
                btns[next].focus();
            } else if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                activate(tabByBtn.get(btn), true);
            }
        });
    });
}

/**
 * 绑定 SC/Relations 标签切换后的行为
 * 1) 懒加载：首次激活 'shift-current' 时绘制 SC 图
 * 2) 自适应：切换/展开后对 SC 图进行重绘，避免隐藏容器导致的尺寸异常
 */
function setupSCTabBehavior() {
    // 获取右侧综合卡片容器
    const scPropsCombined = document.getElementById('sc-properties-combined');
    if (!scPropsCombined) return;

    const buttons = scPropsCombined.querySelectorAll('.tab-button');
    if (!buttons || buttons.length === 0) return;

    // 内部工具：当目标标签为 shift-current 时，执行绘制或重绘
    function ensureSCPlottedAndRelayout() {
        const scPlotEl = document.getElementById('sc-plot');
        // 首次绘制
        if (!window._scPlotted) {
            const container = document.getElementById('scStructure');
            if (container) {
                // 延迟少许，确保容器完成显示
                setTimeout(() => {
                    try {
                        if (typeof plotSCStructure === 'function') {
                            plotSCStructure('scStructure', window._scDataPath);
                            window._scPlotted = true;
                        }
                        // 绘制完成后自适应一次
                        if (window.Plotly && document.getElementById('sc-plot')) {
                            setTimeout(() => Plotly.relayout('sc-plot', { autosize: true }), 150);
                        }
                    } catch (e) {
                        console.error('绘制SC结构图失败:', e);
                    }
                }, 150);
            }
        } else if (window.Plotly && scPlotEl) {
            // 已绘制则重绘
            setTimeout(() => Plotly.relayout('sc-plot', { autosize: true }), 150);
        }
    }

    // 绑定事件：点击与键盘激活
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.getAttribute('data-tab');
            if (tab === 'shift-current') ensureSCPlottedAndRelayout();
        });
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                const tab = btn.getAttribute('data-tab');
                if (tab === 'shift-current') ensureSCPlottedAndRelayout();
            }
        });
    });

    // 页面初始：若默认即为 shift-current，则执行一次
    const saved = localStorage.getItem('scActiveTab') || 'element-relations';
    if (saved === 'shift-current') {
        ensureSCPlottedAndRelayout();
    }
}

// [Deprecated 20250822] 导出SC图为PNG功能已下线
// 原函数 exportSCToPNG 及 window.exportSCToPNG 已移除
// 原因：页面已无入口按钮，避免冗余代码与维护成本

// [Deprecated 20250822] 导出元素关系表为 CSV 的功能已下线
// 原函数 exportRelationsToCSV 与 window.exportRelationsToCSV 已移除
// 原因：模板中已移除入口按钮，避免冗余代码与维护成本

/**
 * 打印当前激活标签内容
 * 使用方式：onclick="printActiveTab()"
 */
function printActiveTab() {
    // 找到当前激活的 .tab-content.active，将其内容放入新窗口进行打印
    const active = document.querySelector('#sc-properties-combined .tab-content.active');
    if (!active) {
        console.warn('未找到激活的标签内容，无法打印');
        return;
    }

    const win = window.open('', '_blank');
    if (!win) {
        console.warn('浏览器阻止了弹窗，无法打印');
        return;
    }

    // 简单的打印文档，保留基础样式继承
    win.document.write(`<!DOCTYPE html><html><head><title>Print</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="stylesheet" href="/static/css/style.css" />
    </head><body>
        <div class="print-container">${active.innerHTML}</div>
    </body></html>`);
    win.document.close();
    // 等待内容渲染稳定后再调用打印
    win.onload = function() {
        win.focus();
        win.print();
        win.close();
    };
}
window.printActiveTab = printActiveTab;

/**
 * 页面加载完成后的初始化函数
 * 负责设置各种组件、加载数据和绑定事件监听器
 */
document.addEventListener('DOMContentLoaded', function() {
    // 从页面加载材料数据
    window.materialData = loadMaterialDataFromPage();
    if (!window.materialData) {
        console.error('材料数据加载失败，请检查HTML模板中的数据传递');
        return;
    }
    
    // 检查必要的库是否已加载
    console.log("检查库加载状态:");
    console.log("THREE:", typeof THREE !== 'undefined' ? "已加载" : "未加载");
    console.log("CrystalViewer:", typeof CrystalViewer !== 'undefined' ? "已加载" : "未加载");

    // 初始化3D晶体结构查看器
    // 'crystalViewer'是DOM容器ID，用于放置3D模型
    if (typeof CrystalViewer !== 'undefined') {
        CrystalViewer.init('crystalViewer');
        console.log("CrystalViewer初始化完成");
    } else {
        console.error("CrystalViewer未定义，无法初始化3D查看器");
    }
    // 注意：晶体结构数据的加载在loadCrystalStructureData()函数中进行
    
    // 初始化能带结构图
    // 使用从模板传递的完整路径，确保路径正确性
    const bandDataPath = window.materialData.band_data_path || `/static/materials/IMR-${window.materialData.id}/band/band.dat`;
    console.log('能带数据路径:', bandDataPath);
    // 调用绘图函数，传入容器ID和数据路径
    plotBandStructure('bandStructure', bandDataPath);

    // 初始化SC结构图（Shift Current）- 立即绘制
    window._scDataPath = window.materialData.sc_data_path || `/static/materials/IMR-${window.materialData.id}/sc/sc.dat`;
    console.log('SC数据路径:', window._scDataPath);
    try {
        if (typeof plotSCStructure === 'function') {
            plotSCStructure('scStructure', window._scDataPath);
            window._scPlotted = true;
            // 绘制后短延时自适应一次
            if (window.Plotly && document.getElementById('sc-plot')) {
                setTimeout(() => Plotly.relayout('sc-plot', { autosize: true }), 200);
            }
        }
    } catch (e) {
        console.error('绘制SC结构图失败:', e);
    }
    
    // 初始化卡片折叠功能（对“非 Tab 卡片”生效）
    initializeCollapsibleCards();
    
    // 获取所有导航链接
    const navLinks = document.querySelectorAll('.nav-property-link');
    const sections = document.querySelectorAll('.content-section');
    
    // 阻止下载按钮点击事件传播
    document.querySelectorAll('.download-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
    
    // 监听滚动事件，高亮当前所在的导航项
    window.addEventListener('scroll', function() {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            // 检查当前滚动位置是否在这个section范围内
            if (pageYOffset >= (sectionTop - 180)) {
                current = section.getAttribute('id');
            }
        });
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            const href = link.getAttribute('href');
            if (href && href.slice(1) === current) {
                link.classList.add('active');
            }
        });
    });
    
    // 为导航链接添加点击事件
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href && href.startsWith('#')) {
                e.preventDefault();
                const targetId = href.substring(1);
                const targetSection = document.getElementById(targetId);
                if (targetSection) {
                    window.scrollTo({
                        top: targetSection.offsetTop - 180, // 增加更大偏移量，确保标题完全可见
                        behavior: 'smooth'
                    });
                }
            }
        });
    });
    
    // 加载晶体结构数据
    loadCrystalStructureData();

    // 顶部 Tabs：接管 SC 卡片 tab 切换（记忆 key: scTabsActive）
    setup_tabs('#sc-card', 'scTabsActive');
});

/**
 * 初始化可折叠卡片功能
 * 为所有卡片头部添加点击事件，实现折叠/展开效果
 */
function initializeCollapsibleCards() {
    const cardHeaders = document.querySelectorAll('.card-header');
    
    cardHeaders.forEach(header => {
        // 若是“Tab 卡片”，即 header 后紧邻 .tab-header，则跳过折叠逻辑
        const next = header.nextElementSibling;
        if (next && next.classList.contains('tab-header')) {
            return;
        }
        // 绑定点击事件切换折叠状态
        header.addEventListener('click', function() {
            this.classList.toggle('collapsed');
            
            // 获取相邻的内容区域
            let content = this.nextElementSibling;
            
            // 处理3D结构查看器和能带图的特殊情况
            if (content.classList.contains('viewer-content')) {
                content.classList.toggle('collapsed');
                
                // 处理3D结构查看器的特殊情况
                if (!content.classList.contains('collapsed') && content.querySelector('#crystalViewer')) {
                    // 延迟一下，等待内容展开后再重新调整3D查看器
                    setTimeout(() => {
                        if (window.CrystalViewer && CrystalViewer.updateSize) {
                            CrystalViewer.updateSize();
                        }
                    }, 300);
                }
                
                // 处理能带图的特殊情况
                if (!content.classList.contains('collapsed') && content.querySelector('#bandStructure')) {
                    setTimeout(() => {
                        if (window.Plotly) {
                            Plotly.relayout('bandStructure', {autosize: true});
                        }
                    }, 300);
                }
                
                // 处理SC结构图的特殊情况
                if (!content.classList.contains('collapsed') && content.querySelector('#scStructure')) {
                    setTimeout(() => {
                        if (window.Plotly) {
                            Plotly.relayout('sc-plot', {autosize: true});
                        }
                    }, 300);
                }
            } else {
                content.classList.toggle('collapsed');
            }
        });
    });
    
    // 默认展开所有卡片
    const allCards = document.querySelectorAll('.card-header');
    allCards.forEach(header => {
        // Tab 卡片不做默认展开/折叠处理
        const next = header.nextElementSibling;
        if (next && next.classList.contains('tab-header')) return;
        header.classList.remove('collapsed');
        
        // 获取相邻的内容区域
        const content = header.nextElementSibling;
        content.classList.remove('collapsed');
    });
    
    // 页面加载后，确保内容不被顶部导航栏遮挡
    setTimeout(() => {
        const firstSection = document.getElementById('first-section');
        if (firstSection) {
            // 如果当前滚动位置过低(可能导致标题被遮挡)，则自动滚动到适当位置
            if (window.scrollY < firstSection.offsetTop - 180 && window.scrollY > 0) {
                window.scrollTo({
                    top: firstSection.offsetTop - 180,
                    behavior: 'smooth'
                });
            }
        }
    }, 500);
    
    // 延迟重新布局所有Plotly图表，确保它们正确显示
    setTimeout(() => {
        if (window.Plotly) {
            if (document.getElementById('bandStructure')) {
                Plotly.relayout('bandStructure', {autosize: true});
            }
            if (document.getElementById('sc-plot')) {
                Plotly.relayout('sc-plot', {autosize: true});
            }
        }
    }, 600);
}

/**
 * 加载晶体结构数据的函数
 * 从API获取晶体结构信息并更新页面显示
 */
function loadCrystalStructureData() {
    if (!window.materialData) {
        console.error('材料数据未设置，无法加载晶体结构数据');
        return;
    }

    const materialId = window.materialData.id;
    const materialName = window.materialData.name;

    // 创建API请求URL
    let url = `/api/structure?material_id=${materialId}`;
    if (!materialId && materialName) {
        url = `/api/structure?material_name=${materialName}`;
    }

    // 发送请求获取晶体结构数据
    fetch(url)
        .then(response => response.json())
        .then(data => {
            // 调试: 输出完整的API响应
            console.log("API Response:", data);

            if (data.error) {
                console.error("Error loading crystal structure data:", data.error);
                document.querySelectorAll('#crystal-structure .property-value').forEach(el => {
                    el.textContent = 'Data not available';
                });
                return;
            }

            // 加载3D晶体结构模型
            // 将获取到的数据直接传递给CrystalViewer，避免重复API调用
            console.log("准备渲染3D结构，数据:", data);
            console.log("CrystalViewer对象:", window.CrystalViewer);

            if (window.CrystalViewer && typeof window.CrystalViewer.render === 'function') {
                console.log("使用CrystalViewer.render方法");
                window.CrystalViewer.render(data);
            } else {
                // 如果render方法不存在，则使用load方法
                console.log("使用CrystalViewer.load方法");
                CrystalViewer.load(materialId);
            }

            // 更新晶体结构卡片中的数据
            updateCrystalStructureDisplay(data);

            // 添加原子坐标信息
            updateAtomicCoordinatesDisplay(data);
        })
        .catch(error => {
            console.error("Error fetching crystal structure data:", error);
            document.querySelectorAll('#crystal-structure .property-value').forEach(el => {
                el.textContent = 'Error loading data';
            });
        });
}

/**
 * 更新晶体结构显示信息
 * @param {Object} data - 从API获取的晶体结构数据
 */
function updateCrystalStructureDisplay(data) {
    // 晶体系统
    if (data.symmetry && data.symmetry.crystal_system) {
        document.getElementById('crystal-system').textContent = data.symmetry.crystal_system;
    }

    // 空间群 - 优先使用数据库中的数据，如果没有则使用API数据
    const spaceGroupElement = document.getElementById('space-group');
    const currentSpaceGroup = spaceGroupElement.textContent.trim();

    // 只有当前显示"Loading..."时才从API更新
    if (currentSpaceGroup === 'Loading...' && data.symmetry && data.symmetry.space_group_symbol) {
        const spaceGroup = `${data.symmetry.space_group_symbol} (${data.symmetry.space_group_number})`;
        spaceGroupElement.textContent = spaceGroup;
    }

    // 晶格参数
    if (data.lattice) {
        document.getElementById('lattice-a').textContent = `${data.lattice.a.toFixed(2)} Å`;
        document.getElementById('lattice-b').textContent = `${data.lattice.b.toFixed(2)} Å`;
        document.getElementById('lattice-c').textContent = `${data.lattice.c.toFixed(2)} Å`;
        document.getElementById('lattice-alpha').textContent = `${data.lattice.alpha.toFixed(2)}°`;
        document.getElementById('lattice-beta').textContent = `${data.lattice.beta.toFixed(2)}°`;
        document.getElementById('lattice-gamma').textContent = `${data.lattice.gamma.toFixed(2)}°`;
        document.getElementById('lattice-volume').textContent = `${data.lattice.volume.toFixed(2)} Å³`;
    }

    // 密度
    try {
        if (data.density !== undefined && data.density !== null) {
            document.getElementById('structure-density').textContent = `${parseFloat(data.density).toFixed(2)} g/cm³`;
        } else {
            document.getElementById('structure-density').textContent = '5.00 g/cm³ (estimated)';
        }
    } catch (e) {
        console.error("Error displaying density:", e);
        document.getElementById('structure-density').textContent = '5.00 g/cm³ (estimated)';
    }
}

/**
 * 更新原子坐标显示
 * @param {Object} data - 从API获取的晶体结构数据
 */
function updateAtomicCoordinatesDisplay(data) {
    // 添加原子坐标信息
    if (data.sites && Array.isArray(data.sites)) {
        const atomListElement = document.getElementById('atom-list');
        const totalAtoms = data.sites.length;

        // 创建元素计数对象
        const elementCounts = {};
        data.sites.forEach(site => {
            const element = site.species[0].element;
            elementCounts[element] = (elementCounts[element] || 0) + 1;
        });

        // 构建元素统计信息（用于调试，可以在控制台查看）
        let elementCountsText = Object.entries(elementCounts)
            .map(([element, count]) => `${element}: ${count}`)
            .join(', ');
        console.log('元素组成:', elementCountsText);

        // 创建表格显示原子坐标
        let tableHTML = `
            <div class="atom-info-card">
                <div class="atom-info-section">
                    <div class="atom-count">
                        <i class="fas fa-atom"></i>
                        <span class="atom-total">${totalAtoms}</span>
                        <span class="atom-total-label">atoms</span>
                    </div>
                    <div class="atom-composition-container">
                        ${Object.entries(elementCounts).map(([element, count]) =>
                            `<div class="element-chip"><span class="element-symbol">${element}</span><span class="element-count">${count}</span></div>`
                        ).join('')}
                    </div>
                </div>
                <div class="coordinates-controls">
                    <div class="coordinates-toggle">
                        <button class="coords-toggle-btn" id="coords-toggle-btn">
                            <i class="fas fa-sync-alt"></i>
                            <span id="toggle-btn-text">Show Fractional</span>
                        </button>
                    </div>
                    <div class="coords-display-info">
                        <i class="fas fa-ruler-combined"></i>
                        <span id="coords-type-label">Showing coordinates in Å</span>
                    </div>
                </div>
            </div>
            <div class="atom-coords-container">
                <table class="atom-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Element</th>
                            <th>x</th>
                            <th>y</th>
                            <th>z</th>
                            <th>Wyckoff</th>
                        </tr>
                    </thead>
                    <tbody id="atom-coordinates-body">
        `;

        // 添加所有原子的信息，不再限制显示数量
        for (let i = 0; i < totalAtoms; i++) {
            const site = data.sites[i];
            const element = site.species[0].element;

            // 笛卡尔坐标（默认显示）
            const x = site.xyz[0].toFixed(4);
            const y = site.xyz[1].toFixed(4);
            const z = site.xyz[2].toFixed(4);

            // 分数坐标（初始隐藏）
            const fx = site.frac_coords[0].toFixed(4);
            const fy = site.frac_coords[1].toFixed(4);
            const fz = site.frac_coords[2].toFixed(4);

            // 获取Wyckoff位置
            const wyckoff = site.wyckoff || "-";

            tableHTML += `
                <tr>
                    <td>${i + 1}</td>
                    <td class="atom-element">${element}</td>
                    <td class="atom-coords" data-cart="${x}" data-frac="${fx}">${x}</td>
                    <td class="atom-coords" data-cart="${y}" data-frac="${fy}">${y}</td>
                    <td class="atom-coords" data-cart="${z}" data-frac="${fz}">${z}</td>
                    <td>${wyckoff}</td>
                </tr>
            `;
        }

        tableHTML += `
                    </tbody>
                </table>
            </div>
        `;

        atomListElement.innerHTML = tableHTML;

        // 添加坐标切换功能
        setupCoordinateToggle();
    } else {
        document.getElementById('atom-list').textContent = 'Atomic coordinates not available';
    }
}

/**
 * 设置坐标切换功能
 * 允许用户在笛卡尔坐标和分数坐标之间切换显示
 */
function setupCoordinateToggle() {
    const coordsToggle = document.getElementById('coords-toggle-btn');
    let showingFractional = false;

    if (!coordsToggle) {
        console.warn('坐标切换按钮未找到');
        return;
    }

    coordsToggle.addEventListener('click', function() {
        showingFractional = !showingFractional;
        const coordsLabel = document.getElementById('coords-type-label');
        const toggleText = document.getElementById('toggle-btn-text');

        // 更新标签
        if (coordsLabel) {
            coordsLabel.textContent = showingFractional ? 'Showing fractional coordinates' : 'Showing coordinates in Å';
        }
        if (toggleText) {
            toggleText.textContent = showingFractional ? 'Show Cartesian' : 'Show Fractional';
        }

        // 更新按钮状态
        if (showingFractional) {
            this.classList.add('active');
        } else {
            this.classList.remove('active');
        }

        // 为按钮添加交互视觉效果
        this.classList.add('pulse-animation');
        setTimeout(() => {
            this.classList.remove('pulse-animation');
        }, 500);

        // 更新表格中的坐标值
        const coordCells = document.querySelectorAll('.atom-coords');
        coordCells.forEach(cell => {
            const frac = cell.getAttribute('data-frac');
            const cart = cell.getAttribute('data-cart');
            cell.textContent = showingFractional ? frac : cart;
        });
    });
}
