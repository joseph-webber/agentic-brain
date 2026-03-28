#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace agentic_brain::audio {

struct Vec3 {
    float x {0.0f};
    float y {0.0f};
    float z {1.0f};
};

struct StereoFrame {
    float left {0.0f};
    float right {0.0f};
};

struct ListenerPose {
    float yawDegrees {0.0f};
    float pitchDegrees {0.0f};
    float rollDegrees {0.0f};
};

struct SourceState {
    Vec3 position;
    float gain {1.0f};
};

class BinauralRenderer {
public:
    explicit BinauralRenderer(std::size_t sourceCount)
        : sources_(sourceCount) {}

    void setListenerPose(const ListenerPose& pose) {
        listener_ = pose;
    }

    void setSource(std::size_t index, const Vec3& position, float gain) {
        if (index >= sources_.size()) {
            return;
        }
        sources_[index] = SourceState { position, gain };
    }

    StereoFrame renderMono(float sample, std::size_t index) const {
        if (index >= sources_.size()) {
            return {};
        }

        const auto& source = sources_[index];
        const float yawRadians = listener_.yawDegrees * static_cast<float>(M_PI) / 180.0f;
        const float rotatedX = std::cos(-yawRadians) * source.position.x - std::sin(-yawRadians) * source.position.z;
        const float rotatedZ = std::sin(-yawRadians) * source.position.x + std::cos(-yawRadians) * source.position.z;
        const float azimuth = std::atan2(rotatedX, std::max(0.001f, rotatedZ));
        const float pan = std::clamp(std::sin(azimuth), -1.0f, 1.0f);
        const float distance = std::max(0.25f, std::sqrt(
            source.position.x * source.position.x +
            source.position.y * source.position.y +
            source.position.z * source.position.z
        ));
        const float attenuation = source.gain / distance;

        StereoFrame frame;
        frame.left = sample * attenuation * (0.5f * (1.0f - pan));
        frame.right = sample * attenuation * (0.5f * (1.0f + pan));
        return frame;
    }

private:
    ListenerPose listener_ {};
    std::vector<SourceState> sources_;
};

}  // namespace agentic_brain::audio

extern "C" {

using ABRendererHandle = agentic_brain::audio::BinauralRenderer*;

ABRendererHandle ab_create_renderer(std::size_t source_count) {
    return new agentic_brain::audio::BinauralRenderer(source_count);
}

void ab_destroy_renderer(ABRendererHandle handle) {
    delete handle;
}

void ab_set_listener_pose(ABRendererHandle handle, float yaw, float pitch, float roll) {
    if (!handle) {
        return;
    }
    handle->setListenerPose({yaw, pitch, roll});
}

void ab_set_source_position(
    ABRendererHandle handle,
    std::size_t index,
    float x,
    float y,
    float z,
    float gain
) {
    if (!handle) {
        return;
    }
    handle->setSource(index, {x, y, z}, gain);
}

void ab_render_mono_frame(
    ABRendererHandle handle,
    float sample,
    std::size_t index,
    float* left,
    float* right
) {
    if (!handle || !left || !right) {
        return;
    }
    const auto frame = handle->renderMono(sample, index);
    *left = frame.left;
    *right = frame.right;
}

}
