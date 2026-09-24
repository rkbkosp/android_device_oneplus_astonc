#include <aidl/android/hardware/power/stats/BnPowerStats.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>

#include <cerrno>
#include <cstdint>
#include <fstream>
#include <memory>
#include <string>
#include <time.h>
#include <utility>
#include <vector>

namespace stats = aidl::android::hardware::power::stats;

namespace {

constexpr char kEnergyPath[] =
        "/sys/kernel/oplus_battery_energy/battery_discharge_energy_uws";
constexpr char kReadyProperty[] = "vendor.astonc.powerstats.ready";
constexpr int32_t kBatteryChannelId = 0;

class AstoncPowerStats final : public stats::BnPowerStats {
  public:
    ndk::ScopedAStatus getPowerEntityInfo(std::vector<stats::PowerEntity>* result) override {
        result->clear();
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus getStateResidency(const std::vector<int32_t>& ids,
                                         std::vector<stats::StateResidencyResult>* result) override {
        result->clear();
        if (!ids.empty()) {
            return ndk::ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
        }
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus getEnergyConsumerInfo(std::vector<stats::EnergyConsumer>* result) override {
        result->clear();
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus getEnergyConsumed(
            const std::vector<int32_t>& ids,
            std::vector<stats::EnergyConsumerResult>* result) override {
        result->clear();
        if (!ids.empty()) {
            return ndk::ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
        }
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus getEnergyMeterInfo(std::vector<stats::Channel>* result) override {
        result->clear();
        stats::Channel channel;
        channel.id = kBatteryChannelId;
        channel.name = "Battery discharge (fuel gauge derived)";
        channel.subsystem = "Battery";
        result->push_back(std::move(channel));
        return ndk::ScopedAStatus::ok();
    }

    ndk::ScopedAStatus readEnergyMeter(const std::vector<int32_t>& ids,
                                       std::vector<stats::EnergyMeasurement>* result) override {
        result->clear();
        for (const int32_t id : ids) {
            if (id != kBatteryChannelId) {
                return ndk::ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
            }
        }

        std::ifstream energyFile(kEnergyPath);
        int64_t energyUws = -1;
        if (!(energyFile >> energyUws) || energyUws < 0) {
            LOG(ERROR) << "Cannot read " << kEnergyPath;
            return ndk::ScopedAStatus::fromServiceSpecificError(EIO);
        }

        struct timespec now;
        if (clock_gettime(CLOCK_BOOTTIME, &now) != 0) {
            return ndk::ScopedAStatus::fromServiceSpecificError(errno);
        }
        const int64_t timestampMs = now.tv_sec * 1000LL + now.tv_nsec / 1000000LL;

        stats::EnergyMeasurement measurement;
        measurement.id = kBatteryChannelId;
        measurement.timestampMs = timestampMs;
        measurement.durationMs = timestampMs;
        measurement.energyUWs = energyUws;
        result->push_back(std::move(measurement));
        return ndk::ScopedAStatus::ok();
    }
};

}  // namespace

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    auto service = ndk::SharedRefBase::make<AstoncPowerStats>();
    const std::string instance = std::string(stats::IPowerStats::descriptor) + "/default";
    const binder_status_t status = AServiceManager_addService(service->asBinder().get(),
                                                               instance.c_str());
    if (status != STATUS_OK) {
        LOG(ERROR) << "Cannot register " << instance << ": " << status;
        return 1;
    }

    // The stock process keeps its independent Oplus HandleFactory service.
    // It starts only after this process owns the default PowerStats instance.
    if (!android::base::SetProperty(kReadyProperty, "1")) {
        LOG(ERROR) << "Cannot mark PowerStats ready; HandleFactory will not start";
    }

    ABinderProcess_joinThreadPool();
    return 1;
}
