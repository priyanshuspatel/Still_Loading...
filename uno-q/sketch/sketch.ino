/*
  Still Loading... — Arduino UNO Q desk companion sketch (Phase 5)

  State codes (kept in sync with shared/state_engine.py and shared/matrix_display.py):
    0 = idle
    1 = running
    2 = slow
    3 = suspected_stall
    4 = failed
    5 = completed
    6 = battery (discharging / full / normal percentage)
    7 = battery_charging (percentage + bottom charging pulse)
    8 = battery_unavailable (neutral '--' dashes, never a fake percentage)
    9 = download (real-time download percentage + 100% -> checkmark on completion)

  RGB LED 3 indicates calm state color.
  The 8x13 blue LED matrix renders animations locally using millis()
  so Bridge.provide("set_job_lights", ...) is never blocked.
*/

#include <Arduino_RouterBridge.h>
#include "Arduino_LED_Matrix.h"

Arduino_LED_Matrix matrix;

const int ROWS = 8;
const int COLS = 13;
uint8_t frame[ROWS * COLS];

// Timing constants in milliseconds (mirrored in shared/matrix_display.py).
const unsigned long START_HEART_BLINKS = 2;
const unsigned long START_HEART_PERIOD_MS = 650;
const unsigned long START_HEART_ON_MS = 400;
const unsigned long START_INTRO_MS = START_HEART_BLINKS * START_HEART_PERIOD_MS;

const unsigned long RUNNING_CYCLE_MS = 8000;
const unsigned long RUNNING_PERCENT_MS = 4400;
const unsigned long RUNNING_WAIT_MS = 6600;
const unsigned long DOT_STEP_MS = 450;
const unsigned long SLOW_STEP_MS = 700;

const unsigned long COMPLETE_HEART_BLINKS = 3;
const unsigned long COMPLETE_HEART_PERIOD_MS = 750;
const unsigned long COMPLETE_HEART_ON_MS = 450;
const unsigned long COMPLETE_HEART_TOTAL_MS = COMPLETE_HEART_BLINKS * COMPLETE_HEART_PERIOD_MS;
const unsigned long COMPLETE_PERCENT_MS = COMPLETE_HEART_TOTAL_MS + 1800;

volatile int current_state = 0;
volatile int current_progress = 0;
volatile unsigned long state_entered_ms = 0;

// 3x5 glyphs for digits 0..9 and '%' (index 10). Each byte is 3 bits for one row.
const uint8_t GLYPHS[11][5] = {
  {0b111, 0b101, 0b101, 0b101, 0b111}, // 0
  {0b010, 0b110, 0b010, 0b010, 0b111}, // 1
  {0b111, 0b001, 0b111, 0b100, 0b111}, // 2
  {0b111, 0b001, 0b111, 0b001, 0b111}, // 3
  {0b101, 0b101, 0b111, 0b001, 0b001}, // 4
  {0b111, 0b100, 0b111, 0b001, 0b111}, // 5
  {0b111, 0b100, 0b111, 0b101, 0b111}, // 6
  {0b111, 0b001, 0b001, 0b001, 0b001}, // 7
  {0b111, 0b101, 0b111, 0b101, 0b111}, // 8
  {0b111, 0b101, 0b111, 0b001, 0b111}, // 9
  {0b110, 0b001, 0b010, 0b100, 0b011}  // % (index 10)
};

// 7x6 heart centered at columns 3..9, rows 1..6.
const uint8_t HEART_BITMAP[6] = {
  0b0110110,
  0b1111111,
  0b1111111,
  0b0111110,
  0b0011100,
  0b0001000
};

void clear_frame() {
  memset(frame, 0, sizeof(frame));
}

void pixel(int row, int col, uint8_t brightness) {
  if (row < 0 || row >= ROWS || col < 0 || col >= COLS) {
    return;
  }
  if (brightness > 7) brightness = 7;
  frame[row * COLS + col] = brightness;
}

void show_frame() {
  matrix.draw(frame);
}

void set_job_lights(int state_code, int progress) {
  if (state_code < 0 || state_code > 9) state_code = 0;
  if (progress < 0) progress = 0;
  if (progress > 100) progress = 100;

  if (state_code != current_state || (state_code == 9 && progress == 100 && current_progress != 100)) {
    state_entered_ms = millis();
  }
  current_state = state_code;
  current_progress = progress;
}

void paint_led3(int red, int green, int blue) {
  analogWrite(LED3_R, red);
  analogWrite(LED3_G, green);
  analogWrite(LED3_B, blue);
}

void draw_bar(int row, int progress, uint8_t brightness) {
  if (progress <= 0) return;
  int lit = (progress * COLS) / 100;
  if (lit < 1) lit = 1;
  for (int col = 0; col < lit; col++) {
    pixel(row, col, brightness);
  }
}

