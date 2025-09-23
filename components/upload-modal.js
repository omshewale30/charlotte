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
import { uploadEDIReport, uploadMultipleEDIReports } from "@/api";

export default function UploadModal({ isOpen, onClose }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState(null); // 'success', 'error', null
  const [errorMessage, setErrorMessage] = useState('');
  const [fileResults, setFileResults] = useState([]);
  const [currentFileName, setCurrentFileName] = useState('');
  const fileInputRef = useRef(null);

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
        const response = await uploadEDIReport(selectedFiles[0], (progress) => {
          setUploadProgress(progress);
          setCurrentFileName(selectedFiles[0].name);
        });

        setFileResults([{ file: selectedFiles[0].name, success: true, result: response }]);
        setUploadStatus('success');
        setUploadProgress(100);
      } else {
        // Multiple file upload
        const results = await uploadMultipleEDIReports(
          selectedFiles,
          (progress, fileIndex, fileName) => {
            setUploadProgress(progress);
            setCurrentFileName(fileName);
          },
          (fileName, success, result) => {
            setFileResults(prev => [...prev, { file: fileName, success, result }]);
          }
        );

        const hasErrors = results.some(r => !r.success);
        setUploadStatus(hasErrors ? 'partial' : 'success');
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
          {uploadStatus === 'success' && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {selectedFiles.length === 1
                  ? 'File uploaded successfully!'
                  : `All ${selectedFiles.length} files uploaded successfully!`}
                They will be processed and added to the system.
              </AlertDescription>
            </Alert>
          )}

          {uploadStatus === 'partial' && (
            <Alert className="border-yellow-200 bg-yellow-50">
              <AlertCircle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                Some files uploaded successfully, but others failed. Check the results below.
              </AlertDescription>
            </Alert>
          )}

          {uploadStatus === 'error' && (
            <Alert className="border-red-200 bg-red-50">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {errorMessage}
              </AlertDescription>
            </Alert>
          )}

          {/* File Results */}
          {fileResults.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Upload Results:</h4>
              <div className="max-h-32 overflow-y-auto space-y-1">
                {fileResults.map((result, index) => (
                  <div key={index} className="flex items-center gap-2 text-sm">
                    {result.success ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : result.result && result.result.startsWith('Duplicate:') ? (
                      <AlertCircle className="h-4 w-4 text-yellow-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    )}
                    <span className="flex-1 truncate">{result.file}</span>
                    <span className={
                      result.success
                        ? "text-green-600"
                        : result.result && result.result.startsWith('Duplicate:')
                          ? "text-yellow-600"
                          : "text-red-600"
                    }>
                      {result.success
                        ? "Success"
                        : result.result && result.result.startsWith('Duplicate:')
                          ? "Duplicate"
                          : "Failed"}
                    </span>
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