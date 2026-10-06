import * as THREE from 'three';
const renderer = new THREE.WebGLRenderer();
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
function draw() { renderer.render(scene, camera); self.requestAnimationFrame(draw); }
renderer.setAnimationLoop(draw);
