/**
 * crystal-viewer.js
 * 使用Three.js实现晶体结构的3D可视化
 */

// 全局变量
let scene, camera, renderer, controls;
let crystalGroup;
let isAnimating = false;
let atomMaterials = {};
let raycaster, mouse;
let atomTooltip;
let selectedAtom = null;
let hoveredAtom = null;

// 元素颜色映射表
const elementColors = {
    'H': 0xFFFFFF,   // 白色
    'He': 0xFFC0CB,  // 粉红色
    'Li': 0xCC80FF,  // 紫色
    'Be': 0xC2FF00,  // 黄绿色
    'B': 0xFFB5B5,   // 浅红色
    'C': 0x808080,   // 深灰色
    'N': 0x3050F8,   // 深蓝色
    'O': 0xFF0000,   // 鲜红色
    'F': 0x90E050,   // 浅绿色
    'Ne': 0xFF1493,  // 深粉色
    'Na': 0x0000FF,  // 纯蓝色
    'Mg': 0x228B22,  // 森林绿
    'Al': 0x808090,  // 金属灰
    'Si': 0xDAA520,  // 金黄色
    'P': 0xFF8C00,   // 深橙色
    'S': 0xFFD700,   // 金色
    'Cl': 0x00FF00,  // 鲜绿色
    'Ar': 0xFF69B4,  // 热粉色
    'K': 0x8A2BE2,   // 紫罗兰
    'Ca': 0x32CD32,  // 酸橙绿
    'Sc': 0x4169E1,  // 皇家蓝
    'Ti': 0x4682B4,  // 钢青色
    'V': 0x6A5ACD,   // 板岩蓝
    'Cr': 0x9370DB,  // 中紫色
    'Mn': 0xBA55D3,  // 兰花紫
    'Fe': 0xCD853F,  // 秘鲁色
    'Co': 0xDC143C,  // 深红色
    'Ni': 0x00CED1,  // 深青色
    'Cu': 0xB87333,  // 铜色
    'Zn': 0x7B68EE,  // 中暗蓝色
    'Ga': 0xC71585,  // 中紫红色
    'Ge': 0x48D1CC,  // 中绿宝石
    'As': 0x9932CC,  // 深兰花紫
    'Se': 0xFF4500,  // 橙红色
    'Br': 0x8B0000,  // 深红色
    'Kr': 0x00BFFF,  // 深天蓝
    'Rb': 0x9400D3,  // 深紫色
    'Sr': 0x32CD32,  // 酸橙绿
    'Y': 0x00FFFF,   // 青色
    'Zr': 0x40E0D0,  // 绿宝石色
    'Nb': 0x4682B4,  // 钢青色
    'Mo': 0x6495ED,  // 矢车菊蓝
    'Tc': 0x7B68EE,  // 中暗蓝色
    'Ru': 0x4169E1,  // 皇家蓝
    'Rh': 0x0000CD,  // 中蓝色
    'Pd': 0x00008B,  // 深蓝色
    'Ag': 0xC0C0C0,  // 银色
    'Cd': 0xFFD700,  // 金色
    'In': 0xCD5C5C,  // 印第安红
    'Sn': 0x4682B4,  // 钢青色
    'Sb': 0x9932CC,  // 深兰花紫
    'Te': 0xFF8C00,  // 深橙色
    'I': 0x8B008B,   // 深洋红
    'Xe': 0x00CED1,  // 深青色
    'Cs': 0x8A2BE2,  // 紫罗兰色
    'Ba': 0x32CD32,  // 酸橙绿
    'La': 0x00BFFF,  // 深天蓝
    'Ce': 0xFFD700,  // 金色
    'Pr': 0x32CD32,  // 酸橙绿
    'Nd': 0x7CFC00,  // 草绿色
    'Pm': 0x98FB98,  // 浅绿色
    'Sm': 0x90EE90,  // 淡绿色
    'Eu': 0x00FF7F,  // 春绿色
    'Gd': 0x3CB371,  // 中海绿
    'Tb': 0x2E8B57,  // 海绿色
    'Dy': 0x228B22,  // 森林绿
    'Ho': 0x008000,  // 绿色
    'Er': 0x006400,  // 深绿色
    'Tm': 0x556B2F,  // 暗橄榄绿
    'Yb': 0x6B8E23,  // 橄榄褐色
    'Lu': 0x808000,  // 橄榄色
    'Hf': 0x00BFFF,  // 深天蓝
    'Ta': 0x4169E1,  // 皇家蓝
    'W': 0x0000FF,   // 蓝色
    'Re': 0x0000CD,  // 中蓝色
    'Os': 0x00008B,  // 深蓝色
    'Ir': 0x000080,  // 海军蓝
    'Pt': 0xE5E4E2,  // 铂金色
    'Au': 0xFFD700,  // 金色
    'Hg': 0xB8860B,  // 暗金色
    'Tl': 0xCD5C5C,  // 印第安红
    'Pb': 0x2F4F4F,  // 深岩灰
    'Bi': 0x9932CC,  // 深兰花紫
    'Po': 0x8B4513,  // 马鞍棕色
    'At': 0x800000,  // 栗色
    'Rn': 0x4169E1,  // 皇家蓝
    'Fr': 0x8B008B,  // 深洋红
    'Ra': 0x006400,  // 深绿色
    'Ac': 0x00BFFF,  // 深天蓝
    'Th': 0x00BFFF,  // 深天蓝
    'Pa': 0x0000FF,  // 蓝色
    'U': 0x0000CD,   // 中蓝色
    'Np': 0x00008B,  // 深蓝色
    'Pu': 0x000080,  // 海军蓝
    'Am': 0x9400D3,  // 深紫色
    'Cm': 0x8A2BE2,  // 紫罗兰色
    'Bk': 0x9932CC,  // 深兰花紫
    'Cf': 0x8B008B,  // 深洋红
    'Es': 0x800080,  // 紫色
    'Fm': 0x4B0082,  // 靛青色
    'Md': 0x483D8B,  // 暗灰蓝色
    'No': 0x8B008B,  // 深洋红
    'Lr': 0x800080   // 紫色
};

