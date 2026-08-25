#include "MicroBit.h"
#include "MemorySource.h"
#include "MicRecorder.h"
#include "VoiceBLEService.h"
#include "WukongLights.h"
#include "WukongRainbow.h"
#include "AliveAnimator.h"
#include "ImaAdpcm.h"

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
    uint8_t packet[19];
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

int main() {
    uBit.init();

    VoiceBLEService voice;
    uBit.bleManager.setTransmitPower(7);
    uBit.bleManager.stopAdvertising();
    uBit.bleManager.advertise();

    uBit.audio.enable();
    uBit.audio.mic->setSampleRate(8000);
    uBit.audio.setPinEnabled(false);
    uBit.audio.setSpeakerEnabled(true);
    uBit.audio.setVolume(210);

    MemorySource ttsSource;
    ttsSource.setFormat(DATASTREAM_FORMAT_8BIT_UNSIGNED);
    ttsSource.setBufferSize(256);
    uBit.audio.mixer.addChannel(ttsSource, 8000, 255);

    SplitterChannel *micChannel = uBit.audio.splitter->createChannel();
    MicRecorder recorder(*micChannel);
    recorder.stop();
    uBit.audio.deactivateMic();

    WukongLights baseLights(uBit.i2c);
    WukongRainbow rainbow(uBit.io.P16);

    // Keep the boot diagnostic the user liked: W means the base-light I2C
    // controller did not answer; H means Wukong was detected. The animation
    // takes over immediately afterward instead of hanging on the letter.
    bool wukongBaseOk = baseLights.selfTest();
    rainbow.selfTest();
    uBit.display.print(wukongBaseOk ? "H" : "W");
    uBit.sleep(350);

    AliveAnimator animator(uBit, baseLights, rainbow);
    animator.setState(PHYS_DISCONNECTED);

    bool lastConnected = false;
    bool pttActive = false;
    bool lastA = false;
    bool lastB = false;
    bool lastAB = false;
    bool speaking = false;
    bool muted = false;
    uint8_t lastPcState = 255;
    uint8_t micSequence = 0;
    ImaAdpcmState ttsDecoder;

    // About three seconds. While the agent is busy, push-to-talk is only
    // accepted during this grace window after A has interrupted the old task.
    int interruptGraceTicks = 0;
    int animationDivider = 0;

    while (true) {
        bool connected = voice.getConnected();

        if (interruptGraceTicks > 0)
            --interruptGraceTicks;

        if (connected != lastConnected) {
            lastConnected = connected;
            if (connected) {
                animator.setState(PHYS_IDLE);
                voice.sendControl(HB_EVT_READY);
                voice.sendControl(HB_EVT_WUKONG_STATUS, baseLights.ok() ? 1 : 0);
            } else {
                if (pttActive) {
                    recorder.stop();
                    pttActive = false;
                }
                uBit.audio.deactivateMic();
                voice.abortTts();
                animator.setState(PHYS_DISCONNECTED);
                lastPcState = 255;
            }
        }

        bool a = uBit.buttonA.isPressed();
        bool b = uBit.buttonB.isPressed();
        bool ab = a && b;

        if (ab && !lastAB) {
            muted = !muted;
            animator.setMuted(muted);
            voice.sendControl(HB_EVT_MUTE_CHANGED, muted ? 1 : 0);
        } else if (!ab) {
            if (a && !lastA) {
                // A is a real interruption: stop playback, tell the PC to
                // discard the in-flight answer, and briefly arm busy-state PTT.
                voice.abortTts();
                voice.sendControl(HB_EVT_CANCEL);
                interruptGraceTicks = 300;
                animator.setState(PHYS_IDLE);
                lastPcState = voice.pcState();
            }

            if (b && !lastB) {
                voice.sendControl(HB_EVT_REPLAY);
            }
        }

        lastA = a;
        lastB = b;
        lastAB = ab;

        if (connected && voice.ttsReady() && !speaking) {
            speaking = true;
            recorder.stop();
            pttActive = false;
            uBit.audio.deactivateMic();

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
                // Playback can only return early through A, so let the user
                // immediately hold the gold logo to replace the interrupted reply.
                interruptGraceTicks = 300;
            }

            speaking = false;
            lastPcState = 255;
        }

        uint8_t pcState = voice.pcState();
        if (connected && !speaking && !pttActive && pcState != lastPcState) {
            lastPcState = pcState;
            animator.setState(visualStateFromPc(pcState));
        }

        // V2 GOLD LOGO = push-to-talk. It works freely while idle. If HyperBit
        // is busy, A must have just interrupted the old operation first.
        bool logoTouched = uBit.logo.isPressed();
        bool busy = stateIsBusyForPtt(animator.state());
        bool logoAllowed = connected && !speaking && (!busy || interruptGraceTicks > 0);
        bool logo = logoTouched && logoAllowed;

        if (logo && !pttActive) {
            if (busy) {
                // Consume the grace window and reinforce cancellation on the PC.
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
            if (logoTouched) {
                animator.setInputLevel(recorder.level());
                drainMicPackets(voice, recorder, micSequence, false);
            } else {
                animator.setInputLevel(0);
                animator.setState(PHYS_UPLOADING);
                finishMicUtterance(voice, recorder, micSequence);
                pttActive = false;
            }
        }

        // ~33 fps visual loop without blocking the BLE/audio loop.
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
