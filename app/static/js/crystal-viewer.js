/**
 * crystal-viewer.js
 * 使用Three.js实现晶体结构的3D可视化
 * 这个文件提供了晶体结构的交互式3D可视化功能
 */

// 全局变量声明
let scene, camera, renderer, controls; // 声明Three.js的基本组件：场景、相机、渲染器和控制器
let crystalGroup; // 用于存储晶体结构的组，包含所有的原子和晶胞
let isAnimating = false; // 控制晶体是否自动旋转的标志
let atomMaterials = {}; // 存储不同元素的材质，避免重复创建
let raycaster, mouse; // 用于实现射线拾取功能，检测鼠标与3D对象的交互
let atomTooltip; // 显示原子信息的提示框元素
let selectedAtom = null; // 当前选中的原子
let hoveredAtom = null; // 当前悬停的原子
let currentModelType = 'ball-and-stick'; // 默认使用球棍模型
let _projectionMode = 'perspective'; // 视角模式：'perspective' 或 'orthographic'

// 用于保存不同模型表示的对象组
let ballsGroup = null; // 存储球模型的组
let sticksGroup = null; // 存储棍模型的组

// 元素颜色映射表 - 使用符合学术标准的CPK配色方案
// 为每种化学元素定义特定的颜色，以便在3D视图中区分不同的原子
// 用于存储已生成的颜色，避免重复生成
let generatedColors = new Set();

/**
 * 生成独特的颜色
 * @param {string} element - 元素符号
 * @returns {number} - 生成的颜色值
 */
function generateDistinctColor(element) {
    // 使用元素符号的字符编码作为基础生成色相值
    let hue = 0;
    for (let i = 0; i < element.length; i++) {
        hue += element.charCodeAt(i);
    }
    hue = hue % 360; // 将色相值限制在0-360范围内

    // 使用较高的饱和度和亮度以确保颜色鲜明
    const saturation = 0.7 + Math.random() * 0.3; // 70%-100%
    const lightness = 0.4 + Math.random() * 0.3;  // 40%-70%

    // 转换HSL为RGB
    const rgb = hslToRgb(hue / 360, saturation, lightness);
    const color = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2];

    // 确保颜色的唯一性
    if (generatedColors.has(color)) {
        return generateDistinctColor(element + '1'); // 递归生成新颜色
    }
    generatedColors.add(color);
    return color;
}

/**
 * 将HSL颜色值转换为RGB
 * @param {number} h - 色相 (0-1)
 * @param {number} s - 饱和度 (0-1)
 * @param {number} l - 亮度 (0-1)
 * @returns {number[]} - RGB颜色值数组 [r, g, b]
 */
function hslToRgb(h, s, l) {
    let r, g, b;

    if (s === 0) {
        r = g = b = l; // 灰度
    } else {
        const hue2rgb = (p, q, t) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };

        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
    }

    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

const elementColors = {
    'H': 0xFFFFFF,   // 氢 - 白色
    'He': 0xD9FFFF,  // 氦 - 浅青色
    'Li': 0xCC80FF,  // 锂 - 紫色
    'Be': 0xC2FF00,  // 铍 - 黄绿色
    'B': 0xFFB5B5,   // 硼 - 浅红色
    'C': 0x909090,   // 碳 - 中灰色
    'N': 0x3050F8,   // 氮 - 深蓝色
    'O': 0xFF0D0D,   // 氧 - 鲜红色
    'F': 0x90E050,   // 氟 - 浅绿色
    'Ne': 0xB3E3F5,  // 氖 - 浅蓝色
    'Na': 0xAB5CF2,  // 钠 - 紫色
    'Mg': 0x8AFF00,  // 镁 - 亮绿色
    'Al': 0xBFA6A6,  // 铝 - 浅灰粉色
    'Si': 0xF0C8A0,  // 硅 - 浅棕色
    'P': 0xFF8000,   // 磷 - 橙色
    'S': 0xFFFF30,   // 硫 - 黄色
    'Cl': 0x1FF01F,  // 氯 - 绿色
    'Ar': 0x80D1E3,  // 氩 - 青色
    'K': 0x8F40D4,   // 钾 - 紫色
    'Ca': 0x3DFF00,  // 钙 - 绿色
    'Sc': 0xE6E6E6,  // 钪 - 浅灰色
    'Ti': 0xBFC2C7,  // 钛 - 灰色
    'V': 0xA6A6AB,   // 钒 - 浅灰色
    'Cr': 0x8A99C7,  // 铬 - 灰蓝色
    'Mn': 0x9C7AC7,  // 锰 - 紫色
    'Fe': 0xE06633,  // 铁 - 棕红色
    'Co': 0xF090A0,  // 钴 - 粉红色
    'Ni': 0x50D050,  // 镍 - 绿色
    'Cu': 0xC88033,  // 铜 - 铜色
    'Zn': 0x7D80B0,  // 锌 - 浅蓝色
    'Ga': 0xC28F8F,  // 镓 - 粉红色
    'Ge': 0x668F8F,  // 锗 - 灰绿色
    'As': 0xBD80E3,  // 砷 - 紫色
    'Se': 0xFFA100,  // 硒 - 橙色
    'Br': 0xA62929,  // 溴 - 棕色
    'Kr': 0x5CB8D1,  // 氪 - 青色
    'Rb': 0x702EB0,  // 铷 - 深紫色
    'Sr': 0x00FF00,  // 锶 - 绿色
    'Y': 0x94FFFF,   // 钇 - 青色
    'Zr': 0x94E0E0,  // 锆 - 浅青色
    'Nb': 0x73C2C9,  // 铌 - 浅青色
    'Mo': 0x54B5B5,  // 钼 - 青色
    'Tc': 0x3B9E9E,  // 锝 - 深青色
    'Ru': 0x248F8F,  // 钌 - 深青色
    'Rh': 0x0A7D8C,  // 铑 - 深青色
    'Pd': 0x006985,  // 钯 - 深青色
    'Ag': 0xC0C0C0,  // 银 - 银色
    'Cd': 0xFFD98F,  // 镉 - 浅黄色
    'In': 0xA67573,  // 铟 - 浅棕色
    'Sn': 0x668080,  // 锡 - 灰青色
    'Sb': 0x9E63B5,  // 锑 - 紫色
    'Te': 0xD47A00,  // 碲 - 棕色
    'I': 0x940094,   // 碘 - 深紫色
    'Xe': 0x429EB0,  // 氙 - 青色
    'Cs': 0x57178F,  // 铯 - 深紫色
    'Ba': 0x00C900,  // 钡 - 深绿色
    'La': 0x70D4FF,  // 镧 - 浅蓝色
    'Ce': 0xFFFFC7,  // 铈 - 浅黄色
    'Pr': 0xD9FFC7,  // 镨 - 浅绿色
    'Nd': 0xC7FFC7,  // 钕 - 浅绿色
    'Pm': 0xA3FFC7,  // 钷 - 浅绿色
    'Sm': 0x8FFFC7,  // 钐 - 浅绿色
    'Eu': 0x61FFC7,  // 铕 - 浅绿色
    'Gd': 0x45FFC7,  // 钆 - 浅绿色
    'Tb': 0x30FFC7,  // 铽 - 浅绿色
    'Dy': 0x1FFFC7,  // 镝 - 浅绿色
    'Ho': 0x00FF9C,  // 钬 - 绿色
    'Er': 0x00E675,  // 铒 - 绿色
    'Tm': 0x00D452,  // 铥 - 绿色
    'Yb': 0x00BF38,  // 镱 - 绿色
    'Lu': 0x00AB24,  // 镥 - 绿色
    'Hf': 0x4DC2FF,  // 铪 - 浅蓝色
    'Ta': 0x4DA6FF,  // 钽 - 浅蓝色
    'W': 0x2194D6,   // 钨 - 蓝色
    'Re': 0x267DAB,  // 铼 - 深蓝色
    'Os': 0x266696,  // 锇 - 深蓝色
    'Ir': 0x175487,  // 铱 - 深蓝色
    'Pt': 0xD0D0E0,  // 铂 - 浅灰色
    'Au': 0xFFD123,  // 金 - 金色
    'Hg': 0xB8B8D0,  // 汞 - 灰色
    'Tl': 0xA6544D,  // 铊 - 棕色
    'Pb': 0x575961,  // 铅 - 深灰色
    'Bi': 0x9E4FB5,  // 铋 - 紫色
    'Po': 0xAB5C00,  // 钋 - 棕色
    'At': 0x754F45,  // 砹 - 深棕色
    'Rn': 0x428296,  // 氡 - 青色
    'Fr': 0x420066,  // 钫 - 深紫色
    'Ra': 0x007D00,  // 镭 - 深绿色
    'Ac': 0x70ABFA,  // 锕 - 浅蓝色
    'Th': 0x00BAFF,  // 钍 - 浅蓝色
    'Pa': 0x00A1FF,  // 镤 - 浅蓝色
    'U': 0x008FFF,   // 铀 - 蓝色
    'Np': 0x0080FF,  // 镎 - 蓝色
    'Pu': 0x006BFF,  // 钚 - 蓝色
    'Am': 0x545CF2,  // 镅 - 蓝色
    'Cm': 0x785CE3,  // 锔 - 紫蓝色
    'Bk': 0x8A4FE3,  // 锫 - 紫色
    'Cf': 0xA136D4,  // 锎 - 紫色
    'Es': 0xB31FD4,  // 锿 - 紫色
    'Fm': 0xB31FBA,  // 镄 - 紫色
    'Md': 0xB30DA6,  // 钔 - 紫色
    'No': 0xBD0D87,  // 锘 - 紫红色
    'Lr': 0xC70066   // 铹 - 紫红色
};

/**
 * 初始化Three.js场景
 * @param {string} containerId - 容器元素ID
 */
