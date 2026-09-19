import { spawn } from 'node:child_process';
const want = process.argv[2];                 // 'schemas' | 'call'
const toolName = process.argv[3];
const args = process.argv[4] ? JSON.parse(process.argv[4]) : {};
const p = spawn('npx', ['-y','@clawpump/agents'], { env: process.env, stdio:['pipe','pipe','pipe'] });
let buf='';
const handle = line => {
  let m; try { m = JSON.parse(line); } catch { return; }
  if (m.id === 2 && want === 'schemas') {
    const names = ['perps_order_preview','perps_order_execute','swap_quote','swap_execute','get_portfolio','agent_portfolio','get_price','perps_markets','perps_account','perps_trader_register'];
    for (const t of m.result.tools) if (names.includes(t.name))
      console.log('\n###', t.name, '\n', t.description?.slice(0,300), '\nINPUT', JSON.stringify(t.inputSchema));
    console.log('\nTOTAL TOOLS', m.result.tools.length);
    p.kill(); process.exit(0);
  }
  if (m.id === 3) { console.log(JSON.stringify(m, null, 1).slice(0,3000)); p.kill(); process.exit(0); }
};
p.stdout.on('data', d => { buf += d; const parts = buf.split('\n'); buf = parts.pop(); parts.forEach(handle); });
p.stderr.on('data', () => {});
const send = o => p.stdin.write(JSON.stringify(o)+'\n');
send({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'redline-probe',version:'1.0'}}});
setTimeout(()=>{ send({jsonrpc:'2.0',method:'notifications/initialized'});
  if (want==='schemas') send({jsonrpc:'2.0',id:2,method:'tools/list'});
  else send({jsonrpc:'2.0',id:3,method:'tools/call',params:{name:toolName,arguments:args}});
}, 4500);
setTimeout(()=>{ console.log('TIMEOUT'); p.kill(); process.exit(1); }, 60000);
