# 🎮 Пошаговая инструкция: Playit.gg для Hysteria 2 (UDP)

Playit.gg предоставляет **бесплатный Anycast UDP-туннель** без жёстких лимитов на гигабайты. Это идеальный транспорт для **Hysteria 2 (QUIC/UDP)**, когда прямой IPv4 сервера заблокирован или оператор режет/душит трафик.

---

## 1. Регистрация и установка агента
1. Создайте бесплатный аккаунт на [playit.gg](https://playit.gg/).
2. Установите `playit` на VPS (`scripts/setup_server.sh` делает это автоматически).

---

## 2. Привязка агента (Claim)
1. Запустите на сервере:
   ```bash
   playit setup
   ```
2. Откройте в браузере выданную ссылку `https://playit.gg/claim/<КОД>` и подтвердите добавление агента.
3. Конфигурация сохранится в `/etc/playit/playit.toml` (либо скопируйте секрет из консоли для запуска через `--secret <SECRET>`).

---

## 3. Создание UDP-туннеля (КРИТИЧЕСКИ ВАЖНО)

> [!WARNING]
> **НЕ ВЫБИРАЙТЕ ИГРОВЫЕ ШАБЛОНЫ!**
> - ❌ **Minecraft Java / Terraria** — это TCP-шаблоны, Hysteria 2 работать не будет!
> - **Hysteria 2 работает исключительно поверх UDP (QUIC).**

1. В панели Playit.gg откройте **Tunnels** ➔ **Add Tunnel**.
2. Выберите тип **`Custom`** ➔ **`UDP`**.
3. Укажите:
   - **Local IP:** `127.0.0.1`
   - **Local Port:** `20443`
4. Нажмите **Add Tunnel**. Вы получите адрес вида:
   - Домен: `<RANDOM>.tun.ply.gg:<PORT>`
   - **Anycast IPv4:** `<PLAYIT_IPV4>:<PORT>` (например, `147.185.x.x:17635`)

---

## 4. Запуск Hysteria 2 и автозапуск
```bash
# Проверьте /etc/hysteria/config.yaml и переменные в /etc/systemd/system/hysteria-panel.service
sudo systemctl enable --now hysteria-server hysteria-panel playit
```

---

## 5. Настройка клиента (NekoBox / Hiddify / v2rayN)
- **Protocol:** `Hysteria 2`
- **Server:** **числовой Anycast IPv4 Playit** (`<PLAYIT_IPV4>`) — не домен `*.tun.ply.gg`!
- **Port:** `<PORT>`
- **Password / Auth:** `<USER>:<PASSWORD>` (или пароль)
- **SNI:** `bing.com`
- **AllowInsecure:** `true`
- **Hop Interval:** `0`

> 💡 **Почему важно вписывать IPv4 вместо домена `tun.ply.gg`:**  
> Домены Playit возвращают IPv6 (`AAAA`) записи. В Windows-сетях без IPv6 клиент может попытаться подключиться по IPv6 и упасть с ошибкой **`connectex: The requested address is not valid in its context` (WinSock 10049)**. Прямой IPv4 (или `Domain Strategy = ipv4_only`) полностью решает проблему.