function initCrystalViewer(containerId) {
    // 获取DOM容器元素
    const container = document.getElementById(containerId);
    if (!container) {
        // 如果找不到容器元素，输出错误信息并退出
        console.error(`Container element with ID '${containerId}' not found`);
        return;
    }
    
    // 初始化Raycaster和鼠标向量，用于实现鼠标与3D对象的交互
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();
    
    // 创建原子信息提示框，用于显示被选中原子的详细信息
    atomTooltip = document.createElement('div');
    atomTooltip.className = 'atom-tooltip'; // 设置CSS类名
    atomTooltip.style.display = 'none'; // 初始状态为隐藏
    atomTooltip.style.position = 'absolute'; // 绝对定位
    atomTooltip.style.backgroundColor = 'rgba(30, 30, 30, 0.7)'; // 设置半透明背景色
    atomTooltip.style.color = '#ffffff'; // 设置文字颜色为白色
    atomTooltip.style.padding = '10px'; // 设置内边距
    atomTooltip.style.borderRadius = '5px'; // 设置圆角
    atomTooltip.style.fontSize = '14px'; // 设置字体大小
    atomTooltip.style.zIndex = '1000'; // 设置层级，确保显示在最上层
    atomTooltip.style.pointerEvents = 'none'; // 禁止鼠标事件，使tooltip不影响下层元素的交互
    atomTooltip.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.3)'; // 添加阴影效果
    atomTooltip.style.minWidth = '150px'; // 设置最小宽度
    atomTooltip.style.backdropFilter = 'blur(5px)'; // 添加背景模糊效果，提升视觉体验
    container.appendChild(atomTooltip); // 添加到容器中
    
    // 添加原子提示框样式，定义更详细的CSS样式
    const tooltipStyle = document.createElement('style');
    tooltipStyle.textContent = `
        .atom-tooltip .element-symbol {
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 5px;
        }
        .atom-tooltip .element-details {
            font-size: 12px;
        }
        .atom-tooltip .element-details div {
            margin: 3px 0;
        }
    `;
    document.head.appendChild(tooltipStyle); // 将样式添加到文档头部

    // 获取容器尺寸，用于设置渲染器和相机
    const width = container.clientWidth;
    const height = container.clientHeight || 600; // 如果高度未定义，使用默认值600px

    // 创建Three.js场景
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff); // 设置场景背景为白色

    // 创建透视相机
    // 参数1: 视场角(FOV) - 45度,决定视野范围的大小
    // 参数2: 宽高比 - 根据容器尺寸计算,保持图像不变形
    // 参数3: 近裁剪面 - 0.1,小于此距离的物体不会被渲染
    // 参数4: 远裁剪面 - 1000,大于此距离的物体不会被渲染
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.x = 12; // 设置相机初始位置
    camera.position.y = 12; // 设置相机初始位置
    camera.position.z = 12; // 设置相机初始位置

    // 创建WebGL渲染器
    renderer = new THREE.WebGLRenderer({ 
        antialias: true, // 启用抗锯齿，提升画面质量
        preserveDrawingBuffer: true // 保留绘图缓冲区，支持截图功能
    }); 
    renderer.setSize(width, height); // 设置渲染器尺寸
    renderer.setPixelRatio(window.devicePixelRatio); // 设置设备像素比，适应高分辨率屏幕
    container.appendChild(renderer.domElement); // 将渲染器的DOM元素添加到容器中

    // 添加轨道控制器，实现相机绕物体旋转、平移和缩放功能
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; // 启用阻尼效果，使控制更平滑
    controls.dampingFactor = 0.25; // 设置阻尼系数
    controls.screenSpacePanning = true; // 启用屏幕空间平移，避免平移时改变旋转中心
    controls.maxDistance = 50; // 设置最大缩放距离
    controls.minDistance = 2; // 设置最小缩放距离
    controls.rotateSpeed = 0.6; // 设置适当的旋转速度
    controls.zoomSpeed = 0.8; // 设置适当的缩放速度
    controls.panSpeed = 0.6; // 设置适当的平移速度
    controls.addEventListener('change', function() {
        // 控制器变化时，确保更新射线以修复悬停问题
        updateRaycasterFromMouse();
    });
    controls.update(); // 更新控制器

    // 添加光照系统
    // 添加环境光，提供基础环境光照
    // 创建环境光源
    // 参数1: 0xffffff 表示白色光源
    // 参数2: 0.7 表示光照强度为70%
    // 环境光会均匀照亮场景中的所有物体,不产生阴影
    // 用于提供基础环境照明,使物体不会完全黑暗
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    
    // 将环境光添加到场景中
    // 这样场景中的所有物体都会受到这个光源的影响
    scene.add(ambientLight);

    // 添加半球光以提供更自然的照明效果，模拟环境光反射
    const hemisphereLight = new THREE.HemisphereLight(0xffffff, 0xbbbbbb, 0.3);
    scene.add(hemisphereLight);

    // 添加方向光提供适度的阴影和立体感，增强3D效果
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.4);
    directionalLight.position.set(1, 1, 1).normalize(); // 设置光源方向
    scene.add(directionalLight);

    // 创建晶体结构的容器组，所有原子和晶胞框架都将添加到这个组中
    crystalGroup = new THREE.Group();
    scene.add(crystalGroup);

    // 添加增强的坐标轴辅助，帮助用户理解3D空间方向
    addEnhancedAxesHelper();
    
    // 创建功能工具栏，提供用户交互界面
    createToolbar(container);
    
    // 创建扩胞控制面板，用于调整晶胞显示
    createSupercellPanel(container);

    // 开始动画循环，不断更新场景渲染
    animate();

    // 添加窗口大小调整事件处理程序，确保画面自适应
    window.addEventListener('resize', () => {
        const width = container.clientWidth;
        const height = container.clientHeight || 600;
        const aspect = width / height;
        if (_projectionMode === 'perspective' && camera && camera.isPerspectiveCamera) {
            camera.aspect = aspect; // 更新相机宽高比
            camera.updateProjectionMatrix(); // 更新相机投影矩阵
        } else if (_projectionMode === 'orthographic' && camera && camera.isOrthographicCamera) {
            // 依据当前到目标点的距离与默认FOV推导正交视椎大小，保持切换一致的视觉尺度
            const dist = camera.position.clone().sub(controls.target).length();
            const baseFov = 45; // 与默认透视FOV一致
            const frustumHeight = 2 * dist * Math.tan(THREE.MathUtils.degToRad(baseFov * 0.5));
            const frustumWidth = frustumHeight * aspect;
            camera.left = -frustumWidth / 2;
            camera.right = frustumWidth / 2;
            camera.top = frustumHeight / 2;
            camera.bottom = -frustumHeight / 2;
            camera.updateProjectionMatrix();
        }
        renderer.setSize(width, height); // 调整渲染器尺寸
    });
    
    // 添加点击事件监听器
    renderer.domElement.addEventListener('click', onAtomClick);
    
    // 添加鼠标移动事件用于获取光标位置
    renderer.domElement.addEventListener('mousemove', function(event) {
        // 更新鼠标位置
        updateMousePosition(event);
    });
}

/**
 * 创建功能工具栏
 * @param {HTMLElement} container - 容器元素
 */
function createToolbar(container) {
    // 创建工具栏的DOM容器
    const toolbar = document.createElement('div');
    toolbar.className = 'crystal-toolbar'; // 设置CSS类名便于样式调整
    toolbar.style.position = 'absolute'; // 使用绝对定位
    toolbar.style.top = '20px'; // 距顶部20px
    toolbar.style.right = '20px'; // 定位在右上角
    toolbar.style.display = 'flex'; // 使用flex布局排列按钮
    toolbar.style.gap = '15px'; // 按钮之间的间距增加到15px
    toolbar.style.zIndex = '1000'; // 设置层级确保在上层显示
    toolbar.style.padding = '10px'; // 添加内边距
    toolbar.style.backgroundColor = 'rgba(255, 255, 255, 0.9)'; // 半透明白色背景
    toolbar.style.borderRadius = '5px'; // 圆角边框
    toolbar.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)'; // 添加阴影效果
    
    // 创建截图按钮
    const screenshotBtn = document.createElement('button');
    screenshotBtn.innerHTML = '<i class="fas fa-camera"></i>'; // 使用Font Awesome图标
    screenshotBtn.title = '截图'; // 设置鼠标悬停提示文字
    screenshotBtn.className = 'button-tool-small'; // 统一按钮体系，保留原类
    screenshotBtn.addEventListener('click', takeScreenshot); // 添加点击事件监听器
    toolbar.appendChild(screenshotBtn); // 将按钮添加到工具栏
    
    // 创建下载CIF文件按钮
    const downloadCIFBtn = document.createElement('button');
    downloadCIFBtn.innerHTML = '<i class="fas fa-download"></i>'; // 使用下载图标
    downloadCIFBtn.title = '下载CIF文件'; // 设置提示文字
    downloadCIFBtn.className = 'button-tool-small';
    downloadCIFBtn.addEventListener('click', downloadCIFFile); // 添加下载CIF文件的点击事件
    toolbar.appendChild(downloadCIFBtn);
    
    // 创建重置视图按钮
    const resetViewBtn = document.createElement('button');
    resetViewBtn.innerHTML = '<i class="fas fa-redo-alt"></i>'; // 使用重置图标
    resetViewBtn.title = '重置视图'; // 设置提示文字
    resetViewBtn.className = 'button-tool-small';
    resetViewBtn.addEventListener('click', resetView); // 添加重置视图的点击事件
    toolbar.appendChild(resetViewBtn);
    
    // 创建投影切换按钮（透视/正交）
    const projectionBtn = document.createElement('button');
    projectionBtn.className = 'button-tool-small';
    function updateProjectionBtnUI() {
        if (_projectionMode === 'perspective') {
            projectionBtn.innerHTML = '<i class="fas fa-border-all"></i>';
            projectionBtn.title = 'Switch to Orthographic';
        } else {
            projectionBtn.innerHTML = '<i class="fas fa-cube"></i>';
            projectionBtn.title = 'Switch to Perspective';
        }
    }
    updateProjectionBtnUI();
    projectionBtn.addEventListener('click', () => {
        switchProjection(container);
        updateProjectionBtnUI();
    });
    toolbar.appendChild(projectionBtn);
    
    // 创建模型切换按钮（带下拉菜单）
    const modelTypeContainer = document.createElement('div');
    modelTypeContainer.className = 'model-type-container';
    modelTypeContainer.style.position = 'relative'; // 设为相对定位，作为下拉菜单的参考点
    
    // 创建模型切换按钮
    const modelTypeBtn = document.createElement('button');
    modelTypeBtn.innerHTML = '<i class="fas fa-cubes"></i>'; // 使用立方体图标
    modelTypeBtn.title = 'Switch Model Type'; // 设置提示文字
    modelTypeBtn.className = 'button-tool-small';
    
    // 创建模型类型下拉菜单
    const modelTypeDropdown = document.createElement('div');
    modelTypeDropdown.className = 'model-type-dropdown';
    modelTypeDropdown.style.position = 'absolute'; // 绝对定位
    modelTypeDropdown.style.top = '100%'; // 定位在按钮下方
    modelTypeDropdown.style.right = '0'; // 右对齐
    modelTypeDropdown.style.backgroundColor = 'white'; // 白色背景
    modelTypeDropdown.style.borderRadius = '8px'; // 增加圆角
    modelTypeDropdown.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.15)'; // 更柔和的阴影
    modelTypeDropdown.style.display = 'none'; // 初始状态为隐藏
    modelTypeDropdown.style.zIndex = '1001'; // 确保显示在最上层
    modelTypeDropdown.style.marginTop = '8px'; // 增加与按钮的间距
    modelTypeDropdown.style.width = '180px'; // 增加下拉菜单宽度
    modelTypeDropdown.style.border = '1px solid rgba(0, 0, 0, 0.1)'; // 添加边框
    modelTypeDropdown.style.padding = '6px 0'; // 添加内边距
    
    // 定义可选的模型类型选项
    const modelOptions = [
        { label: 'Ball-And-Stick', value: 'ball-and-stick' },
        { label: 'Ball', value: 'ball' },
        { label: 'Stick', value: 'stick' }
    ];
    
    // 为每个模型类型创建DOM元素
    modelOptions.forEach(option => {
        // 创建模型类型选项容器
        const modelOption = document.createElement('div');
        modelOption.className = 'model-option';
        modelOption.style.display = 'flex'; // 使用flex布局
        modelOption.style.alignItems = 'center'; // 垂直居中对齐
        modelOption.style.padding = '10px 15px'; // 增加内边距
        modelOption.style.cursor = 'pointer'; // 鼠标悬停时显示手型光标
        modelOption.style.borderBottom = '1px solid rgba(0, 0, 0, 0.06)'; // 更淡的分隔线
        modelOption.style.fontSize = '14px'; // 设置字体大小
        modelOption.style.transition = 'background-color 0.2s ease'; // 添加过渡效果
        modelOption.style.color = '#333'; // 设置文字颜色
        
        // 添加悬停效果
        modelOption.addEventListener('mouseover', () => {
            modelOption.style.backgroundColor = 'rgba(0, 0, 0, 0.05)';
        });
        modelOption.addEventListener('mouseout', () => {
            modelOption.style.backgroundColor = 'transparent';
        });
        
        // 创建选项图标
        const optionIcon = document.createElement('div');
        optionIcon.className = 'option-icon';
        optionIcon.style.width = '16px'; // 设置宽度
        optionIcon.style.height = '16px'; // 设置高度
        optionIcon.style.marginRight = '10px'; // 右侧间距
        optionIcon.style.display = 'flex'; // 使用flex布局
        optionIcon.style.alignItems = 'center'; // 垂直居中对齐
        optionIcon.style.justifyContent = 'center'; // 水平居中对齐
        
        // 根据模型类型设置不同的图标
        let iconHTML = '';
        switch (option.value) {
            case 'ball-and-stick':
                iconHTML = '<i class="fas fa-atom"></i>'; // 原子图标
                break;
            case 'ball':
                iconHTML = '<i class="fas fa-circle"></i>'; // 圆形图标
                break;
            case 'stick':
                iconHTML = '<i class="fas fa-minus"></i>'; // 横线图标
                break;
        }
        optionIcon.innerHTML = iconHTML;
        
        // 创建选项标签文本
        const optionLabel = document.createElement('span');
        optionLabel.textContent = option.label; // 设置显示文本
        
        // 将图标和标签添加到选项容器
        modelOption.appendChild(optionIcon);
        modelOption.appendChild(optionLabel);
        
        // 添加悬停效果，鼠标移入时改变背景色
        modelOption.addEventListener('mouseover', () => {
            modelOption.style.backgroundColor = '#f5f5f5';
        });
        
        // 鼠标移出时恢复原背景色
        modelOption.addEventListener('mouseout', () => {
            modelOption.style.backgroundColor = 'white';
        });
        
        // 添加点击事件，切换模型类型并隐藏下拉菜单
        modelOption.addEventListener('click', () => {
            changeModelType(option.value); // 调用切换模型类型函数
            modelTypeDropdown.style.display = 'none'; // 隐藏下拉菜单
        });
        
        // 将模型类型选项添加到下拉菜单
        modelTypeDropdown.appendChild(modelOption);
    });
    
    // 处理下拉菜单的显示和隐藏
    modelTypeBtn.addEventListener('click', () => {
        // 切换下拉菜单的显示状态
        if (modelTypeDropdown.style.display === 'none') {
            modelTypeDropdown.style.display = 'block';
        } else {
            modelTypeDropdown.style.display = 'none';
        }
    });
    
    // 添加点击外部区域关闭下拉菜单的事件监听
    document.addEventListener('click', (event) => {
        // 如果点击的不是模型类型按钮区域，则隐藏下拉菜单
        if (!modelTypeContainer.contains(event.target)) {
            modelTypeDropdown.style.display = 'none';
        }
    });
    
    // 将按钮和下拉菜单添加到容器中
    modelTypeContainer.appendChild(modelTypeBtn);
    modelTypeContainer.appendChild(modelTypeDropdown);
    toolbar.appendChild(modelTypeContainer);
    
    // 将工具栏添加到主容器中
    container.appendChild(toolbar);
}