void draw_glyph(int glyph_index, int top_row, int left_col, uint8_t brightness) {
  if (glyph_index < 0 || glyph_index > 10) return;
  for (int r = 0; r < 5; r++) {
    uint8_t bits = GLYPHS[glyph_index][r];
    for (int c = 0; c < 3; c++) {
      if ((bits >> (2 - c)) & 1) {
        pixel(top_row + r, left_col + c, brightness);
      }
    }
  }
}

void draw_percent_symbol(int top_row, int left_col, uint8_t brightness) {
  // Upper dot
  pixel(top_row, left_col, brightness);
  pixel(top_row, left_col + 1, brightness);
  pixel(top_row + 1, left_col, brightness);

  // Straight diagonal slash, from upper right to lower left
  pixel(top_row, left_col + 3, brightness);
  pixel(top_row + 1, left_col + 2, brightness);
  pixel(top_row + 2, left_col + 1, brightness);
  pixel(top_row + 3, left_col, brightness);

  // Lower dot
  pixel(top_row + 3, left_col + 2, brightness);
  pixel(top_row + 3, left_col + 3, brightness);
  pixel(top_row + 4, left_col + 2, brightness);
  pixel(top_row + 4, left_col + 3, brightness);
}

void draw_heart(uint8_t brightness, int progress) {
  for (int r = 0; r < 6; r++) {
    uint8_t bits = HEART_BITMAP[r];
    for (int c = 0; c < 7; c++) {
      if ((bits >> (6 - c)) & 1) {
        pixel(1 + r, 3 + c, brightness);
      }
    }
  }
  if (progress > 0) {
    draw_bar(7, progress, 3);
  }
}

void draw_waiting_dots(unsigned long ms, int progress, bool slow, unsigned long step_ms) {
  const int cols[3] = {3, 6, 9};
  int active = (ms / step_ms) % 3;

  for (int i = 0; i < 3; i++) {
    uint8_t level = (i == active) ? 5 : 2;
    pixel(3, cols[i], level);
    if (slow) {
      pixel(4, cols[i], (i == active) ? 3 : 1);
    }
  }
  if (slow) {
    pixel(6, 1, 3);
    pixel(6, 11, 3);
  }
  if (progress > 0) {
    draw_bar(7, progress, 4);
  }
}

void draw_percentage(int percent, bool charging, bool slow, unsigned long ms) {
  if (percent < 0) percent = 0;
  if (percent > 100) percent = 100;

  if (percent == 100) {
    // '100' across cols 1..11 plus full row-7 bar.
    draw_glyph(1, 1, 1, 6);
    draw_glyph(0, 1, 5, 6);
    draw_glyph(0, 1, 9, 6);
    for (int c = 0; c < COLS; c++) {
      pixel(7, c, 5);
    }
    return;
  }

  if (percent < 10) {
    draw_glyph(percent, 1, 3, 6);
    draw_percent_symbol(1, 8, 4);
    } else {
    draw_glyph(percent / 10, 1, 1, 6);
    draw_glyph(percent % 10, 1, 5, 6);
    draw_percent_symbol(1, 9, 4);
  }

  if (charging) {
    draw_bar(7, percent, 3);
    int head = (ms / 250) % COLS;
    pixel(7, head, 6);
  } else if (slow) {
    draw_bar(7, percent, 3);
    pixel(6, 0, 3);
    pixel(6, COLS - 1, 3);
  } else if (percent > 0) {
    draw_bar(7, percent, 3);
  }
}

void draw_stall_warning(unsigned long ms, int progress) {
  bool blink_on = ((ms / 400) % 2) == 0;
  uint8_t level = blink_on ? 6 : 3;
  pixel(1, 6, level);
  pixel(2, 6, level);
  pixel(3, 6, level);
  pixel(4, 6, level);
  pixel(6, 6, level);

  uint8_t side = blink_on ? 3 : 1;
  for (int r = 2; r <= 5; r++) {
    pixel(r, 2, side);
    pixel(r, 10, side);
  }
  if (progress > 0) {
    draw_bar(7, progress, 2);
  }
}

void draw_failed_x() {
  for (int i = 0; i < 5; i++) {
    pixel(1 + i, 4 + i, 7);
    pixel(1 + i, 8 - i, 7);
  }
  pixel(1, 1, 4);
  pixel(5, 1, 4);
  pixel(1, 11, 4);
  pixel(5, 11, 4);
}

void draw_completed_check() {
  pixel(4, 3, 5);
  pixel(5, 4, 5);
  pixel(4, 5, 5);
  pixel(3, 6, 5);
  pixel(2, 7, 5);
  pixel(1, 8, 5);
  for (int c = 3; c < 10; c++) {
    pixel(7, c, 2);
  }
}