/**
 * 初始化Three.js场景
 * @param {string} containerId - 容器元素ID
 */
function initCrystalViewer(containerId) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container element with ID '${containerId}' not found`);
        return;
    }
    
    // 初始化Raycaster和鼠标向量
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();
    
    // 创建原子信息提示框
    atomTooltip = document.createElement('div');
    atomTooltip.className = 'atom-tooltip';
    atomTooltip.style.display = 'none';
    container.appendChild(atomTooltip);

    // 获取容器尺寸
    const width = container.clientWidth;
    const height = container.clientHeight || 400; // 默认高度

    // 创建场景
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff); // 白色背景

    // 创建相机
    camera = new THREE.PerspectiveCamera(70, width / height, 0.1, 1000);
    camera.position.z = 10;

    // 创建渲染器
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    // 添加轨道控制器
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; // 启用阻尼效果
    controls.dampingFactor = 0.25;
    controls.screenSpacePanning = false;
    controls.maxDistance = 100;
    controls.update();

    // 添加环境光和方向光
    const ambientLight = new THREE.AmbientLight(0x404040, 1.5);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(1, 1, 1).normalize();
    scene.add(directionalLight);

    // 创建晶体结构组
    crystalGroup = new THREE.Group();
    scene.add(crystalGroup);

    // 添加坐标轴辅助
    const axesHelper = new THREE.AxesHelper(5);
    scene.add(axesHelper);

    // 开始动画循环
    animate();

    // 窗口大小调整处理
    window.addEventListener('resize', () => {
        const width = container.clientWidth;
        const height = container.clientHeight || 400;
        
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    });
    
    // 添加点击事件监听器
    renderer.domElement.addEventListener('click', onAtomClick);
    
    // 添加鼠标移动事件监听器
    renderer.domElement.addEventListener('mousemove', onAtomHover);
    
    // 添加鼠标离开事件监听器
    renderer.domElement.addEventListener('mouseleave', () => {
        if (hoveredAtom && hoveredAtom !== selectedAtom) {
            resetAtomMaterial(hoveredAtom);
        }
        hoveredAtom = null;
        if (!selectedAtom) {
            atomTooltip.style.display = 'none';
        }
    });
    
    // 添加CSS样式
    const style = document.createElement('style');
    style.textContent = `
        .atom-tooltip {
            position: absolute;
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            display: none;
        }
    `;
    document.head.appendChild(style);
}

/**
 * 动画循环
 */
function animate() {
    requestAnimationFrame(animate);
    
    // 更新控制器
    controls.update();
    
    // 如果启用了自动旋转
    if (isAnimating) {
        crystalGroup.rotation.y += 0.005;
    }
    
    // 更新提示框位置
    updateTooltipPosition();
    
    // 渲染场景
    renderer.render(scene, camera);
}

/**
 * 处理原子点击事件
 * @param {Event} event - 点击事件对象
 */
function onAtomClick(event) {
    // 更新鼠标位置
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    
    // 发射射线
    raycaster.setFromCamera(mouse, camera);
    
    // 获取与射线相交的对象
    const intersects = raycaster.intersectObjects(crystalGroup.children);
    
    if (intersects.length > 0) {
        const atom = intersects[0].object;
        if (atom.userData.element) {
            if (selectedAtom === atom) {
                // 如果点击的是已选中的原子，取消选中
                resetAtomMaterial(atom);
                selectedAtom = null;
                atomTooltip.style.display = 'none';
            } else {
                // 如果之前有选中的原子，重置其材质
                if (selectedAtom) {
                    resetAtomMaterial(selectedAtom);
                }
                // 选中新的原子
                selectedAtom = atom;
                highlightAtom(atom);
                // 显示原子信息
                atomTooltip.innerHTML = `
                    Element: ${atom.userData.element}<br>
                    Position: (${atom.userData.position.map(p => p.toFixed(3)).join(', ')})
                `;
                atomTooltip.style.display = 'block';
                updateTooltipPosition();
            }
        }
    } else {
        // 点击空白处，取消选中状态
        if (selectedAtom) {
            resetAtomMaterial(selectedAtom);
            selectedAtom = null;
            atomTooltip.style.display = 'none';
        }
    }
}

/**
 * 处理原子悬停事件
 * @param {Event} event - 鼠标事件对象
 */
function onAtomHover(event) {
    // 更新鼠标位置
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    
    // 发射射线
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(crystalGroup.children);
    
    if (intersects.length > 0) {
        const atom = intersects[0].object;
        if (atom.userData.element) {
            // 如果悬停的原子不是当前悬停的原子
            if (hoveredAtom !== atom) {
                // 重置之前悬停的原子（如果有且不是选中的原子）
                if (hoveredAtom && hoveredAtom !== selectedAtom) {
                    resetAtomMaterial(hoveredAtom);
                }
                // 设置新的悬停原子
                hoveredAtom = atom;
                if (atom !== selectedAtom) {
                    highlightAtom(atom, true);
                }
            }
            // 如果没有选中的原子，显示悬停提示
            if (!selectedAtom) {
                atomTooltip.innerHTML = `
                    Element: ${atom.userData.element}<br>
                    Position: (${atom.userData.position.map(p => p.toFixed(3)).join(', ')})
                `;
                atomTooltip.style.display = 'block';
                updateTooltipPosition();
            }
        }
    } else {
        // 鼠标没有悬停在任何原子上
        if (hoveredAtom && hoveredAtom !== selectedAtom) {
            resetAtomMaterial(hoveredAtom);
        }
        hoveredAtom = null;
        if (!selectedAtom) {
            atomTooltip.style.display = 'none';
        }
    }
}

/**
 * 高亮显示原子
 * @param {THREE.Mesh} atom - 要高亮的原子
 * @param {boolean} isHover - 是否是悬停状态
 */
function highlightAtom(atom, isHover = false) {
    const element = atom.userData.element;
    const color = elementColors[element] || 0x808080;
    const material = atom.material;
    
    // 保存原始颜色
    if (!atom.userData.originalColor) {
        atom.userData.originalColor = material.color.getHex();
    }
    
    // 设置高亮效果
    material.emissive.setHex(isHover ? 0x444444 : 0x666666);
    material.color.setHex(color);
}

/**
 * 重置原子材质到原始状态
 * @param {THREE.Mesh} atom - 要重置的原子
 */
function resetAtomMaterial(atom) {
    const material = atom.material;
    material.emissive.setHex(0x000000);
    if (atom.userData.originalColor) {
        material.color.setHex(atom.userData.originalColor);
    }
}

/**
 * 更新提示框位置
 */
function updateTooltipPosition() {
    if (atomTooltip.style.display === 'none') return;
    
    // 发射射线
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(crystalGroup.children);
    
    if (intersects.length > 0) {
        const atom = intersects[0].object;
        // 将3D坐标转换为屏幕坐标
        const vector = atom.position.clone();
        vector.project(camera);
        
        const x = (vector.x * 0.5 + 0.5) * renderer.domElement.clientWidth;
        const y = (-vector.y * 0.5 + 0.5) * renderer.domElement.clientHeight;
        
        // 更新提示框位置
        atomTooltip.style.left = `${x}px`;
        atomTooltip.style.top = `${y - 30}px`; // 在原子上方显示
    }
}

/**
 * 加载晶体结构数据
 * @param {number} materialId - 材料ID
 */
function loadCrystalStructure(materialId) {
    // 显示加载指示器
    showLoadingIndicator();
    
    // 从API获取结构数据
    fetch(`/api/structure/${materialId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // 清除加载指示器
            hideLoadingIndicator();
            
            // 渲染晶体结构
            renderCrystalStructure(data);
        })
        .catch(error => {
            console.error('Error loading crystal structure:', error);
            hideLoadingIndicator();
            showErrorMessage('Failed to load crystal structure data');
        });
}

