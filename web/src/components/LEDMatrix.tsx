import React, { useState, useEffect, useId, useMemo } from 'react';
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
  onPixelClick?: (row: number, col: number) => void;
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
  onPixelClick,
  size = 'md',
  showLabels = true,
  showLed3 = true,
  className = '',
}) => {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [hoveredPixel, setHoveredPixel] = useState<{ r: number; c: number; val: number } | null>(null);
  const matrixId = useId();

  useEffect(() => {
    const startTime = performance.now();
    const interval = setInterval(() => {
      setElapsedMs(Math.round(performance.now() - startTime));
    }, 60);

    return () => clearInterval(interval);
  }, [state, progress]);

  const frameResult = selectDisplayFrame(state, progress, elapsedMs, progressKnown);
  const activeFrame = manualFrame || frameResult.frame;

  const { litCount } = useMemo(() => {
    let lit = 0;
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        if ((activeFrame[r]?.[c] ?? 0) > 0) lit++;
      }
    }
    return { litCount: lit };
  }, [activeFrame]);

  const sizeConfig = {
    sm: {
      pixel: 'w-2 h-2 sm:w-2.5 sm:h-2.5',
      cellPadding: 'p-0.5',
      padding: 'p-3',
      cavityPadding: 'p-2.5',
      showSilkIndices: false,
    },
    md: {
      pixel: 'w-2.5 h-2.5 sm:w-3.5 sm:h-3.5',
      cellPadding: 'p-0.5 sm:p-1',
      padding: 'p-4',
      cavityPadding: 'p-3 sm:p-3.5',
      showSilkIndices: false,
    },
    lg: {
      pixel: 'w-3 h-3 sm:w-4 sm:h-4 md:w-4.5 md:h-4.5',
      cellPadding: 'p-0.5 sm:p-1',
      padding: 'p-4 sm:p-5',
      cavityPadding: 'p-3.5 sm:p-4',
      showSilkIndices: true,
    },
    hero: {
      pixel: 'w-3 h-3 sm:w-4 sm:h-4 md:w-5 md:h-5',
      cellPadding: 'p-[3px] sm:p-1',
      padding: 'p-4 sm:p-5 md:p-6',
      cavityPadding: 'p-3.5 sm:p-4',
      showSilkIndices: true,
    },
  }[size];

  const getBrightnessStyle = (val: number) => {
    switch (val) {
      case 0:
        return 'bg-[#161D27] border-[#232D3B]/80 shadow-inner opacity-90';
      case 1:
        return 'bg-[#073659] border-[#0C4A78] shadow-[0_0_5px_rgba(56,189,248,0.22)]';
      case 2:
        return 'bg-[#035388] border-[#0284C7]/60 shadow-[0_0_7px_rgba(56,189,248,0.38)]';
      case 3:
        return 'bg-[#0284C7] border-[#38BDF8]/70 shadow-[0_0_10px_rgba(56,189,248,0.55)]';
      case 4:
        return 'bg-[#0EA5E9] border-[#7DD3FC]/85 shadow-[0_0_13px_rgba(56,189,248,0.75)]';
      case 5:
        return 'bg-[#38BDF8] border-[#BAE6FD] shadow-[0_0_16px_rgba(56,189,248,0.9),0_0_4px_#38BDF8]';
      case 6:
        return 'bg-[#7DD3FC] border-white shadow-[0_0_20px_rgba(56,189,248,1),0_0_6px_#BAE6FD]';
      case 7:
      default:
        return 'bg-white border-white shadow-[0_0_24px_rgba(56,189,248,1),0_0_10px_#FFFFFF]';
    }
  };

  return (
    <div
      className={`relative inline-flex flex-col items-center select-none ${className}`}
      role="region"
      aria-label={`Arduino UNO Q 8 by 13 physical LED matrix showing ${frameResult.description}`}
    >
      {/* CNC Bead-Blasted Aluminum Enclosure */}
      <div
        className={`relative w-full aluminum-chassis transition-all duration-300 ${sizeConfig.padding}`}
      >
        {showLabels && (
          <div className="flex items-center justify-between gap-2 mb-3 px-0.5 text-[11px] font-medium text-[#4A4D52] dark:text-[#9CA3AF]">
            <div className="flex items-center gap-2 min-w-0">
              <span className="font-bold tracking-tight text-[#141517] dark:text-white truncate">
                UNO Q Matrix
              </span>
              <span className="text-[#787C82] text-[10px] font-mono">
                8×13 • 104 LEDs
              </span>
            </div>

            {showLed3 && (
              <div
                className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-black/[0.05] dark:bg-white/[0.08] text-[#141517] dark:text-white shrink-0"
                title={`Companion RGB LED 3: ${frameResult.led3.name}`}
              >
                <span className="text-[10px] font-mono text-[#4A4D52] dark:text-[#9CA3AF]">
                  LED 3: {frameResult.led3.name}
                </span>
                <span
                  className={`w-2 h-2 rounded-full transition-all duration-300 ${
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

        {/* Recessed Dark Optical Silicon Cavity */}
        <div
          className={`relative pcb-cavity overflow-hidden ${sizeConfig.cavityPadding}`}
        >
          {sizeConfig.showSilkIndices && (
            <div
              className="grid mb-1 px-0.5 select-none"
              style={{
                gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))`,
              }}
            >
              {Array.from({ length: COLS }).map((_, cIdx) => (
                <div
                  key={`col-idx-${cIdx}`}
                  className={`text-center font-mono text-[8px] tracking-tighter transition-colors ${
                    hoveredPixel?.c === cIdx
                      ? 'text-[#38BDF8] font-bold'
                      : 'text-slate-600/80'
                  }`}
                >
                  {String(cIdx).padStart(2, '0')}
                </div>
              ))}
            </div>
          )}

          {/* 8 Rows × 13 Columns Physical LED Array */}
          <div
            className="grid relative z-10"
            style={{
              gridTemplateColumns: `repeat(${COLS}, minmax(0, 1fr))`,
            }}
          >
            {activeFrame.map((rowArr, rIdx) => (
              <React.Fragment key={`row-${rIdx}`}>
                {rowArr.map((val, cIdx) => {
                  const brightnessStyle = getBrightnessStyle(val);
                  const isHovered =
                    hoveredPixel?.r === rIdx && hoveredPixel?.c === cIdx;
                  return (
                    <div
                      key={`pixel-${rIdx}-${cIdx}`}
                      className={`${sizeConfig.cellPadding} flex items-center justify-center ${
                        onPixelClick
                          ? 'cursor-crosshair hover:scale-125 transition-transform'
                          : interactive
                          ? 'cursor-pointer'
                          : ''
                      }`}
                      onClick={() =>
                        interactive && onPixelClick && onPixelClick(rIdx, cIdx)
                      }
                      onMouseEnter={() =>
                        interactive && setHoveredPixel({ r: rIdx, c: cIdx, val })
                      }
                      onMouseLeave={() => interactive && setHoveredPixel(null)}
                      title={`LED [R${rIdx}, C${cIdx}] • Brightness ${val}/7`}
                    >
                      <div
                        className={`rounded-full transition-all duration-150 border ${
                          sizeConfig.pixel
                        } ${brightnessStyle} ${
                          isHovered ? 'ring-1 ring-[#38BDF8] scale-110' : ''
                        }`}
                      />
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>

          <div className="absolute inset-0 pointer-events-none mix-blend-screen opacity-35 bg-[radial-gradient(ellipse_at_center,rgba(56,189,248,0.18),transparent_72%)]" />
        </div>

        {/* Bottom Status Readout */}
        {showLabels && (
          <div className="mt-2.5 px-0.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#4A4D52] dark:text-[#9CA3AF]">
            <div className="flex items-center gap-1.5 truncate max-w-[200px] sm:max-w-[280px]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0055FF] dark:bg-[#38BDF8] shrink-0" />
              <span className="font-semibold text-[#141517] dark:text-white truncate">
                {manualFrame ? 'Custom 3-Bit Bitmap' : frameResult.description}
              </span>
            </div>

            <div className="font-mono text-[10px] text-[#787C82]">
              {hoveredPixel ? (
                <span className="text-[#0055FF] dark:text-[#38BDF8] font-semibold">
                  [{hoveredPixel.r},{hoveredPixel.c}] L{hoveredPixel.val}/7
                </span>
              ) : (
                <span>{litCount}/104 LEDs</span>
              )}
            </div>
          </div>
        )}
      </div>

      <div id={matrixId} className="sr-only" aria-live="polite">
        Matrix state is {state}. {frameResult.description}. Progress: {progress} percent.
      </div>
    </div>
  );
};
