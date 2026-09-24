#!/system/bin/sh
# Wait for physical disconnection, then save a read-only battery sample.

base=/data/local/tmp/astonc_powerstats_discharge
sample=/data/local/tmp/astonc_battery_sample.sh
printf 'armed utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "${base}.status"

elapsed=0
while [ "$elapsed" -lt 3600 ]; do
    status=$(cat /sys/class/power_supply/battery/status 2>/dev/null)
    usb=$(cat /sys/class/power_supply/usb/online 2>/dev/null)
    if [ "$status" = Discharging ] && [ "$usb" = 0 ]; then
        sleep 5
        status=$(cat /sys/class/power_supply/battery/status 2>/dev/null)
        usb=$(cat /sys/class/power_supply/usb/online 2>/dev/null)
        if [ "$status" = Discharging ] && [ "$usb" = 0 ]; then
            printf 'sampling utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "${base}.status"
            sh "$sample" > "${base}.tsv" 2> "${base}.stderr"
            rc=$?
            printf 'done rc=%s utc=%s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "${base}.status"
            exit "$rc"
        fi
    fi
    sleep 2
    elapsed=$((elapsed + 2))
done

printf 'timeout utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "${base}.status"
exit 1
