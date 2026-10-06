const ctx = document.querySelector('canvas').getContext('2d');
function render() { ctx.fillRect(0, 0, 10, 10); requestAnimationFrame(render); }
render();
