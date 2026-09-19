import { spawn } from 'node:child_process';
const p = spawn('npx', ['-y','@clawpump/agents'], { env: process.env, stdio:['pipe','pipe','pipe'] });
let buf='';
p.stdout.on('data', d => {
  buf += d;
  const parts = buf.split('\n'); buf = parts.pop();
  for (const line of parts) {
    let m; try { m = JSON.parse(line); } catch { continue; }
    if (m.id === 2) {
      const names = m.result.tools.map(t => t.name);
      const want = names.filter(n => /verif|twitter|social|token|claim|agent_x|link/i.test(n));
      console.log('total', names.length);
      console.log(JSON.stringify(want, null, 1));
      for (const t of m.result.tools) if (want.includes(t.name) && /verif|token_x|social/i.test(t.name))
        console.log('\n###', t.name, '\n', (t.description||'').slice(0,240), '\n', JSON.stringify(t.inputSchema).slice(0,500));
      p.kill(); process.exit(0);
    }
  }
});
p.stderr.on('data', () => {});
const send = o => p.stdin.write(JSON.stringify(o)+'\n');
send({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'probe',version:'1'}}});
setTimeout(()=>{ send({jsonrpc:'2.0',method:'notifications/initialized'}); send({jsonrpc:'2.0',id:2,method:'tools/list'}); }, 4500);
setTimeout(()=>{ console.log('TIMEOUT'); p.kill(); process.exit(1); }, 45000);