/**
 * 透视/正交投影切换
 * 保留相机位置与控制器目标，尽量保持视觉尺寸一致
 */
function switchProjection(container) {
    const width = container.clientWidth;
    const height = container.clientHeight || 600;
    const aspect = width / height;

    const oldPos = camera.position.clone();
    const oldUp = camera.up.clone();
    const target = controls ? controls.target.clone() : new THREE.Vector3(0, 0, 0);
    const near = camera.near || 0.1;
    const far = camera.far || 1000;

    if (_projectionMode === 'perspective') {
        // 切换到正交
        const dist = oldPos.clone().sub(target).length();
        const baseFov = camera.isPerspectiveCamera ? camera.fov : 45;
        const frustumHeight = 2 * dist * Math.tan(THREE.MathUtils.degToRad(baseFov * 0.5));
        const frustumWidth = frustumHeight * aspect;
        const ortho = new THREE.OrthographicCamera(
            -frustumWidth / 2,
            frustumWidth / 2,
            frustumHeight / 2,
            -frustumHeight / 2,
            near,
            far
        );
        camera = ortho;
        camera.position.copy(oldPos);
        camera.up.copy(oldUp);
        camera.lookAt(target);
        if (controls) controls.dispose();
        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.25;
        controls.screenSpacePanning = true;
        controls.maxDistance = 50;
        controls.minDistance = 2;
        controls.rotateSpeed = 0.6;
        controls.zoomSpeed = 0.8;
        controls.panSpeed = 0.6;
        controls.target.copy(target);
        controls.update();
        _projectionMode = 'orthographic';
    } else {
        // 切换回透视
        const persp = new THREE.PerspectiveCamera(45, aspect, near, far);
        camera = persp;
        camera.position.copy(oldPos);
        camera.up.copy(oldUp);
        camera.lookAt(target);
        if (controls) controls.dispose();
        controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.25;
        controls.screenSpacePanning = true;
        controls.maxDistance = 50;
        controls.minDistance = 2;
        controls.rotateSpeed = 0.6;
        controls.zoomSpeed = 0.8;
        controls.panSpeed = 0.6;
        controls.target.copy(target);
        controls.update();
        _projectionMode = 'perspective';
    }
    camera.updateProjectionMatrix();
}

/**
 * 截图并保存
 * 将当前晶体结构的视图保存为PNG图片
 */
function takeScreenshot() {
    // 从渲染器获取图像数据，转换为PNG格式的Data URL
    const imgData = renderer.domElement.toDataURL('image/png');
    
    // 创建下载链接
    const link = document.createElement('a');
    link.href = imgData; // 设置链接地址为图像数据
    link.download = 'crystal-structure.png'; // 设置下载的文件名
    document.body.appendChild(link); // 将链接添加到文档
    link.click(); // 模拟点击链接触发下载
    document.body.removeChild(link); // 下载后移除链接
}

/**
 * 更新鼠标光标位置
 * 跟踪鼠标在渲染区域中的位置坐标，转换为Three.js中的标准化坐标系
 * @param {Event} event - 鼠标事件对象
 */
function updateMousePosition(event) {
    // 获取渲染区域的边界矩形，用于计算相对位置
    const rect = renderer.domElement.getBoundingClientRect();
    // 将鼠标位置转换为标准化设备坐标系，范围在-1到1之间
    // X坐标：从左到右为-1到1
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    // Y坐标：从上到下为1到-1（注意Y轴是反的）
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
}

/**
 * 更新光线发射器，用于修复旋转后悬停问题
 * 在相机视角变化后重新设置射线，确保交互正确
 */
function updateRaycasterFromMouse() {
    // 如果有选中的原子，更新射线以保持提示框位置正确
    if (selectedAtom) {
        // 根据当前鼠标位置和相机设置射线
        raycaster.setFromCamera(mouse, camera);
    // 更新提示框位置
    updateTooltipPosition();
    }
}

/**
 * 处理原子点击事件
 * 实现原子的选择、取消选择，并显示相关信息
 * @param {Event} event - 点击事件对象
 */
function onAtomClick(event) {
    // 更新鼠标位置坐标
    updateMousePosition(event);
    
    // 根据鼠标位置设置射线
    raycaster.setFromCamera(mouse, camera);
    
    // 首先检查球体组中的原子
    const ballIntersects = ballsGroup.visible ? raycaster.intersectObjects(ballsGroup.children) : [];
    
    // 然后检查棍组中的连接
    const stickIntersects = sticksGroup.visible ? raycaster.intersectObjects(sticksGroup.children) : [];
    
    // 合并交点结果并按距离排序
    const allIntersects = [...ballIntersects, ...stickIntersects].sort((a, b) => a.distance - b.distance);
    
    // 如果点击到了对象
    if (allIntersects.length > 0) {
        const obj = allIntersects[0].object;
        
        // 处理不同类型的点击对象
        if (obj.userData.type === 'ball') {
            // 点击的是原子球体
            handleAtomClick(obj);
        } else if (obj.userData.type === 'stick') {
            // 点击的是连接棍
            // 如果需要处理键的点击，可以在这里添加逻辑
            // 例如，显示键长或键的详细信息
            console.log('键连接被点击', obj.userData);
        }
    } else {
        // 点击空白处，取消选中状态
        if (selectedAtom) {
            resetAtomMaterial(selectedAtom); // 恢复原子材质
            selectedAtom = null; // 清除选中的原子引用
            atomTooltip.style.display = 'none'; // 隐藏提示框
        }
    }
}

/**
 * 处理原子点击
 * @param {THREE.Mesh} atom - 点击的原子对象
 */
function handleAtomClick(atom) {
            // 如果点击的是已选中的原子
            if (selectedAtom === atom) {
                // 取消选中状态
                resetAtomMaterial(atom); // 恢复原子材质
                selectedAtom = null; // 清除选中的原子引用
                atomTooltip.style.display = 'none'; // 隐藏提示框
            } else {
                // 如果点击的是新原子，但之前已有选中的原子
                if (selectedAtom) {
                    // 重置之前选中原子的材质
                    resetAtomMaterial(selectedAtom);
                }
                // 选中新的原子
                selectedAtom = atom;
                highlightAtom(atom); // 高亮显示选中的原子
                
                // 填充提示框内容，显示原子的详细信息
                const element = atom.userData.element; // 元素符号
                const position = atom.userData.position; // 原子位置
                const properties = atom.userData.properties || {}; // 原子属性
                
                // 使用HTML设置提示框内容
                atomTooltip.innerHTML = `
                    <div class="element-symbol">${element}</div>
                    <div class="element-details">
                        <div>Position: (${position[0].toFixed(3)}, ${position[1].toFixed(3)}, ${position[2].toFixed(3)})</div>
                        ${properties.charge ? `<div>Charge: ${properties.charge}</div>` : ''}
                        ${properties.coordination ? `<div>Coordination Number: ${properties.coordination}</div>` : ''}
                    </div>
                `;
                atomTooltip.style.display = 'block'; // 显示提示框
                updateTooltipPosition(); // 更新提示框位置
    }
}

/**
 * 动画循环
 * 实现持续渲染和更新，创建平滑的交互体验
 */
function animate() {
    // 请求下一帧动画，创建无限循环
    requestAnimationFrame(animate);
    
    // 更新控制器状态，实现阻尼效果
    controls.update();
    
    // 如果启用了自动旋转，旋转晶体结构
    if (isAnimating && crystalGroup) {
        crystalGroup.rotation.y += 0.005; // 每帧旋转一小角度
    }
    
    // 更新选中原子信息提示框位置，跟随原子移动
    if (selectedAtom && atomTooltip.style.display !== 'none') {
                updateTooltipPosition();
            }
    
    // 渲染当前场景，更新显示
    renderer.render(scene, camera);
    
    // 渲染独立的坐标轴，与主场景的旋转同步
    if (window.renderAxes) {
        window.renderAxes();
    }
}

/**
 * 切换模型类型
 * 在球棍模型、球模型和棍模型之间切换
 * @param {string} type - 模型类型: 'ball-and-stick', 'ball', 或 'stick'
 */
function changeModelType(type) {
    // 如果选择了当前已经使用的模型类型，则不需要进行任何操作
    if (type === currentModelType) return;
    
    // 更新当前模型类型变量
    currentModelType = type;
    
    // 更新模型可见性，不需要重新生成模型
    updateModelVisibility();
}

/**
 * 更新模型可见性
 * 根据当前选择的模型类型显示或隐藏相应的组件
 */
function updateModelVisibility() {
    // 确保球和棍组已经创建
    if (!ballsGroup || !sticksGroup) {
        console.warn('球或棍组未初始化');
        return;
    }
    
    // 根据当前模型类型设置可见性
    switch (currentModelType) {
        case 'ball': // 只显示球体
            ballsGroup.visible = true;
            sticksGroup.visible = false;
            break;
            
        case 'stick': // 只显示棍
            ballsGroup.visible = false;
            sticksGroup.visible = true;
            break;
            
        case 'ball-and-stick': // 同时显示球和棍
        default:
            ballsGroup.visible = true;
            sticksGroup.visible = true;
            break;
    }
    
    // 记录状态变化，便于调试
    console.log(`模型类型已更改为 ${currentModelType}。球体可见性: ${ballsGroup.visible}, 棍可见性: ${sticksGroup.visible}`);
}

/**
 * 获取当前加载的结构数据
 * 注意：这个函数需要在应用中存储当前的结构数据才能正常工作
 * 现在暂时返回null，需要实现具体逻辑
 */
function getCurrentStructureData() {
    // 如果没有存储当前结构数据，则从晶体组中提取数据
    if (!window.currentStructureData) {
        console.warn('未找到存储的结构数据。结构重新渲染可能不完整。');
        return null;
    }
    
    return window.currentStructureData;
}

/**
 * 转换为原胞
 * 将当前结构转换为原胞并重新渲染
 */
function convertToPrimitiveCell() {
    // 获取当前材料ID
    const materialId = window.currentMaterialId;
    if (!materialId) {
        console.error('未找到当前材料ID');
        return;
    }
    
    // 显示加载提示
    showLoadingIndicator();
    
    // 调用后端API获取原胞数据
    fetch(`/api/structure/${materialId}/primitive`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('转换原胞失败:', data.error);
                showErrorMessage('转换原胞失败，请稍后重试');
                return;
            }
            
            // 保存新的结构数据
            window.currentStructureData = data;
            
            // 清除场景中的现有结构
            clearStructure();
            
            // 重新渲染结构
            renderStructure(data);
            
            // 更新UI状态
            updateCellTypeIndicator('primitive');
            
            // 隐藏加载提示
            hideLoadingIndicator();
        })
        .catch(error => {
            console.error('转换原胞请求失败:', error);
            showErrorMessage('网络错误，请稍后重试');
            hideLoadingIndicator();
        });
}

