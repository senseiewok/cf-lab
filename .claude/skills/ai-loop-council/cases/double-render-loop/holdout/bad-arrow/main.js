import * as THREE from 'three';
const renderer = new THREE.WebGLRenderer();
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
const tick = () => {
  renderer.render(scene, camera);
  window.requestAnimationFrame(tick);
};
renderer.setAnimationLoop(tick);
