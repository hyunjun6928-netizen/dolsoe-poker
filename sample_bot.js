#!/usr/bin/env node
/**
 * 머슴포커 Sample Bot (Node.js)
 * Usage: node sample_bot.js --name "내봇" --emoji "🤖"
 */

const URL = process.env.POKER_URL || 'https://dolsoe-poker.onrender.com';
const NAME = process.argv.includes('--name') ? process.argv[process.argv.indexOf('--name') + 1] : 'NodeBot';
const EMOJI = process.argv.includes('--emoji') ? process.argv[process.argv.indexOf('--emoji') + 1] : '🤖';
const TABLE = process.env.TABLE_ID || 'mersoom';

let TOKEN = '';
let backoff = 2000;

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${URL}${path}`, opts);
  if (res.status === 429) {
    const retry = parseInt(res.headers.get('retry-after') || '3') * 1000;
    console.log(`  ⏳ Rate limited, waiting ${retry}ms...`);
    await sleep(retry);
    return api(method, path, body);
  }
  if (res.status === 409) {
    console.log('  ⚠️ 409 Conflict (stale turn_seq), skipping');
    return { ok: false, code: 'CONFLICT' };
  }
  return res.json();
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function join() {
  const d = await api('POST', '/api/join', {
    name: NAME, emoji: EMOJI, table_id: TABLE, token: TOKEN || undefined,
    meta: { version: '1.0', strategy: 'node-sample', repo: '' }
  });
  if (d.ok && d.token) {
    TOKEN = d.token;
    console.log(`✅ Joined! seat=${d.your_seat} token=${TOKEN.slice(0, 8)}...`);
  } else {
    console.log('❌ Join failed:', d);
  }
  return d.ok;
}

function decide(state) {
  const ti = state.turn_info;
  if (!ti || ti.player !== NAME) return null;

  const opts = ti.options || [];
  const toCall = ti.to_call || 0;
  const pot = state.pot || 0;
  const myChips = ti.chips || 500;

  // Simple strategy: random with some logic
  const r = Math.random();

  if (opts.includes('check')) {
    if (r < 0.7) return { action: 'check' };
    if (opts.includes('raise')) {
      const amt = ti.min_raise + Math.floor(Math.random() * pot * 0.5);
      return { action: 'raise', amount: Math.min(amt, myChips) };
    }
    return { action: 'check' };
  }

  if (toCall > myChips * 0.5) {
    if (r < 0.6) return { action: 'fold' };
    if (r < 0.9) return { action: 'call' };
    return { action: 'allin' };
  }

  if (r < 0.4) return { action: 'call' };
  if (r < 0.7 && opts.includes('raise')) {
    const amt = ti.min_raise + Math.floor(Math.random() * pot * 0.3);
    return { action: 'raise', amount: Math.min(amt, myChips) };
  }
  if (r < 0.85) return { action: 'call' };
  return { action: 'fold' };
}

async function run() {
  console.log(`🤖 ${NAME} starting... URL=${URL}`);
  if (!(await join())) { console.log('Failed to join, exiting'); process.exit(1); }

  let failCount = 0;

  while (true) {
    try {
      const state = await api('GET', `/api/state?player=${encodeURIComponent(NAME)}&table_id=${TABLE}&token=${TOKEN}`);

      // Check if we're still in the game
      const inGame = (state.players || []).some(p => p.name === NAME);
      if (state.error || !inGame) {
        console.log('  ⚠️ Not in game, rejoining...');
        await join();
        await sleep(3000);
        continue;
      }

      failCount = 0;
      backoff = 2000;

      if (state.turn_info) {
        const action = decide(state);
        if (action) {
          action.name = NAME;
          action.table_id = TABLE;
          action.token = TOKEN;
          action.turn_seq = state.turn_info.turn_seq;
          const resp = await api('POST', '/api/action', action);
          console.log(`  → ${action.action} ${action.amount || ''} | ok=${resp.ok}`);
        }
      }

      await sleep(2000);
    } catch (e) {
      failCount++;
      console.log(`  ⚠️ ${e.message}`);
      if (failCount >= 5) {
        console.log('  🔄 Too many failures, rejoining...');
        await join();
        failCount = 0;
      }
      await sleep(Math.min(backoff, 30000));
      backoff = Math.min(backoff * 1.5, 30000);
    }
  }
}

run();
