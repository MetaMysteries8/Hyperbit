#include "MicroBit.h"
#include "MemorySource.h"
#include "MicRecorder.h"
#include "VoiceBLEService.h"
#include "WukongLights.h"
#include "WukongRainbow.h"
#include "AliveAnimator.h"
#include "ImaAdpcm.h"
#include "ble.h"
#include "ble_hci.h"

using namespace codal;
MicroBit uBit;

static bool playTtsInterruptible(
    MemorySource &source,
    ImaAdpcmState &decoder,
    AliveAnimator &animator,
    const uint8_t *adpcm,
    uint16_t len
) {
    uint8_t pcm[256];
    int out = 0;
    int peak = 0;

    animator.setState(PHYS_SPEAKING);

    for (uint16_t i = 0; i < len; ++i) {
        if (uBit.buttonA.isPressed()) {
            animator.setOutputLevel(0);
            return false;
        }

        uint8_t b = adpcm[i];
        int16_t s0 = decoder.decode(b & 0x0F);
        int16_t s1 = decoder.decode((b >> 4) & 0x0F);

        int a0 = s0 < 0 ? -((int)s0) : (int)s0;
        int a1 = s1 < 0 ? -((int)s1) : (int)s1;
        if (a0 > peak) peak = a0;
        if (a1 > peak) peak = a1;

        int p0 = (s0 >> 8) + 128;
        int p1 = (s1 >> 8) + 128;
        if (p0 < 0) p0 = 0;
        if (p0 > 255) p0 = 255;
        if (p1 < 0) p1 = 0;
        if (p1 > 255) p1 = 255;

        pcm[out++] = (uint8_t)p0;
        pcm[out++] = (uint8_t)p1;

        if (out >= (int)sizeof(pcm)) {
            source.play(pcm, out);
            int level = peak >> 7;
            if (level > 255) level = 255;
            animator.setOutputLevel((uint8_t)level);
            animator.tick();
            peak = 0;
            out = 0;
        }
    }

    if (out) {
        source.play(pcm, out);
        int level = peak >> 7;
        if (level > 255) level = 255;
        animator.setOutputLevel((uint8_t)level);
        animator.tick();
    }

    animator.setOutputLevel(0);
    return !uBit.buttonA.isPressed();
}

static void drainMicPackets(
    VoiceBLEService &ble,
    MicRecorder &rec,
    uint8_t &sequence,
    bool drainAll
) {
    uint8_t packet[HYPERBIT_NUS_AUDIO_PAYLOAD];
    int budget = drainAll ? 10000 : 8;

    while (budget-- > 0) {
        int n = rec.read(packet, sizeof(packet));
        if (n <= 0)
            break;

        int tries = 0;
        while (!ble.sendMic(sequence, packet, n) && ble.getConnected() && tries < 100) {
            uBit.sleep(2);
            ++tries;
        }

        if (tries >= 100)
            rec.markTransportOverflow();

        ++sequence;
    }
}

static void finishMicUtterance(VoiceBLEService &ble, MicRecorder &rec, uint8_t &sequence) {
    rec.stop();
    uBit.audio.deactivateMic();
    drainMicPackets(ble, rec, sequence, true);

    uint32_t samples = rec.samples();
    uint8_t low = samples & 0xFF;
    uint8_t mid = (samples >> 8) & 0xFF;
    uint8_t high = (samples >> 16) & 0x7F;
    if (rec.overflowed())
        high |= 0x80;

    ble.sendControl(HB_EVT_PTT_END, low, mid, high);
}

static uint8_t visualStateFromPc(uint8_t pcState) {
    switch (pcState) {
        case 1: return PHYS_IDLE;
        case 2: return PHYS_LISTENING;
        case 3: return PHYS_TRANSCRIBING;
        case 4: return PHYS_THINKING;
        case 5: return PHYS_SPEAKING;
        case 6: return PHYS_ERROR;
        default: return PHYS_IDLE;
    }
}

static bool stateIsBusyForPtt(uint8_t state) {
    return state == PHYS_UPLOADING ||
           state == PHYS_TRANSCRIBING ||
           state == PHYS_THINKING ||
           state == PHYS_SPEAKING;
}

