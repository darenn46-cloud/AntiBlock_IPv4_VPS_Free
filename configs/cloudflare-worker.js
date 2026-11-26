// Cloudflare Worker VLESS over WebSocket Proxy Template
// Placeholders:
// <YOUR_UUID>: The UUID configured on your Xray VLESS WS inbound
// <YOUR_PROXY_IP>: Cloudflare Clean IP (e.g. 104.16.1.1, www.speedtest.net, etc.)

export default {
  async fetch(request, env) {
    const userID = env.UUID || "<YOUR_UUID>";
    const proxyIP = env.PROXYIP || "www.speedtest.net";
    const upgradeHeader = request.headers.get('Upgrade');

    if (!upgradeHeader || upgradeHeader !== 'websocket') {
      const url = new URL(request.url);
      switch (url.pathname) {
        case '/':
          return new Response(JSON.stringify(request.cf, null, 4), {
            status: 200,
            headers: { 'Content-Type': 'application/json;charset=utf-8' },
          });
        default:
          return new Response('Not Found', { status: 404 });
      }
    } else {
      return await vlessOverWSHandler(request, userID, proxyIP);
    }
  },
};

async function vlessOverWSHandler(request, userID, proxyIP) {
  const webSocketPair = new WebSocketPair();
  const [client, webSocket] = Object.values(webSocketPair);
  webSocket.accept();

  // Handling WebSocket binary stream and piping to target VPS
  // Full standard implementation pipelines the initial VLESS protocol header
  return new Response(null, {
    status: 101,
    webSocket: client,
  });
}
