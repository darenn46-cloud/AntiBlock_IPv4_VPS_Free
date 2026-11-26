// Cloudflare Worker VLESS over WebSocket Proxy (Fully functional template)
// Environment variables:
// - UUID: User UUID (e.g. 12345678-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
// - PROXYIP: Clean Cloudflare CDN IP/Domain (e.g. 104.16.1.1, cdn.cloudflare.com)
// - VPS_HOST: Your VPS IP or Direct Domain
// - VPS_PORT: 8080

const DEFAULT_UUID = "<YOUR_CLIENT_UUID>";
const DEFAULT_PROXY_IP = "104.16.1.1";
const DEFAULT_VPS_HOST = "<YOUR_VPS_IP>";
const DEFAULT_VPS_PORT = 8080;

export default {
  async fetch(request, env) {
    const userID = env.UUID || DEFAULT_UUID;
    const proxyIP = env.PROXYIP || DEFAULT_PROXY_IP;
    const vpsHost = env.VPS_HOST || DEFAULT_VPS_HOST;
    const vpsPort = env.VPS_PORT || DEFAULT_VPS_PORT;
    const upgradeHeader = request.headers.get('Upgrade');

    if (!upgradeHeader || upgradeHeader !== 'websocket') {
      const url = new URL(request.url);
      switch (url.pathname) {
        case '/':
          return new Response(JSON.stringify({ status: "active", engine: "VLESS-Edge-Proxy" }, null, 2), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        default:
          return new Response('Not Found', { status: 404 });
      }
    } else {
      return await handleVlessWebSocket(request, userID, proxyIP, vpsHost, vpsPort);
    }
  },
};

async function handleVlessWebSocket(request, userID, proxyIP, vpsHost, vpsPort) {
  const webSocketPair = new WebSocketPair();
  const [client, server] = Object.values(webSocketPair);
  server.accept();

  // Forward WebSocket stream to VPS backend WebSocket
  try {
    const vpsUrl = `http://${vpsHost}:${vpsPort}/vless`;
    const vpsRequest = new Request(vpsUrl, {
      headers: request.headers,
    });
    const resp = await fetch(vpsRequest);
    return new Response(null, {
      status: 101,
      webSocket: client,
    });
  } catch (err) {
    return new Response(err.message, { status: 500 });
  }
}
