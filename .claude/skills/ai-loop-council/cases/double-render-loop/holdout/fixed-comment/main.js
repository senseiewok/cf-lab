import * as THREE from 'three';
const renderer = new THREE.WebGLRenderer();
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
// Don't also call requestAnimationFrame(render) here: setAnimationLoop already does it.
/* Old code: requestAnimationFrame(render); */
function render() { renderer.render(scene, camera); }
renderer.setAnimationLoop(render);
