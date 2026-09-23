# LHDC port for astonc

This worktree adds A2DP LHDC V3/V4 and V5 to the source Bluetooth stack. The
stack implementation comes from Savitech's AOSP 16 integration, with protocol
capabilities and encoder calls adapted for the PJE110 / ColorOS 16.0.5.1002
libraries. The four stock encoder binaries are under `lhdc/liblhdc` and
`lhdc/liblhdcv5`; their SHA-256 hashes match
`~/lhdc-ace3-stock-kit-16.0.5.1002.zip`.

`device.mk` installs the four libraries to `/system/lib64`. The Bluetooth APEX
also includes the two wrapper libraries and their direct encoder dependencies
for `dlopen` from the Bluetooth process inside the APEX.
Headers copied from the public integration are compile-time inputs only.

The native A2DP stack advertises the stock-compatible V3/V4 capability bytes
`3c d1 81` and the V5 subset `30 06 11 40 00`. V5 omits the stock 32-bit PCM
capability because this source integration only exposes 16- and 24-bit PCM.
The V5 wrapper call uses the stock seven-argument `lhdcv5BT_init_encoder` ABI
and does not load the newer `lhdcv5BT_set_improved_low_bitrate` symbol.
Bluetooth framework codec indices in this source stack are 7 (V3) and 8 (V5),
while the stock Bluetooth.apk uses 18 and 19; the stock APK/JNI pair is not
part of this port.

The generic `audio.bluetooth.default` path should provide PCM to the source
stack's software encoder. As of 2026-09-23 the stock `audio.bluetooth_qti.default.so`
and its LHDC audio policy route **are** installed, mirroring the stock ROM:

* HAL blob `vendor/oneplus/sm8550-common/proprietary/vendor/lib64/hw/audio.bluetooth_qti.default.so`,
  declared as `cc_prebuilt_library_shared` in `vendor/oneplus/sm8550-common/Android.bp`
  (`relative_install_path: "hw"`; ELF prebuilts cannot go through `PRODUCT_COPY_FILES`).
* Audio policy: the `bluetooth_qti` module in
  `device/oneplus/sm8550-common/configs/audio/audio_policy_configuration.xml` now carries
  the hearing aid path only. LHDC must **not** be declared as an offload format there:
  with `AUDIO_FORMAT_LHDC`/`AUDIO_FORMAT_LHDC_LL` on that module's BT A2DP device ports,
  AudioPolicyManager routed LHDC to the ADSP offload datapath (`session_type=2`), which
  has no LHDC encoder, and the HAL then failed to open the stream —
  `open_a2dp_source: Failed to open source stream for a2dp: status -1`, retried forever.
* The stack keeps LHDC off that datapath explicitly: `is_lhdc_source_codec()` in
  `packages/modules/Bluetooth/system/audio_hal_interface/aidl/a2dp/a2dp_encoding_aidl.cc`
  skips both offload branches of `setup_codec()` (the AIDL v4 provider branch, which the
  stock HAL claims for LHDC, and the legacy hardware path), so LHDC reaches
  `getHalPcmConfiguration()` and `A2DP_SOFTWARE_ENCODING_DATAPATH`.

Reason: with the AOSP AIDL impl alone the software datapath is dead on this device —
`startSession()` succeeds, yet the vendor PAL in the same process reports
"bluetooth provider session is not avail", so every codec is silent once A2DP
offload is disabled. The stock HAL is self-consistent (it provides the AIDL
provider and consumes the session). Playback is still unverified on a running device; the 2026-09-23 capture confirms the
negotiation side (LHDC V5, 48 kHz / 24 bit, SEP configured and requested) and pins the
failure to the offload routing above. The LHDC path is the host-encoded one (software
datapath), never offload — the ADSP firmware carries no LHDC encoder.
In particular, the public V5 code targets a newer encoder release than the
stock PJE110 V5 binary despite the adjusted ABI and capability subset.

Validation after building and flashing requires a LHDC-capable headset:
inspect selectable/current codecs, A2DP negotiation, encoder loading, audio
route, playback, reconnect and fallback. Do not infer V5 operation from the
resource priorities alone.
