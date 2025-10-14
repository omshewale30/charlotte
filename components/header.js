/**
 * need to add a "Dashboard" button to the header
 * need to create a dashboard page
 * the dashboard page will be the EDI data visualizations and excel export
 * 
 */

'use client';

import { useRouter } from "next/navigation";
import { useState } from "react";
import UploadModal from "@/components/upload-modal";
import { Database, LogOut, User, Upload, RefreshCw , ChartArea} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-context-msal";
import { FileText } from "lucide-react";





import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

async function updateSearchIndex(getAuthHeaders) {
  const authHeaders = await getAuthHeaders();
  if (!authHeaders || !authHeaders.Authorization) {
    throw new Error('Authentication required');
  }

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const response = await fetch(`${API_BASE}/api/update-search-index`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update search index: ${response.status}`);
  }

  return await response.json();
}

export default function Header() {
  const { user, logout, isAuthenticated, getAuthHeaders } = useAuth();
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [isUpdatingIndex, setIsUpdatingIndex] = useState(false);
  const [updateStatus, setUpdateStatus] = useState(null);
  const router = useRouter();
  const handleUpdateSearchIndex = async () => {
    setIsUpdatingIndex(true);
    setUpdateStatus(null);

    try {
      const result = await updateSearchIndex(getAuthHeaders);
      setUpdateStatus({
        type: 'success',
        message: result.message,
        details: result.details
      });
    } catch (error) {
      setUpdateStatus({
        type: 'error',
        message: error.message || 'Failed to update search index'
      });
    } finally {
      setIsUpdatingIndex(false);

      // Clear status after 5 seconds
      setTimeout(() => {
        setUpdateStatus(null);
      }, 5000);
    }
  };

  return (
    <header className="border-b border-border bg-card">
      <div className="container mx-auto px-6 py-6 flex items-center justify-between max-w-6xl">
        {/* Logo Section */}
        <div className="flex items-center gap-3">
          <Database className="h-7 w-7 text-primary" />
          <h1 className="text-2xl font-bold">Charlotte</h1>
        </div>

        {/* Navigation Section */}
        <nav className="flex items-center gap-3">
          <Button
            variant="outline"
            size="default"
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 px-4 py-2"
          >
            <ChartArea className="h-4 w-4" />
            <span className="hidden sm:inline">Dashboard</span>
          </Button>

          <Button
            variant="outline"
            size="default"
            onClick={() => router.push('/edi-viewer')}
            className="flex items-center gap-2 px-4 py-2"
          >
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">EDI Viewer</span>
          </Button>
        </nav>

        {/* Actions Section */}
        <div className="flex items-center gap-3">
          {isAuthenticated() && user && (
            <>
              <Button
                variant="outline"
                size="default"
                onClick={() => setShowUploadModal(true)}
                className="flex items-center gap-2 px-4 py-2"
              >
                <Upload className="h-4 w-4" />
                <span className="hidden md:inline">Upload EDI Report</span>
                <span className="md:hidden">Upload</span>
              </Button>

              <Button
                variant="outline"
                size="default"
                onClick={handleUpdateSearchIndex}
                disabled={isUpdatingIndex}
                className="flex items-center gap-2 px-4 py-2 relative"
              >
                <RefreshCw className={`h-4 w-4 ${isUpdatingIndex ? 'animate-spin' : ''}`} />
                <span className="hidden md:inline">
                  {isUpdatingIndex ? 'Updating...' : 'Update Search Index'}
                </span>
                <span className="md:hidden">
                  {isUpdatingIndex ? 'Updating...' : 'Update'}
                </span>
              </Button>
            </>
          )}

          {isAuthenticated() && user && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="default" className="flex items-center gap-2 px-4 py-2">
                  <User className="h-4 w-4" />
                  <span className="hidden sm:inline">{user.given_name || user.name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <DropdownMenuLabel>
                  <div className="space-y-1">
                    <p className="font-medium">{user.name}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                    {user.department && (
                      <p className="text-xs text-muted-foreground">{user.department}</p>
                    )}
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} className="text-destructive cursor-pointer">
                  <LogOut className="h-4 w-4 mr-2" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      <UploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
      />

      {/* Status notification */}
      {updateStatus && (
        <div className={`w-full px-6 py-4 text-sm ${
          updateStatus.type === 'success'
            ? 'bg-green-50 text-green-800 border-b border-green-200'
            : 'bg-red-50 text-red-800 border-b border-red-200'
        }`}>
          <div className="container mx-auto max-w-6xl">
            <div className="flex items-center justify-between">
              <div>
                <strong>{updateStatus.type === 'success' ? '✅ Success:' : '❌ Error:'}</strong> {updateStatus.message}
                {updateStatus.details && (
                  <div className="text-xs mt-1 opacity-75">
                    {updateStatus.details.new_files_processed} files processed, {updateStatus.details.transactions_added} transactions added
                  </div>
                )}
              </div>
              <button
                onClick={() => setUpdateStatus(null)}
                className="text-sm opacity-60 hover:opacity-100 px-2 py-1 rounded hover:bg-black/5"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}