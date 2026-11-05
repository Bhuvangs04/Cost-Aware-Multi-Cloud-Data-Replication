import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';
import { Overview } from './pages/Overview';
import { CloudProviders } from './pages/CloudProviders';
import { FileManagement } from './pages/FileManagement';
import { ReplicationPolicies } from './pages/ReplicationPolicies';
import { CostAnalytics } from './pages/CostAnalytics';
import { DisasterRecovery } from './pages/DisasterRecovery';
import { ExperimentResults } from './pages/ExperimentResults';
import { api } from './services/api';
import { HealthStatusReport } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [healthReport, setHealthReport] = useState<HealthStatusReport | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const report = await api.getHealth();
        setHealthReport(report);
      } catch (err) {
        console.error('Failed to fetch initial health status', err);
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const renderActivePage = () => {
    switch (activeTab) {
      case 'overview':
        return <Overview />;
      case 'providers':
        return <CloudProviders />;
      case 'files':
        return <FileManagement />;
      case 'policies':
        return <ReplicationPolicies />;
      case 'cost':
        return <CostAnalytics />;
      case 'dr':
        return <DisasterRecovery />;
      case 'benchmarks':
        return <ExperimentResults />;
      default:
        return <Overview />;
    }
  };

  return (
    <div className="flex min-h-screen bg-[#0B0F19] text-slate-100">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      <div className="flex-1 flex flex-col min-w-0">
        <Navbar healthReport={healthReport} activeTab={activeTab} />
        <main className="flex-1 overflow-y-auto">
          {renderActivePage()}
        </main>
      </div>
    </div>
  );
};

export default App;

