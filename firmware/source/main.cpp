#include "MicroBit.h"
#include "MemorySource.h"
#include "MicRecorder.h"
#include "VoiceBLEService.h"
#include "WukongLights.h"
#include "ImaAdpcm.h"

using namespace codal;
MicroBit uBit;

static void playTts(MemorySource &source, const uint8_t *adpcm, uint16_t len) {
    ImaAdpcmState state;
    uint8_t pcm[512];
    int out = 0;
    for (uint16_t i = 0; i < len; i++) {
        uint8_t b = adpcm[i];
        int16_t s0 = state.decode(b & 0x0F);
        int16_t s1 = state.decode((b >> 4) & 0x0F);
        int p0 = (s0 >> 8) + 128;
        int p1 = (s1 >> 8) + 128;
        if (p0 < 0) p0 = 0; if (p0 > 255) p0 = 255;
        if (p1 < 0) p1 = 0; if (p1 > 255) p1 = 255;
        pcm[out++] = (uint8_t)p0;
        pcm[out++] = (uint8_t)p1;
        if (out >= (int)sizeof(pcm)) {
            source.play(pcm, out);
            out = 0;
        }
    }
    if (out) source.play(pcm, out);
}

static void sendRecordedAudio(VoiceBLEService &ble, MicRecorder &rec) {
    const uint8_t *data = rec.data();
    uint16_t len = rec.length();
    uint8_t seq = 0;
    for (uint16_t off = 0; off < len; off += 19) {
        int n = len - off;
        if (n > 19) n = 19;
        int tries = 0;
        while (!ble.sendMic(seq, data + off, n) && ble.getConnected() && tries < 100) {
            uBit.sleep(2);
            tries++;
        }
        seq++;
        uBit.sleep(1);
    }
    uint16_t samples = rec.samples();
    ble.sendControl(HB_EVT_PTT_END, samples & 0xFF, (samples >> 8) & 0xFF, rec.overflowed() ? 1 : 0);
}

int main() {
    uBit.init();
    uBit.audio.mic->setSampleRate(8000);
    uBit.audio.activateMic();
    uBit.audio.enable();
    uBit.audio.setPinEnabled(false);
    uBit.audio.setSpeakerEnabled(true);
    uBit.audio.setVolume(210);

    MemorySource ttsSource;
    ttsSource.setFormat(DATASTREAM_FORMAT_8BIT_UNSIGNED);
    ttsSource.setBufferSize(512);
    uBit.audio.mixer.addChannel(ttsSource, 8000, 255);

    SplitterChannel *micChannel = uBit.audio.splitter->createChannel();
    MicRecorder recorder(*micChannel);
    VoiceBLEService voice;
    WukongLights lights(uBit.i2c);

    bool lastConnected = false;
    bool lastTouched = false;
    bool speaking = false;
    uint8_t lastPcState = 255;

    lights.breath();
    uBit.display.print("H");

    while (true) {
        bool connected = voice.getConnected();
        if (connected != lastConnected) {
            lastConnected = connected;
            if (connected) {
                lights.steady(12);
                uBit.display.print("I");
                voice.sendControl(HB_EVT_READY);
            } else {
                recorder.stop();
                lights.breath();
                uBit.display.print("X");
            }
        }

        if (connected && voice.ttsReady() && !speaking) {
            speaking = true;
            recorder.stop();
            uBit.display.print("S");
            lights.steady(100);
            playTts(ttsSource, voice.ttsData(), voice.ttsLength());
            voice.clearTtsReady();
            speaking = false;
            lastPcState = 255;
        }

        uint8_t pcState = voice.pcState();
        if (connected && !speaking && pcState != lastPcState) {
            lastPcState = pcState;
            switch (pcState) {
                case 1: lights.steady(12); uBit.display.print("I"); break;
                case 2: lights.steady(45); uBit.display.print("L"); break;
                case 3: lights.steady(65); uBit.display.print("R"); break;
                case 4: lights.steady(85); uBit.display.print("T"); break;
                case 5: lights.steady(100); uBit.display.print("S"); break;
                case 6: lights.steady(100); uBit.display.print("E"); break;
                default: lights.steady(12); break;
            }
        }

        bool touched = connected && !speaking && uBit.logo.isPressed();
        if (touched && !lastTouched) {
            recorder.start();
            voice.sendControl(HB_EVT_PTT_START);
            lights.steady(45);
            uBit.display.print("L");
        }
        if (!touched && lastTouched) {
            recorder.stop();
            lights.steady(70);
            uBit.display.print("U");
            sendRecordedAudio(voice, recorder);
        }
        lastTouched = touched;
        uBit.sleep(10);
    }
    release_fiber();
    return 0;
}
