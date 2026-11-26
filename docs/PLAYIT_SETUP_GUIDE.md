# 🎮 Пошаговая инструкция: Настройка Playit.gg для Hysteria 2 (UDP)

Playit.gg предоставляет **полностью бесплатный туннель без ограничений по трафику** через Anycast IP-адреса. Это идеальный транспорт для протокола **Hysteria 2 (QUIC/UDP)**, позволяющий обходить блокировки провайдеров и пробивать любые строгие NAT и фильтры ТСПУ.

---

## 1. Регистрация аккаунта Playit
1. Перейдите на официальный сайт [playit.gg](https://playit.gg/).
2. Нажмите **Log in** / **Sign up** и создайте бесплатный аккаунт (по почте или через Google/Discord).

---

## 2. Установка агента на VPS
Выполните на сервере:
```bash
# Скачивание актуального бинарника playit
curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor -o /etc/apt/trusted.gpg.d/playit.gpg
echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./" | tee /etc/apt/sources.list.d/playit.list
apt update && apt install -y playit
```
*(Или скрипт из репозитория `scripts/setup_server.sh` сделает это автоматически).*

---

## 3. Привязка агента к вашему аккаунту (Claiming Agent)
1. Запустите в терминале команду первичной настройки:
   ```bash
   playit setup
   ```
2. В терминале появится ссылка вида:
   ```text
   Visit https://playit.gg/claim/<УНИКАЛЬНЫЙ_КОД> to link this agent
   ```
3. Откройте эту ссылку в браузере под своим аккаунтом Playit.
4. Нажмите кнопку **Add Agent**.
5. Сервер сгенерирует секретный ключ и сохранит его в `/etc/playit/playit.toml`.

---

## 4. Создание UDP-туннеля для Hysteria 2
1. В веб-панели Playit.gg перейдите в раздел **Tunnels** -> нажмите **Add Tunnel**.
2. Заполните параметры:
   - **Tunnel Type:** выберите `Custom` -> `UDP`.
   - **Local Port:** введите `20443` (порт, на котором слушает Hysteria 2 на вашем VPS).
   - **Local IP:** `127.0.0.1` (или оставьте по умолчанию).
3. Нажмите **Add Tunnel**.
4. Playit выдаст вам публичный адрес:
   - Домен: например, `xxxx-xxx.tun.ply.gg:17635`
   - Выделенный Anycast IPv4: например, `147.185.221.217:17635`

---

## 5. Настройка автозапуска Playit как системного сервиса (Systemd)
Чтобы туннель работал непрерывно и поднимался после перезагрузки VPS:
```bash
# Скопируйте готовый сервис из репозитория
sudo cp configs/systemd/playit.service /etc/systemd/system/playit.service
sudo systemctl daemon-reload
sudo systemctl enable --now playit
sudo systemctl status playit
```

---

## 6. Настройка клиента (NekoBox / Hiddify / v2rayN)
Создайте профиль Hysteria 2:
- **Server:** Anycast IP-адрес Playit (например, `147.185.221.217`)
- **Port:** порт Playit (например, `17635`)
- **Auth / Password:** пароль, настроенный в панели Hysteria
- **SNI:** домен вашего самоподписанного сертификата (например, `bing.com` или имя сервера)
- **AllowInsecure / Skip Cert Verify:** `true` (если сертификат самоподписанный)
- **Hop Interval:** `0` (отключить port hopping, так как порт фиксирован туннелем)

> 💡 **Совет:** Указывайте именно **числовой IPv4** (`147.185.221.217`), а не буквенный домен `tun.ply.gg`. Это защищает от попытки клиента подключиться через нерабочий IPv6 в сетях без поддержки IPv6.