/**
 * 渲染晶体结构
 * @param {Object} structureData - 晶体结构数据
 */
function renderCrystalStructure(structureData) {
    // 清除现有结构
    while (crystalGroup.children.length > 0) {
        const object = crystalGroup.children[0];
        object.geometry.dispose();
        object.material.dispose();
        crystalGroup.remove(object);
    }

    // 添加晶格框架
    addUnitCell(structureData.lattice);
    
    // 添加原子
    structureData.atoms.forEach(atom => {
        addAtom(atom);
    });

    // 重置相机位置以适应结构
    resetCameraPosition(structureData);
    
    // 添加标题和原子图例
    addTitleAndLegend(structureData);
}

/**
 * 添加单位晶胞框架
 * @param {Object} lattice - 晶格参数
 */
function addUnitCell(lattice) {
    const matrix = lattice.matrix;
    
    // 创建晶胞顶点
    const vertices = [
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(matrix[0][0], matrix[0][1], matrix[0][2]),
        new THREE.Vector3(matrix[1][0], matrix[1][1], matrix[1][2]),
        new THREE.Vector3(matrix[0][0] + matrix[1][0], matrix[0][1] + matrix[1][1], matrix[0][2] + matrix[1][2]),
        new THREE.Vector3(matrix[2][0], matrix[2][1], matrix[2][2]),
        new THREE.Vector3(matrix[0][0] + matrix[2][0], matrix[0][1] + matrix[2][1], matrix[0][2] + matrix[2][2]),
        new THREE.Vector3(matrix[1][0] + matrix[2][0], matrix[1][1] + matrix[2][1], matrix[1][2] + matrix[2][2]),
        new THREE.Vector3(matrix[0][0] + matrix[1][0] + matrix[2][0], matrix[0][1] + matrix[1][1] + matrix[2][1], matrix[0][2] + matrix[1][2] + matrix[2][2])
    ];

    // 创建晶胞边
    const edges = [
        [0, 1], [0, 2], [1, 3], [2, 3],
        [0, 4], [1, 5], [2, 6], [3, 7],
        [4, 5], [4, 6], [5, 7], [6, 7]
    ];

    // 创建线条几何体
    const geometry = new THREE.BufferGeometry();
    const positions = [];

    edges.forEach(edge => {
        positions.push(
            vertices[edge[0]].x, vertices[edge[0]].y, vertices[edge[0]].z,
            vertices[edge[1]].x, vertices[edge[1]].y, vertices[edge[1]].z
        );
    });

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    // 创建线条材质
    const material = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 1 });

    // 创建线条对象并添加到晶体组
    const unitCell = new THREE.LineSegments(geometry, material);
    crystalGroup.add(unitCell);
}

