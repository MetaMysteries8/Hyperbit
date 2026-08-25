#include "MicroBit.h"
#include "MemorySource.h"
#include "MicRecorder.h"
#include "VoiceBLEService.h"
#include "WukongLights.h"
#include "WukongRainbow.h"
#include "ImaAdpcm.h"

using namespace codal;
MicroBit uBit;

enum PhysicalState {
    PHYS_DISCONNECTED = 0,
    PHYS_IDLE = 1,
    PHYS_LISTENING = 2,
    PHYS_UPLOADING = 3,
    PHYS_TRANSCRIBING = 4,
    PHYS_THINKING = 5,
    PHYS_SPEAKING = 6,
    PHYS_ERROR = 7,
    PHYS_MUTED = 8
};

static void applyState(WukongLights &base, WukongRainbow &rainbow, uint8_t state, bool muted) {
    if (muted && state != PHYS_LISTENING && state != PHYS_UPLOADING) {
        base.steady(8);
        rainbow.state(PHYS_MUTED);
        return;
    }

    switch (state) {
        case PHYS_DISCONNECTED: base.breath(); break;
        case PHYS_IDLE: base.steady(12); break;
        case PHYS_LISTENING: base.steady(45); break;
        case PHYS_UPLOADING: base.steady(65); break;
        case PHYS_TRANSCRIBING: base.steady(70); break;
        case PHYS_THINKING: base.steady(85); break;
        case PHYS_SPEAKING: base.steady(100); break;
        case PHYS_ERROR: base.steady(100); break;
        default: base.steady(12); break;
    }

    rainbow.state(state);
}

static bool playTtsInterruptible(
    MemorySource &source,
    ImaAdpcmState &decoder,
    const uint8_t *adpcm,
    uint16_t len
) {
    uint8_t pcm[256];
    int out = 0;

    for (uint16_t i = 0; i < len; ++i) {
        if (uBit.buttonA.isPressed())
            return false;

        uint8_t b = adpcm[i];
        int16_t s0 = decoder.decode(b & 0x0F);
        int16_t s1 = decoder.decode((b >> 4) & 0x0F);

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
            out = 0;
        }
    }

    if (out)
        source.play(pcm, out);

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

    // The physical microphone is OFF at rest. It is activated only while the
    // V2 gold logo at the top of the board is held.
    recorder.stop();
    uBit.audio.deactivateMic();

    WukongLights baseLights(uBit.i2c);
    WukongRainbow rainbow(uBit.io.P16);

    // Visible Wukong self-test at boot.
    bool wukongBaseOk = baseLights.selfTest();
    rainbow.selfTest();

    bool lastConnected = false;
    bool lastLogo = false;
    bool lastA = false;
    bool lastB = false;
    bool lastAB = false;
    bool speaking = false;
    bool muted = false;
    uint8_t lastPcState = 255;
    uint8_t micSequence = 0;
    ImaAdpcmState ttsDecoder;

    applyState(baseLights, rainbow, PHYS_DISCONNECTED, muted);
    uBit.display.print(wukongBaseOk ? "H" : "W");

    while (true) {
        bool connected = voice.getConnected();

        if (connected != lastConnected) {
            lastConnected = connected;
            if (connected) {
                applyState(baseLights, rainbow, PHYS_IDLE, muted);
                uBit.display.print("I");
                voice.sendControl(HB_EVT_READY);
                voice.sendControl(HB_EVT_WUKONG_STATUS, baseLights.ok() ? 1 : 0);
            } else {
                recorder.stop();
                uBit.audio.deactivateMic();
                voice.abortTts();
                applyState(baseLights, rainbow, PHYS_DISCONNECTED, muted);
                uBit.display.print("X");
            }
        }

        bool a = uBit.buttonA.isPressed();
        bool b = uBit.buttonB.isPressed();
        bool ab = a && b;

        if (ab && !lastAB) {
            muted = !muted;
            voice.sendControl(HB_EVT_MUTE_CHANGED, muted ? 1 : 0);
            applyState(baseLights, rainbow, muted ? PHYS_MUTED : PHYS_IDLE, muted);
            uBit.display.print(muted ? "M" : "I");
        } else if (!ab) {
            if (a && !lastA) {
                voice.abortTts();
                voice.sendControl(HB_EVT_CANCEL);
                uBit.display.print("C");
                applyState(baseLights, rainbow, PHYS_IDLE, muted);
            }

            if (b && !lastB) {
                voice.sendControl(HB_EVT_REPLAY);
                uBit.display.print("B");
            }
        }

        lastA = a;
        lastB = b;
        lastAB = ab;

        if (connected && voice.ttsReady() && !speaking) {
            speaking = true;
            recorder.stop();
            uBit.audio.deactivateMic();

            if (voice.ttsFirstSegment())
                ttsDecoder.reset();

            bool completed = true;
            if (!muted) {
                uBit.display.print("S");
                applyState(baseLights, rainbow, PHYS_SPEAKING, muted);
                completed = playTtsInterruptible(
                    ttsSource,
                    ttsDecoder,
                    voice.ttsData(),
                    voice.ttsLength()
                );
            }

            voice.clearTtsReady();
            voice.sendControl(HB_EVT_TTS_SEGMENT_DONE, completed ? 1 : 0);

            if (!completed)
                voice.sendControl(HB_EVT_CANCEL);

            speaking = false;
            lastPcState = 255;
        }

        uint8_t pcState = voice.pcState();
        if (connected && !speaking && pcState != lastPcState) {
            lastPcState = pcState;
            switch (pcState) {
                case 1:
                    applyState(baseLights, rainbow, PHYS_IDLE, muted);
                    uBit.display.print(muted ? "M" : "I");
                    break;
                case 2:
                    applyState(baseLights, rainbow, PHYS_LISTENING, muted);
                    uBit.display.print("L");
                    break;
                case 3:
                    applyState(baseLights, rainbow, PHYS_TRANSCRIBING, muted);
                    uBit.display.print("R");
                    break;
                case 4:
                    applyState(baseLights, rainbow, PHYS_THINKING, muted);
                    uBit.display.print("T");
                    break;
                case 5:
                    applyState(baseLights, rainbow, PHYS_SPEAKING, muted);
                    uBit.display.print("S");
                    break;
                case 6:
                    applyState(baseLights, rainbow, PHYS_ERROR, muted);
                    uBit.display.print("E");
                    break;
                default:
                    applyState(baseLights, rainbow, PHYS_IDLE, muted);
                    break;
            }
        }

        // The V2 gold logo at the top is the ONLY push-to-talk input.
        bool logo = connected && !speaking && uBit.logo.isPressed();

        if (logo && !lastLogo) {
            micSequence = 0;
            uBit.audio.activateMic();
            recorder.start();
            voice.sendControl(HB_EVT_PTT_START);
            applyState(baseLights, rainbow, PHYS_LISTENING, muted);
            uBit.display.print("L");
        }

        if (logo) {
            // Stream microphone ADPCM in tiny BLE packets while the logo is held.
            drainMicPackets(voice, recorder, micSequence, false);
        }

        if (!logo && lastLogo) {
            applyState(baseLights, rainbow, PHYS_UPLOADING, muted);
            uBit.display.print("U");
            finishMicUtterance(voice, recorder, micSequence);
        }

        lastLogo = logo;
        uBit.sleep(10);
    }

    release_fiber();
    return 0;
}