/**
 * 转换为传统胞
 * 将当前结构转换为传统胞并重新渲染
 */
function convertToConventionalCell() {
    // 获取当前材料ID
    const materialId = window.currentMaterialId;
    if (!materialId) {
        console.error('未找到当前材料ID');
        return;
    }
    
    // 显示加载提示
    showLoadingIndicator();
    
    // 调用后端API获取传统胞数据
    fetch(`/api/structure/${materialId}/conventional`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('转换传统胞失败:', data.error);
                showErrorMessage('转换传统胞失败，请稍后重试');
                return;
            }
            
            // 保存新的结构数据
            window.currentStructureData = data;
            
            // 清除场景中的现有结构
            clearStructure();
            
            // 重新渲染结构
            renderStructure(data);
            
            // 更新UI状态
            updateCellTypeIndicator('conventional');
            
            // 隐藏加载提示
            hideLoadingIndicator();
        })
        .catch(error => {
            console.error('转换传统胞请求失败:', error);
            showErrorMessage('网络错误，请稍后重试');
            hideLoadingIndicator();
        });
}

/**
 * 清除当前结构
 * 从场景中移除所有结构相关的对象
 */
function clearStructure() {
    if (!crystalGroup) return;
    
    // 移除所有子对象并释放资源
    while (crystalGroup.children.length > 0) {
        const object = crystalGroup.children[0];
        crystalGroup.remove(object);
        
        // 释放几何体和材质
        if (object.geometry) object.geometry.dispose();
        if (object.material) {
            if (Array.isArray(object.material)) {
                object.material.forEach(material => material.dispose());
            } else {
                object.material.dispose();
            }
        }
    }
    
    // 清除材质缓存
    atomMaterials = {};
}

/**
 * 显示加载提示
 */
function showLoadingIndicator() {
    // 创建或显示加载提示元素
    let loadingIndicator = document.getElementById('loading-indicator');
    if (!loadingIndicator) {
        loadingIndicator = document.createElement('div');
        loadingIndicator.id = 'loading-indicator';
        loadingIndicator.className = 'loading-indicator';
        loadingIndicator.innerHTML = '<div class="spinner"></div><div class="loading-text">正在处理...</div>';
        document.body.appendChild(loadingIndicator);
    }
    loadingIndicator.style.display = 'flex';
}

/**
 * 隐藏加载提示
 */
function hideLoadingIndicator() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

/**
 * 显示错误消息
 * @param {string} message - 错误消息文本
 */
function showErrorMessage(message) {
    // 创建或更新错误消息元素
    let errorMessage = document.getElementById('error-message');
    if (!errorMessage) {
        errorMessage = document.createElement('div');
        errorMessage.id = 'error-message';
        errorMessage.className = 'error-message';
        document.body.appendChild(errorMessage);
    }
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    
    // 3秒后自动隐藏错误消息
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 3000);
}

/**
 * 更新晶胞类型指示器
 * @param {string} cellType - 晶胞类型（'primitive' 或 'conventional'）
 */
function updateCellTypeIndicator(cellType) {
    // 更新UI元素以反映当前晶胞类型
    const indicator = document.getElementById('cell-type-indicator');
    if (indicator) {
        indicator.textContent = cellType === 'primitive' ? '原胞' : '传统胞';
    }
}

/**
 * 根据当前模型类型重新渲染结构
 * @param {Object} structureData - 结构数据
 */
function rerenderStructure(structureData) {
    // 如果没有有效的结构数据，则停止渲染
    if (!structureData) {
        // 从当前原子对象中获取数据创建一个临时结构
        const tempStructure = {
            atoms: []
        };
        
        // 遍历晶体组中的所有对象
        crystalGroup.children.forEach(obj => {
            // 只处理原子对象（具有element属性的对象）
            if (obj.userData && obj.userData.element) {
                tempStructure.atoms.push({
                    element: obj.userData.element,
                    position: obj.userData.position,
                    properties: obj.userData.properties || { radius: 0.5 }
                });
            }
        });
        
        // 使用临时结构
        structureData = tempStructure;
    }
    
    // 清除晶体组中的原子（保留晶胞和其他结构元素）
    const nonAtoms = [];
    while (crystalGroup.children.length > 0) {
        const object = crystalGroup.children[0];
        crystalGroup.remove(object);
        
        // 如果不是原子对象，保存起来以便后续添加回晶体组
        if (!object.userData || !object.userData.element) {
            nonAtoms.push(object);
        } else {
            // 释放原子对象资源
            object.geometry.dispose();
            object.material.dispose();
        }
    }
    
    // 将非原子对象添加回晶体组
    nonAtoms.forEach(obj => crystalGroup.add(obj));
    
    // 清除材质缓存，以便应用新的模型类型
    atomMaterials = {};
    
    // 重新添加原子，应用新的模型类型
    structureData.atoms.forEach(atom => {
        addAtom(atom);
    });
}

/**
 * 高亮显示选中的原子
 * 通过改变材质和添加轮廓效果使选中的原子更突出
 * @param {THREE.Object3D} atom - 要高亮显示的原子对象
 */
function highlightAtom(atom) {
    // 保存原有材质，以便之后恢复
    if (!atom.userData.originalMaterial) {
        atom.userData.originalMaterial = atom.material;
    }

    // 创建高亮材质 - 使用原子的基本颜色但更加明亮
    const color = atom.material.color.clone();
    
    // 选中状态 - 使用发光材质使原子更突出
    atom.material = new THREE.MeshStandardMaterial({
        color: color.clone().multiplyScalar(1.3), // 增加颜色亮度
        emissive: color.clone().multiplyScalar(0.3), // 添加自发光效果
        emissiveIntensity: 0.5, // 设置自发光强度
        metalness: 0.3, // 增加金属感
        roughness: 0.5, // 降低粗糙度，增加光泽
        flatShading: false // 使用平滑着色
    });
    
    // 添加边框效果，进一步增强选中效果
    if (!atom.userData.outline) {
        // 获取原子半径，稍微放大用于边框
        const radius = atom.geometry.parameters.radius * 1.1;
        
        // 创建边框几何体和材质
        const outlineGeometry = new THREE.SphereGeometry(radius, 32, 32);
        const outlineMaterial = new THREE.MeshBasicMaterial({
            color: 0xffffff, // 白色边框
            side: THREE.BackSide, // 使用背面渲染，形成轮廓效果
            transparent: true, // 启用透明度
            opacity: 0.3 // 设置透明度
        });
        
        // 创建边框网格并添加到原子对象
        const outline = new THREE.Mesh(outlineGeometry, outlineMaterial);
        atom.add(outline); // 将边框添加为原子的子对象
        atom.userData.outline = outline; // 保存边框引用以便后续操作
    }
}

/**
 * 重置原子材质
 * 取消高亮显示，恢复原子的原始外观
 * @param {THREE.Object3D} atom - 要重置的原子对象
 */
function resetAtomMaterial(atom) {
    // 如果有保存的原始材质，则恢复
    if (atom.userData.originalMaterial) {
        atom.material = atom.userData.originalMaterial;
        atom.userData.originalMaterial = null; // 清除保存的材质引用
    }
    
    // 移除边框效果
    if (atom.userData.outline) {
        atom.remove(atom.userData.outline); // 从原子移除边框对象
        atom.userData.outline = null; // 清除边框引用
    }
    
    // 重置脉冲动画状态（如果有）
    if (atom.userData.pulseAnimation) {
        atom.scale.set(1, 1, 1); // 重置原子缩放
        atom.userData.pulseAnimation = null; // 清除动画引用
    }
}

/**
 * 更新提示框位置
 * 确保提示框跟随选中的原子位置
 */
function updateTooltipPosition() {
    // 如果提示框已隐藏或没有选中的原子，则不更新
    if (atomTooltip.style.display === 'none' || !selectedAtom) return;
    
    // 将原子的3D坐标转换为屏幕坐标
    const vector = new THREE.Vector3();
    vector.setFromMatrixPosition(selectedAtom.matrixWorld); // 获取原子在世界坐标系中的位置
    vector.project(camera); // 将3D坐标投影到2D屏幕坐标
    
    // 转换为CSS像素坐标
        const x = (vector.x * 0.5 + 0.5) * renderer.domElement.clientWidth;
        const y = (-vector.y * 0.5 + 0.5) * renderer.domElement.clientHeight;
        
    // 更新提示框位置，显示在原子上方
        atomTooltip.style.left = `${x}px`;
    atomTooltip.style.top = `${y - 30}px`; // 向上偏移30像素，避免遮挡原子
}

/**
 * 加载晶体结构数据
 * 通过API获取指定材料ID的晶体结构数据并渲染
 * @param {number} materialId - 材料ID，用于API请求
 */
function loadCrystalStructure(materialId) {
    // 显示加载指示器，提示用户正在加载数据
    showLoadingIndicator();
    
    // 保存当前正在加载的材料ID，以便后续使用
    window.currentMaterialId = materialId;
    
    // 从API获取结构数据
    fetch(`/api/structure/${materialId}`)
        .then(response => {
            // 检查API响应状态
            if (!response.ok) {
                throw new Error(`HTTP错误! 状态码: ${response.status}`);
            }
            return response.json(); // 将响应解析为JSON
        })
        .then(data => {
            // 数据加载成功，隐藏加载指示器
            hideLoadingIndicator();
            
            // 保存结构数据以便后续使用
            window.currentStructureData = data;
            
            // 如果数据中没有材料ID，添加它
            if (!data.id && materialId) {
                data.id = materialId;
            }
            
            // 渲染晶体结构
            renderCrystalStructure(data);
        })
        .catch(error => {
            // 处理错误情况
            console.error('加载晶体结构出错:', error);
            hideLoadingIndicator(); // 隐藏加载指示器
            
            // 显示"No data"而不是错误信息
            const container = document.getElementById('crystalViewer');
            if (container) {
                container.innerHTML = `<div style="text-align:center;padding:50px;color:#666;background:#f9f9f9;border-radius:8px;margin:20px 0;font-size:18px;">
                    <p>No data</p>
                </div>`;
            } else {
                showErrorMessage('加载晶体结构数据失败'); // 如果找不到容器，则显示错误信息
            }
        });
}

/**
 * 渲染晶体结构
 * 根据获取的数据创建3D晶体模型
 * @param {Object} structureData - 晶体结构数据，包含晶格和原子信息
 */
function renderCrystalStructure(structureData) {
    console.log("renderCrystalStructure被调用，数据:", structureData);

    // 存储结构数据以便后续使用
    window.currentStructureData = structureData;

    // 检查是否为原胞结构
    const isPrimitive = structureData.isPrimitive || false;
    
    // 重置场景状态
    selectedAtom = null;
    hoveredAtom = null;
    if (atomTooltip) {
        atomTooltip.style.display = 'none';
    }

    // 清除现有结构，避免重叠显示
    function disposeObject(object) {
        if (object.geometry) {
            object.geometry.dispose();
        }
        if (object.material) {
            if (Array.isArray(object.material)) {
                object.material.forEach(mat => {
                    if (mat.map) mat.map.dispose();
                    mat.dispose();
                });
            } else {
                if (object.material.map) object.material.map.dispose();
                object.material.dispose();
            }
        }
        if (object.children && object.children.length > 0) {
            object.children.forEach(child => disposeObject(child));
        }
    }

    // 递归清理所有对象
    while (crystalGroup.children.length > 0) {
        const object = crystalGroup.children[0];
        disposeObject(object);
        crystalGroup.remove(object);
        object.parent = null; // 确保对象完全从场景中移除
    }

    // 重置全局组引用
    if (ballsGroup) {
        ballsGroup.clear();
        ballsGroup = null;
    }
    if (sticksGroup) {
        sticksGroup.clear();
        sticksGroup = null;
    }

    // 添加晶格框架，显示晶胞边界
    addUnitCell(structureData.lattice);
    
    // 创建新的球和棍组
    ballsGroup = new THREE.Group();
    sticksGroup = new THREE.Group();
    
    // 将球和棍组添加到晶体组
    crystalGroup.add(ballsGroup);
    crystalGroup.add(sticksGroup);
    
    // 首先向组中添加所有原子球体
    structureData.atoms.forEach(atom => {
        addBall(atom);
    });
    
    // 然后添加所有的键连接
    generateBonds(structureData.atoms);
    
    // 根据当前选择的模型类型，显示或隐藏相应的组
    updateModelVisibility();
    
    // 计算晶胞中心
    const boundingBox = new THREE.Box3().setFromObject(crystalGroup);
    const center = boundingBox.getCenter(new THREE.Vector3());
    
    // 将晶体组移动，使晶胞中心位于原点
    crystalGroup.position.sub(center);
    
    // 重置相机位置以适应整个结构
    resetCameraPosition(structureData);
    
    // 添加标题和原子图例，增强可视化效果
    addTitleAndLegend(structureData);
}

