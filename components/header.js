'use client';

import { Database, LogOut, User, Upload, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-context";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useState } from "react";
import UploadModal from "@/components/upload-modal";

async function updateSearchIndex() {
  const sessionId = localStorage.getItem('session_id');
  if (!sessionId) {
    throw new Error('Authentication required');
  }

  const response = await fetch('http://localhost:8000/api/update-search-index', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${sessionId}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to update search index: ${response.status}`);
  }

  return await response.json();
}

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [isUpdatingIndex, setIsUpdatingIndex] = useState(false);
  const [updateStatus, setUpdateStatus] = useState(null);

  const handleUpdateSearchIndex = async () => {
    setIsUpdatingIndex(true);
    setUpdateStatus(null);

    try {
      const result = await updateSearchIndex();
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
      <div className="container mx-auto px-4 py-4 flex items-center justify-between max-w-4xl">
        <div className="flex items-center gap-2">
          <Database className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-semibold">Charlotte</h1>
        </div>
        
        <div className="flex items-center gap-4">
          {isAuthenticated() && user && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUploadModal(true)}
                className="flex items-center gap-2"
              >
                <Upload className="h-4 w-4" />
                <span className="hidden sm:inline">Upload EDI Report</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={handleUpdateSearchIndex}
                disabled={isUpdatingIndex}
                className="flex items-center gap-2 relative"
              >
                <RefreshCw className={`h-4 w-4 ${isUpdatingIndex ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">
                  {isUpdatingIndex ? 'Updating...' : 'Update Search Index'}
                </span>
              </Button>
            </>
          )}

          {isAuthenticated() && user && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="flex items-center gap-2">
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
        <div className={`w-full px-4 py-3 text-sm ${
          updateStatus.type === 'success'
            ? 'bg-green-50 text-green-800 border-b border-green-200'
            : 'bg-red-50 text-red-800 border-b border-red-200'
        }`}>
          <div className="container mx-auto max-w-4xl">
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
                className="text-xs opacity-60 hover:opacity-100"
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