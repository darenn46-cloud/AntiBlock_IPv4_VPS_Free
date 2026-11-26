// Cloudflare Worker VLESS WebSocket Relay (cloudflare:sockets -> VPS Xray :8080)
//
// Environment variables (Settings -> Variables and Secrets):
// - VPS_HOST: Raw public IPv4 (or non-proxied domain) of your VPS
// - VPS_PORT: Xray WebSocket inbound port (default: 8080)
// - WS_PATH:  WebSocket path configured in Xray (default: /vless)

import { connect } from 'cloudflare:sockets';

const DEFAULT_VPS_HOST = '<YOUR_VPS_IP>';
const DEFAULT_VPS_PORT = 8080;
const DEFAULT_WS_PATH = '/vless';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const vpsHost = (env.VPS_HOST || DEFAULT_VPS_HOST).trim();
    const vpsPort = Number(env.VPS_PORT || DEFAULT_VPS_PORT);
    const wsPath = normalizePath(env.WS_PATH || DEFAULT_WS_PATH);

    const upgrade = request.headers.get('Upgrade');
    if (!upgrade || upgrade.toLowerCase() !== 'websocket') {
      if (url.pathname === '/') {
        return new Response(
          JSON.stringify({ status: 'active', engine: 'VLESS-WS-Relay' }, null, 2),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response('Not Found', { status: 404 });
    }

    if (url.pathname !== wsPath) {
      return new Response('Not Found', { status: 404 });
    }

    if (!vpsHost || vpsHost === '<YOUR_VPS_IP>' || !Number.isInteger(vpsPort) || vpsPort < 1 || vpsPort > 65535) {
      return new Response('Worker is not configured: set VPS_HOST and VPS_PORT variables.', { status: 500 });
    }

    return await relayWebSocketToVps(vpsHost, vpsPort, wsPath, ctx);
  },
};

function normalizePath(p) {
  const trimmed = (p || '/vless').trim();
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
}