/**
 * 添加单位晶胞框架
 * 根据晶格参数绘制晶胞的边框
 * @param {Object} lattice - 晶格参数，包含矩阵信息
 */
function addUnitCell(lattice) {
    const matrix = lattice.matrix; // 获取晶格矩阵
    
    // 创建晶胞八个顶点的坐标
    // 使用向量表示，基于晶格矩阵中的基矢量
    const vertices = [
        new THREE.Vector3(0, 0, 0), // 原点
        new THREE.Vector3(matrix[0][0], matrix[0][1], matrix[0][2]), // a方向
        new THREE.Vector3(matrix[1][0], matrix[1][1], matrix[1][2]), // b方向
        new THREE.Vector3(matrix[0][0] + matrix[1][0], matrix[0][1] + matrix[1][1], matrix[0][2] + matrix[1][2]), // a+b
        new THREE.Vector3(matrix[2][0], matrix[2][1], matrix[2][2]), // c方向
        new THREE.Vector3(matrix[0][0] + matrix[2][0], matrix[0][1] + matrix[2][1], matrix[0][2] + matrix[2][2]), // a+c
        new THREE.Vector3(matrix[1][0] + matrix[2][0], matrix[1][1] + matrix[2][1], matrix[1][2] + matrix[2][2]), // b+c
        new THREE.Vector3(matrix[0][0] + matrix[1][0] + matrix[2][0], matrix[0][1] + matrix[1][1] + matrix[2][1], matrix[0][2] + matrix[1][2] + matrix[2][2]) // a+b+c
    ];

    // 定义晶胞的12条边，每条边由两个顶点的索引表示
    const edges = [
        [0, 1], [0, 2], [1, 3], [2, 3], // 底面的四条边
        [0, 4], [1, 5], [2, 6], [3, 7], // 连接底面和顶面的四条边
        [4, 5], [4, 6], [5, 7], [6, 7]  // 顶面的四条边
    ];

    // 创建线条几何体，用于绘制晶胞边框
    const geometry = new THREE.BufferGeometry();
    const positions = []; // 存储顶点坐标

    // 将每条边的两个顶点坐标添加到positions数组
    edges.forEach(edge => {
        positions.push(
            vertices[edge[0]].x, vertices[edge[0]].y, vertices[edge[0]].z, // 第一个顶点
            vertices[edge[1]].x, vertices[edge[1]].y, vertices[edge[1]].z  // 第二个顶点
        );
    });

    // 将坐标数组设置为几何体的属性
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    // 创建线条材质，设置为黑色细线
    const material = new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 1 });

    // 创建线段对象并添加到晶体组
    const unitCell = new THREE.LineSegments(geometry, material);
    crystalGroup.add(unitCell); // 将晶胞边框添加到晶体组
}

/**
 * 添加原子球体
 * 创建表示原子的彩色球体并添加到球体组
 * @param {Object} atom - 原子数据，包含元素类型、位置和属性
 * @returns {THREE.Mesh} 创建的原子球体网格对象
 */
function addBall(atom) {
    const element = atom.element; // 获取元素符号
    const position = atom.position; // 获取原子位置坐标
    const radius = atom.properties.radius || 0.5; // 获取原子半径，如果未定义则使用默认值
    
    // 获取或生成元素颜色
    let color = elementColors[element];
    if (!color) {
        // 如果颜色未定义，根据元素特性生成独特的颜色
        color = generateDistinctColor(element);
        // 将生成的颜色缓存到elementColors中
        elementColors[element] = color;
    }
    
    // 创建材质的键
    const materialKey = `${element}-ball`;
    
    // 如果材质不存在，创建新材质
    if (!atomMaterials[materialKey]) {
        atomMaterials[materialKey] = new THREE.MeshStandardMaterial({
            color: color, // 设置颜色
            metalness: 0.2,    // 低金属感
            roughness: 0.7,    // 较高粗糙度，减少强反射
            emissive: new THREE.Color(color).multiplyScalar(0.1), // 轻微自发光
            emissiveIntensity: 0.2, // 低自发光强度
            flatShading: false // 平滑着色
        });
    }
    
    // 创建球体几何体表示原子 - 增加细分以获得更光滑的外观
    const geometry = new THREE.SphereGeometry(radius * 0.6, 32, 32);
    
    // 创建网格对象并设置位置
    const mesh = new THREE.Mesh(geometry, atomMaterials[materialKey]);
    mesh.position.set(position[0], position[1], position[2]); // 设置原子位置
    
    // 添加轮廓以增强原子间的区分度
    const outlineGeometry = new THREE.SphereGeometry(radius * 0.63, 32, 32); // 稍大一点的球体作为轮廓
    const outlineMaterial = new THREE.MeshBasicMaterial({
        color: 0x000000, // 黑色轮廓
        side: THREE.BackSide, // 背面渲染
        transparent: true, // 启用透明度
        opacity: 0.1 // 低透明度
    });
    
    // 创建轮廓网格并添加为原子的子对象
    const outline = new THREE.Mesh(outlineGeometry, outlineMaterial);
    mesh.add(outline);
    
    // 添加用户数据（用于交互），存储原子的相关信息
    mesh.userData = {
        element: element, // 元素符号
        position: position, // 位置坐标
        properties: atom.properties, // 原子属性
        type: 'ball' // 标记为球模型
    };
    
    // 将原子添加到球体组
    ballsGroup.add(mesh);
    
    // 返回创建的网格对象，以便后续可能需要引用
    return mesh;
}

/**
 * 生成原子间的键连接
 * 根据原子位置计算可能的键，并添加到棍组
 * @param {Array} atoms - 原子数据数组
 */
function generateBonds(atoms) {
    // 创建键连接前，先清除所有现有的键
    while (sticksGroup.children.length > 0) {
        const object = sticksGroup.children[0];
        object.geometry.dispose();
        object.material.dispose();
        sticksGroup.remove(object);
    }
    
    // 用于跟踪已处理的键对，避免重复添加相同的键
    const bondPairs = new Set();
    
    // 遍历所有原子对，寻找可能的键连接
    for (let i = 0; i < atoms.length; i++) {
        const atom1 = atoms[i];
        const pos1 = atom1.position;
        const radius1 = atom1.properties.radius || 0.5;
        
        for (let j = i + 1; j < atoms.length; j++) {
            const atom2 = atoms[j];
            const pos2 = atom2.position;
            const radius2 = atom2.properties.radius || 0.5;
            
            // 计算两个原子之间的距离
            const dx = pos1[0] - pos2[0];
            const dy = pos1[1] - pos2[1];
            const dz = pos1[2] - pos2[2];
            const distance = Math.sqrt(dx*dx + dy*dy + dz*dz);
            
            // 根据元素类型和距离判断是否有键连接
            // 这里使用一个估算的键距离判断标准，可以根据需要调整
            // 合理的键距离通常是两个原子半径之和的1.2~1.8倍
            const bondThreshold = (radius1 + radius2) * 1.6;
            
            if (distance > 0 && distance < bondThreshold) {
                // 为避免重复添加，创建键的唯一标识符
                const bondId = [i, j].sort().join('-');
                
                if (!bondPairs.has(bondId)) {
                    bondPairs.add(bondId);
                    
                    // 创建键连接
                    addBond(atom1, atom2, distance);
                }
            }
        }
    }
}

/**
 * 添加键连接
 * 在两个原子之间创建圆柱体表示化学键
 * @param {Object} atom1 - 第一个原子数据
 * @param {Object} atom2 - 第二个原子数据
 * @param {number} distance - 两原子间的距离
 */
function addBond(atom1, atom2, distance) {
    const pos1 = atom1.position;
    const pos2 = atom2.position;
    
    // 获取元素颜色
    const color1 = elementColors[atom1.element] || 0x808080;
    const color2 = elementColors[atom2.element] || 0x808080;
    
    // 键的半径（可以调整）
    const bondRadius = 0.1;
    
    // 创建圆柱体几何体表示键
    const geometry = new THREE.CylinderGeometry(bondRadius, bondRadius, distance, 12);
    
    // 使用两端原子颜色的混合作为键的颜色
    const materialKey = `bond-${atom1.element}-${atom2.element}`;
    if (!atomMaterials[materialKey]) {
        atomMaterials[materialKey] = new THREE.MeshStandardMaterial({
            color: new THREE.Color(color1).lerp(new THREE.Color(color2), 0.5),
            metalness: 0.1,
            roughness: 0.8
        });
    }
    
    // 创建键的网格对象
    const bond = new THREE.Mesh(geometry, atomMaterials[materialKey]);
    
    // 计算键的中点位置
    const midpoint = {
        x: (pos1[0] + pos2[0]) / 2,
        y: (pos1[1] + pos2[1]) / 2,
        z: (pos1[2] + pos2[2]) / 2
    };
    
    // 设置键的位置为中点
    bond.position.set(midpoint.x, midpoint.y, midpoint.z);
    
    // 计算键的方向向量
    const direction = new THREE.Vector3(
        pos2[0] - pos1[0],
        pos2[1] - pos1[1],
        pos2[2] - pos1[2]
    ).normalize();
    
    // 默认圆柱体是沿Y轴的，需要将其旋转为沿键方向
    // 使用四元数计算从Y轴到键方向的旋转
    const quaternion = new THREE.Quaternion();
    quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    bond.setRotationFromQuaternion(quaternion);
    
    // 添加标识数据
    bond.userData = {
        atom1: atom1,
        atom2: atom2,
        type: 'stick'
    };
    
    // 将键添加到棍组
    sticksGroup.add(bond);
    
    return bond;
}

/**
 * 重置相机位置
 * 计算晶体结构的边界框，并根据其大小自动调整相机位置以确保整个结构可见
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
    
    // 将相机定位到立体中心的正面位置，增加距离系数以确保更好的视野
    const direction = new THREE.Vector3(1, 1, 1).normalize();
    camera.position.copy(center).add(direction.multiplyScalar(cameraDistance * 1.8));
    camera.lookAt(center);
    
    // 设置控制器的目标为晶体结构的中心，确保旋转围绕中心点进行
    controls.target.copy(center);
    
    // 更新控制器
    controls.update();
    
    console.log("相机已重置到中心位置:", center);
    console.log("相机距离:", cameraDistance);
    console.log("结构大小:", size);
}

/**
 * 显示加载指示器
 */