/**
 * 添加原子
 * @param {Object} atom - 原子数据
 */
function addAtom(atom) {
    const element = atom.element;
    const position = atom.position;
    const radius = atom.properties.radius || 0.5;
    
    // 获取元素颜色，如果未定义则使用默认颜色
    const color = elementColors[element] || 0x808080;
    
    // 创建或重用材质
    if (!atomMaterials[element]) {
        atomMaterials[element] = new THREE.MeshPhongMaterial({
            color: color,
            specular: 0x666666,
            shininess: 30,
            transparent: false,
            emissive: 0x000000
        });
    }
    
    // 创建球体几何体
    const geometry = new THREE.SphereGeometry(radius * 0.5, 32, 32);
    
    // 创建网格并设置位置
    const mesh = new THREE.Mesh(geometry, atomMaterials[element]);
    mesh.position.set(position[0], position[1], position[2]);
    
    // 添加用户数据（用于交互）
    mesh.userData = {
        element: element,
        position: position,
        properties: atom.properties
    };
    
    // 添加到晶体组
    crystalGroup.add(mesh);
}

/**
 * 重置相机位置以适应结构
 * @param {Object} structureData - 晶体结构数据
 */
function resetCameraPosition(structureData) {
    // 计算结构的边界框
    const boundingBox = new THREE.Box3().setFromObject(crystalGroup);
    const center = boundingBox.getCenter(new THREE.Vector3());
    const size = boundingBox.getSize(new THREE.Vector3());
    
    // 计算适当的相机距离
    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = camera.fov * (Math.PI / 180);
    let cameraDistance = (maxDim / 2) / Math.tan(fov / 2);
    
    // 设置相机位置
    camera.position.set(center.x, center.y, center.z + cameraDistance * 1.5);
    camera.lookAt(center);
    
    // 更新控制器目标点
    controls.target.copy(center);
    controls.update();
}

