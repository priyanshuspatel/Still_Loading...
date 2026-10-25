import React from 'react';
import { Compass, Lightbulb, Shield, Heart } from 'lucide-react';

export const AboutSection: React.FC = () => {
  return (
    <section id="about" className="py-24 bg-graphite-950">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-graphite-900 border border-white/10 text-xs font-mono text-graphite-300 mb-4">
          <Compass className="w-3.5 h-3.5 text-accent-lime" />
          <span>Project Philosophy</span>
        </div>

        <h2 className="text-3xl sm:text-5xl font-bold tracking-tight text-white mb-6 leading-tight">
          Stop staring. <br className="hidden sm:inline" />
          <span className="text-led-blue">Start living.</span>
        </h2>

        {/* Narrative */}
        <div className="prose prose-invert prose-lg max-w-none text-graphite-300 space-y-6 leading-relaxed">
          <p className="text-lg sm:text-xl text-graphite-200">
            Digital progress is notoriously invisible until you break focus to check a screen.
            Whether you’re compiling a complex project, waiting for a multi-gigabyte Chrome download, or monitoring a MacBook charging on a desk across the room, waiting pulls you back into the digital feed.
          </p>

          <p>
            <strong>Still Loading...</strong> was born from a simple belief: <em className="text-white">your Mac should do the waiting, and the waiting should have a dedicated physical display</em>.
            By connecting macOS system telemetry directly to a small, ambient 8×13 LED matrix, you can glance up, register progress at a sub-conscious level, and get back to what you were doing.
          </p>

          {/* Core Values Card */}
          <div className="my-10 grid grid-cols-1 sm:grid-cols-3 gap-6 not-prose">
            <div className="p-5 rounded-2xl bg-graphite-900/60 border border-white/10">
              <div className="p-2 w-fit rounded-lg bg-accent-lime/10 text-accent-lime mb-3">
                <Lightbulb className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white mb-1">Tangible Waiting</h4>
              <p className="text-xs text-graphite-400 leading-normal">
                Turning abstract computer percentages into physical blue photons on an 8×13 grid.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-graphite-900/60 border border-white/10">
              <div className="p-2 w-fit rounded-lg bg-led-blue/10 text-led-blue mb-3">
                <Shield className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white mb-1">Local-First Privacy</h4>
              <p className="text-xs text-graphite-400 leading-normal">
                Zero third-party cloud required. Runs over local Wi-Fi with strict bearer authentication.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-graphite-900/60 border border-white/10">
              <div className="p-2 w-fit rounded-lg bg-sky-500/10 text-sky-400 mb-3">
                <Heart className="w-5 h-5" />
              </div>
              <h4 className="text-base font-semibold text-white mb-1">Calm Computing</h4>
              <p className="text-xs text-graphite-400 leading-normal">
                Subtle breathing pulses and clear state cues that inform without demanding attention.
              </p>
            </div>
          </div>

          <p>
            The project pairs an <strong>Arduino UNO Q</strong> (with a Qualcomm Quad-core application processor and an STM32U585 microcontroller) with an agent running on macOS.
            The receiver code, message schema, and state engine are backed by <strong>74 automated unit tests</strong> to ensure that every failure, heartbeat stall, and battery reading behaves with mathematical predictability.
          </p>
        </div>

        {/* Creator / Project Attribution */}
        <div className="mt-12 pt-6 border-t border-white/[0.08] flex flex-col sm:flex-row sm:items-center justify-between text-xs font-mono text-graphite-400 gap-3">
          <div>
            <span>Project: </span>
            <span className="text-white font-semibold">Still Loading...</span>
            <span className="text-graphite-500"> (stillloading.tech)</span>
          </div>
          <div>
            <span>Open Source under MIT License • 2026</span>
          </div>
        </div>
      </div>
    </section>
  );
};
