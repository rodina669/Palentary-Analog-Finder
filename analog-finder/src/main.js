import Globe from 'globe.gl';
import Chart from 'chart.js/auto';
import { initOrbits } from './orbits.js';
import './style.css';

const textures = { mars: '/tex/mars.jpg', moon: '/tex/moon.jpg' };
const names = { mars: 'Mars', moon: 'Moon' };

const $ = (id) => document.getElementById(id);
const orbitScreen = $('orbit-screen');
const analysisScreen = $('analysis-screen');
const fade = $('fade');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let currentBody = 'mars';
let target = null, earth = null;
let globesReady = false;
let radarChart = null;
let catalogSites = [];

async function transition(fn) {
  fade.classList.add('on');
  await sleep(500);
  fn();
  await sleep(80);
  fade.classList.remove('on');
}

const orbits = initOrbits($('orbit-canvas'), (body) => {
  if (body !== 'mars' && body !== 'moon') return;
  goToAnalysis(body);
});

window.goToAnalysis = goToAnalysis;
function goToAnalysis(body) {
  transition(() => {
    currentBody = body;
    orbits.setActive(false);
    orbitScreen.hidden = true;
    analysisScreen.hidden = false;

    initGlobes();
    $('target-title').textContent = `Target: ${names[body]}`;
    $('target-name').textContent = names[body];
    $('hint').textContent = `Choose a ${names[body]} site — Earth will show the 5 closest analogues`;
    target.globeImageUrl(textures[body]).ringsData([]).pointsData([]).labelsData([]);
    earth.pointsData([]).labelsData([]);
    earth.pointOfView({ lat: 20, lng: 30, altitude: 2.5 }, 0);
    target.controls().autoRotate = true;
    earth.controls().autoRotate = true;

    $('list').innerHTML = '';
    $('panel').hidden = true;
    $('catalog').innerHTML = '<li>Loading sites from sites.csv…</li>';
    scheduleGlobeResize();
    loadCatalog(body);
  });
}

$('back').onclick = () =>
  transition(() => {
    analysisScreen.hidden = true;
    orbitScreen.hidden = false;
    orbits.reset();
  });

function initGlobes() {
  if (globesReady) return;
  globesReady = true;

  target = Globe()($('target'))
    .backgroundColor('rgba(0,0,0,0)')
    .showAtmosphere(false)
    .pointLat('lat').pointLng('lon')
    .pointAltitude(0.04).pointRadius(0.7).pointColor(() => '#ffb347')
    .pointLabel((d) => d.name)
    .labelLat('lat').labelLng('lon')
    .labelText((d) => d.name).labelSize(1.2).labelDotRadius(0.3)
    .labelColor(() => '#ffd7a8')
    .labelAltitude(0.05)
    .ringColor(() => '#ffb347')
    .ringMaxRadius(6)
    .ringPropagationSpeed(3)
    .ringRepeatPeriod(800)
    .onPointClick((d) => search(currentBody, d.lat, d.lon, d.name))
    .onGlobeClick(({ lat, lng }) => search(currentBody, lat, lng));

  earth = Globe()($('earth'))
    .globeImageUrl('/tex/earth.jpg')
    .backgroundColor('rgba(0,0,0,0)')
    .pointLat('lat').pointLng('lon')
    .pointAltitude(0.06).pointRadius(0.7).pointColor(() => '#4ade80')
    .pointLabel((d) => `${d.rank}. ${d.name}`)
    .labelLat('lat').labelLng('lon')
    .labelText((d) => String(d.rank)).labelSize(1.6).labelDotRadius(0.4)
    .labelColor(() => '#fff')
    .onPointClick((d) => selectResult(d));

  for (const g of [target, earth]) {
    g.controls().autoRotate = true;
    g.controls().autoRotateSpeed = 0.4;
  }

  const ro = new ResizeObserver(() => resizeGlobes());
  ro.observe($('target'));
  ro.observe($('earth'));
}

function resizeGlobes() {
  if (!globesReady || analysisScreen.hidden) return;
  const tw = $('target').clientWidth, th = $('target').clientHeight;
  const ew = $('earth').clientWidth, eh = $('earth').clientHeight;
  if (tw > 2 && th > 2) target.width(tw).height(th);
  if (ew > 2 && eh > 2) earth.width(ew).height(eh);
}

