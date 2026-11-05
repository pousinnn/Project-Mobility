const glCanvas = document.getElementById("glcanvas");
const info = document.getElementById("info");

let gl, program, textureProgram;
let nodes = {}, routes = {};
let agents = [];
let running = false;
let lastTime = 0;
const SPEED = 2.0; // world units per second; identical for all agents

const vertexShaderSource = `#version 300 es
in vec2 a_position;
in vec2 a_uv;
uniform vec2 u_translation;
uniform vec2 u_scale;
out vec2 v_uv;
void main() {
  vec2 p = a_position * u_scale + u_translation;
  gl_Position = vec4(p, 0.0, 1.0);
  v_uv = a_uv;
}`;

const fragmentShaderSource = `#version 300 es
precision mediump float;
in vec2 v_uv;
uniform sampler2D u_texture;
out vec4 outColor;
void main() {
  vec4 c = texture(u_texture, v_uv);
  if (c.a < 0.05) discard;
  outColor = c;
}`;

const colorVertex = `#version 300 es
in vec2 a_position;
uniform vec2 u_translation;
uniform vec2 u_scale;
void main() {
  vec2 p = a_position * u_scale + u_translation;
  gl_Position = vec4(p,0.0,1.0);
}`;
const colorFragment = `#version 300 es
precision mediump float;
uniform vec4 u_color;
out vec4 outColor;
void main(){ outColor=u_color; }`;

function shader(type, source) {
  const s = gl.createShader(type);
  gl.shaderSource(s, source);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
    throw new Error(gl.getShaderInfoLog(s));
  return s;
}
function makeProgram(vs, fs) {
  const p = gl.createProgram();
  gl.attachShader(p, shader(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, shader(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS))
    throw new Error(gl.getProgramInfoLog(p));
  return p;
}

function createTexture(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
      resolve(tex);
    };
    img.onerror = reject;
    img.src = url;
  });
}

function makeQuad() {
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1,-1, 0,0,  1,-1, 1,0,  -1,1, 0,1,
    -1,1, 0,1,   1,-1, 1,0,   1,1, 1,1
  ]), gl.STATIC_DRAW);

  const pos = gl.getAttribLocation(textureProgram, "a_position");
  const uv = gl.getAttribLocation(textureProgram, "a_uv");
  gl.enableVertexAttribArray(pos);
  gl.vertexAttribPointer(pos,2,gl.FLOAT,false,16,0);
  gl.enableVertexAttribArray(uv);
  gl.vertexAttribPointer(uv,2,gl.FLOAT,false,16,8);
  return vao;
}

function resize() {
  const dpr = devicePixelRatio || 1;
  glCanvas.width = innerWidth*dpr;
  glCanvas.height = innerHeight*dpr;
  glCanvas.style.width = innerWidth+"px";
  glCanvas.style.height = innerHeight+"px";
  gl.viewport(0,0,glCanvas.width,glCanvas.height);
}

function project(point) {
  const xs = Object.values(nodes).map(n=>n.point[0]);
  const ys = Object.values(nodes).map(n=>n.point[1]);
  const minX=Math.min(...xs), maxX=Math.max(...xs);
  const minY=Math.min(...ys), maxY=Math.max(...ys);
  const px=(point[0]-minX)/(maxX-minX || 1);
  const py=(point[1]-minY)/(maxY-minY || 1);
  return [px*1.7-0.85, py*1.5-0.70];
}

function makeAgents() {
  agents = Object.entries(routes).map(([id, route]) => ({
    id:Number(id), route, segment:0, t:0, done:route.length<2
  }));
}

