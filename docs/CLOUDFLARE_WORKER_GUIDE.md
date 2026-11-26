# ☁️ Пошаговая инструкция: Настройка Cloudflare Worker для VLESS over WebSocket

Cloudflare Workers позволяют бесплатно проксировать TCP/WebSocket трафик через глобальную сеть Cloudflare CDN (до 100 000 бесплатных запросов в сутки). Ваш VPS скрывается за миллионами Anycast IP-адресов Cloudflare.

---

## 1. Подготовка на VPS (Inbound в 3X-UI)
Трафик от Cloudflare Worker приходит на порт вашего сервера по протоколу WebSocket:
1. Зайдите в панель 3X-UI (`http://<YOUR_VPS_IP>:2053`).
2. Перейдите в **Inbounds** -> нажмите **Add Inbound**.
3. Задайте настройки:
   - **Protocol:** `vless`
   - **Port:** `8080` (или `80`)
   - **Transmission:** `ws` (WebSocket)
   - **Path:** `/vless`
   - **Security:** `none` (шифрование TLS берет на себя Cloudflare на внешнем периметре)
   - **Client:** сгенерируйте и скопируйте **UUID** (он понадобится для воркера).
4. Сохраните инбаунд и нажмите **Restart Service**.

---

## 2. Создание Worker в панели Cloudflare
1. Зарегистрируйтесь или войдите на [dash.cloudflare.com](https://dash.cloudflare.com/).
2. В левом меню выберите **Compute (Workers & Pages)** -> **Workers & Pages**.
3. Нажмите кнопку **Create application** -> вкладка **Workers** -> **Create Worker**.
4. Введите понятное имя (например, `vless-edge-proxy`) и нажмите **Deploy**.
5. Нажмите кнопку **Edit code**.

---

## 3. Установка готового кода VLESS WebSocket
1. Полностью очистите редактор кода в Cloudflare.
2. Вставьте рабочий скрипт из файла [configs/cloudflare-worker.js](file:///s:/VPN/vps-bypass-kit/configs/cloudflare-worker.js).
3. В коде (или во вкладке **Settings** -> **Variables**) укажите:
   - `UUID` = ваш UUID клиента из шага 1.
   - `PROXYIP` = чистый IP/домен Cloudflare CDN (например, `104.16.1.1` или `www.speedtest.net`).
   - `VPS_HOST` = `<YOUR_VPS_IP>` (или домен сервера).
   - `VPS_PORT` = `8080`.
4. Нажмите **Deploy** (или **Save and deploy**).

---

## 4. Настройка клиента (NekoBox / Hiddify / v2rayN)
Создайте конфигурацию VLESS:
- **Address:** `104.16.1.1` (или любой чистый незаблокированный IP Cloudflare / провайдерский CDN)
- **Port:** `443`
- **UUID:** ваш UUID
- **Network / Transport:** `ws` (WebSocket)
- **Path:** `/vless`
- **TLS:** `true` (Включен)
- **SNI (Server Name):** домен вашего воркера, например `vless-edge-proxy.ваше_имя.workers.dev`
- **Host Header:** `vless-edge-proxy.ваше_имя.workers.dev`

> 💡 **Преимущество:** Даже если провайдер полностью заблокирует IP-адрес вашего VPS, подключение продолжит работать на максимальной скорости, так как клиент подключается к Cloudflare, а не к вашему серверу напрямую.