/**
 * 显示加载指示器
 */
function showLoadingIndicator() {
    // 创建加载指示器元素
    const loadingIndicator = document.createElement('div');
    loadingIndicator.id = 'crystal-loading-indicator';
    loadingIndicator.style.position = 'absolute';
    loadingIndicator.style.top = '50%';
    loadingIndicator.style.left = '50%';
    loadingIndicator.style.transform = 'translate(-50%, -50%)';
    loadingIndicator.style.background = 'rgba(255, 255, 255, 0.8)';
    loadingIndicator.style.padding = '20px';
    loadingIndicator.style.borderRadius = '5px';
    loadingIndicator.style.zIndex = '1000';
    loadingIndicator.innerHTML = 'Loading crystal structure...';
    
    // 添加到容器
    const container = renderer.domElement.parentElement;
    container.style.position = 'relative';
    container.appendChild(loadingIndicator);
}

/**
 * 隐藏加载指示器
 */
function hideLoadingIndicator() {
    const loadingIndicator = document.getElementById('crystal-loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

/**
 * 添加标题和原子图例
 * @param {Object} structureData - 晶体结构数据
 */
function addTitleAndLegend(structureData) {
    const container = renderer.domElement.parentElement;
    container.style.position = 'relative';
    
    // 移除已存在的标题和图例（如果有）
    const existingTitle = document.getElementById('crystal-title');
    if (existingTitle) existingTitle.remove();
    
    const existingLegend = document.getElementById('crystal-legend');
    if (existingLegend) existingLegend.remove();
    
    // 创建标题
    const titleElement = document.createElement('div');
    titleElement.id = 'crystal-title';
    titleElement.className = 'crystal-title';
    titleElement.innerHTML = `<h3>Crystal Structure - ${structureData.formula}</h3>`;
    container.appendChild(titleElement);
    
    // 统计每种元素的原子数量
    const elementCounts = {};
    structureData.atoms.forEach(atom => {
        const element = atom.element;
        if (!elementCounts[element]) {
            elementCounts[element] = 1;
        } else {
            elementCounts[element]++;
        }
    });
    
    // 创建图例面板
    const legendElement = document.createElement('div');
    legendElement.id = 'crystal-legend';
    legendElement.className = 'crystal-legend';
    
    // 添加图例标题
    const legendTitle = document.createElement('div');
    legendTitle.className = 'legend-title';
    legendTitle.textContent = 'Atom Legend';
    legendElement.appendChild(legendTitle);
    
    // 添加每种元素的图例项
    const legendItems = document.createElement('div');
    legendItems.className = 'legend-items';
    
    // 按元素符号排序
    const sortedElements = Object.keys(elementCounts).sort();
    
    sortedElements.forEach(element => {
        const count = elementCounts[element];
        const color = elementColors[element] || 0x808080;
        
        // 创建图例项
        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item';
        
        // 创建颜色示例
        const colorSample = document.createElement('div');
        colorSample.className = 'color-sample';
        colorSample.style.backgroundColor = `#${color.toString(16).padStart(6, '0')}`;
        legendItem.appendChild(colorSample);
        
        // 创建元素名称和数量
        const elementInfo = document.createElement('div');
        elementInfo.className = 'element-info';
        elementInfo.textContent = `${element}: ${count} atoms`;
        legendItem.appendChild(elementInfo);
        
        // 添加到图例项容器
        legendItems.appendChild(legendItem);
    });
    
    legendElement.appendChild(legendItems);
    container.appendChild(legendElement);
    
    // 添加CSS样式
    const style = document.createElement('style');
    style.textContent = `
        .crystal-title {
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background-color: rgba(255, 255, 255, 0.8);
            padding: 5px 15px;
            border-radius: 5px;
            z-index: 100;
            text-align: center;
        }
        
        .crystal-title h3 {
            margin: 0;
            font-size: 16px;
            color: #333;
        }
        
        .crystal-legend {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: rgba(255, 255, 255, 0.8);
            padding: 10px;
            border-radius: 5px;
            z-index: 100;
            max-width: 200px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        
        .legend-title {
            font-weight: bold;
            margin-bottom: 8px;
            text-align: center;
            font-size: 14px;
            color: #333;
        }
        
        .legend-items {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .color-sample {
            width: 15px;
            height: 15px;
            border-radius: 50%;
            border: 1px solid #ddd;
        }
        
        .element-info {
            font-size: 12px;
            color: #333;
        }
        
        @media (max-width: 600px) {
            .crystal-legend {
                top: auto;
                bottom: 10px;
                right: 10px;
                max-width: 150px;
            }
            
            .crystal-title {
                top: 5px;
                padding: 3px 10px;
            }
            
            .crystal-title h3 {
                font-size: 14px;
            }
        }
    `;
    document.head.appendChild(style);
}

/**
 * 显示错误消息
 * @param {string} message - 错误消息
 */
function showErrorMessage(message) {
    const errorMessage = document.createElement('div');
    errorMessage.id = 'crystal-error-message';
    errorMessage.style.position = 'absolute';
    errorMessage.style.top = '50%';
    errorMessage.style.left = '50%';
    errorMessage.style.transform = 'translate(-50%, -50%)';
    errorMessage.style.background = 'rgba(255, 0, 0, 0.1)';
    errorMessage.style.color = '#ff0000';
    errorMessage.style.padding = '20px';
    errorMessage.style.borderRadius = '5px';
    errorMessage.style.zIndex = '1000';
    errorMessage.innerHTML = message;
    
    // 添加到容器
    const container = renderer.domElement.parentElement;
    container.style.position = 'relative';
    container.appendChild(errorMessage);
    
    // 3秒后自动移除
    setTimeout(() => {
        errorMessage.remove();
    }, 3000);
}

/**
 * 控制功能：向左旋转
 */
function rotateLeft() {
    crystalGroup.rotation.y -= Math.PI / 12;
}

/**
 * 控制功能：向右旋转
 */
function rotateRight() {
    crystalGroup.rotation.y += Math.PI / 12;
}

/**
 * 控制功能：重置视图
 */
function resetView() {
    crystalGroup.rotation.set(0, 0, 0);
    controls.reset();
}

/**
 * 控制功能：切换自动旋转
 */
function toggleSpin() {
    isAnimating = !isAnimating;
}

// 导出公共函数
window.CrystalViewer = {
    init: initCrystalViewer,
    load: loadCrystalStructure,
    rotateLeft: rotateLeft,
    rotateRight: rotateRight,
    resetView: resetView,
    toggleSpin: toggleSpin
};