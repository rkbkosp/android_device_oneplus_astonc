#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

# Build identity mirrored from the stock OnePlus Ace 3 (PJE110) 16.0.5.1002 files.
#
# A stock device reports no single one of those files: /odm/etc/build.prop is an import rule
# that pulls in /odm/etc/<ro.boot.prjname>/build.<ro.boot.flag>.prop (= build.default.prop,
# prjname 23801, flag default), and odm is loaded after system/vendor/product, so the profile
# owns ro.build.id, ro.build.fingerprint and ro.build.version.incremental while the system
# image keeps display.id, description, date, host/user/flavor:
#
#   system image  id BP2A.250605.015, incremental 1783519872530, flavor qssi-user,
#                 host kvm-slave-build-s-system-12140018, user root, date 1783519872,
#                 security_patch 2026-07-01, ro.product.* = oplus/ossi
#   odm profile   id TP1A.220905.001, fingerprint .../U.202607082244:user/release-keys,
#                 unprefixed ro.product.* = OnePlus/PJE110/PJE110/OP5CF9L1,
#                 first_api_level 34, odm/vendor/bootimage fingerprint ...U.202607082244...
#
# Every key below is consumed by build/soong/scripts/gen_build_prop.py; the per-partition
# property names (ro.product.<partition>.*, ro.<partition>.build.*) are accepted there in
# addition to the shared keys, which is the only way to express a device whose partitions
# carry different identities. A key that does not exist aborts the build.
# Build date, version.incremental and the security patch level are deliberately NOT mirrored:
# both OTA paths refuse a package that looks older than what is installed. recovery compares the
# package's post-timestamp with the device's ro.build.date.utc, and update_engine
# (DeltaPerformer::CheckSPLDowngrade) rejects a payload whose security_patch_level is older than
# the device's - hard when ro.boot.verifiedbootstate reads green, and with a mandatory data wipe
# otherwise. Everything the ROM is identified by - build.id, fingerprints, product names, the
# vendor/odm SDK and release levels - is still the stock one; only the timestamps and the patch
# level stay real.
PRODUCT_BUILD_PROP_OVERRIDES += \
    BuildFingerprint=OnePlus/PJE110/OP5CF9L1:16/TP1A.220905.001/U.202607082244:user/release-keys \
    BuildId=TP1A.220905.001 \
    BuildDesc="qssi-user 16 BP2A.250605.015 1783519872530 release-keys" \
    BuildFlavor=qssi-user \
    BuildHostname=kvm-slave-build-s-system-12140018 \
    BuildUsername=root \
    Platform_base_os=OnePlus/PJE110/OP5CF9L1:14/TP1A.220905.001/U.1472d34_2_1:user/release-keys \
    DeviceName=OP5CF9L1 \
    DeviceProduct=PJE110 \
    SystemBrand=oplus \
    SystemDevice=ossi \
    SystemManufacturer=oplus \
    SystemModel=ossi \
    SystemName=ossi \
    ro.product.product.brand=oplus \
    ro.product.product.device=ossi \
    ro.product.product.manufacturer=oplus \
    ro.product.product.model=ossi \
    ro.product.product.name=ossi \
    ro.product.system_ext.brand=oplus \
    ro.product.system_ext.device=ossi \
    ro.product.system_ext.manufacturer=oplus \
    ro.product.system_ext.model=ossi \
    ro.product.system_ext.name=ossi \
    ro.product.vendor.brand=OnePlus \
    ro.product.vendor.device=OP5CF9L1 \
    ro.product.vendor.manufacturer=OnePlus \
    ro.product.vendor.model=PJE110 \
    ro.product.vendor.name=PJE110 \
    ro.product.odm.brand=OnePlus \
    ro.product.odm.device=OP5CF9L1 \
    ro.product.odm.manufacturer=OnePlus \
    ro.product.odm.model=PJE110 \
    ro.product.odm.name=PJE110 \
    ro.system.build.fingerprint=oplus/ossi/ossi:16/BP2A.250605.015/1783519872530:user/release-keys \
    ro.product.build.fingerprint=oplus/ossi/ossi:16/BP2A.250605.015/1783519872530:user/release-keys \
    ro.system_ext.build.fingerprint=oplus/ossi/ossi:16/BP2A.250605.015/1783519872530:user/release-keys \
    ro.system.build.id=BP2A.250605.015 \
    ro.product.build.id=BP2A.250605.015 \
    ro.system_ext.build.id=BP2A.250605.015 \
    ro.vendor.build.fingerprint=OnePlus/PJE110/OP5CF9L1:16/TP1A.220905.001/U.202607082244:user/release-keys \
    ro.odm.build.fingerprint=OnePlus/PJE110/OP5CF9L1:16/TP1A.220905.001/U.202607082244:user/release-keys \
    ro.vendor.build.version.release=13 \
    ro.vendor.build.version.release_or_codename=13 \
    ro.vendor.build.version.sdk=33 \
    ro.vendor.build.version.sdk_full=33 \
    ro.product.bootimage.brand=OnePlus \
    ro.product.bootimage.device=OP5CF9L1 \
    ro.product.bootimage.manufacturer=OnePlus \
    ro.product.bootimage.model=PJE110 \
    ro.product.bootimage.name=PJE110 \
    ro.bootimage.build.fingerprint=OnePlus/PJE110/OP5CF9L1:16/TP1A.220905.001/U.202607082244:user/release-keys \
    ro.build.display.id="BP2A.250605.015 release-keys"

# The system_ext build-info section was not part of the package readout; its values are set
# to the system/product image values because all three come from the same QSSI/OSSI build
# (ro.system_ext.build.* = oplus/ossi:16/BP2A... is the expected shape, not an observed one).

# /product/etc/build.prop is the last property file init reads and it is loaded under
# kInitContext, so the profile's device-owned declarations that are not generated per
# partition are placed here. Property files under /odm are checked as vendor_init
# (property_service.cpp:LoadProperties/kVendorContext), which may not set system owned
# props, so an odm import cannot carry them.
PRODUCT_PRODUCT_PROPERTIES += \
    ro.product.brand=OnePlus \
    ro.product.manufacturer=OnePlus \
    ro.product.model=PJE110 \
    ro.product.name=PJE110 \
    ro.product.device=OP5CF9L1 \
    ro.product.first_api_level=34 \
    ro.build.emergency_base_os=OnePlus/PJE110/OP5CF9L1:14/TP1A.220905.001/U.1472d34_2_1:user/release-keys

# The profile does not touch display.id, so a stock device shows the system image id next to
# the profile's ro.build.id (that value lives in PRODUCT_BUILD_PROP_OVERRIDES above because it
# contains a space). property_source_order is stock's own value.
PRODUCT_SYSTEM_PROPERTIES += \
    ro.product.property_source_order=odm,vendor,product,system_ext,system
