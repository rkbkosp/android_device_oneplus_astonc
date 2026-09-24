#include <aidl/android/hardware/power/stats/IPowerStats.h>
#include <android/binder_manager.h>

#include <cstdint>
#include <iostream>
#include <memory>
#include <vector>

using aidl::android::hardware::power::stats::Channel;
using aidl::android::hardware::power::stats::EnergyConsumer;
using aidl::android::hardware::power::stats::EnergyConsumerResult;
using aidl::android::hardware::power::stats::EnergyMeasurement;
using aidl::android::hardware::power::stats::IPowerStats;

int main() {
    constexpr char kService[] = "android.hardware.power.stats.IPowerStats/default";
    ndk::SpAIBinder binder(AServiceManager_checkService(kService));
    if (!binder.get()) {
        std::cerr << "PowerStats HAL is not registered\n";
        return 1;
    }

    std::shared_ptr<IPowerStats> stats = IPowerStats::fromBinder(binder);
    if (!stats) {
        std::cerr << "Could not create IPowerStats client\n";
        return 1;
    }

    std::vector<Channel> channels;
    auto status = stats->getEnergyMeterInfo(&channels);
    if (!status.isOk()) {
        std::cerr << "getEnergyMeterInfo: " << status.getDescription() << '\n';
        return 1;
    }
    std::cout << "channels=" << channels.size() << '\n';
    for (const auto& channel : channels) {
        std::cout << "channel id=" << channel.id << " name=" << channel.name
                  << " subsystem=" << channel.subsystem << '\n';
    }

    std::vector<EnergyMeasurement> measurements;
    status = stats->readEnergyMeter({}, &measurements);
    if (!status.isOk()) {
        std::cerr << "readEnergyMeter: " << status.getDescription() << '\n';
        return 1;
    }
    std::cout << "measurements=" << measurements.size() << '\n';
    for (const auto& measurement : measurements) {
        std::cout << "measurement id=" << measurement.id
                  << " energyUWs=" << measurement.energyUWs
                  << " timestampMs=" << measurement.timestampMs
                  << " durationMs=" << measurement.durationMs << '\n';
    }

    std::vector<EnergyConsumer> consumers;
    status = stats->getEnergyConsumerInfo(&consumers);
    if (!status.isOk()) {
        std::cerr << "getEnergyConsumerInfo: " << status.getDescription() << '\n';
        return 1;
    }
    std::cout << "consumers=" << consumers.size() << '\n';
    for (const auto& consumer : consumers) {
        std::cout << "consumer id=" << consumer.id << " name=" << consumer.name
                  << " type=" << static_cast<int32_t>(consumer.type)
                  << " ordinal=" << consumer.ordinal << '\n';
    }

    std::vector<EnergyConsumerResult> consumed;
    status = stats->getEnergyConsumed({}, &consumed);
    if (!status.isOk()) {
        std::cerr << "getEnergyConsumed: " << status.getDescription() << '\n';
        return 1;
    }
    std::cout << "consumed=" << consumed.size() << '\n';
    for (const auto& result : consumed) {
        std::cout << "consumed id=" << result.id
                  << " energyUWs=" << result.energyUWs
                  << " timestampMs=" << result.timestampMs << '\n';
    }

    return 0;
}
