'use client';

import { useState, useRef } from "react";
import { X, Upload, FileText, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { APIClient } from "@/lib/api-client";
import { useAuth } from "@/components/auth-context-msal";

export default function UploadModal({ isOpen, onClose }) {
  const { getAuthHeaders } = useAuth();
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState(null); // 'success', 'error', 'partial', null
  const [errorMessage, setErrorMessage] = useState('');
  const [fileResults, setFileResults] = useState([]);
  const [currentFileName, setCurrentFileName] = useState('');
  const fileInputRef = useRef(null);
  
  // Create API client instance
  const apiClient = new APIClient(getAuthHeaders);

  const allowedTypes = ['.pdf', '.txt', '.csv', '.xlsx', '.xls'];
  const maxFileSize = 50 * 1024 * 1024; // 50MB

  const handleFileSelect = (files) => {
    if (!files || files.length === 0) return;

    const validFiles = [];
    const errors = [];

    Array.from(files).forEach(file => {
      // Validate file type
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      if (!allowedTypes.includes(fileExtension)) {
        errors.push(`${file.name}: File type not allowed`);
        return;
      }

      // Validate file size
      if (file.size > maxFileSize) {
        errors.push(`${file.name}: File size too large (max 50MB)`);
        return;
      }

      // Check for duplicates
      if (selectedFiles.some(existing => existing.name === file.name)) {
        errors.push(`${file.name}: File already selected`);
        return;
      }

      validFiles.push(file);
    });

    if (errors.length > 0) {
      setErrorMessage(errors.join(', '));
      setUploadStatus('error');
    } else {
      setUploadStatus(null);
      setErrorMessage('');
    }

    setSelectedFiles(prev => [...prev, ...validFiles]);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    handleFileSelect(files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const uploadFiles = async () => {
    if (selectedFiles.length === 0) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadStatus(null);
    setErrorMessage('');
    setFileResults([]);

    try {
      if (selectedFiles.length === 1) {
        // Single file upload
        try {
          const response = await apiClient.uploadEDIReport(selectedFiles[0], (progress) => {
            setUploadProgress(progress);
            setCurrentFileName(selectedFiles[0].name);
          });

          setFileResults([{ 
            file: selectedFiles[0].name, 
            success: true, 
            result: response,
            error: null
          }]);
          setUploadStatus('success');
          setUploadProgress(100);
        } catch (error) {
          const isDuplicate = error.message && error.message.startsWith('Duplicate:');
          setFileResults([{ 
            file: selectedFiles[0].name, 
            success: false, 
            result: null,
            error: error.message || 'Upload failed'
          }]);
          setUploadStatus(isDuplicate ? 'partial' : 'error');
          setErrorMessage(error.message || 'Failed to upload file');
          setUploadProgress(100);
        }
      } else {
        // Multiple file upload
        const results = await apiClient.uploadMultipleEDIReports(
          selectedFiles,
          (progress, fileIndex, fileName) => {
            setUploadProgress(progress);
            setCurrentFileName(fileName);
          },
          (fileName, success, result, error) => {
            setFileResults(prev => [...prev, { 
              file: fileName, 
              success, 
              result: result || null,
              error: error || null
            }]);
          }
        );

        const hasErrors = results.some(r => !r.success);
        const allFailed = results.every(r => !r.success);
        setUploadStatus(allFailed ? 'error' : hasErrors ? 'partial' : 'success');
        setUploadProgress(100);
      }
    } catch (error) {
      console.error('Upload error:', error);
      setErrorMessage(error.message || 'Failed to upload files');
      setUploadStatus('error');
    } finally {
      setUploading(false);
    }
  };

  const resetModal = () => {
    setSelectedFiles([]);
    setUploading(false);
    setUploadProgress(0);
    setUploadStatus(null);
    setErrorMessage('');
    setFileResults([]);
    setCurrentFileName('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    setUploadStatus(null);
    setErrorMessage('');
  };

  const handleClose = () => {
    if (!uploading) {
      resetModal();
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Upload EDI Report
          </DialogTitle>
          <DialogDescription>
            Upload your EDI report files. You can select multiple files at once. Supported formats: PDF, TXT, CSV, Excel files (up to 50MB each)
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* File Drop Zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-8 text-center hover:border-muted-foreground/50 transition-colors cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-sm text-muted-foreground mb-2">
              Drag and drop your files here, or click to browse
            </p>
            <p className="text-xs text-muted-foreground">
              {allowedTypes.join(', ')} • Max 50MB each • Multiple files supported
            </p>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept={allowedTypes.join(',')}
              multiple
              onChange={(e) => handleFileSelect(e.target.files)}
            />
          </div>

          {/* Selected Files Display */}
          {selectedFiles.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium">Selected Files ({selectedFiles.length})</h4>
                {!uploading && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedFiles([])}
                  >
                    Clear All
                  </Button>
                )}
              </div>

              <div className="max-h-40 overflow-y-auto space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="border rounded-lg p-3">
                    <div className="flex items-center gap-3">
                      <FileText className="h-6 w-6 text-blue-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                      {!uploading && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(index)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Upload Progress */}
              {uploading && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>
                      {selectedFiles.length === 1 ? 'Uploading...' : `Uploading... (${currentFileName})`}
                    </span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} className="h-2" />
                </div>
              )}
            </div>
          )}

          {/* Status Messages */}
          {uploadStatus === 'success' && selectedFiles.length === 1 && fileResults[0]?.result && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800 space-y-2">
                <div className="font-semibold">File uploaded successfully!</div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="font-medium">CHS Transactions:</span> {fileResults[0].result.chs_transaction_count || 0}
                  </div>
                  <div>
                    <span className="font-medium">All Transactions:</span> {fileResults[0].result.all_transaction_count || 0}
                  </div>
                  <div>
                    <span className="font-medium">CHS Indexed:</span> {fileResults[0].result.chs_indexed ? '✓ Yes' : '✗ No'}
                  </div>
                  <div>
                    <span className="font-medium">All Indexed:</span> {fileResults[0].result.all_indexed ? '✓ Yes' : '✗ No'}
                  </div>
                </div>
                {fileResults[0].result.chs_duplicate && fileResults[0].result.all_duplicate ? (
                  <div className="text-yellow-700 text-sm mt-2 p-2 bg-yellow-100 rounded">
                    ⚠ Both CHS and all transactions were skipped due to duplicate trace numbers. File was uploaded to blob storage.
                  </div>
                ) : (
                  <>
                    {fileResults[0].result.chs_duplicate && (
                      <div className="text-yellow-700 text-sm mt-2 p-2 bg-yellow-100 rounded">
                        ⚠ CHS transactions were skipped due to duplicate trace numbers in the CHS search index
                      </div>
                    )}
                    {fileResults[0].result.all_duplicate && (
                      <div className="text-yellow-700 text-sm mt-2 p-2 bg-yellow-100 rounded">
                        ⚠ All transactions were skipped due to duplicate trace numbers in the master-edi search index
                      </div>
                    )}
                  </>
                )}
                {fileResults[0].result.uploaded_by && (
                  <div className="text-xs text-green-700 mt-1">
                    Uploaded by: {fileResults[0].result.uploaded_by}
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}

          {uploadStatus === 'success' && selectedFiles.length > 1 && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                All {selectedFiles.length} files uploaded successfully! Check details below.
              </AlertDescription>
            </Alert>
          )}

          {uploadStatus === 'partial' && (
            <Alert className="border-yellow-200 bg-yellow-50">
              <AlertCircle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                Some files uploaded successfully, but others failed or were duplicates. Check the detailed results below.
              </AlertDescription>
            </Alert>
          )}

          {uploadStatus === 'error' && errorMessage && (
            <Alert className="border-red-200 bg-red-50">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {errorMessage}
              </AlertDescription>
            </Alert>
          )}

          {/* Detailed File Results */}
          {fileResults.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-semibold">Upload Results:</h4>
              <div className="max-h-64 overflow-y-auto space-y-3">
                {fileResults.map((result, index) => (
                  <div 
                    key={index} 
                    className={`border rounded-lg p-4 ${
                      result.success 
                        ? 'border-green-200 bg-green-50/50' 
                        : result.error && result.error.startsWith('Duplicate:')
                          ? 'border-yellow-200 bg-yellow-50/50'
                          : 'border-red-200 bg-red-50/50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {result.success ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                      ) : result.error && result.error.startsWith('Duplicate:') ? (
                        <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0 space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium truncate">{result.file}</p>
                          <span className={`text-xs font-medium px-2 py-1 rounded ${
                            result.success
                              ? "bg-green-100 text-green-700"
                              : result.error && result.error.startsWith('Duplicate:')
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-red-100 text-red-700"
                          }`}>
                            {result.success
                              ? "Success"
                              : result.error && result.error.startsWith('Duplicate:')
                                ? "Duplicate"
                                : "Failed"}
                          </span>
                        </div>
                        
                        {result.success && result.result && (
                          <div className="space-y-2 text-sm">
                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <span className="text-muted-foreground">CHS Transactions:</span>
                                <span className="ml-2 font-medium">{result.result.chs_transaction_count || 0}</span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">All Transactions:</span>
                                <span className="ml-2 font-medium">{result.result.all_transaction_count || 0}</span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">CHS Indexed:</span>
                                <span className={`ml-2 font-medium ${result.result.chs_indexed ? 'text-green-600' : 'text-red-600'}`}>
                                  {result.result.chs_indexed ? '✓ Yes' : '✗ No'}
                                </span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">All Indexed:</span>
                                <span className={`ml-2 font-medium ${result.result.all_indexed ? 'text-green-600' : 'text-red-600'}`}>
                                  {result.result.all_indexed ? '✓ Yes' : '✗ No'}
                                </span>
                              </div>
                            </div>
                            
                            {result.result.chs_duplicate && !result.result.all_duplicate && (
                              <div className="mt-2 p-2 bg-yellow-100 border border-yellow-300 rounded text-yellow-800 text-xs">
                                ⚠ CHS transactions were skipped due to duplicate trace numbers in the CHS search index. 
                                All transactions were still indexed to master-edi.
                              </div>
                            )}
                            {result.result.all_duplicate && !result.result.chs_duplicate && (
                              <div className="mt-2 p-2 bg-yellow-100 border border-yellow-300 rounded text-yellow-800 text-xs">
                                ⚠ All transactions were skipped due to duplicate trace numbers in the master-edi search index. 
                                CHS transactions were still indexed to edi-transactions.
                              </div>
                            )}
                            {result.result.chs_duplicate && result.result.all_duplicate && (
                              <div className="mt-2 p-2 bg-yellow-100 border border-yellow-300 rounded text-yellow-800 text-xs">
                                ⚠ Both CHS and all transactions were skipped due to duplicate trace numbers in their respective search indexes. 
                                File was uploaded to blob storage but no transactions were indexed.
                              </div>
                            )}
                            
                            {result.result.message && (
                              <div className="text-xs text-muted-foreground mt-1">
                                {result.result.message}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {!result.success && result.error && (
                          <div className="text-sm">
                            <p className={`font-medium ${
                              result.error.startsWith('Duplicate:')
                                ? 'text-yellow-700'
                                : 'text-red-700'
                            }`}>
                              {result.error.startsWith('Duplicate:') 
                                ? result.error.replace('Duplicate: ', '')
                                : result.error}
                            </p>
                            {result.error.startsWith('Duplicate:') && (
                              <p className="text-xs text-yellow-600 mt-1">
                                This file already exists in the system. No changes were made.
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={uploading}
          >
            {uploadStatus === 'success' || uploadStatus === 'partial' ? 'Close' : 'Cancel'}
          </Button>
          {selectedFiles.length > 0 && uploadStatus !== 'success' && uploadStatus !== 'partial' && (
            <Button
              onClick={uploadFiles}
              disabled={uploading}
              className="flex items-center gap-2"
            >
              {uploading ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-background border-t-foreground" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" />
                  Upload {selectedFiles.length === 1 ? 'File' : `${selectedFiles.length} Files`}
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}