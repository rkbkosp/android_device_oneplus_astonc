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

The `audio.bluetooth.default` path supplies PCM to the source stack's LHDC
encoder. The `bluetooth` policy module also carries the hearing aid port.
The stock `audio.bluetooth_qti.default.so` is declared as a prebuilt but is
not installed by astonc:

* HAL blob `vendor/oneplus/sm8550-common/proprietary/vendor/lib64/hw/audio.bluetooth_qti.default.so`,
  declared as `cc_prebuilt_library_shared` in `vendor/oneplus/sm8550-common/Android.bp`
  (`relative_install_path: "hw"`; ELF prebuilts cannot go through `PRODUCT_COPY_FILES`).
* Audio policy: the `bluetooth` module carries PCM A2DP for AAC, SBC, and LHDC,
  plus hearing aid. `primary` retains encoded A2DP profiles in the shared policy,
  but astonc disables hardware A2DP offload.
* `AudioSystem.bluetoothA2dpCodecToAudioFormat()` maps LHDC V3 and V5 to
  `AUDIO_FORMAT_LHDC`. This lets AudioPolicyManager select the `bluetooth`
  module when LHDC is negotiated. Without the mapping, it reports
  `AUDIO_FORMAT_DEFAULT` and can keep the primary A2DP route.
* The stack keeps AAC, SBC, and LHDC off that datapath explicitly: `uses_host_encoding()` in
  `packages/modules/Bluetooth/system/audio_hal_interface/aidl/a2dp/a2dp_encoding_aidl.cc`
  skips both offload branches of `setup_codec()`, so these codecs reach
  `getHalPcmConfiguration()` and `A2DP_SOFTWARE_ENCODING_DATAPATH`.

The Bluetooth AIDL provider is registered by `android.hardware.audio.service`
from `android.hardware.bluetooth.audio-impl`, separately from the audio policy
module. `lshal` lists HIDL services and cannot verify that registration. The
2026-09-24 device capture showed that the software session started, but
`audio.bluetooth.default` reported that session type not ready. AudioPolicyManager
then failed to open A2DP output with `-19` and routed LHDC and AAC to the
speaker. Removing the `bluetooth_qti` policy module alone did not fix this:
`AudioExtn::a2dp_source_feature_init()` in the primary HAL also loads
`btaudio_offload_if.so` when `vendor.audio.feature.a2dp_offload.enable=true`.
That library brings the QTI AIDL session library into the same audio service
process as the AOSP session library. Both export the same
`BluetoothAudioSessionInstance` symbols with incompatible session interfaces.

A live test set `vendor.audio.feature.a2dp_offload.enable=false` and restarted
`vendor.audio-hal`. The QTI session libraries disappeared from the audio service
process, A2DP output opened successfully, and the headset became the selected
media output. The user confirmed audible AAC and LHDC playback and smooth video.
`astonc/vendor.prop` now disables the Qualcomm offload client and A2DP hardware
offload by default. `ro.bluetooth.a2dp_offload.supported=false` keeps software
encoding selected even if an old persisted offload setting is still `false`.
The common properties use optional defaults so other sm8550 devices retain their
previous values. The QTI/AOSP symbol collision is the likely mechanism; the
live test establishes that disabling the QTI client fixes routing.

The intended LHDC path is host encoding; the ADSP offload capability string
does not list LHDC. The public V5 code targets a newer encoder release than the
stock PJE110 V5 binary despite the adjusted ABI and capability subset.

Validation after flashing a new build still requires AAC and LHDC-capable
headsets: check that `bluetooth_qti` is absent from audio policy, QTI session
libraries are absent from the audio service, A2DP appears in available outputs,
and the software session carries both codecs. Check audible playback, video
smoothness, reconnect, and fallback. Do not infer V5 operation from resource
priorities alone.
