import React, { useState, useEffect, useId } from 'react';
import { HardwareLightState } from '../types/telemetry';
import {
  COLS,
  ROWS,
  MatrixFrame,
  selectDisplayFrame,
} from '../lib/matrixEngine';

interface LEDMatrixProps {
  state?: HardwareLightState;
  progress?: number;
  progressKnown?: boolean;
  manualFrame?: MatrixFrame | null;
  interactive?: boolean;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  showLabels?: boolean;
  showLed3?: boolean;
  className?: string;
}

export const LEDMatrix: React.FC<LEDMatrixProps> = ({
  state = 'idle',
  progress = 0,
  progressKnown = true,
  manualFrame = null,
  interactive = true,
  size = 'md',
  showLabels = true,
  showLed3 = true,
  className = '',
}) => {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [hoveredPixel, setHoveredPixel] = useState<{ r: number; c: number; val: number } | null>(null);
  const matrixId = useId();

  // Animation clock for internal frame transitions (dots, pulsing hearts, charging bars)
  useEffect(() => {
    const startTime = performance.now();
    const interval = setInterval(() => {
      setElapsedMs(Math.round(performance.now() - startTime));
    }, 60);

    return () => clearInterval(interval);
  }, [state, progress]);

  const frameResult = selectDisplayFrame(state, progress, elapsedMs, progressKnown);
  const activeFrame = manualFrame || frameResult.frame;

  // Pixel sizing based on container size
  const sizeConfig = {
    sm: {
      pixel: 'w-2 h-2 sm:w-2.5 sm:h-2.5',
      gap: 'gap-1',
      padding: 'p-3',
      text: 'text-[10px]',
    },
    md: {
      pixel: 'w-3 h-3 sm:w-4 sm:h-4',
      gap: 'gap-1.5 sm:gap-2',
      padding: 'p-4 sm:p-5',
      text: 'text-xs',
    },
    lg: {
      pixel: 'w-4 h-4 sm:w-5 sm:h-5',
      gap: 'gap-2 sm:gap-2.5',
      padding: 'p-5 sm:p-6',
      text: 'text-sm',
    },
    hero: {
      pixel: 'w-4 h-4 sm:w-6 sm:h-6 md:w-7 md:h-7',
      gap: 'gap-2 sm:gap-2.5 md:gap-3',
      padding: 'p-5 sm:p-7 md:p-8',
      text: 'text-sm sm:text-base',
    },
  }[size];

  // Brightness mapping: 3-bit (0..7) to blue LED styling
  const getBrightnessStyle = (val: number) => {
    switch (val) {
      case 0:
        return 'bg-graphite-900/80 border-white/[0.04] text-transparent shadow-none';
      case 1:
        return 'bg-sky-950/70 border-sky-800/40 shadow-[0_0_4px_rgba(56,189,248,0.2)]';
      case 2:
        return 'bg-sky-800/80 border-sky-600/50 shadow-[0_0_6px_rgba(56,189,248,0.35)]';
      case 3:
        return 'bg-sky-600 border-sky-400/60 shadow-[0_0_8px_rgba(56,189,248,0.5)]';
      case 4:
        return 'bg-sky-500 border-sky-300/70 shadow-[0_0_10px_rgba(56,189,248,0.65)]';
      case 5:
        return 'bg-sky-400 border-sky-200/80 shadow-[0_0_14px_rgba(56,189,248,0.8),0_0_4px_#38bdf8]';
      case 6:
        return 'bg-sky-300 border-white shadow-[0_0_18px_rgba(56,189,248,0.95),0_0_6px_#7dd3fc]';
      case 7:
      default:
        return 'bg-white border-white shadow-[0_0_24px_rgba(56,189,248,1),0_0_8px_#ffffff]';
    }
  };

  return (
    <div
      className={`relative inline-flex flex-col items-center select-none ${className}`}
      role="region"
      aria-label={`Arduino UNO Q 8 by 13 physical LED matrix preview showing ${frameResult.description}`}
    >
      {/* Outer Enclosure / Hardware Frame */}
      <div className={`relative bg-gradient-to-b from-graphite-900 to-graphite-950 rounded-2xl border border-white/10 shadow-matrix-case ${sizeConfig.padding}`}>
        {/* Subtle Silkscreen Header */}
        {showLabels && (
          <div className="flex items-center justify-between mb-3 text-[11px] font-mono tracking-wider text-graphite-400 border-b border-white/[0.06] pb-2">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-lime/80 animate-pulse" />
              <span className="font-semibold text-graphite-200">UNO Q MATRIX</span>
              <span className="text-graphite-500 text-[10px]">8 × 13 LED (104 px)</span>
            </div>
            {showLed3 && (
              <div className="flex items-center gap-1.5" title={`RGB LED 3: ${frameResult.led3.name}`}>
                <span className="text-graphite-500 text-[10px]">LED 3</span>
                <span
                  className={`w-2.5 h-2.5 rounded-full transition-all duration-300 ${
                    frameResult.led3.pulse ? 'animate-pulse' : ''
                  }`}
                  style={{
                    backgroundColor: frameResult.led3.color,
                    boxShadow: `0 0 8px ${frameResult.led3.color}`,
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* 8 Rows x 13 Cols Grid Container */}
        <div
          className="relative bg-graphite-950/90 p-3 sm:p-4 rounded-xl border border-black/80 shadow-inner overflow-hidden"
          style={{
            backgroundImage:
              'radial-gradient(circle at 50% 50%, rgba(56, 189, 248, 0.05) 0%, transparent 80%)',
          }}
        >
          {/* Subtle PCB Grid Lines */}
          <div
            className="grid grid-cols-13"
            style={{
              gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))`,
            }}
          >
            {activeFrame.map((rowArr, rIdx) => (
              <React.Fragment key={`row-${rIdx}`}>
                {rowArr.map((val, cIdx) => {
                  const brightnessStyle = getBrightnessStyle(val);
                  return (
                    <div
                      key={`pixel-${rIdx}-${cIdx}`}
                      className="p-1 flex items-center justify-center"
                      onMouseEnter={() => interactive && setHoveredPixel({ r: rIdx, c: cIdx, val })}
                      onMouseLeave={() => interactive && setHoveredPixel(null)}
                      title={`Pixel [${rIdx}, ${cIdx}] Brightness: ${val}/7`}
                    >
                      <div
                        className={`rounded-full transition-all duration-150 border ${sizeConfig.pixel} ${brightnessStyle}`}
                      />
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>

          {/* Diffuse Phosphor Glow Overlay */}
          <div className="absolute inset-0 pointer-events-none mix-blend-screen opacity-40 bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.15),transparent_70%)]" />
        </div>

        {/* Hardware Status / Telemetry Footer */}
        {showLabels && (
          <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-graphite-400 pt-2 border-t border-white/[0.06]">
            <div className="flex items-center gap-1.5 truncate max-w-[200px] sm:max-w-[300px]">
              <span className="text-graphite-500">STATE:</span>
              <span className="text-graphite-200 font-medium truncate">{frameResult.description}</span>
            </div>
            <div className="text-[10px] text-graphite-500 font-mono">
              {hoveredPixel ? (
                <span className="text-led-blue">
                  [{hoveredPixel.r},{hoveredPixel.c}] L:{hoveredPixel.val}
                </span>
              ) : (
                <span>3-BIT GRAYSCALE</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Screen Reader Live Description */}
      <div id={matrixId} className="sr-only" aria-live="polite">
        Matrix state is {state}. {frameResult.description}. Progress: {progress} percent.
      </div>
    </div>
  );
};
