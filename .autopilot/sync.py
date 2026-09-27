#!/usr/bin/env python3
"""Дзеркалить state.js у саму сторінку дашборда і тримає сервер живим.

Викликається після кожної правки .autopilot/state.js — одним рядком, без аргументів:

    python3 .autopilot/sync.py

Робить рівно три речі, у цьому порядку:

  1. Перевіряє, що state.js розбирається. Битий файл не йде далі: знімок на
     сторінці залишається попереднім, а не затирається сміттям.
  2. Вписує стан усередину dashboard.html між маркерами — атомарно, через
     тимчасовий файл поряд. Обірветься на середині — на місці залишиться ціла
     попередня сторінка. Звідси дашборд показує дані, навіть коли його відкрили
     файлом, з панелі через data:, з мертвим сервером або через місяць після
     прогону.
  3. Дивиться, чи живий статичний сервер цього прогону, і піднімає на попередньому
     порту, якщо ні. Попередній порт — щоб посилання, яке користувач уже
     скопіював, продовжувало працювати.

Нічого не друкує в чат сама по собі: один рядок на stdout, його бачить агент.
"""

import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request

A = os.path.dirname(os.path.abspath(__file__))          # .autopilot цього прогону
STATE = os.path.join(A, "state.js")
PAGE = os.path.join(A, "dashboard.html")
PIDF = os.path.join(A, "serve.pid")
LOG = os.path.join(A, "serve.log")
BEGIN, END = "/*STATE-BEGIN*/", "/*STATE-END*/"


def fail(msg):
    print(msg)
    sys.exit(1)


def read_state():
    try:
        raw = open(STATE, encoding="utf-8").read()
    except FileNotFoundError:
        fail("state.js ще немає — знімок не вписаний, сервер не чіпано")
    body = raw.split("=", 1)[1] if "=" in raw.split("\n", 1)[0] else raw
    try:
        return json.loads(body.strip().rstrip(";"))
    except json.JSONDecodeError as e:
        # Тут і був режим відмови «файл пом'явся»: раніше він був видимий тільки по
        # порожній сторінці, тепер — рядком з номером рядка, одразу після запису.
        fail("state.js не розбирається (рядок %d: %s) — знімок залишено попереднім" % (e.lineno, e.msg))


def write_snapshot(state):
    """Знімок усередину сторінки. Повертає текст для звіту."""
    try:
        page = open(PAGE, encoding="utf-8").read()
    except FileNotFoundError:
        return "сторінки немає — перекопіюй dashboard.html із навички"
    i, j = page.find(BEGIN), page.find(END)
    if i < 0 or j < 0:
        return "сторінка без маркерів знімка — перекопіюй dashboard.html із навички"
    # </ усередині <script> закрив би тег і порвав сторінку; < безпечний у JSON.
    payload = "window.STATE=" + json.dumps(state, ensure_ascii=False).replace("</", "<\\/") + ";"
    new = page[: i + len(BEGIN)] + payload + page[j:]
    if new == page:
        return "знімок уже збігався"
    tmp = PAGE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, PAGE)                                # атомарно: битої сторінки не буває
    return "знімок вписано"


def http_ok(port, path="/dashboard.html"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def cmdline(pid):
    try:
        return subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def is_ours(cmd):
    """Чи наш це процес. Вузька перевірка навмисно: широка вже вбивала чуже."""
    return "-m http.server" in cmd and "--directory " + A in cmd


def recorded():
    try:
        port, pid = open(PIDF).read().split()
        return int(port), int(pid)
    except (OSError, ValueError):
        return None, None


def free_port(prefer):
    """Попередній порт, якщо вільний, інакше будь-який. Стабільна адреса важливіша за випадкову."""
    for p in ([prefer] if prefer else []) + [0]:
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            return s.getsockname()[1]
        except OSError:
            continue
        finally:
            s.close()
    return None


def serve(state):
    if state.get("finishedAt"):
        return "прогін закрито — сервер не піднімаю"     # Phase 8 його вже вбила
    if os.environ.get("SSH_CONNECTION") or os.environ.get("CI"):
        return "віддалена сесія — без сервера"

    port, pid = recorded()
    if port and http_ok(port) and (not pid or is_ours(cmdline(pid))):
        return "сервер живий: http://localhost:%d/dashboard.html" % port

    # Осиротілі сервери цього ж каталогу: їх ніхто не вб'є, крім нас, і
    # тільки їх — за повним --directory, ніколи за «всі http.server, крім...».
    for line in subprocess.run(["ps", "-Ao", "pid=,command="], capture_output=True,
                               text=True).stdout.splitlines():
        num, _, cmd = line.strip().partition(" ")
        if is_ours(cmd) and num.isdigit():
            try:
                os.kill(int(num), 15)
            except OSError:
                pass

    port = free_port(port)
    if not port:
        return "порт не знайшовся — дашборд відкривається файлом: %s" % PAGE
    try:
        log = open(LOG, "a")
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port),
                                "--bind", "127.0.0.1", "--directory", A],
                               stdout=subprocess.DEVNULL, stderr=log,
                               start_new_session=True)     # переживає кінець сесії агента
    except OSError as e:
        return "сервер не запустився (%s) — дашборд відкривається файлом: %s" % (e, PAGE)
    for _ in range(10):
        if http_ok(port):
            open(PIDF, "w").write("%d %d\n" % (port, srv.pid))
            return "сервер піднято: http://localhost:%d/dashboard.html" % port
        try:
            srv.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            continue
    srv.terminate()
    return "сервер не відповів — дашборд відкривається файлом: %s" % PAGE