void draw_unavailable() {
  const int cols[6] = {3, 4, 5, 7, 8, 9};
  for (int i = 0; i < 6; i++) {
    pixel(3, cols[i], 3);
  }
}

void render(unsigned long now_ms) {
  clear_frame();
  int state = current_state;
  int progress = current_progress;
  unsigned long elapsed = now_ms - state_entered_ms;

  if (state == 0) {
    // IDLE: calm three dots, soft neutral RGB.
    paint_led3(4, 4, 8);
    draw_waiting_dots(elapsed, 0, false, DOT_STEP_MS);

  } else if (state == 1) {
    // RUNNING: 2 gentle heart blinks on start, then percentage / waiting dots / heartbeat.
    int phase = (now_ms / 60) % 60;
    int level = phase < 30 ? phase : 60 - phase;
    paint_led3(0, 0, 16 + level * 2);

    if (elapsed < START_INTRO_MS) {
      unsigned long within = elapsed % START_HEART_PERIOD_MS;
      uint8_t bright = (within < START_HEART_ON_MS) ? 5 : 1;
      draw_heart(bright, progress);
    } else {
      unsigned long cycle = (elapsed - START_INTRO_MS) % RUNNING_CYCLE_MS;
      if (progress > 0) {
        if (cycle < RUNNING_PERCENT_MS) {
          draw_percentage(progress, false, false, elapsed);
        } else if (cycle < RUNNING_WAIT_MS) {
          draw_waiting_dots(elapsed, progress, false, DOT_STEP_MS);
        } else {
          draw_heart(4, progress);
        }
      } else {
        if (cycle < RUNNING_WAIT_MS) {
          draw_waiting_dots(elapsed, 0, false, DOT_STEP_MS);
        } else {
          draw_heart(4, 0);
        }
      }
    }

  } else if (state == 2) {
    // SLOW: warm amber RGB, slow cue with known percentage or slow waiting dots.
    paint_led3(70, 28, 0);
    unsigned long cycle = elapsed % RUNNING_CYCLE_MS;
    if (progress > 0 && cycle < RUNNING_PERCENT_MS) {
      draw_percentage(progress, false, true, elapsed);
    } else {
      draw_waiting_dots(elapsed, progress, true, SLOW_STEP_MS);
    }

  } else if (state == 3) {
    // SUSPECTED STALL: distinct framed warning symbol, never an X.
    bool on = ((elapsed / 400) % 2) == 0;
    paint_led3(on ? 75 : 15, 0, on ? 40 : 8);
    draw_stall_warning(elapsed, progress);

  } else if (state == 4) {
    // FAILED: steady red RGB and unmistakable X symbol.
    paint_led3(95, 0, 0);
    draw_failed_x();

  } else if (state == 5) {
    // COMPLETED: 3 gentle heart beats, brief 100 display, then calm settled check.
    paint_led3(0, 50, 0);
    if (elapsed < COMPLETE_HEART_TOTAL_MS) {
      unsigned long within = elapsed % COMPLETE_HEART_PERIOD_MS;
      uint8_t bright = (within < COMPLETE_HEART_ON_MS) ? 5 : 1;
      draw_heart(bright, 100);
    } else if (elapsed < COMPLETE_PERCENT_MS) {
      draw_percentage(100, false, false, elapsed);
    } else {
      draw_completed_check();
    }

  } else if (state == 6) {
    // BATTERY (discharging / full): calm teal-green RGB and numeric percentage.
    if (progress >= 100) {
      paint_led3(0, 45, 10);
    } else {
      paint_led3(0, 25, 35);
    }
    draw_percentage(progress, false, false, elapsed);

  } else if (state == 7) {
    // BATTERY CHARGING: numeric percentage plus animated bottom charging bar.
    paint_led3(0, 50, 20);
    draw_percentage(progress, true, false, elapsed);

  } else if (state == 8) {
    // BATTERY UNAVAILABLE: neutral '--' dashes, never a fake percentage.
    paint_led3(8, 8, 8);
    draw_unavailable();

  } else if (state == 9) {
    // DOWNLOAD: real-time numeric percentage, then 100% -> checkmark on completion.
    if (progress >= 100) {
      paint_led3(0, 50, 0);
      if (elapsed < 1800) {
        draw_percentage(100, false, false, elapsed);
      } else {
        draw_completed_check();
      }
    } else {
      paint_led3(0, 35, 55);
      draw_percentage(progress, false, false, elapsed);
    }
  }

  show_frame();
}

void setup() {
  pinMode(LED3_R, OUTPUT);
  pinMode(LED3_G, OUTPUT);
  pinMode(LED3_B, OUTPUT);

  matrix.begin();
  matrix.setGrayscaleBits(3);

  Bridge.begin();
  Bridge.provide("set_job_lights", set_job_lights);

  state_entered_ms = millis();
  render(state_entered_ms);
}

void loop() {
  render(millis());
  delay(30);
}
