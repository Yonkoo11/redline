import { spawn } from 'node:child_process';
const key = process.env.CLAWPUMP_API_KEY;
if (!key) { console.error('no key'); process.exit(1); }
const p = spawn('npx', ['-y','@clawpump/agents'], { env: { ...process.env }, stdio:['pipe','pipe','pipe'] });
let buf='';
p.stdout.on('data', d => { buf += d; for (const line of buf.split('\n').slice(0,-1)) { if(line.trim()) console.log('OUT', line.slice(0,3000)); } buf = buf.split('\n').pop(); });
p.stderr.on('data', d => console.log('ERR', String(d).slice(0,400)));
const send = o => p.stdin.write(JSON.stringify(o)+'\n');
send({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'redline-probe',version:'1.0'}}});
setTimeout(()=>{ send({jsonrpc:'2.0',method:'notifications/initialized'}); send({jsonrpc:'2.0',id:2,method:'tools/list'}); }, 4000);
setTimeout(()=>{ p.kill(); process.exit(0); }, 30000);