function showLoadingIndicator() {
    // 检查加载指示器是否已存在
    let loadingIndicator = document.getElementById('loading-indicator');
    
    // 如果不存在，创建新的加载指示器
    if (!loadingIndicator) {
        loadingIndicator = document.createElement('div');
        loadingIndicator.id = 'loading-indicator';
    loadingIndicator.style.position = 'absolute';
    loadingIndicator.style.top = '50%';
    loadingIndicator.style.left = '50%';
    loadingIndicator.style.transform = 'translate(-50%, -50%)';
        loadingIndicator.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
    loadingIndicator.style.padding = '20px';
        loadingIndicator.style.borderRadius = '10px';
        loadingIndicator.style.display = 'flex';
        loadingIndicator.style.flexDirection = 'column';
        loadingIndicator.style.alignItems = 'center';
        loadingIndicator.style.justifyContent = 'center';
        loadingIndicator.style.zIndex = '2000';
        loadingIndicator.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
        
        // 添加旋转动画
        const spinner = document.createElement('div');
        spinner.style.width = '40px';
        spinner.style.height = '40px';
        spinner.style.border = '4px solid #f3f3f3';
        spinner.style.borderTop = '4px solid #3498db';
        spinner.style.borderRadius = '50%';
        spinner.style.animation = 'spin 1s linear infinite';
        
        // 添加关键帧动画
        const style = document.createElement('style');
        style.textContent = `
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        `;
        document.head.appendChild(style);
        
        // 添加文本
        const text = document.createElement('div');
        text.textContent = '加载中...';
        text.style.marginTop = '10px';
        
        loadingIndicator.appendChild(spinner);
        loadingIndicator.appendChild(text);
        
        const viewerContainer = document.querySelector('.crystal-viewer');
        if (viewerContainer) {
            viewerContainer.appendChild(loadingIndicator);
        } else {
            document.body.appendChild(loadingIndicator);
        }
    } else {
        loadingIndicator.style.display = 'flex';
    }
}

/**
 * 隐藏加载指示器
 */
function hideLoadingIndicator() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

/**
 * 添加标题和原子图例
 * 在3D视图上方显示晶体结构的名称，在左侧显示元素图例
 * @param {Object} structureData - 晶体结构数据
 */
function addTitleAndLegend(structureData) {
    // 移除现有标题和图例
    const existingTitle = document.getElementById('crystal-title');
    if (existingTitle) {
        existingTitle.remove();
    }
    
    const existingLegend = document.getElementById('crystal-legend');
    if (existingLegend) {
        existingLegend.remove();
    }
    
    // 创建容器元素
    const infoContainer = document.createElement('div');
    infoContainer.style.position = 'absolute';
    infoContainer.style.top = '10px';
    infoContainer.style.left = '10px';
    infoContainer.style.color = '#000';
    infoContainer.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
    infoContainer.style.padding = '10px';
    infoContainer.style.borderRadius = '5px';
    infoContainer.style.fontFamily = 'Arial, sans-serif';
    infoContainer.style.maxWidth = '300px';
    infoContainer.style.zIndex = '1000';
    
    // 创建标题元素
    const title = document.createElement('div');
    title.id = 'crystal-title';
    title.style.fontWeight = 'bold';
    title.style.marginBottom = '8px';
    title.style.fontSize = '16px';
    
    // 获取结构名称
    let structureName = structureData.name || structureData.formula || `Structure ID: ${structureData.id || 'Unknown'}`;
    
    // 如果是原胞，添加标记
    if (structureData.isPrimitive) {
        structureName += ' (原胞)';
    }
    
    title.textContent = structureName;
    infoContainer.appendChild(title);
    
    // 创建图例元素
    const legend = document.createElement('div');
    legend.id = 'crystal-legend';
    
    // 查找结构中的所有元素并去重
    const elements = [...new Set(structureData.atoms.map(atom => atom.element))];
    
    // 对每个元素创建图例项
    elements.forEach(element => {
        const elementColor = elementColors[element] || 0x808080;
        const colorHex = '#' + elementColor.toString(16).padStart(6, '0');
        
        const legendItem = document.createElement('div');
        legendItem.style.display = 'flex';
        legendItem.style.alignItems = 'center';
        legendItem.style.marginBottom = '5px';
        
        // 创建颜色示例
        const colorSwatch = document.createElement('div');
        colorSwatch.style.width = '15px';
        colorSwatch.style.height = '15px';
        colorSwatch.style.backgroundColor = colorHex;
        colorSwatch.style.borderRadius = '50%';
        colorSwatch.style.marginRight = '8px';
        
        // 创建元素标签
        const elementLabel = document.createElement('span');
        elementLabel.textContent = element;
        
        // 将颜色样例和标签添加到图例项
        legendItem.appendChild(colorSwatch);
        legendItem.appendChild(elementLabel);
        
        // 将图例项添加到图例
        legend.appendChild(legendItem);
    });
    
    // 将图例添加到容器
    infoContainer.appendChild(legend);
    
    // 将容器添加到视图容器
    const container = renderer.domElement.parentElement;
    container.appendChild(infoContainer);
}

/**
 * 显示错误消息
 * 在界面上显示操作错误提示，几秒后自动消失
 * @param {string} message - 错误消息文本
 */
function showErrorMessage(message) {
    // 检查是否已存在错误消息框
    let errorMessage = document.getElementById('error-message');
    
    // 如果不存在，创建新的错误消息框
    if (!errorMessage) {
        errorMessage = document.createElement('div');
        errorMessage.id = 'error-message'; // 设置ID
        errorMessage.style.position = 'absolute'; // 绝对定位
        errorMessage.style.top = '20px'; // 顶部距离
        errorMessage.style.left = '50%'; // 水平居中
        errorMessage.style.transform = 'translateX(-50%)'; // 精确居中
        errorMessage.style.backgroundColor = 'rgba(220, 53, 69, 0.9)'; // 半透明红色背景
        errorMessage.style.color = 'white'; // 白色文字
        errorMessage.style.padding = '10px 20px'; // 内边距
        errorMessage.style.borderRadius = '5px'; // 圆角边框
        errorMessage.style.zIndex = '2000'; // 确保显示在最上层
        errorMessage.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)'; // 阴影效果
        errorMessage.style.minWidth = '200px'; // 最小宽度
        errorMessage.style.textAlign = 'center'; // 文字居中
        
        // 将错误消息框添加到视图容器或文档主体
        const viewerContainer = document.querySelector('.crystal-viewer');
        if (viewerContainer) {
            viewerContainer.appendChild(errorMessage);
        } else {
            document.body.appendChild(errorMessage);
        }
    }
    
    // 更新错误消息文本
    errorMessage.textContent = message;
    errorMessage.style.display = 'block'; // 显示错误消息
    
    // 3秒后自动隐藏错误消息
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 3000);
}

/**
 * 控制功能：向左旋转
 * 将晶体结构绕Y轴向左旋转15度
 */
function rotateLeft() {
    // 绕Y轴逆时针旋转π/12弧度（15度）
    crystalGroup.rotation.y -= Math.PI / 12;
}

/**
 * 控制功能：向右旋转
 * 将晶体结构绕Y轴向右旋转15度
 */
function rotateRight() {
    // 绕Y轴顺时针旋转π/12弧度（15度）
    crystalGroup.rotation.y += Math.PI / 12;
}

/**
 * 控制功能：重置视图
 * 将晶体结构恢复到初始位置和方向
 */
function resetView() {
    // 重置晶体组的旋转
    crystalGroup.rotation.set(0, 0, 0);
    // 重置轨道控制器，恢复初始视角
    controls.reset();
}

/**
 * 控制功能：切换自动旋转
 * 启用或禁用晶体结构的自动旋转动画
 */
function toggleSpin() {
    // 反转动画状态标志
    isAnimating = !isAnimating;
}

/**
 * 添加增强的坐标轴辅助
 * 创建固定在左下角的坐标轴系统，与主场景的旋转同步但保持独立位置
 */
function addEnhancedAxesHelper() {
    // 移除现有的坐标轴辅助
    scene.children.forEach(child => {
        if (child.userData && child.userData.isAxesHelper) {
            scene.remove(child);
        }
    });
    
    // 移除现有的坐标轴容器（如果存在）
    const existingContainer = document.getElementById('axes-container');
    if (existingContainer) {
        existingContainer.remove();
    }
    
    // 创建新的场景用于坐标轴，这样它可以独立于主场景
    const axesScene = new THREE.Scene();
    
    // 创建自定义坐标轴组
    const axesGroup = new THREE.Group();
    axesGroup.userData = { isAxesHelper: true };
    
    // 设置轴的长度和宽度 - 稍微加大尺寸提高可视性
    const axisLength = 4; // 更长的轴
    const axisWidth = 0.12; // 更粗的轴
    
    // 创建X轴（红色）
    const xAxisGeometry = new THREE.CylinderGeometry(axisWidth, axisWidth, axisLength, 16);
    xAxisGeometry.rotateZ(-Math.PI / 2);
    const xAxisMaterial = new THREE.MeshStandardMaterial({ 
        color: 0xFF0000, 
        metalness: 0.2, 
        roughness: 0.5,
        emissive: 0xFF0000,
        emissiveIntensity: 0.3 // 添加发光效果增强可视性
    });
    const xAxis = new THREE.Mesh(xAxisGeometry, xAxisMaterial);
    xAxis.position.set(axisLength / 2, 0, 0);
    
    // 创建Y轴（绿色）
    const yAxisGeometry = new THREE.CylinderGeometry(axisWidth, axisWidth, axisLength, 16);
    const yAxisMaterial = new THREE.MeshStandardMaterial({ 
        color: 0x00FF00, 
        metalness: 0.2, 
        roughness: 0.5,
        emissive: 0x00FF00,
        emissiveIntensity: 0.3
    });
    const yAxis = new THREE.Mesh(yAxisGeometry, yAxisMaterial);
    yAxis.position.set(0, axisLength / 2, 0);
    
    // 创建Z轴（蓝色）
    const zAxisGeometry = new THREE.CylinderGeometry(axisWidth, axisWidth, axisLength, 16);
    zAxisGeometry.rotateX(Math.PI / 2);
    const zAxisMaterial = new THREE.MeshStandardMaterial({ 
        color: 0x0000FF, 
        metalness: 0.2, 
        roughness: 0.5,
        emissive: 0x0000FF,
        emissiveIntensity: 0.3
    });
    const zAxis = new THREE.Mesh(zAxisGeometry, zAxisMaterial);
    zAxis.position.set(0, 0, axisLength / 2);
    
    // 创建箭头头部 - 更大的箭头
    const coneHeight = 0.6;
    const coneRadius = 0.25;
    
    // X轴箭头
    const xConeGeometry = new THREE.ConeGeometry(coneRadius, coneHeight, 16);
    xConeGeometry.rotateZ(-Math.PI / 2);
    const xCone = new THREE.Mesh(xConeGeometry, xAxisMaterial);
    xCone.position.set(axisLength, 0, 0);
    
    // Y轴箭头
    const yConeGeometry = new THREE.ConeGeometry(coneRadius, coneHeight, 16);
    const yCone = new THREE.Mesh(yConeGeometry, yAxisMaterial);
    yCone.position.set(0, axisLength, 0);
    
    // Z轴箭头
    const zConeGeometry = new THREE.ConeGeometry(coneRadius, coneHeight, 16);
    zConeGeometry.rotateX(Math.PI / 2);
    const zCone = new THREE.Mesh(zConeGeometry, zAxisMaterial);
    zCone.position.set(0, 0, axisLength);
    
    // 添加轴标签 - 更大的标签
    function createTextLabel(text, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 128; // 更大的画布
        canvas.height = 128;
        
        const context = canvas.getContext('2d');
        context.fillStyle = 'rgba(255, 255, 255, 0)';
        context.fillRect(0, 0, canvas.width, canvas.height);
        
        context.font = 'Bold 60px Arial'; // 更大的字体
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillStyle = '#' + color.toString(16).padStart(6, '0');
        context.fillText(text, canvas.width / 2, canvas.height / 2);
        
        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ 
            map: texture,
            transparent: true
        });
        
        return new THREE.Sprite(material);
    }
    
    // 创建标签
    const xLabel = createTextLabel('X', 0xFF0000);
    xLabel.position.set(axisLength + 0.8, 0, 0);
    xLabel.scale.set(1.2, 1.2, 1.2); // 更大的标签
    
    const yLabel = createTextLabel('Y', 0x00FF00);
    yLabel.position.set(0, axisLength + 0.8, 0);
    yLabel.scale.set(1.2, 1.2, 1.2);
    
    const zLabel = createTextLabel('Z', 0x0000FF);
    zLabel.position.set(0, 0, axisLength + 0.8);
    zLabel.scale.set(1.2, 1.2, 1.2);
    
    // 将所有组件添加到坐标轴组
    axesGroup.add(xAxis, yAxis, zAxis, xCone, yCone, zCone, xLabel, yLabel, zLabel);
    
    // 添加坐标系原点指示器 - 小球体标记原点
    const originGeometry = new THREE.SphereGeometry(0.15, 16, 16);
    const originMaterial = new THREE.MeshStandardMaterial({ 
        color: 0xFFFFFF, 
        emissive: 0xFFFFFF,
        emissiveIntensity: 0.5
    });
    const originMarker = new THREE.Mesh(originGeometry, originMaterial);
    originMarker.position.set(0, 0, 0);
    axesGroup.add(originMarker);
    
    // 创建固定在左下角的坐标轴容器 - 更大的容器
    const axesContainer = document.createElement('div');
    axesContainer.id = 'axes-container';
    axesContainer.style.position = 'absolute';
    axesContainer.style.bottom = '20px';
    axesContainer.style.left = '20px';
    axesContainer.style.width = '150px'; // 更大的渲染区域
    axesContainer.style.height = '150px';
    axesContainer.style.pointerEvents = 'none'; // 允许鼠标事件穿透
    axesContainer.style.zIndex = '1000'; // 确保在最上层
    
    // 创建渲染器并添加到容器
    const axesRenderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true
    });
    axesRenderer.setSize(150, 150); // 匹配容器大小
    axesRenderer.setClearColor(0x000000, 0); // 透明背景
    axesRenderer.setPixelRatio(window.devicePixelRatio); // 提高渲染清晰度
    axesContainer.appendChild(axesRenderer.domElement);
    
    // 获取主容器元素
    const container = renderer.domElement.parentElement;
    container.appendChild(axesContainer);
    
    // 创建独立的相机 - 调整视角以获得更好的观察角度
    const axesCamera = new THREE.PerspectiveCamera(50, 1, 0.1, 50);
    axesCamera.position.set(6, 6, 6); // 稍微远一点，以便看清整个坐标系
    axesCamera.lookAt(0, 0, 0);
    
    // 添加光源到坐标轴场景 - 更好的照明
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    axesScene.add(ambientLight);
    
    // 添加方向光以增强3D效果
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    axesScene.add(directionalLight);
    
    // 添加坐标轴组到独立场景
    axesScene.add(axesGroup);
    
    // 创建更新函数，会在主渲染循环中调用，使坐标轴与主场景同步旋转
    function renderAxes() {
        // 从主相机和控制器同步旋转信息到坐标轴
        if (camera && controls) {
            // 保存当前相机位置并计算方向向量
            const cameraPosition = new THREE.Vector3();
            camera.getWorldPosition(cameraPosition);
            
            // 计算相机到原点的方向向量并归一化
            const direction = new THREE.Vector3();
            direction.subVectors(new THREE.Vector3(0, 0, 0), cameraPosition).normalize();
            
            // 使用朝向和向上向量重新定位坐标轴摄像机
            // 保持坐标轴相机位置固定，但朝向与主相机同步
            const upVector = camera.up.clone();
            
            // 根据主相机方向计算坐标轴相机的位置
            // 保持距离固定但方向跟随主相机
            const distance = 8; // 固定距离
            const axesCameraPosition = new THREE.Vector3()
                .copy(direction)
                .multiplyScalar(-distance);
                
            // 更新坐标轴相机位置和朝向
            axesCamera.position.copy(axesCameraPosition);
            axesCamera.up.copy(upVector);
            axesCamera.lookAt(0, 0, 0);
        }
        
        // 渲染独立的坐标轴场景
        axesRenderer.render(axesScene, axesCamera);
    }
    
    // 导出渲染函数，使其可以被主循环调用
    window.renderAxes = renderAxes;
    
    // 首次渲染
    renderAxes();
    
    return { axesGroup, renderAxes, axesScene, axesCamera };
}

