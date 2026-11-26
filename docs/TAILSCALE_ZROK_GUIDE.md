# 🛰️ Руководство по Tailscale Funnel и Zrok v2

Оба туннеля подключаются **к одному общему локальному порту Xray (`127.0.0.1:8080`, VLESS WebSocket `/vless`)** и не требуют отдельного инбаунда на каждого провайдера.

---

## 1. Tailscale Funnel и конфликт порта 443

### В чём была проблема, если ставить и Reality, и Funnel на 443
1. Когда вы запускаете `tailscale funnel --bg --https=443 ...`, демон `tailscaled` открывает локальный сокет на интерфейсе `tailscale0`:`443` (например, `100.x.y.z:443`).
2. В 3X-UI по умолчанию поле **Listen IP** у инбаунда пустое — Xray пытается занять `0.0.0.0:443` (все интерфейсы сразу, включая `tailscale0`).
3. Ядро Linux отклоняет такой запуск с ошибкой **`bind: address already in use`** — эшелон 1 (Stealth Reality) падает или не стартует.
4. *(Частая ошибка в старых гайдах: команда `tailscale funnel --bg 443 tcp://127.0.0.1:8080` неверна для HTTPS/WS-режима — Funnel должен терминировать Let's Encrypt TLS и проксировать HTTP/WebSocket к `http://127.0.0.1:8080`).*

### Два правильных решения (без конфликтов)

#### Вариант А — по умолчанию и без доп. настроек: Funnel на порт `8443`
Tailscale Funnel официально поддерживает 3 публичных порта: `443`, `8443`, `10000`.  
Запуск Funnel на **`8443`** оставляет `443` полностью свободным для Xray Reality Stealth:

```bash
sudo tailscale up
sudo tailscale funnel --bg --https=8443 http://127.0.0.1:8080
sudo tailscale funnel status
```

* Публичный адрес будет `https://<NODE>.<TAILNET>.ts.net:8443`.
* В клиенте (NekoBox / Hiddify):
  * `Address`: `<EDGE_IPV4>` (например `185.40.234.172`, резолвится из `<NODE>.<TAILNET>.ts.net`) или сам домен с **`Domain Strategy = ipv4_only`**.
  * `Port`: **`8443`**, `TLS`: `true`, `SNI`: `<NODE>.<TAILNET>.ts.net`, `Host`: `<NODE>.<TAILNET>.ts.net`, `Path`: `/vless`, `ALPN`: `http/1.1`.

#### Вариант Б — если нужно, чтобы И Stealth Reality, И Tailscale Funnel работали на `443`
Поскольку `tailscaled` слушает только `tailscale0:443` (`100.x.y.z:443`), а **не** `0.0.0.0:443`, вы можете явно ограничить инбаунд `443-reality` в 3X-UI вашим сетевым интерфейсом VPS:
1. Узнайте IP основного интерфейса VPS:
   ```bash
   ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}'
   ```
2. В 3X-UI у инбаунда `443` в поле **`Listen` (`listen`)** впишите этот IPv4 вместо пустого поля.
3. После этого Xray слушает `<VPS_IFACE_IP>:443`, а `tailscaled` слушает `<TAILSCALE_IP>:443` (`sudo tailscale funnel --bg --https=443 http://127.0.0.1:8080`) — конфликта сокетов не будет.

---

## 2. Zrok v2 (AWS Global Accelerator Anycast)

1. Зарегистрируйтесь на [myzrok.io](https://myzrok.io) / [zrok.io](https://zrok.io) и получите Account Token.
2. Активируйте окружение и запустите службу (`configs/systemd/zrok2-tunnel.service`):
   ```bash
   zrok2 enable <YOUR_ZROK_TOKEN>
   sudo systemctl enable --now zrok2-tunnel
   journalctl -u zrok2-tunnel -n 30 --no-pager
   ```
   В службе используется команда **`zrok2 share public 127.0.0.1:8080 --backend-mode proxy --headless`** (а не устаревший `zrok` и не `--backend-mode web`).
3. Узнайте выделенный домен вида `<ID>.shares.zrok.io` и его IPv4-адреса Anycast AWS (`dig +short <ID>.shares.zrok.io`, например группы `52.223.x.x` / `35.71.x.x`).

### Нюанс для Hiddify (`HTTP 200 OK` / Interstitial)
Бесплатный Zrok при обнаружении браузерного `User-Agent` (который отправляет Hiddify) подсовывает HTML-страницу приветствия вместо WebSocket `101`.  
**Решение:** импортируйте профиль JSON с кастомным заголовком:
```json
"headers": {
  "Host": "<YOUR_ID>.shares.zrok.io",
  "skip_zrok_interstitial": "true"
}
```

### Нюанс для Proxifier
Балансировщики AWS ALB (`zrok`) и Cloudflare Edge не пропускают прямой метод HTTP `CONNECT` от Proxifier (`400 Bad Request`).  
**Решение:** запустите NekoBox в фоне **без режима TUN** (поднимется локальный SOCKS5 на `127.0.0.1:2080`) и направьте нужные программы в Proxifier на `127.0.0.1:2080`.

---

## 3. Ошибка `connectex: The requested address is not valid in its context` (`WinSock 10049`)

Если в логах NekoBox вы видите попытки подключения на IPv6-адреса вида `[2a00:dd80:...]` или `[2602:fbaf:...]` с ошибкой `WinSock 10049`:
- **Почему «Маршрутизация -> IPv4» в NekoBox не помогает:** настройки маршрутизации управляют сайтами *внутри* туннеля, а домен **самого прокси-сервера** (`*.ts.net`, `*.shares.zrok.io`, `*.workers.dev`, `*.tun.ply.gg`) ядро резолвит через системный/outbound DNS и при отсутствии IPv6 у провайдера падает.
- **Решение (любое из двух):**
  1. Выставьте в свойствах профиля / настройках DNS NekoBox **`Domain Strategy = ipv4_only`**.
  2. Либо вставьте в поле **Address** прямой **IPv4-адрес шлюза** (полученный через `nslookup`/`dig`), оставив домен в **SNI** и **Host**!