function concatBytes(a, b) {
  if (!a || a.length === 0) return b;
  if (!b || b.length === 0) return a;
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

function findDoubleCrlf(buf) {
  for (let i = 0; i <= buf.length - 4; i++) {
    if (buf[i] === 13 && buf[i + 1] === 10 && buf[i + 2] === 13 && buf[i + 3] === 10) {
      return i;
    }
  }
  return -1;
}

function makeWsKey() {
  const raw = new Uint8Array(16);
  crypto.getRandomValues(raw);
  let bin = '';
  for (let i = 0; i < raw.length; i++) bin += String.fromCharCode(raw[i]);
  return btoa(bin);
}

/**
 * Encodes a masked client-to-server WebSocket frame (RFC 6455).
 */
export function encodeWsFrame(opcode, payloadBytes) {
  const payload = payloadBytes instanceof Uint8Array ? payloadBytes : new Uint8Array(payloadBytes || 0);
  const len = payload.length;
  let headerLen = 6; // 2 base + 4 mask
  if (len >= 126 && len <= 65535) headerLen += 2;
  else if (len > 65535) headerLen += 8;

  const frame = new Uint8Array(headerLen + len);
  frame[0] = 0x80 | (opcode & 0x0f);

  let offset = 2;
  if (len < 126) {
    frame[1] = 0x80 | len;
  } else if (len <= 65535) {
    frame[1] = 0x80 | 126;
    frame[2] = (len >>> 8) & 0xff;
    frame[3] = len & 0xff;
    offset = 4;
  } else {
    frame[1] = 0x80 | 127;
    const high = Math.floor(len / 0x100000000);
    const low = len >>> 0;
    frame[2] = (high >>> 24) & 0xff;
    frame[3] = (high >>> 16) & 0xff;
    frame[4] = (high >>> 8) & 0xff;
    frame[5] = high & 0xff;
    frame[6] = (low >>> 24) & 0xff;
    frame[7] = (low >>> 16) & 0xff;
    frame[8] = (low >>> 8) & 0xff;
    frame[9] = low & 0xff;
    offset = 10;
  }

  const mask = new Uint8Array(4);
  crypto.getRandomValues(mask);
  frame.set(mask, offset);
  offset += 4;

  for (let i = 0; i < len; i++) {
    frame[offset + i] = payload[i] ^ mask[i & 3];
  }
  return frame;
}

/**
 * Attempts to parse one complete WebSocket frame from buffer.
 * Returns { frame, rest } or null if more bytes are needed.
 */
export function tryDecodeWsFrame(buf) {
  if (buf.length < 2) return null;

  const b0 = buf[0];
  const b1 = buf[1];
  const fin = (b0 & 0x80) !== 0;
  const opcode = b0 & 0x0f;
  const masked = (b1 & 0x80) !== 0;
  let payloadLen = b1 & 0x7f;
  let offset = 2;

  if (payloadLen === 126) {
    if (buf.length < offset + 2) return null;
    payloadLen = (buf[offset] << 8) | buf[offset + 1];
    offset += 2;
  } else if (payloadLen === 127) {
    if (buf.length < offset + 8) return null;
    const high =
      (buf[offset] * 0x1000000) +
      ((buf[offset + 1] << 16) | (buf[offset + 2] << 8) | buf[offset + 3]);
    const low =
      ((buf[offset + 4] << 24) >>> 0) +
      ((buf[offset + 5] << 16) | (buf[offset + 6] << 8) | buf[offset + 7]);
    payloadLen = high * 0x100000000 + low;
    offset += 8;
  }

  const maskLen = masked ? 4 : 0;
  if (buf.length < offset + maskLen + payloadLen) return null;

  let payload = buf.slice(offset + maskLen, offset + maskLen + payloadLen);
  if (masked) {
    const mask = buf.subarray(offset, offset + 4);
    for (let i = 0; i < payload.length; i++) {
      payload[i] ^= mask[i & 3];
    }
  }

  return {
    frame: { fin, opcode, payload },
    rest: buf.subarray(offset + maskLen + payloadLen),
  };
}

async function relayWebSocketToVps(vpsHost, vpsPort, wsPath, ctx, socketConnector = connect) {
  let socket;
  try {
    socket = socketConnector({ hostname: vpsHost, port: vpsPort }, { secureTransport: 'off' });
    const writer = socket.writable.getWriter();
    const reader = socket.readable.getReader();

    const handshake =
      `GET ${wsPath} HTTP/1.1\r\n` +
      `Host: ${vpsHost}:${vpsPort}\r\n` +
      `Upgrade: websocket\r\n` +
      `Connection: Upgrade\r\n` +
      `Sec-WebSocket-Key: ${makeWsKey()}\r\n` +
      `Sec-WebSocket-Version: 13\r\n\r\n`;

    await writer.write(new TextEncoder().encode(handshake));

    let buf = new Uint8Array(0);
    let headerEnd = -1;
    while (headerEnd === -1) {
      const { value, done } = await reader.read();
      if (done) {
        await safeCloseSocket(socket);
        return new Response('Upstream closed connection during WebSocket handshake', { status: 502 });
      }
      buf = concatBytes(buf, value);
      headerEnd = findDoubleCrlf(buf);
      if (buf.length > 16384 && headerEnd === -1) {
        await safeCloseSocket(socket);
        return new Response('Upstream HTTP response header too large', { status: 502 });
      }
    }

    const respHeaders = new TextDecoder().decode(buf.subarray(0, headerEnd));
    const statusLine = respHeaders.split('\r\n')[0] || '';
    if (!statusLine.includes(' 101 ')) {
      await safeCloseSocket(socket);
      return new Response(`Upstream WebSocket upgrade rejected: ${statusLine}`, { status: 502 });
    }

    let upstreamCarry = buf.subarray(headerEnd + 4);
    const pair = new WebSocketPair();
    const [clientWs, serverWs] = Object.values(pair);
    serverWs.accept();

    let closed = false;
    let writeQueue = Promise.resolve();
    const textEncoder = new TextEncoder();
    const textDecoder = new TextDecoder();

    const enqueueWrite = (bytes) => {
      writeQueue = writeQueue
        .then(async () => {
          if (!closed) await writer.write(bytes);
        })
        .catch(() => closeBoth());
    };

    const closeBoth = async () => {
      if (closed) return;
      closed = true;
      try { serverWs.close(1000, 'Closed'); } catch {}
      try { writer.releaseLock(); } catch {}
      try { reader.releaseLock(); } catch {}
      await safeCloseSocket(socket);
    };

    serverWs.addEventListener('message', (event) => {
      if (closed) return;
      if (typeof event.data === 'string') {
        enqueueWrite(encodeWsFrame(0x1, textEncoder.encode(event.data)));
      } else {
        enqueueWrite(encodeWsFrame(0x2, new Uint8Array(event.data)));
      }
    });

    serverWs.addEventListener('close', () => {
      if (!closed) {
        enqueueWrite(encodeWsFrame(0x8, new Uint8Array(0)));
        writeQueue.finally(() => closeBoth());
      }
    });

    serverWs.addEventListener('error', () => {
      closeBoth();
    });

    const pump = (async () => {
      let pendingBuf = upstreamCarry;
      let fragOpcode = 0;
      let fragChunks = [];

      const handleDecodedFrame = ({ fin, opcode, payload }) => {
        if (opcode === 0x8) {
          closeBoth();
          return false;
        }
        if (opcode === 0x9) {
          enqueueWrite(encodeWsFrame(0xA, payload));
          return true;
        }
        if (opcode === 0xA) {
          return true;
        }

        if (opcode !== 0x0) {
          if (fin) {
            serverWs.send(opcode === 0x1 ? textDecoder.decode(payload) : payload);
          } else {
            fragOpcode = opcode;
            fragChunks = [payload];
          }
        } else {
          fragChunks.push(payload);
          if (fin) {
            let full = new Uint8Array(0);
            for (const c of fragChunks) full = concatBytes(full, c);
            fragChunks = [];
            serverWs.send(fragOpcode === 0x1 ? textDecoder.decode(full) : full);
            fragOpcode = 0;
          }
        }
        return true;
      };

      try {
        while (!closed) {
          let parsed;
          while ((parsed = tryDecodeWsFrame(pendingBuf)) !== null) {
            pendingBuf = parsed.rest;
            if (!handleDecodedFrame(parsed.frame)) return;
          }
          const { value, done } = await reader.read();
          if (done) break;
          pendingBuf = concatBytes(pendingBuf, value);
        }
      } catch {
        // Stream terminated
      } finally {
        await closeBoth();
      }
    })();

    if (ctx && typeof ctx.waitUntil === 'function') {
      ctx.waitUntil(pump);
    }

    return new Response(null, { status: 101, webSocket: clientWs });
  } catch (err) {
    await safeCloseSocket(socket);
    return new Response(`Relay error: ${err.message}`, { status: 502 });
  }
}

async function safeCloseSocket(socket) {
  if (!socket) return;
  try {
    await socket.close();
  } catch {}
}