/**
 * 下载CIF文件
 */
function downloadCIFFile() {
    // Get current material ID
    const materialId = getCurrentMaterialId();
    if (!materialId) {
        showErrorMessage('Material ID not found');
        return;
    }
    
    // Get current supercell values if available
    const expansionValues = getExpansionValues();
    const cellType = document.querySelector('input[name="cellType"]:checked')?.value || 'primitive';
    
    // Build URL for download
    let url = `/api/database/functional_materials/structure/${materialId}/cif`;
    
    // Add supercell parameters if they're not all 1
    if (expansionValues.a > 1 || expansionValues.b > 1 || expansionValues.c > 1) {
        url += `?a=${expansionValues.a}&b=${expansionValues.b}&c=${expansionValues.c}&cellType=${cellType}`;
    }
    
    // Open download in new tab
    window.open(url, '_blank');
}

/**
 * 获取当前材料ID
 * @returns {string|null} 当前材料ID或null
 */
function getCurrentMaterialId() {
    // 从URL中提取ID
    const urlParams = new URLSearchParams(window.location.search);
    const id = urlParams.get('id');
    
    // 如果URL中有ID，直接返回
    if (id) {
        return id;
    }
    
    // 如果没有，尝试从window.currentStructureData获取
    if (window.currentStructureData && window.currentStructureData.id) {
        return window.currentStructureData.id;
    }
    
    // 如果没有，尝试从页面元素中获取
    // 检查多种可能的元素ID和类名
    const possibleIdElements = [
        document.getElementById('material-id'),
        document.getElementById('structure-id'),
        document.getElementById('crystal-id'),
        document.querySelector('.material-id'),
        document.querySelector('.structure-id'),
        document.querySelector('.crystal-id'),
        document.querySelector('[data-id]')
    ];
    
    // 检查第一个找到的非空元素
    for (const element of possibleIdElements) {
        if (element) {
            // 尝试从innerHTML、textContent、value或data-id属性获取ID
            const idValue = element.dataset?.id || element.value || element.textContent || element.innerHTML;
            if (idValue && typeof idValue === 'string') {
                const trimmedValue = idValue.trim();
                if (trimmedValue) {
                    return trimmedValue;
                }
            }
        }
    }
    
    // 尝试检查structureData.formula是否存在，如果存在，我们可以用formula作为id
    if (window.currentStructureData && window.currentStructureData.formula) {
        console.warn("Using structure formula as ID:", window.currentStructureData.formula);
        return window.currentStructureData.formula;
    }
    
    // 最后检查URL路径，看是否包含ID信息
    // 匹配新格式: /materials/IMR-{id}
    const pathMatch = window.location.pathname.match(/\/materials\/IMR-(\d+)/);
    if (pathMatch && pathMatch[1]) {
        return pathMatch[1];
    }
    
    // 创建一个临时ID，以确保不会失败
    const tempId = 'temp-' + Math.floor(Math.random() * 10000);
    console.warn("Using temporary ID:", tempId);
    return tempId;
}

/**
 * 创建原胞转换按钮
 * 添加一个简单的按钮，用于将晶体结构转换为原胞
 * @param {HTMLElement} container - 添加按钮的DOM容器
 */
function createPrimitiveCellButton(container) {
    // 创建主按钮
    const mainButton = document.createElement('button');
    mainButton.className = 'primitive-cell-button btn btn--secondary btn--sm';
    mainButton.textContent = 'Primitive Cell';
    mainButton.style.position = 'absolute';
    mainButton.style.bottom = '10px';
    mainButton.style.right = '10px';
    mainButton.style.zIndex = '1000';
    
    // 添加点击事件，转换为原胞
    mainButton.addEventListener('click', () => {
        convertToPrimitiveCell();
    });
    
    // 将按钮添加到容器
    container.appendChild(mainButton);
}

/**
 * 替换旧的超晶胞面板创建函数，保持API兼容性
 * @param {HTMLElement} container - 容器元素
 */
function createSupercellPanel(container) {
    // 创建扩胞控制面板容器
    const panel = document.createElement('div');
    panel.className = 'supercell-panel';
    panel.style.position = 'absolute';
    panel.style.right = '10px';
    panel.style.bottom = '10px';
    panel.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
    panel.style.padding = '10px';
    panel.style.borderRadius = '8px';
    panel.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)';
    panel.style.zIndex = '1000';
    panel.style.display = 'flex';
    panel.style.flexDirection = 'column';
    panel.style.gap = '8px';
    panel.style.minWidth = '220px';

    // 创建转换按钮
    const transformBtn = document.createElement('button');
    transformBtn.textContent = 'Transform';
    transformBtn.className = 'button-secondary';
    // 视觉交由 .btn 控制
    transformBtn.style.gap = '3px';
    panel.appendChild(transformBtn);

    // 创建编辑界面容器
    const editPanel = document.createElement('div');
    editPanel.className = 'edit-panel';
    editPanel.style.display = 'none';
    editPanel.style.flexDirection = 'column';
    editPanel.style.gap = '10px';

    // 创建三个方向的扩胞输入框
    const directions = ['X', 'Y', 'Z'];
    directions.forEach(dir => {
        const inputGroup = document.createElement('div');
        inputGroup.style.display = 'flex';
        inputGroup.style.alignItems = 'center';
        inputGroup.style.justifyContent = 'center';
        // 设置输入组内元素之间的间距为10像素
        inputGroup.style.gap = '8px';
        // 设置输入组底部外边距为5像素，使布局更紧凑
        inputGroup.style.marginBottom = '5px';

        const label = document.createElement('label');
        label.textContent = `${dir} Direction:`;
        // 设置标签宽度为80像素，减少留白
        label.style.width = '80px';
        // 统一字体大小为14像素
        label.style.fontSize = '14px';
        // 使用正常字重，保持一致性
        label.style.fontWeight = 'normal';
        // 设置文本右对齐,使标签文本与输入框之间有清晰的视觉分隔
        label.style.textAlign = 'right';

        const input = document.createElement('input');
        input.type = 'number';
        input.min = '1';
        input.value = '1';
        input.style.width = '80px';
        input.style.padding = '4px 8px';
        input.style.border = '1px solid #ccc';
        input.style.borderRadius = '4px';
        input.style.fontSize = '14px';
        input.style.transition = 'all 0.1s ease';
        input.style.textAlign = 'center';
        
        // 添加输入框悬停和焦点效果
        input.addEventListener('mouseover', () => {
            input.style.borderColor = '#2196F3';
            input.style.boxShadow = '0 0 5px rgba(33, 150, 243, 0.3)';
        });
        
        input.addEventListener('mouseout', () => {
            if (document.activeElement !== input) {
                input.style.borderColor = '#ccc';
                input.style.boxShadow = 'none';
            }
        });

        inputGroup.appendChild(label);
        inputGroup.appendChild(input);
        editPanel.appendChild(inputGroup);
    });

    // 创建按钮组
    const buttonGroup = document.createElement('div');
    buttonGroup.style.display = 'flex';
    buttonGroup.style.flexDirection = 'column'; /* [Fix 20251001] 竖向堆叠避免拥挤导致裁切 */
    buttonGroup.style.gap = '8px';
    buttonGroup.style.marginTop = '10px';
    buttonGroup.style.justifyContent = 'center';

    // 创建显示原胞按钮
    const primitiveBtn = document.createElement('button');
    primitiveBtn.textContent = 'Primitive Cell';
    primitiveBtn.className = 'button-secondary';
    primitiveBtn.style.width = '100%';
    primitiveBtn.style.whiteSpace = 'nowrap';

    // 创建显示传统胞按钮
    const conventionalBtn = document.createElement('button');
    conventionalBtn.textContent = 'Conventional Cell';
    conventionalBtn.className = 'button-secondary';
    conventionalBtn.style.width = '100%';
    conventionalBtn.style.whiteSpace = 'nowrap';

    // 创建完成按钮
    const doneBtn = document.createElement('button');
    doneBtn.textContent = 'Cell expansion';
    doneBtn.className = 'button-secondary';
    doneBtn.style.width = '100%';
    doneBtn.style.whiteSpace = 'nowrap';

    buttonGroup.appendChild(primitiveBtn);
    buttonGroup.appendChild(conventionalBtn);
    buttonGroup.appendChild(doneBtn);
    editPanel.appendChild(buttonGroup);

    panel.appendChild(editPanel);

    // 添加转换按钮点击事件
    transformBtn.addEventListener('click', () => {
        if (editPanel.style.display === 'none') {
            editPanel.style.display = 'flex';
            transformBtn.style.backgroundColor = '#f44336';
            transformBtn.innerHTML = '<i class="fas fa-times"></i> Close';
        } else {
            editPanel.style.display = 'none';
            transformBtn.style.backgroundColor = '#4CAF50';
            transformBtn.innerHTML = '<i class="fas fa-exchange-alt"></i> Transform';
        }
    });

    // 添加按钮点击事件
    primitiveBtn.addEventListener('click', () => {
        // 获取当前材料ID
        const materialId = window.currentMaterialId || getCurrentMaterialId();
        if (!materialId) {
            showErrorMessage('未找到材料ID');
            return;
        }

        // 显示加载指示器
        showLoadingIndicator();

        // 调用原胞API
        fetch(`/api/database/functional_materials/structure/${materialId}/primitive`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP错误! 状态码: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // 隐藏加载指示器
                hideLoadingIndicator();
                
                // 保存数据并标记为原胞
                window.currentStructureData = data;
                if (!data.id && materialId) {
                    data.id = materialId;
                }
                data.isPrimitive = true;
                
                // 渲染新的晶体结构
                renderCrystalStructure(data);
            })
            .catch(error => {
                console.error('获取原胞数据失败:', error);
                hideLoadingIndicator();
                showErrorMessage(`转换为原胞失败。${error.message || '请稍后重试。'}`);
            });

        // 关闭编辑面板
        editPanel.style.display = 'none';
        transformBtn.style.backgroundColor = '#4CAF50';
        transformBtn.innerHTML = '<i class="fas fa-exchange-alt"></i> Transform';
    });

    conventionalBtn.addEventListener('click', () => {
        // 获取当前材料ID
        const materialId = window.currentMaterialId || getCurrentMaterialId();
        if (!materialId) {
            showErrorMessage('未找到材料ID');
            return;
        }

        // 显示加载指示器
        showLoadingIndicator();

        // 调用传统胞API
        fetch(`/api/database/functional_materials/structure/${materialId}/conventional`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP错误! 状态码: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // 隐藏加载指示器
                hideLoadingIndicator();
                
                // 保存数据
                window.currentStructureData = data;
                if (!data.id && materialId) {
                    data.id = materialId;
                }
                
                // 渲染新的晶体结构
                renderCrystalStructure(data);
            })
            .catch(error => {
                console.error('获取传统胞数据失败:', error);
                hideLoadingIndicator();
                showErrorMessage(`转换为传统胞失败。${error.message || '请稍后重试。'}`);
            });

        // 关闭编辑面板
        editPanel.style.display = 'none';
        transformBtn.style.backgroundColor = '#4CAF50';
        transformBtn.innerHTML = '<i class="fas fa-exchange-alt"></i> Transform';
    });

    doneBtn.addEventListener('click', () => {
        const [x, y, z] = Array.from(editPanel.querySelectorAll('input')).map(input => parseInt(input.value));
        updateSupercell(x, y, z);
        editPanel.style.display = 'none';
        transformBtn.style.backgroundColor = '#4CAF50';
        transformBtn.innerHTML = '<i class="fas fa-exchange-alt"></i> Transform';
    });

    // 添加面板到容器
    container.appendChild(panel);
}

