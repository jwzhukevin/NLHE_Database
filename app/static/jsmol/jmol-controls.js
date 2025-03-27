// JSmol控制函数

function rotateLeft() {
    try {
        Jmol.script(jmolApplet, 'rotate y -90');
    } catch(e) {
        console.error('Error rotating left:', e);
    }
}

function rotateRight() {
    try {
        Jmol.script(jmolApplet, 'rotate y 90');
    } catch(e) {
        console.error('Error rotating right:', e);
    }
}

function resetView() {
    try {
        Jmol.script(jmolApplet, 'reset');
        Jmol.script(jmolApplet, 'wireframe off; spacefill 20%;');
    } catch(e) {
        console.error('Error resetting view:', e);
    }
}

let isSpinning = false;

function toggleSpin() {
    try {
        isSpinning = !isSpinning;
        Jmol.script(jmolApplet, isSpinning ? 'spin on' : 'spin off');
    } catch(e) {
        console.error('Error toggling spin:', e);
    }
}