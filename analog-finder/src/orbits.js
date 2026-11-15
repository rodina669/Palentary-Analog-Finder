import * as THREE from 'three';
import gsap from 'gsap';

export function initOrbits(container, onPick) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 3000);
  const HOME = new THREE.Vector3(0, 52, 78);
  camera.position.copy(HOME);
  const lookAt = new THREE.Vector3(0, 0, 0);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const loader = new THREE.TextureLoader();
  const tex = (name) => {
    const t = loader.load(`/tex/${name}.jpg`);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  };

  // ---------- نجوم ----------
  const starPos = [];
  for (let i = 0; i < 1500; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(500 + Math.random() * 500);
    starPos.push(v.x, v.y, v.z);
  }
  const starGeo = new THREE.BufferGeometry();
  starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
  scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 2 })));

  // ---------- إضاءة ----------
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  scene.add(new THREE.PointLight(0xffffff, 2.5, 0, 0)); // من الشمس

  // ---------- شمس ----------
  const sun = new THREE.Mesh(
    new THREE.SphereGeometry(10, 48, 48),
    new THREE.MeshBasicMaterial({ map: tex('sun') })
  );
  scene.add(sun);

  // ---------- كواكب ----------
  const hits = [];
  function makeBody(name, radius, texName, hitRadius) {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 48, 48),
      new THREE.MeshStandardMaterial({ map: tex(texName), roughness: 1 })
    );
    // كرة شفافة أكبر عشان الضغط يبقى سهل (خصوصاً على القمر الصغير)
    const hit = new THREE.Mesh(
      new THREE.SphereGeometry(hitRadius, 12, 12),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
    );
    hit.userData = { name, mesh };
    mesh.add(hit);
    scene.add(mesh);
    return { mesh, hit, radius };
  }

  const earth = makeBody('earth', 3, 'earth', 3);
  const mars  = makeBody('mars', 2.4, 'mars', 5);
  const moon  = makeBody('moon', 1, 'moon', 3);
  hits.push(mars.hit, moon.hit);

  // ---------- خطوط المدارات ----------
  const R_EARTH = 26, R_MARS = 38, R_MOON = 6;
  function makeRing(r) {
    const pts = [];
    for (let i = 0; i < 128; i++) {
      const t = (i / 128) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(t) * r, 0, Math.sin(t) * r));
    }
    return new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0x4a5280, transparent: true, opacity: 0.6 })
    );
  }
  scene.add(makeRing(R_EARTH), makeRing(R_MARS));
  const moonRing = makeRing(R_MOON);
  scene.add(moonRing);

  // ---------- أسماء الكواكب ----------
  const labels = [];
  function makeLabel(text, body) {
    const c = document.createElement('canvas');
    c.width = 256; c.height = 64;
    const ctx = c.getContext('2d');
    ctx.font = '700 34px system-ui, sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.fillText(text, 128, 44);
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthTest: false })
    );
    sprite.scale.set(16, 4, 1);
    scene.add(sprite);
    labels.push({ sprite, body });
  }
  makeLabel('Earth', earth);
  makeLabel('Mars', mars);
  makeLabel('Moon', moon);

  // ---------- الحركة ----------
  let tEarth = 0, tMars = 2, tMoon = 0;
  let paused = false, picking = false, active = true;
  const clock = new THREE.Clock();

  function tick() {
    requestAnimationFrame(tick);
    const dt = Math.min(clock.getDelta(), 0.05);
    if (!active) return;

    if (!paused) {
      tEarth += dt * 0.25;
      tMars  += dt * 0.13;
      tMoon  += dt * 1.1;
      sun.rotation.y += dt * 0.05;
      earth.mesh.rotation.y += dt * 0.5;
      mars.mesh.rotation.y  += dt * 0.5;
      moon.mesh.rotation.y  += dt * 0.2;
    }

    earth.mesh.position.set(Math.cos(tEarth) * R_EARTH, 0, Math.sin(tEarth) * R_EARTH);
    mars.mesh.position.set(Math.cos(tMars) * R_MARS, 0, Math.sin(tMars) * R_MARS);
    moon.mesh.position.set(
      earth.mesh.position.x + Math.cos(tMoon) * R_MOON,
      0,
      earth.mesh.position.z + Math.sin(tMoon) * R_MOON
    );
    moonRing.position.copy(earth.mesh.position);

    labels.forEach(({ sprite, body }) => {
      sprite.position.copy(body.mesh.position);
      sprite.position.y += body.radius + 3;
    });

    camera.lookAt(lookAt);
    renderer.render(scene, camera);
  }
  tick();

  // ---------- الضغط على الكواكب ----------
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();

  function hitAt(e) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    return raycaster.intersectObjects(hits, false)[0];
  }

  renderer.domElement.addEventListener('pointermove', (e) => {
    if (picking) return;
    renderer.domElement.style.cursor = hitAt(e) ? 'pointer' : 'default';
  });

  renderer.domElement.addEventListener('click', (e) => {
    if (picking) return;
    const h = hitAt(e);
    if (!h) return;
    const { name, mesh } = h.object.userData;
    pick(name, mesh);
  });

  function pick(name, mesh) {
    picking = true;
    paused = true;
    labels.forEach(l => (l.sprite.visible = false));

    const p = mesh.getWorldPosition(new THREE.Vector3());
    const r = mesh.geometry.parameters.radius;
    const dir = camera.position.clone().sub(p).normalize();
    const dest = p.clone().add(dir.multiplyScalar(r * 3.2));

    gsap.timeline({ onComplete: () => onPick(name) })
      .to(lookAt, { x: p.x, y: p.y, z: p.z, duration: 1.8, ease: 'power2.inOut' }, 0)
      .to(camera.position, { x: dest.x, y: dest.y, z: dest.z, duration: 1.8, ease: 'power2.inOut' }, 0);
  }

  // ---------- مقاس الشاشة ----------
  function homeForSize(w, h) {
    const aspect = w / Math.max(h, 1);
    if (aspect < 0.75) return { x: 0, y: 72, z: 108 };
    if (aspect < 1.05) return { x: 0, y: 60, z: 92 };
    return { x: 0, y: 52, z: 78 };
  }

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (!picking) {
      const home = homeForSize(w, h);
      HOME.set(home.x, home.y, home.z);
      camera.position.copy(HOME);
    }
  }
  window.addEventListener('resize', resize);
  resize();

  return {
    setActive(v) { active = v; },
    reset() {
      gsap.killTweensOf(camera.position);
      gsap.killTweensOf(lookAt);
      camera.position.copy(HOME);
      lookAt.set(0, 0, 0);
      labels.forEach(l => (l.sprite.visible = true));
      picking = false;
      paused = false;
      active = true;
      resize();
    },
  };
}