'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import UploadModal from '@/components/upload-modal';
import AlignRxUploadModal from '@/components/align-rx-upload-modal';
import Logout from '@/components/logout';

import { 
  MessageSquare, 
  BarChart3, 
  FileText, 
  Upload, 
  DollarSign, 
  TrendingUp, 
  FileCheck, 
  Calendar,
  Database,
  FileSpreadsheet,
  ChartArea
} from 'lucide-react';

export default function Dashboard() {
  const router = useRouter();
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showAlignRxUploadModal, setShowAlignRxUploadModal] = useState(false);
  // Placeholder data - will be wired up later
  const dashboardData = {
    totalAmount: '$2,847,392.50',
    totalTransactions: '1,247',
    processedReports: '89',
    currentYear: new Date().getFullYear()
  };

  const quickActions = [
    {
      title: 'Chat',
      description: 'Start a conversation with Charlotte AI',
      icon: MessageSquare,
      onClick: () => router.push('/chat'),
      gradient: 'from-[#4B9CD3] to-[#2B6FA6]',
      iconBg: 'bg-[#4B9CD3]/10'
    },
    {
      title: 'Data Analysis',
      description: 'Analyze EDI data and generate insights',
      icon: BarChart3,
      onClick: () => router.push('/data-analysis'),
      gradient: 'from-[#2B6FA6] to-[#0F3D63]',
      iconBg: 'bg-[#2B6FA6]/10'
    },
    {
      title: 'EDI Reports Viewer',
      description: 'View CHS department EDI reports',
      icon: FileText,
      onClick: () => router.push('/edi-viewer'),
      gradient: 'from-[#4B9CD3] to-[#1E40AF]',
      iconBg: 'bg-[#4B9CD3]/10'
    },
    {
      title: 'Upload EDI Report',
      description: 'Upload new EDI report files',
      icon: Upload,
      onClick: () => setShowUploadModal(true),
      gradient: 'from-[#2B6FA6] to-[#4B9CD3]',
      iconBg: 'bg-[#2B6FA6]/10'
    },
    {
      title: 'Upload AlignRx Report',
      description: 'Upload new AlignRx report files',
      icon: FileSpreadsheet,
      onClick: () => setShowAlignRxUploadModal(true),
      gradient: 'from-[#0F3D63] to-[#2B6FA6]',
      iconBg: 'bg-[#0F3D63]/10'
    },
    {
      title: 'AlignRx Data Analysis',
      description: 'Analyze AlignRx data and generate insights',
      icon: ChartArea,
      onClick: () => router.push('/align-rx-analysis'),
      gradient: 'from-[#4B9CD3] to-[#0F3D63]',
      iconBg: 'bg-[#4B9CD3]/10'
    }
  ];

  const statsCards = [
    {
      title: 'Total Amount',
      value: dashboardData.totalAmount,
      description: `Current year (${dashboardData.currentYear})`,
      icon: DollarSign,
      trend: '+12.5%',
      trendUp: true
    },
    {
      title: 'Total Transactions',
      value: dashboardData.totalTransactions,
      description: 'Processed this year',
      icon: TrendingUp,
      trend: '+8.2%',
      trendUp: true
    },
    {
      title: 'Reports Processed',
      value: dashboardData.processedReports,
      description: 'EDI reports uploaded',
      icon: FileCheck,
      trend: '+15.3%',
      trendUp: true
    },
    {
      title: 'Last Updated',
      value: '2 hours ago',
      description: 'Data refresh status',
      icon: Calendar,
      trend: 'Live',
      trendUp: null
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-[rgba(75,156,211,0.03)] to-background relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-[#4B9CD3]/5 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-[#2B6FA6]/5 rounded-full blur-3xl"></div>
      </div>

      {/* Floating Logout Component */}
      <div className="fixed top-4 right-4 z-50 fade-in-up">
        <div className="bg-background/90 backdrop-blur-md border-2 border-primary/20 rounded-2xl shadow-2xl p-2">
          <Logout />
        </div>
      </div>
      
      <div className="container mx-auto px-4 md:px-6 py-8 md:py-12 max-w-7xl relative z-10">
        {/* Header Section */}
        <div className="mb-12 fade-in-up">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] flex items-center justify-center shadow-lg">
              <Database className="h-7 w-7 text-white" />
            </div>
            <div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground tracking-tight">
                Dashboard
              </h1>
            </div>
          </div>
          <p className="text-lg md:text-xl text-muted-foreground md:ml-[4.5rem]">
            Welcome to <span className="font-semibold text-[#4B9CD3]">Charlotte</span> - Your AI-powered EDI data management platform
          </p>
        </div>

        {/* Stats Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {statsCards.map((stat, index) => {
            const delayClass = index === 0 ? 'fade-in-up-delay-1' : 
                              index === 1 ? 'fade-in-up-delay-2' : 
                              index === 2 ? 'fade-in-up-delay-3' : 'fade-in-up-delay-4';
            return (
              <Card 
                key={index} 
                className={`${delayClass} relative overflow-hidden border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-lg hover:shadow-2xl hover:border-primary/30 transition-all duration-300 group`}
              >
                {/* Gradient overlay on hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-[#4B9CD3]/0 to-[#2B6FA6]/0 group-hover:from-[#4B9CD3]/5 group-hover:to-[#2B6FA6]/5 transition-all duration-300 pointer-events-none"></div>
                
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3 relative z-10">
                  <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                    {stat.title}
                  </CardTitle>
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center group-hover:from-[#4B9CD3]/30 group-hover:to-[#2B6FA6]/30 transition-all duration-300">
                    <stat.icon className="h-5 w-5 text-[#4B9CD3]" />
                  </div>
                </CardHeader>
                <CardContent className="relative z-10">
                  <div className="text-3xl md:text-4xl font-bold text-foreground mb-2">
                    {stat.value}
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-xs md:text-sm text-muted-foreground">
                      {stat.description}
                    </p>
                    {stat.trendUp !== null && (
                      <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                        stat.trendUp ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                      }`}>
                        {stat.trend}
                      </span>
                    )}
                    {stat.trendUp === null && (
                      <span className="text-xs font-semibold px-2 py-1 rounded-full bg-[#4B9CD3]/10 text-[#4B9CD3]">
                        {stat.trend}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Quick Actions Section */}
        <div className="mb-12">
          <div className="mb-8 fade-in-up-delay-2">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3 tracking-tight">
              Quick <span className="bg-gradient-to-r from-[#4B9CD3] to-[#2B6FA6] bg-clip-text text-transparent">Actions</span>
            </h2>
            <p className="text-muted-foreground">Access key features and tools instantly</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {quickActions.map((action, index) => {
              const delayClass = index < 3 ? `fade-in-up-delay-${index + 1}` : `fade-in-up-delay-${(index % 3) + 1}`;
              return (
                <Card 
                  key={index} 
                  className={`${delayClass} group cursor-pointer border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-lg hover:shadow-2xl hover:border-primary/30 transition-all duration-300 transform hover:-translate-y-2 hover:scale-[1.02] relative overflow-hidden`}
                  onClick={action.onClick}
                >
                  {/* Gradient background on hover */}
                  <div className={`absolute inset-0 bg-gradient-to-br ${action.gradient} opacity-0 group-hover:opacity-5 transition-opacity duration-300`}></div>
                  
                  <CardHeader className="text-center pb-4 pt-8 relative z-10">
                    <div className={`mx-auto w-20 h-20 rounded-2xl ${action.iconBg} flex items-center justify-center mb-4 group-hover:scale-110 group-hover:rotate-3 transition-all duration-300`}>
                      <action.icon className={`h-10 w-10 text-[#4B9CD3] group-hover:text-[#2B6FA6] transition-colors duration-300`} />
                    </div>
                    <CardTitle className="text-xl font-bold text-foreground group-hover:text-[#4B9CD3] transition-colors duration-300">
                      {action.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-center pt-0 pb-8 relative z-10">
                    <CardDescription className="text-muted-foreground text-sm leading-relaxed">
                      {action.description}
                    </CardDescription>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Recent Activity Section */}
        <div className="mb-8">
          <div className="mb-8 fade-in-up-delay-3">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-3 tracking-tight">
              Recent <span className="bg-gradient-to-r from-[#4B9CD3] to-[#2B6FA6] bg-clip-text text-transparent">Activity</span>
            </h2>
            <p className="text-muted-foreground">Your most recently processed reports and transactions</p>
          </div>
          <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl fade-in-up-delay-4">
            <CardHeader className="pb-6">
              <CardTitle className="flex items-center gap-3 text-2xl font-bold text-foreground">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                  <FileText className="h-5 w-5 text-[#4B9CD3]" />
                </div>
                Latest EDI Reports
              </CardTitle>
              <CardDescription className="text-base text-muted-foreground mt-2">
                Your most recently processed EDI reports
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-5 bg-gradient-to-r from-[#4B9CD3]/5 to-transparent rounded-xl border border-primary/10 hover:border-primary/20 hover:from-[#4B9CD3]/10 transition-all duration-300 group cursor-pointer">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                      <FileText className="h-6 w-6 text-[#4B9CD3]" />
                    </div>
                    <div>
                      <p className="font-semibold text-foreground group-hover:text-[#4B9CD3] transition-colors duration-300">EDI Remittance Advice Report_2063_20250828_chs.pdf</p>
                      <p className="text-sm text-muted-foreground mt-1">Processed 2 hours ago</p>
                    </div>
                  </div>
                  <span className="px-3 py-1.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full shadow-sm">
                    Completed
                  </span>
                </div>
                <div className="flex items-center justify-between p-5 bg-gradient-to-r from-[#4B9CD3]/5 to-transparent rounded-xl border border-primary/10 hover:border-primary/20 hover:from-[#4B9CD3]/10 transition-all duration-300 group cursor-pointer">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                      <FileText className="h-6 w-6 text-[#4B9CD3]" />
                    </div>
                    <div>
                      <p className="font-semibold text-foreground group-hover:text-[#4B9CD3] transition-colors duration-300">EDI Remittance Advice Report_2063_20250827_studentresource.pdf</p>
                      <p className="text-sm text-muted-foreground mt-1">Processed 4 hours ago</p>
                    </div>
                  </div>
                  <span className="px-3 py-1.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full shadow-sm">
                    Completed
                  </span>
                </div>
                <div className="flex items-center justify-between p-5 bg-gradient-to-r from-[#4B9CD3]/5 to-transparent rounded-xl border border-primary/10 hover:border-primary/20 hover:from-[#4B9CD3]/10 transition-all duration-300 group cursor-pointer">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                      <FileText className="h-6 w-6 text-[#4B9CD3]" />
                    </div>
                    <div>
                      <p className="font-semibold text-foreground group-hover:text-[#4B9CD3] transition-colors duration-300">EDI Remittance Advice Report_2063_20250826_chs.pdf</p>
                      <p className="text-sm text-muted-foreground mt-1">Processed 1 day ago</p>
                    </div>
                  </div>
                  <span className="px-3 py-1.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs font-semibold rounded-full shadow-sm">
                    Completed
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Upload Modal */}
        <UploadModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
        />
        <AlignRxUploadModal
          isOpen={showAlignRxUploadModal}
          onClose={() => setShowAlignRxUploadModal(false)}
        />
      </div>
    </div>
  );
}