function step(dt) {
  let allDone=true;
  for (const a of agents) {
    if (a.done) continue;
    allDone=false;
    const p0=nodes[a.route[a.segment]].point;
    const p1=nodes[a.route[a.segment+1]].point;
    const dx=p1[0]-p0[0], dy=p1[1]-p0[1], dz=p1[2]-p0[2];
    const dist=Math.hypot(dx,dy,dz);
    a.t += SPEED*dt/Math.max(dist,0.00001);
    while (a.t >= 1) {
      a.t -= 1;
      a.segment++;
      if (a.segment >= a.route.length-1) {
        a.segment=a.route.length-1;
        a.t=0;
        a.done=true;
        break;
      }
    }
  }
  // The simulation ends only after every agent has reached its final route node.
  if (agents.length && agents.every(a=>a.done)) running=false;
}

function agentPosition(a) {
  const node = nodes[a.route[a.segment]];
  if (a.done || a.segment>=a.route.length-1) return node.point;
  const next=nodes[a.route[a.segment+1]];
  return [
    node.point[0]+(next.point[0]-node.point[0])*a.t,
    node.point[1]+(next.point[1]-node.point[1])*a.t,
    node.point[2]+(next.point[2]-node.point[2])*a.t
  ];
}

function drawSprite(tex, pos, scale) {
  gl.useProgram(textureProgram);
  gl.bindVertexArray(quad);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D,tex);
  gl.uniform1i(gl.getUniformLocation(textureProgram,"u_texture"),0);
  const p=project(pos);
  gl.uniform2f(gl.getUniformLocation(textureProgram,"u_translation"),p[0],p[1]);
  gl.uniform2f(gl.getUniformLocation(textureProgram,"u_scale"),scale,scale);
  gl.drawArrays(gl.TRIANGLES,0,6);
}

function draw() {
  gl.clearColor(0.07,0.07,0.07,1);
  gl.clear(gl.COLOR_BUFFER_BIT);

  for (const n of Object.values(nodes)) {
    drawSprite(n.dirt ? fullTex : emptyTex, n.point, 0.055);
  }
  for (const a of agents) {
    drawSprite(robotTex, agentPosition(a), 0.085);
  }

  // Labels are rendered as HTML canvas overlay elements.
  updateLabels();
  const status = running ? "Running" : "Simulation stopped";
  const states = agents.map(a=>`Agent ${a.id}: ${a.done ? "finished" : "moving"}`).join(" | ");
  info.textContent = `${status} | ${states} | Speed: ${SPEED} units/s`;
}

function updateLabels() {
  document.querySelectorAll(".node-label").forEach(e=>e.remove());
  for (const n of Object.values(nodes)) {
    const p=project(n.point);
    const x=(p[0]+1)*0.5*innerWidth;
    const y=(1-(p[1]+1)*0.5)*innerHeight;
    const d=document.createElement("div");
    d.className="node-label";
    d.textContent=`Node ${n.node}`;
    d.style.cssText=`position:fixed;left:${x+12}px;top:${y-8}px;color:white;font-weight:bold;font-size:14px;text-shadow:1px 1px 2px #000;pointer-events:none`;
    document.body.appendChild(d);
  }
}

function animate(t) {
  const dt=Math.min((t-lastTime)/1000,0.05);
  lastTime=t;
  if(running) step(dt);
  draw();
  requestAnimationFrame(animate);
}

async function start() {
  gl=glCanvas.getContext("webgl2",{alpha:false});
  if(!gl) { info.textContent="WebGL2 is not supported by this browser."; return; }

  program=makeProgram(colorVertex,colorFragment);
  textureProgram=makeProgram(vertexShaderSource,fragmentShaderSource);
  quad=makeQuad();

  const response=await fetch("/api/data");
  const data=await response.json();
  nodes=data.nodes; routes=data.routes;
  makeAgents();

  [robotTex,fullTex,emptyTex]=await Promise.all([
    createTexture("/static/images/robot.png"),
    createTexture("/static/images/node_full.png"),
    createTexture("/static/images/node_empty.png")
  ]);

  resize();
  addEventListener("resize",resize);
  running=true;
  requestAnimationFrame(animate);
}

let quad, robotTex, fullTex, emptyTex;
start().catch(err=>{ console.error(err); info.textContent="Error: "+err.message; });