static void kickHalfOpenConnection(VoiceBLEService &voice) {
    microbit_gaphandle_t handle = voice.getConnectionHandle();
    if (handle != BLE_CONN_HANDLE_INVALID) {
        (void)sd_ble_gap_disconnect(handle, BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
    }
}

static void suspendDisplayForConnection(bool &displaySuspended) {
    if (displaySuspended)
        return;
    uBit.display.clear();
    uBit.display.disable();
    displaySuspended = true;
}

static void resumeDisplayAfterConnection(bool &displaySuspended) {
    if (!displaySuspended)
        return;
    uBit.display.enable();
    uBit.display.setDisplayMode(DISPLAY_MODE_GREYSCALE);
    uBit.display.clear();
    displaySuspended = false;
}

int main() {
    uBit.init();

    // Finish all boot-time peripheral setup before becoming connectable.
    uBit.bleManager.stopAdvertising();

    VoiceBLEService voice;
    uBit.bleManager.setTransmitPower(7);
    uBit.bleManager.setAdvertiseOnDisconnect(true);

    // Configure the microphone graph, but keep both mic capture and speaker PWM
    // inactive until an application session actually needs them.
    uBit.audio.mic->setSampleRate(8000);
    uBit.audio.setPinEnabled(false);
    uBit.audio.setSpeakerEnabled(true);
    uBit.audio.setVolume(210);

    MemorySource ttsSource;
    ttsSource.setFormat(DATASTREAM_FORMAT_8BIT_UNSIGNED);
    ttsSource.setBufferSize(256);
    bool audioOutputReady = false;

    SplitterChannel *micChannel = uBit.audio.splitter->createChannel();
    MicRecorder recorder(*micChannel);
    recorder.stop();
    uBit.audio.deactivateMic();

    WukongLights baseLights(uBit.i2c);
    WukongRainbow rainbow(uBit.io.P16);

    bool wukongBaseOk = baseLights.selfTest();
    rainbow.selfTest();
    rainbow.setAll(0, 6, 18);
    uBit.display.print(wukongBaseOk ? "H" : "W");
    uBit.sleep(350);

    AliveAnimator animator(uBit, baseLights, rainbow);
    animator.setState(PHYS_DISCONNECTED);

    // Start BLE only after boot/self-test writes are finished.
    uBit.bleManager.advertise();

    bool lastRawConnected = false;
    bool applicationReady = false;
    bool displaySuspended = false;
    bool pttActive = false;
    bool lastA = false;
    bool lastB = false;
    bool lastAB = false;
    bool speaking = false;
    bool muted = false;
    uint8_t lastPcState = 255;
    uint8_t micSequence = 0;
    ImaAdpcmState ttsDecoder;

    int interruptGraceTicks = 0;
    int animationDivider = 0;

    // Windows can leave a raw BLE link half-open. The 45-second limit covers
    // Windows' own discovery timeout while guaranteeing eventual recovery.
    int halfOpenTicks = 0;
    const int HALF_OPEN_LIMIT_TICKS = 4500; // ~45 seconds at 10 ms/tick

    while (true) {
        bool rawConnected = voice.getConnected();

        if (rawConnected != lastRawConnected) {
            lastRawConnected = rawConnected;
            applicationReady = false;
            halfOpenTicks = 0;

            if (rawConnected) {
                // Connection first, personality second: shut off the refresh
                // driver before Windows finishes GATT discovery/CCCD setup.
                suspendDisplayForConnection(displaySuspended);
            } else {
                if (pttActive) {
                    recorder.stop();
                    pttActive = false;
                }
                uBit.audio.deactivateMic();
                voice.abortTts();
                resumeDisplayAfterConnection(displaySuspended);
                animator.setState(PHYS_DISCONNECTED);
                lastPcState = 255;
            }
        }

        // If a client disables TX notifications after being ready, fall back to
        // the isolated handshake state rather than continuing a half-session.
        if (rawConnected && applicationReady && !voice.notificationsReady()) {
            applicationReady = false;
            suspendDisplayForConnection(displaySuspended);
        }

        if (rawConnected && !applicationReady) {
            if (++halfOpenTicks >= HALF_OPEN_LIMIT_TICKS) {
                kickHalfOpenConnection(voice);
                halfOpenTicks = 0;
                uBit.sleep(10);
                continue;
            }

            // HELLO is not sufficient: remain black/peripheral-free until READY
            // itself is successfully queued to the subscribed TX characteristic.
            if (!voice.notificationsReady()) {
                uBit.sleep(10);
                continue;
            }

            if (!voice.sendControl(
                    HB_EVT_READY,
                    HYPERBIT_PROTOCOL_VERSION,
                    HYPERBIT_FIRMWARE_REVISION,
                    HYPERBIT_CAPABILITIES)) {
                uBit.sleep(10);
                continue;
            }

            applicationReady = true;
            halfOpenTicks = 0;
            resumeDisplayAfterConnection(displaySuspended);
            animator.setState(PHYS_IDLE);
            lastPcState = 255;

            // This status report is intentionally after READY succeeds: Wukong
            // traffic and personality resume only after the connection barrier.
            voice.sendControl(HB_EVT_WUKONG_STATUS, baseLights.ok() ? 1 : 0);
        }

        if (!applicationReady) {
            // Disconnected animation is allowed; raw-connected handshakes have
            // already continued above with the matrix physically disabled.
            if (!rawConnected) {
                if (++animationDivider >= 3) {
                    animationDivider = 0;
                    animator.tick();
                }
            }
            uBit.sleep(10);
            continue;
        }

        if (interruptGraceTicks > 0)
            --interruptGraceTicks;

        bool a = uBit.buttonA.isPressed();
        bool b = uBit.buttonB.isPressed();
        bool ab = a && b;

        if (ab && !lastAB) {
            muted = !muted;
            animator.setMuted(muted);
            voice.sendControl(HB_EVT_MUTE_CHANGED, muted ? 1 : 0);
        } else if (!ab) {
            if (a && !lastA) {
                voice.abortTts();
                voice.sendControl(HB_EVT_CANCEL);
                interruptGraceTicks = 300;
                animator.setState(PHYS_IDLE);
                lastPcState = voice.pcState();
            }

            if (b && !lastB)
                voice.sendControl(HB_EVT_REPLAY);
        }

        lastA = a;
        lastB = b;
        lastAB = ab;

        if (voice.ttsReady() && !speaking) {
            speaking = true;
            recorder.stop();
            pttActive = false;
            uBit.audio.deactivateMic();

            if (!audioOutputReady) {
                uBit.audio.enable();
                uBit.audio.mixer.addChannel(ttsSource, 8000, 255);
                audioOutputReady = true;
            }

            if (voice.ttsFirstSegment())
                ttsDecoder.reset();

            bool completed = true;
            if (!muted) {
                completed = playTtsInterruptible(
                    ttsSource,
                    ttsDecoder,
                    animator,
                    voice.ttsData(),
                    voice.ttsLength()
                );
            }

            voice.clearTtsReady();
            voice.sendControl(HB_EVT_TTS_SEGMENT_DONE, completed ? 1 : 0);

            if (!completed) {
                voice.sendControl(HB_EVT_CANCEL);
                interruptGraceTicks = 300;
            }

            speaking = false;
            lastPcState = 255;
        }

        uint8_t pcState = voice.pcState();
        if (!speaking && !pttActive && pcState != lastPcState) {
            lastPcState = pcState;
            animator.setState(visualStateFromPc(pcState));
        }

        bool logoTouched = uBit.logo.isPressed();
        bool busy = stateIsBusyForPtt(animator.state());
        bool logoAllowed = !speaking && (!busy || interruptGraceTicks > 0);
        bool logo = logoTouched && logoAllowed;

        if (logo && !pttActive) {
            if (busy) {
                interruptGraceTicks = 0;
                voice.sendControl(HB_EVT_CANCEL);
            }

            micSequence = 0;
            uBit.audio.activateMic();
            recorder.start();
            pttActive = true;
            voice.sendControl(HB_EVT_PTT_START);
            animator.setState(PHYS_LISTENING);
        }

        if (pttActive) {
            if (logoTouched && voice.notificationsReady()) {
                animator.setInputLevel(recorder.level());
                drainMicPackets(voice, recorder, micSequence, false);
            } else {
                animator.setInputLevel(0);
                animator.setState(PHYS_UPLOADING);
                finishMicUtterance(voice, recorder, micSequence);
                pttActive = false;
            }
        }

        if (++animationDivider >= 3) {
            animationDivider = 0;
            if (pttActive)
                animator.setInputLevel(recorder.level());
            animator.tick();
        }

        uBit.sleep(10);
    }

    release_fiber();
    return 0;
}
