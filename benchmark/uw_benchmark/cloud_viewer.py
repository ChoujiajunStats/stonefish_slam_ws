"""Standalone, offline viewer of measured points. No synthesized geometry."""
import json
import numpy as np


def write_viewer(path,xyz,rgb,trajectory,coverage):
    step=max(1,len(xyz)//90000);points=xyz[::step];colors=rgb[::step]
    center=(points.min(axis=0)+points.max(axis=0))/2;extent=float(max(np.ptp(points,axis=0)))
    payload=json.dumps(dict(points=np.round(points-center,3).tolist(),colors=colors.tolist(),
        trajectory=np.round(np.asarray(trajectory)[::max(1,len(trajectory)//4000)]-center,3).tolist(),extent=extent),separators=(',',':'))
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>Porth 实际 SLAM 重建</title>
<style>body{margin:0;background:#101722;color:#e6edf3;font:15px system-ui}header{position:fixed;top:18px;left:22px;background:#101722dd;padding:16px;border:1px solid #405060;border-radius:10px;max-width:510px}h1{font-size:20px;margin:0 0 9px}p{margin:6px 0;color:#adbac7}button{background:#273648;color:white;border:1px solid #58718a;padding:7px 12px;border-radius:5px;cursor:pointer}canvas{display:block;width:100vw;height:100vh}label{padding:0 8px;font-size:13px}</style>
<canvas id="canvas"></canvas><header><h1>Porth · 实际双目 SLAM 点云</h1>
<p>拖动旋转 · 滚轮缩放 · Shift + 拖动平移</p><p>全视觉表面覆盖（0.30 m）：COVERAGE</p>
<p>点云来自传感器数据库，空缺保持原样，未混入原始洞穴模型。</p>
<button id="reset">重置视角</button> <button id="top">俯视</button><label><input id="track" type="checkbox" checked>实际采集轨迹（真值辅助控制）</label></header>
<script>const data=PAYLOAD,canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');
let az=-.7,el=.75,zoom=1,pan=[0,0],last=null;const colors=data.colors.map(c=>`rgb(${c[0]},${c[1]},${c[2]})`);
function draw(){const w=canvas.width=innerWidth*devicePixelRatio,h=canvas.height=innerHeight*devicePixelRatio;
ctx.fillStyle='#101722';ctx.fillRect(0,0,w,h);const scale=Math.min(w,h)*.85/data.extent*zoom;
let ca=Math.cos(az),sa=Math.sin(az),ce=Math.cos(el),se=Math.sin(el);
function project(p){let x=ca*p[0]-sa*p[1],y=sa*p[0]+ca*p[1];return [w/2+scale*x+pan[0]*devicePixelRatio,h/2-scale*(se*y+ce*p[2])+pan[1]*devicePixelRatio,ce*y-se*p[2]];}
let order=data.points.map((p,i)=>[project(p),i]);order.sort((a,b)=>a[0][2]-b[0][2]);let size=Math.max(1,1.3*devicePixelRatio);
for(const [p,i] of order){ctx.fillStyle=colors[i];ctx.fillRect(p[0],p[1],size,size);}
if(document.getElementById('track').checked){ctx.strokeStyle='#ff9345';ctx.lineWidth=1.3*devicePixelRatio;ctx.beginPath();data.trajectory.forEach((p,i)=>{let q=project(p);i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]);});ctx.stroke();}}
canvas.onpointerdown=e=>{last=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId)};
canvas.onpointerup=()=>last=null;canvas.onpointermove=e=>{if(!last)return;let dx=e.clientX-last[0],dy=e.clientY-last[1];if(e.shiftKey){pan[0]+=dx;pan[1]+=dy}else{az+=dx*.006;el=Math.max(-1.56,Math.min(1.56,el+dy*.006))}last=[e.clientX,e.clientY];draw()};
canvas.onwheel=e=>{e.preventDefault();zoom=Math.max(.2,Math.min(40,zoom*Math.exp(-e.deltaY*.001)));draw()};
document.getElementById('reset').onclick=()=>{az=-.7;el=.75;zoom=1;pan=[0,0];draw()};document.getElementById('top').onclick=()=>{az=0;el=Math.PI/2;draw()};document.getElementById('track').onchange=draw;onresize=draw;draw();</script></html>'''
    path.write_text(html.replace('PAYLOAD',payload).replace('COVERAGE',f'{coverage:.1%}'),encoding='utf-8')
