# PowerStats direct-read probe for astonc

`astonc_powerstats_probe` calls the AIDL HAL directly and prints every
Channel, EnergyConsumer, `EnergyMeasurement.energyUWs`, and
`EnergyConsumerResult.energyUWs`. It is a read-only diagnostic executable,
not included in `PRODUCT_PACKAGES` or the ROM. The ordinary
`dumpsys powerstats` output lists metadata but does not sample these energy
methods.

Targeted build:

```sh
source build/envsetup.sh
lunch lineage_astonc-bp4a-user
OUT_DIR=out m astonc_powerstats_probe -j8
```

The binary is at
`/data/crdroid/out/target/product/astonc/vendor/bin/astonc_powerstats_probe`.
On the connected device, a device-side Codex can push it to
`/data/local/tmp/`, mark it executable, and run it with `su` if the shell
cannot find the HAL service. Save its complete stdout and stderr with UTC
time twice in the same boot, at least 60 seconds apart. A nonempty channel
list alone does not prove measurement; the matching `energyUWs` values must
increase and correspond to a documented hardware counter.

`battery_sample.sh` is a separate read-only fuel-gauge sampler. Run it over
wireless ADB or from a device-local terminal **after disconnecting power**;
it prints 11 samples at 30-second intervals. It writes only to stdout.
Retain raw output, charging status, sysfs permissions, and the units from
the actual driver. Do not infer units from the sysfs filenames alone.

For USB-only ADB, push both shell scripts to `/data/local/tmp/`, then launch
`discharge_watch.sh` with `setsid` and redirected I/O before unplugging. It
waits for `status=Discharging` and `usb/online=0`, waits another five seconds,
and saves the 11-sample run as
`/data/local/tmp/astonc_powerstats_discharge.tsv`. Its state is in the
adjacent `.status` file. Leave the device disconnected for at least six
minutes, then reconnect and pull both files. The watcher times out after one
hour and does not write any sysfs node.
