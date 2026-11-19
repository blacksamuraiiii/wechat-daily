#!/bin/bash
# 重启 wechat-daily 服务
# 正常路径：systemd 管理，waitress 作为 WSGI 服务器（开机自启，异常自动拉起）
# 若 systemd 单元缺失，回退为手动 setsid 启动（便于迁移）
set -u
APP=/www/py_project/wechat-daily
PY=/www/server/pyporject_evn/weather_venv/bin/python

if systemctl list-unit-files wechat-daily.service > /dev/null 2>&1 \
   && systemctl cat wechat-daily.service > /dev/null 2>&1; then
    systemctl restart wechat-daily
    sleep 3
    if systemctl is-active --quiet wechat-daily; then
        echo "重启成功（systemd / waitress）：$(systemctl show -p ActiveEnterTimestamp --value wechat-daily)"
        systemctl show -p MainPID --value wechat-daily | sed 's/^/主进程 PID /'
        exit 0
    fi
    echo "重启失败，服务状态："
    systemctl status wechat-daily --no-pager | tail -15
    echo "最近日志："
    tail -20 "$APP/logs/run.log"
    exit 1
fi

# --- 回退：无 systemd 时手动启动 ---
port_pid() {
    ss -tlnp 2>/dev/null | grep ':1111' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2
}
OLD=$(port_pid)
if [ -n "${OLD:-}" ]; then
    echo "停止旧进程 $OLD"
    kill "$OLD" 2>/dev/null
    for _ in $(seq 1 10); do
        sleep 1
        [ -z "$(port_pid)" ] && break
    done
fi
mkdir -p "$APP/logs"
chown www:www "$APP/logs" 2>/dev/null
echo "--- 手动重启 $(date '+%F %T') ---" >> "$APP/logs/run.log"
setsid su -s /bin/bash www -c "cd $APP && exec $PY -u run.py >> $APP/logs/run.log 2>&1" < /dev/null &
sleep 4
NEW=$(port_pid)
if [ -n "${NEW:-}" ] && [ "${NEW}" != "${OLD:-}" ]; then
    echo "启动成功（手动模式），监听 1111，PID $NEW"
else
    echo "启动失败，最近日志："
    tail -20 "$APP/logs/run.log"
    exit 1
fi
