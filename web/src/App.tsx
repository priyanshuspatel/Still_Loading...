import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { HeroSection } from './components/HeroSection';
import { FeaturesGrid } from './components/FeaturesGrid';
import { HowItWorks } from './components/HowItWorks';
import { LiveDashboard } from './components/LiveDashboard';
import { JobHistory } from './components/JobHistory';
import { TechnicalSpecs } from './components/TechnicalSpecs';
import { AboutSection } from './components/AboutSection';
import { Footer } from './components/Footer';
import { LiveConnectionModal } from './components/LiveConnectionModal';

export function App() {
  const [currentTab, setCurrentTab] = useState<'home' | 'dashboard' | 'architecture' | 'about'>('home');
  const [isLiveMode, setIsLiveMode] = useState<boolean>(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  return (
    <div className="min-h-screen bg-[#FBFBFD] dark:bg-[#0B0C0E] text-[#1D1D1F] dark:text-[#F5F5F7] flex flex-col font-sans selection:bg-[#0066CC]/15 selection:text-[#0066CC] transition-colors duration-300">
      <Navbar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        isLiveMode={isLiveMode}
        setIsLiveMode={setIsLiveMode}
      />

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
          <div className="pt-20 pb-20 space-y-6 bg-[#F5F5F7] dark:bg-[#121418]">
            <LiveDashboard
              isLiveMode={isLiveMode}
              setIsLiveMode={setIsLiveMode}
              onOpenSettingsModal={() => setIsSettingsOpen(true)}
            />
            <JobHistory isLiveMode={isLiveMode} />
          </div>
        )}

        {currentTab === 'architecture' && (
          <div className="pt-16">
            <HowItWorks />
            <TechnicalSpecs />
          </div>
        )}

        {currentTab === 'about' && (
          <div className="pt-16">
            <AboutSection />
            <TechnicalSpecs />
          </div>
        )}
      </main>

      <Footer
        onNavigate={(tab) => {
          setCurrentTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        isLiveMode={isLiveMode}
      />

      <LiveConnectionModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </div>
  );
}

export default App;