ORDER = ["preflight", "manifest", "briefing", "spec", "plan", "build", "review", "final"]


def close_passed(state):
    """Закриває етапи, які прогін уже пройшов. Повертає список закритих.

    Інваріант, а не подія: раніше активного етапу не може бути іншого
    активного. Тому агент лише відкриває наступний — попередній
    закривається тут, часом відкриття нового, тим самим, що він і отримав би
    вручну. Половина ритуалу перестала бути роботою агента, а разом із нею —
    клас помилок, де перехід записаний наполовину (2026-08-19: spec простояв
    активним дві з половиною години поряд із готовим планом і збіркою, що йде).

    Один виняток, і він у самій моделі роботи: рев'ю йде по тасках усередині
    збірки, тому review не закриває build. Усе, що пізніше review, закриває
    обох.

    Не чіпає нічого, крім active: skipped і failed — свідомі стани,
    і перетворити їх на done означало б стерти сказане про прогін.
    """
    rank = {v: i for i, v in enumerate(ORDER)}
    stages = state.get("stages") or []
    live = [s for s in stages if s.get("status") == "active" and s.get("id") in rank]
    if len(live) < 2:
        return []
    closed = []
    for s in live:
        # Що йде слідом. Рев'ю не вважається «наступним» для збірки: воно живе
        # усередині неї, тому не закриває її і не дає їй часу закриття.
        later = [o for o in live if rank[o["id"]] > rank[s["id"]]
                 and not (s["id"] == "build" and o["id"] == "review")]
        if not later:
            continue
        # Закриваємо моментом, коли прогін пішов далі, — відкриттям найближчого
        # наступного етапу, а не найдальшого: інакше специфікація отримала б
        # час початку рев'ю і годину чужої роботи у свій рахунок.
        marks = sorted(o["startedAt"] for o in later if o.get("startedAt"))
        when = marks[0] if marks else state.get("updatedAt")
        if not when:
            continue
        s["status"] = "done"
        s["finishedAt"] = when
        closed.append("%s закрито автоматично (%s)" % (s["id"], when[11:19]))
    return closed


def save(state):
    raw = open(STATE, encoding="utf-8").read()
    head = raw.split("=", 1)[0]
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(head + "=\n" + json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    os.replace(tmp, STATE)


def audit(state):
    """Мовчить, поки стан сходиться сам із собою. Не лагодить: називає.

    Ловить один клас помилок — перехід, записаний наполовину. Стадію лишили
    active і пішли далі; таск запустили без startedAt; закрили без finishedAt.
    Кожна така живе доти, доки її не побачить людина: 2026-08-19 spec
    простояв активним дві з половиною години поряд із готовим планом і збіркою,
    що йде, і помітив це користувач, а не прогін.
    """
    out = []
    stages = state.get("stages") or []
    rank = {v: i for i, v in enumerate(ORDER)}
    live = [s["id"] for s in stages if s.get("status") == "active" and s.get("id") in rank]
    # Етап, до якого прогін дійшов, але який так і не позначили ні пройденим,
    # ні пропущеним: close_passed його не чіпає — «пропущено» вимагає причини,
    # а її знає тільки агент. На екрані він інакше читається як «збірка застрягла».
    if live:
        edge = max(rank[i] for i in live)
        for s in stages:
            if s.get("status") == "pending" and rank.get(s.get("id"), 99) < edge:
                out.append("етап %s лишився pending, а прогін пішов далі — познач skipped з причиною" % s.get("id"))
    for s in stages:
        if s.get("status") == "done" and not s.get("finishedAt"):
            out.append("етап %s закрито без finishedAt" % s.get("id"))
    for t in state.get("tickets") or []:
        if t.get("status") in ("in-progress", "review", "repair") and not t.get("startedAt"):
            out.append("таск %s у роботі без startedAt" % t.get("id"))
        if t.get("status") == "done" and not t.get("finishedAt"):
            out.append("таск %s закрито без finishedAt" % t.get("id"))
    return out


def main():
    state = read_state()
    passed = close_passed(state)
    if passed:
        save(state)                    # updatedAt не рухаємо: пульс належить агенту
    snap = write_snapshot(state)
    srv = "сервер не перевірявся" if "--no-serve" in sys.argv else serve(state)
    print("%s · %s · оновлено %s" % (snap, srv, (state.get("updatedAt") or "?")[11:19]))
    for line in passed:
        print("  · " + line)
    for line in audit(state)[:5]:
        print("  ! " + line)


if __name__ == "__main__":
    main()
