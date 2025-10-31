'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import UploadModal from '@/components/upload-modal';
import AlignRxUploadModal from '@/components/align-rx-upload-modal';

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
      color: 'bg-blue-500 hover:bg-blue-600',
      iconColor: 'text-blue-100'
    },
    {
      title: 'Data Analysis',
      description: 'Analyze EDI data and generate insights',
      icon: BarChart3,
      onClick: () => router.push('/data-analysis'),
      color: 'bg-green-500 hover:bg-green-600',
      iconColor: 'text-green-100'
    },
    {
      title: 'EDI Reports Viewer',
      description: 'View CHS department EDI reports',
      icon: FileText,
      onClick: () => router.push('/edi-viewer'),
      color: 'bg-purple-500 hover:bg-purple-600',
      iconColor: 'text-purple-100'
    },
    {
      title: 'Upload EDI Report',
      description: 'Upload new EDI report files',
      icon: Upload,
      onClick: () => setShowUploadModal(true),
      color: 'bg-orange-500 hover:bg-orange-600',
      iconColor: 'text-orange-100'
    },
    {
      title: 'Upload AlignRx Report',
      description: 'Upload new AlignRx report files',
      icon: FileSpreadsheet,
      onClick: () => setShowAlignRxUploadModal(true),
      color: 'bg-red-500 hover:bg-red-600',
      iconColor: 'text-red-100'
    },
    {
      title: 'AlignRx Data Analysis',
      description: 'Analyze AlignRx data and generate insights',
      icon: ChartArea,
      onClick: () => router.push('/align-rx-analysis'),
      color: 'bg-green-500 hover:bg-green-600',
      iconColor: 'text-green-100'
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto px-6 py-8 max-w-7xl">
        {/* Header Section */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Database className="h-8 w-8 text-primary" />
            <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
          </div>
          <p className="text-lg text-gray-600">
            Welcome to Charlotte - Your AI-powered EDI data management platform
          </p>
        </div>

        {/* Stats Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {statsCards.map((stat, index) => (
            <Card key={index} className="relative overflow-hidden hover:shadow-lg transition-shadow">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">
                  {stat.title}
                </CardTitle>
                <stat.icon className="h-4 w-4 text-gray-400" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-gray-900 mb-1">
                  {stat.value}
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-500">
                    {stat.description}
                  </p>
                  {stat.trendUp !== null && (
                    <span className={`text-xs font-medium ${
                      stat.trendUp ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {stat.trend}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Quick Actions Section */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {quickActions.map((action, index) => (
              <Card 
                key={index} 
                className="group cursor-pointer hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                onClick={action.onClick}
              >
                <CardHeader className="text-center pb-4">
                  <div className={`mx-auto w-16 h-16 rounded-full ${action.color} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}>
                    <action.icon className={`h-8 w-8 ${action.iconColor}`} />
                  </div>
                  <CardTitle className="text-lg font-semibold text-gray-900 group-hover:text-gray-700">
                    {action.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-center pt-0">
                  <CardDescription className="text-gray-600 group-hover:text-gray-500">
                    {action.description}
                  </CardDescription>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Recent Activity Section */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Recent Activity</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Latest EDI Reports
              </CardTitle>
              <CardDescription>
                Your most recently processed EDI reports
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="font-medium text-gray-900">EDI Remittance Advice Report_2063_20250828_chs.pdf</p>
                      <p className="text-sm text-gray-500">Processed 2 hours ago</p>
                    </div>
                  </div>
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                    Completed
                  </span>
                </div>
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="font-medium text-gray-900">EDI Remittance Advice Report_2063_20250827_studentresource.pdf</p>
                      <p className="text-sm text-gray-500">Processed 4 hours ago</p>
                    </div>
                  </div>
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                    Completed
                  </span>
                </div>
                <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <FileText className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="font-medium text-gray-900">EDI Remittance Advice Report_2063_20250826_chs.pdf</p>
                      <p className="text-sm text-gray-500">Processed 1 day ago</p>
                    </div>
                  </div>
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
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

