#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

# AAPT
PRODUCT_AAPT_CONFIG := normal
PRODUCT_AAPT_PREF_CONFIG := xxhdpi

# Audio
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/configs/audio/audio_policy_volumes.xml:$(TARGET_COPY_OUT_VENDOR)/etc/audio_policy_volumes.xml \
    $(LOCAL_PATH)/configs/audio/default_volume_tables.xml:$(TARGET_COPY_OUT_VENDOR)/etc/default_volume_tables.xml

# LHDC encoder blobs from PJE110 16.0.5.1002. Bluetooth APEX also includes
# these libraries; see lhdc/README.md for the port status.
PRODUCT_PACKAGES += \
    liblhdc \
    liblhdcBT_enc \
    liblhdcv5 \
    liblhdcv5BT_enc

# Stock Qualcomm Bluetooth audio HAL from the same firmware (PJE110 16.0.5.1002).
# It is the LHDC-aware counterpart of the AOSP AIDL impl: it registers the AIDL
# session for A2DP_SOFTWARE_ENCODING_DATAPATH and routes LHDC
# (is_lhdc_connected / "open aidl_1_0 success for a2dp(LHDC)"). The AOSP impl
# alone fails that handshake on this device, so the software datapath stays dead
# and every codec is silent once A2DP offload is disabled. Installed to
# vendor/lib64/hw/ by lhdc/Android.bp (relative_install_path: "hw");
# PRODUCT_COPY_FILES cannot carry an ELF prebuilt. See lhdc/README.md.
PRODUCT_PACKAGES += \
    audio.bluetooth_qti.default

# Boot animation
TARGET_SCREEN_HEIGHT := 2780
TARGET_SCREEN_WIDTH := 1264

# Display
PRODUCT_PACKAGES += \
    OplusLtpo

PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/configs/display/displayconfig.xml:$(TARGET_COPY_OUT_VENDOR)/etc/displayconfig/display_id_4630946607878435459.xml

PRODUCT_SYSTEM_PROPERTIES += \
    sys.brightness.disable_gamma_conversion=true

$(call soong_config_set,qtidisplay,pxlw_vendor_namespace,vendor/oneplus/astonc)
$(call soong_config_set_bool,qtidisplay,pxlw_hw_iris7,true)

# Fingerprint
TARGET_HAS_UDFPS := true

# IR
$(call inherit-product, vendor/oneplus/ir/config.mk)

PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.consumerir.xml:$(TARGET_COPY_OUT_ODM)/etc/permissions/android.hardware.consumerir.xml

PRODUCT_PACKAGES += \
    android.hardware.ir-service.oplus

# Fingerprint
$(call soong_config_set,surfaceflinger,udfps_lib,//hardware/oplus:libudfps_extension.oplus)
$(call soong_config_set_bool,qtidisplay,oplus_udfps,true)

# LiveDisplay
$(call soong_config_set_bool,OPLUS_LINEAGE_LIVEDISPLAY_HAL,ENABLE_AF,true)
$(call soong_config_set_bool,OPLUS_LINEAGE_LIVEDISPLAY_HAL,ENABLE_SE,false)

# Metro assistant
# Runtime data packs. hangzhou-v2.json is the generated full city pack
# (tools/metro/convert_hangzhou_pack.py, cellMatchMode LOCAL_CID_COMPAT); hz-lite-v2.json
# is the accepted 1 line / 5 station prototype baseline (CELL_ID_ONLY_DEBUG) kept in tree
# for regression switching. METRO_DEFAULT_PACK selects which of the two is installed at
# the canonical path the app loads (MetroContract.PACK_PATH), so the regression baseline
# is one build variable away: METRO_DEFAULT_PACK=hz-lite-v2.json.
METRO_DEFAULT_PACK ?= hangzhou-v2.json
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/metro/$(METRO_DEFAULT_PACK):$(TARGET_COPY_OUT_PRODUCT)/etc/metro/hangzhou-v2.json \
    $(LOCAL_PATH)/metro/hz-lite-v2.json:$(TARGET_COPY_OUT_PRODUCT)/etc/metro/hz-lite-v2.json

# Permission configuration of the privileged metro app. Both files go to system_ext on
# purpose: PermissionManager validates the privileged allowlist of the partition the
# package lives on (AppIdPermissionPolicy.getPrivilegedPermissionAllowlistState ->
# isSystemExt -> system_ext allowlist) and reads default-permissions from every partition
# (DefaultPermissionGrantPolicy.java:1520).
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/metro/privapp-permissions-dev.contextsurface.metro.xml:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/permissions/privapp-permissions-dev.contextsurface.metro.xml \
    $(LOCAL_PATH)/metro/default-permissions-dev.contextsurface.metro.xml:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/default-permissions/default-permissions-dev.contextsurface.metro.xml

PRODUCT_PACKAGES += \
    HangzhouMetro

# Product feature flag read by the framework trigger service, Settings and the app.
# SELinux context: device/oneplus/astonc/sepolicy/system_ext/{public/property.te,private/property_contexts}
PRODUCT_PRODUCT_PROPERTIES += \
    ro.metro.assistant_supported=true

# Overlays
DEVICE_PACKAGE_OVERLAYS += \
    $(LOCAL_PATH)/overlay-lineage

# Merge the overlays above into the target APKs at build time instead of turning them into
# auto-generated runtime RROs (PRODUCT_ENFORCE_RRO_TARGETS is set to "*" by generic_system.mk).
# The generated <target>__<product>__auto_generated_rro_vendor.apk variants are not applied to
# the system_ext targets used here (Settings, Updater), which silently left the stock values
# (e.g. build_maintainer_summary = "Unofficial", updater_server_url = crDroid's GitHub JSON).
# The overlays inherited from sm8550-common are listed for the same reason.
PRODUCT_ENFORCE_RRO_EXCLUDED_OVERLAYS += \
    device/oneplus/astonc/overlay-lineage \
    device/oneplus/sm8550-common/overlay-lineage

PRODUCT_PACKAGES += \
    KeyHandlerResTarget \
    OPlusFrameworksResTarget \
    OPlusSettingsProviderResTarget \
    OPlusSettingsResTarget \
    OPlusSystemUIResTarget \
    OPlusWifiResTarget

# Power
$(call soong_config_set,qtipower,mode_ext_lib,power-ext-oplus)

# Sensors
PRODUCT_PACKAGES += \
    sensors.oplus

# Soong namespaces
PRODUCT_SOONG_NAMESPACES += \
    $(LOCAL_PATH)

# Telephony
PRODUCT_PACKAGES += \
    OplusEsimSwitcher \
    OplusEuicc

PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.telephony.euicc.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/permissions/android.hardware.telephony.euicc.xml

# Touch
$(call soong_config_set_bool,OPLUS_LINEAGE_TOUCH_HAL,USE_OPLUSTOUCH,true)

# Vibrator
PRODUCT_PACKAGES += \
    vendor.qti.hardware.vibrator.service.oplus

$(call soong_config_set_bool,OPLUS_LINEAGE_VIBRATOR_HAL,USE_EFFECT_STREAM,true)

# Inherit from the common OEM chipset makefile.
$(call inherit-product, device/oneplus/sm8550-common/common.mk)

# Inherit from the proprietary files makefile.
$(call inherit-product, vendor/oneplus/astonc/astonc-vendor.mk)