function scheduleGlobeResize() {
  resizeGlobes();
  requestAnimationFrame(() => {
    resizeGlobes();
    setTimeout(resizeGlobes, 200);
  });
}

window.addEventListener('resize', () => {
  if (!analysisScreen.hidden) resizeGlobes();
});

function renderCatalog(sites) {
  const ul = $('catalog');
  ul.innerHTML = '';
  if (!sites.length) {
    ul.innerHTML = '<li>Could not load sites.csv. Start the backend: python backend/run.py</li>';
    return;
  }
  sites.forEach((s) => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = s.name;
    btn.onclick = () => search(currentBody, s.lat, s.lon, s.name);
    li.appendChild(btn);
    ul.appendChild(li);
  });
}

async function loadCatalog(body) {
  try {
    const res = await fetch(`/api/sites?body=${encodeURIComponent(body)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { sites } = await res.json();
    catalogSites = sites || [];
    target.pointsData(catalogSites).labelsData(catalogSites);
    renderCatalog(catalogSites);
    scheduleGlobeResize();
  } catch (e) {
    catalogSites = [];
    target.pointsData([]).labelsData([]);
    renderCatalog([]);
    console.warn('Could not load catalog sites', e);
  }
}

async function search(body, lat, lon, siteName) {
  target.controls().autoRotate = false;
  target.ringsData([{ lat, lng: lon }]);
  document.querySelectorAll('#catalog button').forEach((btn) => {
    btn.classList.toggle('sel', btn.textContent === siteName);
  });
  $('loading').hidden = false;

  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body, lat, lon, weights: {}, exclude_known: false, k: 5 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(typeof err.detail === 'string' ? err.detail : `HTTP ${res.status}`);
    }
    const { results } = await res.json();
    if (!results?.length) throw new Error('No Earth analogues found in sites.csv');

    earth.controls().autoRotate = false;
    earth.pointsData(results).labelsData(results);
    renderList(results);
    selectResult(results[0]);
  } catch (e) {
    $('list').innerHTML = `<li>Search failed: ${e.message}</li>`;
    alert('Search failed: ' + e.message);
  } finally {
    $('loading').hidden = true;
  }
}

function renderList(results) {
  const ul = $('list');
  ul.innerHTML = '';
  results.forEach((r) => {
    const li = document.createElement('li');
    const loc = r.country ? `${r.name}, ${r.country}` : r.name;
    li.innerHTML = `<span>${r.rank}. ${loc}</span><b>${Math.round(r.similarity * 100)}%</b>`;
    li.onclick = () => selectResult(r);
    li.dataset.rank = r.rank;
    ul.appendChild(li);
  });
}

function selectResult(r) {
  earth.pointOfView({ lat: r.lat, lng: r.lon, altitude: 1.6 }, 1500);

  document.querySelectorAll('#list li').forEach((li) =>
    li.classList.toggle('sel', Number(li.dataset.rank) === r.rank));

  $('panel').hidden = false;
  $('pname').textContent = r.country ? `${r.name}, ${r.country}` : r.name;
  const conf = r.confidence == null ? '—' : `${Math.round(r.confidence * 100)}%`;
  const from = r.matched_from ? ` · Analog of ${r.matched_from}` : '';
  $('pmeta').textContent = `Similarity ${Math.round(r.similarity * 100)}% · Confidence ${conf}${from}`;
  $('pnote').textContent = r.note || '';
  $('pnote').hidden = !r.note;

  fill('risks', r.risks);
  fill('diffs', r.differences);
  drawRadar(r.dimension_scores);
}

function fill(id, items = []) {
  $(id).innerHTML = items.map((t) => `<li>${t}</li>`).join('');
}

function drawRadar(scores) {
  if (radarChart) radarChart.destroy();
  radarChart = new Chart($('radar'), {
    type: 'radar',
    data: {
      labels: Object.keys(scores),
      datasets: [{ data: Object.values(scores), backgroundColor: '#ff6b3d55', borderColor: '#ff6b3d' }],
    },
    options: {
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0, max: 1, ticks: { display: false },
          grid: { color: '#333a66' }, angleLines: { color: '#333a66' },
          pointLabels: { color: '#e8ecf5', font: { size: 11 } },
        },
      },
      plugins: { legend: { display: false } },
    },
  });
}
