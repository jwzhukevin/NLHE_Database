// JSmol控制函数

// 等待JSmol初始化完成的Promise
let jmolReady = false;

// 在JSmol初始化完成时设置标志
function setJmolReady() {
    jmolReady = true;
}

// 检查JSmol是否准备就绪
function checkJmolReady() {
    if (!jmolReady) {
        console.warn('JSmol not ready yet');
        return false;
    }
    return true;
}

function rotateLeft() {
    if (!checkJmolReady()) return;
    try {
        Jmol.script(jmolApplet, 'rotate y -90');
    } catch(e) {
        console.error('Error rotating left:', e);
    }
}

function rotateRight() {
    if (!checkJmolReady()) return;
    try {
        Jmol.script(jmolApplet, 'rotate y 90');
    } catch(e) {
        console.error('Error rotating right:', e);
    }
}

function resetView() {
    if (!checkJmolReady()) return;
    try {
        Jmol.script(jmolApplet, 'reset');
        Jmol.script(jmolApplet, 'wireframe off; spacefill 20%;');
    } catch(e) {
        console.error('Error resetting view:', e);
    }
}

let isSpinning = false;

function toggleSpin() {
    if (!checkJmolReady()) return;
    try {
        isSpinning = !isSpinning;
        Jmol.script(jmolApplet, isSpinning ? 'spin on' : 'spin off');
    } catch(e) {
        console.error('Error toggling spin:', e);
    }
}