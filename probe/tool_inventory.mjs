import { spawn } from 'node:child_process';
const p = spawn('npx', ['-y','@clawpump/agents'], { env: process.env, stdio:['pipe','pipe','pipe'] });
let buf='';
p.stdout.on('data', d => { buf += d; const parts = buf.split('\n'); buf = parts.pop();
  for (const line of parts) { let m; try { m = JSON.parse(line); } catch { continue; }
    if (m.id === 2) {
      const out = m.result.tools.map(t => ({
        name: t.name,
        readOnly: !!(t.annotations && t.annotations.readOnlyHint),
        destructive: !!(t.annotations && t.annotations.destructiveHint),
        desc: (t.description || '').slice(0, 110).replace(/\s+/g, ' '),
      }));
      console.log(JSON.stringify(out));
      p.kill(); process.exit(0);
    } } });
p.stderr.on('data', () => {});
const send = o => p.stdin.write(JSON.stringify(o)+'\n');
send({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'probe',version:'1'}}});
setTimeout(()=>{ send({jsonrpc:'2.0',method:'notifications/initialized'}); send({jsonrpc:'2.0',id:2,method:'tools/list'}); }, 4500);
setTimeout(()=>{ p.kill(); process.exit(1); }, 60000);
