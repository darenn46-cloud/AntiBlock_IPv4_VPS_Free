# ☁️ Пошаговая инструкция: Cloudflare Worker для VLESS over WebSocket

Cloudflare Workers позволяют бесплатно проксировать WebSocket-трафик через глобальную сеть Cloudflare CDN (до 100 000 бесплатных запросов в сутки). Клиент подключается к IP Cloudflare, а Worker через `cloudflare:sockets` устанавливает прямое TCP-соединение с вашим VPS на порт `8080`.

---

## 1. Подготовка на VPS (Inbound в 3X-UI)
1. Зайдите в панель 3X-UI (`https://<YOUR_VPS_IP>:2053`).
2. Создайте Inbound:
   - **Protocol:** `vless`
   - **Port:** `8080`
   - **Transmission:** `ws` (WebSocket)
   - **Path:** `/vless`
   - **Security:** `none` (внешний TLS держит Cloudflare)
3. Убедитесь, что порт `8080/tcp` разрешён в фаерволе (`ufw allow 8080/tcp`).

---

## 2. Создание и настройка Worker в Cloudflare
1. Войдите на [dash.cloudflare.com](https://dash.cloudflare.com/) ➔ **Compute (Workers & Pages)** ➔ **Create Worker**.
2. Откройте **Edit code**, удалите шаблон и вставьте код из файла [`configs/cloudflare-worker.js`](../configs/cloudflare-worker.js).
3. Перейдите в **Settings** ➔ **Variables and Secrets** и задайте переменные окружения:
   - `VPS_HOST` = реальный внешний IPv4 вашего VPS *(не используйте домен, проксированный самим Cloudflare — `cloudflare:sockets` блокирует исходящие подключения к IP-диапазонам Cloudflare)*.
   - `VPS_PORT` = `8080`.
   - `WS_PATH` = `/vless`.
4. Нажмите **Deploy**. Ваш воркер доступен по адресу `https://<WORKER_NAME>.<SUBDOMAIN>.workers.dev`.

---

## 3. Настройка клиента (NekoBox / Hiddify / v2rayN)
Создайте профиль `VLESS`:
- **Address:** чистый IPv4 адрес Cloudflare Anycast (например, `104.16.1.1`, `104.18.0.1` или незаблокированный домен вроде `www.speedtest.net`) — это защитит от попытки подключения по IPv6 на Windows без IPv6-маршрута.
- **Port:** `443`
- **UUID:** ваш UUID из Inbound `8080` в 3X-UI
- **Network / Transport:** `ws`
- **Path:** `/vless`
- **TLS:** `true` (`alpn`: `http/1.1`, `fp`: `chrome`)
- **SNI:** `<WORKER_NAME>.<SUBDOMAIN>.workers.dev`
- **Host Header:** `<WORKER_NAME>.<SUBDOMAIN>.workers.dev`

> 💡 Если вы указываете в `Address` сам домен `*.workers.dev`, обязательно включите в профиле **Domain Strategy = `IPv4 Only`**, чтобы избежать ошибки `connectex: The requested address is not valid in its context` (`WinSock 10049`).
