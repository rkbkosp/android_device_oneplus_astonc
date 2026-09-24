#!/system/bin/sh
# Read-only fuel-gauge sampling. Run on the device after disconnecting charging.

i=0
while [ "$i" -le 10 ]; do
    utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    uptime=$(cat /proc/uptime 2>&1)
    for path in \
        /sys/class/power_supply/battery/status \
        /sys/class/power_supply/battery/charge_counter \
        /sys/class/power_supply/battery/current_now \
        /sys/class/power_supply/battery/current_avg \
        /sys/class/power_supply/battery/voltage_now \
        /sys/class/power_supply/battery/energy_now \
        /sys/class/power_supply/battery/power_now \
        /sys/class/power_supply/battery/power_avg \
        /sys/class/power_supply/usb/online \
        /sys/class/power_supply/ac/online \
        /sys/class/oplus_chg/battery/battery_rm \
        /sys/class/oplus_chg/battery/battery_cc; do
        value=$(cat "$path" 2>&1)
        rc=$?
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$i" "$utc" "$uptime" "$path" "$rc" "$value"
    done
    i=$((i + 1))
    if [ "$i" -le 10 ]; then
        sleep 30
    fi
done
