import board, time, digitalio, synthio, audiobusio, analogio, random
import ulab.numpy as np
import adafruit_matrixkeypad
import usb_cdc

SAMPLE_RATE = 44100
CHANNEL_COUNT = 2
audio = audiobusio.I2SOut(bit_clock=board.GP12, word_select=board.GP13, data=board.GP11)
synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE, channel_count=CHANNEL_COUNT)
audio.play(synth)

cols = [digitalio.DigitalInOut(x) for x in (board.GP20, board.GP21, board.GP22)]
rows = [digitalio.DigitalInOut(x) for x in (board.GP16, board.GP17, board.GP18, board.GP19)]
keymap = ((1, 2, 3),
          (4, 5, 6),
          (7, 8, 9),
          ('*', 0, '#'))
keypad = adafruit_matrixkeypad.Matrix_Keypad(rows, cols, keymap)

volume_pot = analogio.AnalogIn(board.A2)
slide_pot = analogio.AnalogIn(board.A1)

stream = usb_cdc.data

LOW_HZ = 261.63
HIGH_HZ = 523.25

# Waveform code taken from:
# https://todbot.github.io/CircuitPython_Synthio_Tutorial/README-4-Oscillators-Wavetables.html#change-a-notes-oscillator-waveform
NUM = 256    # number of samples in a waveform
VOL = 32767  # loudness (volume) of samples, np.int16 ranges from 0-32767

# sine wave
wave_sine = np.array(np.sin(np.linspace(0, 2*np.pi, NUM, endpoint=False)) * VOL, dtype=np.int16)

# sawtooth wave
wave_saw = np.linspace(VOL, -VOL, num=NUM, dtype=np.int16)

# square wave, like the default
wave_square = np.concatenate((np.ones(NUM // 2, dtype=np.int16) * VOL,
                              np.zeros(NUM // 2, dtype=np.int16) * -VOL))

# 'noise' wave made with random numbers
wave_noise = np.array([random.randint(-VOL, VOL) for i in range(NUM)], dtype=np.int16)

waves = [wave_saw, wave_square, wave_sine, wave_noise]
wave_names = ["saw", "square", "sine", "noise"]
waves_len = len(waves)
# --------------------------------------------------------------------------------------------------------------------------------

def pot_percent(pot, samples=10):
    total = 0
    for x in range(samples):
        total += pot.value
    avg = total / samples
    if avg > 3000:
        return avg / 65535
    return 0

def lerp(start, end, frac):
    return start + (end - start) * frac

wave_index = 0 # Default saw wave
note = synthio.Note(frequency=LOW_HZ, waveform=waves[wave_index])
playing = False
prev_key = None
last_tick = 0.0

PLAY_KEY = 4
UP_KEY = 1
DOWN_KEY = 7

while True:
    hz = lerp(LOW_HZ, HIGH_HZ, pot_percent(slide_pot))
    amp = pot_percent(volume_pot)
    note.frequency = hz
    note.amplitude = amp

    pressed = keypad.pressed_keys

    if UP_KEY in pressed:
        if prev_key != UP_KEY:
            wave_index += 1 if wave_index < waves_len - 1 else 0
            prev_key = UP_KEY
    elif DOWN_KEY in pressed:
        if prev_key != DOWN_KEY:
            wave_index -= 1 if wave_index > 0 else 0
            prev_key = DOWN_KEY
    else:
        prev_key = None

    note.waveform = waves[wave_index]

    if PLAY_KEY in pressed:
        if not playing:
            synth.press(note)
            playing = True
    else:
        if playing:
            synth.release(note)
            playing = False

    now = time.monotonic()
    if stream is not None and now - last_tick > 0.05:
        frame = '{"frequency":%.1f,"amplitude":%.3f,"playing":%d,"keys":"%s","waveform":"%s"}\n' % (
            hz,
            amp,
            1 if playing else 0,
            ",".join(str(k) for k in pressed),
            wave_names[wave_index],
        )
        try:
            stream.write(frame.encode("utf-8"))
        except OSError:
            pass
        last_tick = now

    time.sleep(0.001)