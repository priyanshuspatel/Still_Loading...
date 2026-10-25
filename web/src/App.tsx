import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { HeroSection } from './components/HeroSection';
import { FeaturesGrid } from './components/FeaturesGrid';
import { HowItWorks } from './components/HowItWorks';
import { LiveDashboard } from './components/LiveDashboard';
import { TechnicalSpecs } from './components/TechnicalSpecs';
import { AboutSection } from './components/AboutSection';
import { Footer } from './components/Footer';
import { LiveConnectionModal } from './components/LiveConnectionModal';

export function App() {
  const [currentTab, setCurrentTab] = useState<'home' | 'dashboard' | 'architecture' | 'about'>('home');
  const [isLiveMode, setIsLiveMode] = useState<boolean>(false); // Start in Demo Mode for predictable first impression
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-graphite-950 text-graphite-100 flex flex-col font-sans selection:bg-led-blue/20 selection:text-led-blue">
      {/* Top Fixed Navigation */}
      <Navbar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        isLiveMode={isLiveMode}
        setIsLiveMode={setIsLiveMode}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {currentTab === 'home' && (
          <>
            <HeroSection
              onOpenDashboard={() => {
                setCurrentTab('dashboard');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              onSeeHowItWorks={() => {
                setCurrentTab('architecture');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              isLiveMode={isLiveMode}
            />
            <FeaturesGrid />
            <HowItWorks />
            <TechnicalSpecs />
            <AboutSection />
          </>
        )}

        {currentTab === 'dashboard' && (
          <div className="pt-24 pb-16">
            <LiveDashboard
              isLiveMode={isLiveMode}
              setIsLiveMode={setIsLiveMode}
              onOpenSettingsModal={() => setIsSettingsOpen(true)}
            />
          </div>
        )}

        {currentTab === 'architecture' && (
          <div className="pt-20">
            <HowItWorks />
            <TechnicalSpecs />
          </div>
        )}

        {currentTab === 'about' && (
          <div className="pt-20">
            <AboutSection />
            <TechnicalSpecs />
          </div>
        )}
      </main>

      {/* Footer */}
      <Footer
        onNavigate={(tab) => {
          setCurrentTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        isLiveMode={isLiveMode}
      />

      {/* Telemetry Settings Modal */}
      <LiveConnectionModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
}

export default App;