/**
 * 转换晶体结构为原胞
 * 请求API获取原胞数据并重新渲染晶体结构
 */
function convertToPrimitiveCell() {
    // 获取当前材料ID
    const materialId = window.currentMaterialId || getCurrentMaterialId();
    
    if (!materialId) {
        showErrorMessage('Material ID not found');
        console.error('Cannot determine material ID for primitive cell conversion');
        return;
    }
    
    // 显示加载指示器
    showLoadingIndicator();
    
    // 构建请求URL，请求原胞数据
    const url = `/api/database/functional_materials/structure/${materialId}/primitive`;
    
    console.log(`请求原胞数据: 材料ID=${materialId}`);
    
    // 发送请求获取原胞数据
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP错误! 状态码: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // 隐藏加载指示器
            hideLoadingIndicator();
            
            // 保存数据以供后续使用
            window.currentStructureData = data;
            if (!data.id && materialId) {
                data.id = materialId;
            }
            
            // 标记此结构为原胞
            data.isPrimitive = true;
            
            // 渲染新的晶体结构
            renderCrystalStructure(data);
        })
        .catch(error => {
            console.error('获取原胞数据失败:', error);
            hideLoadingIndicator();
            showErrorMessage(`转换为原胞失败。${error.message || '请稍后重试。'}`);
        });
}

/**
 * 更新原胞结构的标题和信息
 * @param {Object} structureData - 结构数据
 */
function updatePrimitiveCellTitle(structureData) {
    const titleElement = document.getElementById('crystal-title');
    if (titleElement) {
        const originalTitle = titleElement.textContent;
        titleElement.textContent = `${originalTitle} (Prim)`;
    }
}

/**
 * 更新添加标题和图例的函数，支持原胞标记
 * @param {Object} structureData - 结构数据
 */
function addTitleAndLegend(structureData) {
    // 移除现有标题和图例
    const existingTitle = document.getElementById('crystal-title');
    if (existingTitle) {
        existingTitle.remove();
    }
    
    const existingLegend = document.getElementById('crystal-legend');
    if (existingLegend) {
        existingLegend.remove();
    }
    
    // 创建容器元素
    const infoContainer = document.createElement('div');
    infoContainer.style.position = 'absolute';
    infoContainer.style.top = '10px';
    infoContainer.style.left = '10px';
    infoContainer.style.color = '#000';
    infoContainer.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
    infoContainer.style.padding = '10px';
    infoContainer.style.borderRadius = '5px';
    infoContainer.style.fontFamily = 'Arial, sans-serif';
    infoContainer.style.maxWidth = '300px';
    infoContainer.style.zIndex = '1000';
    
    // 创建标题元素
    const title = document.createElement('div');
    title.id = 'crystal-title';
    title.style.fontWeight = 'bold';
    title.style.marginBottom = '8px';
    title.style.fontSize = '16px';
    
    // 获取结构名称
    let structureName = structureData.name || structureData.formula || `Structure ID: ${structureData.id || 'Unknown'}`;
    
    // 如果是原胞，添加标记
    if (structureData.isPrimitive) {
        structureName += ' (Prim)';
    }
    
    title.textContent = structureName;
    infoContainer.appendChild(title);
    
    // 创建图例元素
    const legend = document.createElement('div');
    legend.id = 'crystal-legend';
    
    // 查找结构中的所有元素并去重
    const elements = [...new Set(structureData.atoms.map(atom => atom.element))];
    
    // 对每个元素创建图例项
    elements.forEach(element => {
        const elementColor = elementColors[element] || 0x808080;
        const colorHex = '#' + elementColor.toString(16).padStart(6, '0');
        
        const legendItem = document.createElement('div');
        legendItem.style.display = 'flex';
        legendItem.style.alignItems = 'center';
        legendItem.style.marginBottom = '5px';
        
        // 创建颜色示例
        const colorSwatch = document.createElement('div');
        colorSwatch.style.width = '15px';
        colorSwatch.style.height = '15px';
        colorSwatch.style.backgroundColor = colorHex;
        colorSwatch.style.borderRadius = '50%';
        colorSwatch.style.marginRight = '8px';
        
        // 创建元素标签
        const elementLabel = document.createElement('span');
        elementLabel.textContent = element;
        
        // 将颜色样例和标签添加到图例项
        legendItem.appendChild(colorSwatch);
        legendItem.appendChild(elementLabel);
        
        // 将图例项添加到图例
        legend.appendChild(legendItem);
    });
    
    // 将图例添加到容器
    infoContainer.appendChild(legend);
    
    // 将容器添加到视图容器
    const container = renderer.domElement.parentElement;
    container.appendChild(infoContainer);
}

/**
 * 切换晶胞类型
 * 在原胞和常规晶胞之间切换显示
 * @param {string} cellType - 晶胞类型，可选值为'primitive'(原胞)或'conventional'(常规晶胞)
 */
function changeCellType(cellType) {
    // 获取当前的扩胞参数值
    const expansionValues = getExpansionValues();
    
    // 使用新的晶胞类型重新加载结构
    updateSupercell(expansionValues.a, expansionValues.b, expansionValues.c, cellType);
}

/**
 * 获取当前扩胞参数值
 * 从界面控件中读取a、b、c三个方向的扩胞倍数
 * @returns {Object} 包含a、b、c三个方向扩胞倍数的对象
 */
function getExpansionValues() {
    // 安全地获取扩胞参数值的辅助函数
    try {
        // 尝试从UI元素中获取值（如果存在）
        const aElement = document.querySelector('.supercell-panel div:nth-child(2) div:nth-child(1) span');
        const bElement = document.querySelector('.supercell-panel div:nth-child(2) div:nth-child(2) span');
        const cElement = document.querySelector('.supercell-panel div:nth-child(2) div:nth-child(3) span');
        
        // 如果所有元素都存在，返回它们的值
        if (aElement && bElement && cElement) {
            return {
                a: parseInt(aElement.textContent, 10) || 1,
                b: parseInt(bElement.textContent, 10) || 1,
                c: parseInt(cElement.textContent, 10) || 1
            };
        }
        
        // 如果无法获取值，返回默认值
        return { a: 1, b: 1, c: 1 };
    } catch (error) {
        // 发生错误时记录并返回默认值
        console.error('Error getting supercell parameters:', error);
        return { a: 1, b: 1, c: 1 };
    }
}

/**
 * 更新超晶胞
 * 根据给定的参数创建和显示扩展的晶胞结构
 * @param {number} a - a方向的重复次数
 * @param {number} b - b方向的重复次数
 * @param {number} c - c方向的重复次数
 * @param {string} cellType - 晶胞类型，可选值为'primitive'(原胞)或'conventional'(常规晶胞)
 */
function updateSupercell(a, b, c, cellType) {
    // 获取当前材料ID - 首先检查全局变量，然后调用获取函数
    const materialId = window.currentMaterialId || getCurrentMaterialId();
    
    // 如果找不到材料ID，显示错误信息并退出
    if (!materialId) {
        showErrorMessage('未找到材料ID');
        console.error('Cannot determine material ID for supercell update');
        return;
    }
    
    // 显示加载指示器
    showLoadingIndicator();
    
    // 记录请求信息
    console.log(`Updating supercell: Material ID=${materialId}, a=${a}, b=${b}, c=${c}, Cell Type=${cellType}`);
    
    // 构建请求URL
    let url = `/api/database/functional_materials/structure/${materialId}/supercell?a=${a}&b=${b}&c=${c}`;
    
    // 如果提供了晶胞类型，添加到URL参数中
    if (cellType) {
        url += `&cellType=${cellType}`;
    }
    
    // 发送请求获取超晶胞数据
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP错误! 状态码: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // 隐藏加载指示器
            hideLoadingIndicator();
            
            // 存储数据以供后续使用
            window.currentStructureData = data;
            if (!data.id && materialId) {
                data.id = materialId;
            }
            
            // 渲染新的晶体结构
            renderCrystalStructure(data);
        })
        .catch(error => {
            console.error('Failed to get supercell data:', error);
            hideLoadingIndicator();
            showErrorMessage(`Failed to update supercell. ${error.message || 'Please try again later.'}`);
        });
}

// 导出公共函数
window.CrystalViewer = {
    init: initCrystalViewer,         // 初始化晶体查看器
    load: loadCrystalStructure,      // 加载晶体结构
    render: renderCrystalStructure,  // 直接渲染结构数据
    rotateLeft: rotateLeft,          // 向左旋转
    rotateRight: rotateRight,        // 向右旋转
    resetView: resetView,            // 重置视图
    toggleSpin: toggleSpin,          // 切换自动旋转
    takeScreenshot: takeScreenshot,  // 截图保存
    downloadCIFFile: downloadCIFFile, // 下载CIF文件
    updateSupercell: updateSupercell, // 更新超晶胞
    changeCellType: changeCellType,   // 切换晶胞类型
    changeModelType: changeModelType, // 切换模型类型
    convertToPrimitiveCell: convertToPrimitiveCell // 转换为原胞
};