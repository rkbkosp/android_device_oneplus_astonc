# PJE110 Widevine OEMCrypto client libraries

These three 64-bit libraries come from the unmodified PJE110YS_16.0.5.1002
stock `vendor.img` and `odm.img` in
`/root/Ace3_PJE110_16.0.5.1002_stock_vendor_odm.zip` (SHA-256
`5d7de23328f64943c070486f7eb6714e9b0c4f28d412170ce0ea60f9d54f5442`).
The archive's image checksums both passed. They contain no keybox or license
material.

| Library | Stock path | SHA-256 |
| --- | --- | --- |
| `liboemcrypto.so` | `/odm/lib64` | `548915149dfba65790b8f23a27a6815d268ad96565a2b918bd6d5b6b99a261c0` |
| `libcpion.so` | `/vendor/lib64` | `86a12662b867ee6592a4c5816bec20245b9e10212e3718d0439bf2e2c92b750b` |
| `libtrustedapploader.so` | `/vendor/lib64` | `e8833241864e86bb360bdc844601df15518e401a27d5889a17d6aa41b0233e64` |

The existing 64-bit Widevine service and `libwvaidl.so` match the stock image
byte for byte. `libwvaidl.so` loads `liboemcrypto.so` dynamically. The original
bugreport reported that this load failed and Widevine fell back to L3. These
libraries restore the stock loader input and its two missing direct dependencies.

The loader may still fall back to L3 if another dependency, the trusted app, or
provisioning fails. After flashing a build containing these libraries, check
`/odm/lib64/liboemcrypto.so`, `/vendor/lib64/libcpion.so`, and
`/vendor/lib64/libtrustedapploader.so`, then capture Widevine initialization
logs and the reported security level. Do not claim L1 based on the files alone.

`m libcpion libtrustedapploader liboemcrypto -j8` passed on 2026-09-24 with
Soong ELF checks enabled. The three installed files under `/data/crdroid/out`
match the stock checksums above. This was a targeted build; no new ROM package
or on-device Widevine test has been completed.
