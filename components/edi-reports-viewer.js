/*
This component will display the EDI reports in a table format
The table will have the following columns:
- Date
- Amount
- Status
- Action
The action column will have a button to view the report
The report will be displayed in a modal

The user will be able to filter and sort the reports by date, amount, status, or action

The edi reports that will be displayed are in the Azure blob storage container called edi-reports.
The reports are in the pdf format.
*/

"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/components/auth-context-msal";
import { APIClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { 
  FileText, 
  Download, 
  Eye, 
  Calendar, 
  Filter,
  Search,
  RefreshCw,
  AlertCircle
} from "lucide-react";

export default function EDIReportsViewer() {
  const { getAuthHeaders } = useAuth();
  const [reports, setReports] = useState([]);
  const [filteredReports, setFilteredReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState("effective_date");
  const [sortOrder, setSortOrder] = useState("desc");
  const [apiClient] = useState(() => new APIClient(getAuthHeaders));

  // Load reports on component mount
  useEffect(() => {
    loadReports();
  }, []);

  // Filter and sort reports when search term or sort options change
  useEffect(() => {
    filterAndSortReports();
  }, [reports, searchTerm, sortBy, sortOrder]);

  const loadReports = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getEdiReports();
      
      if (response.success) {
        setReports(response.reports);
      } else {
        setError("Failed to load reports");
      }
    } catch (err) {
      console.error("Error loading reports:", err);
      setError(err.message || "Failed to load reports");
    } finally {
      setLoading(false);
    }
  };

  const filterAndSortReports = () => {
    let filtered = [...reports];

    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(report => 
        report.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (report.parsed_date && report.parsed_date.includes(searchTerm))
      );
    }

    // Sort reports
    filtered.sort((a, b) => {
      let aValue, bValue;
      
      switch (sortBy) {
        case "filename":
          aValue = a.filename.toLowerCase();
          bValue = b.filename.toLowerCase();
          break;
        case "parsed_date":
          aValue = a.parsed_date || "";
          bValue = b.parsed_date || "";
          break;
        case "effective_date":
          aValue = a.effective_date || "";
          bValue = b.effective_date || "";
          break;
        case "size":
          aValue = a.size || 0;
          bValue = b.size || 0;
          break;
        default:
          aValue = a.effective_date || "";
          bValue = b.effective_date || "";
      }

      if (sortOrder === "asc") {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    setFilteredReports(filtered);
  };

  const handleViewReport = async (report) => {
    try {
      console.log("Loading report for viewing:", report.filename);
      // Get a temporary URL for viewing the PDF using API client
      const response = await apiClient.getEdiReport(report.filename);
      console.log("Response received:", response);
      console.log("Content-Type:", response.headers.get('content-type'));
      
      const blob = await response.blob();
      console.log("Blob created:", blob);
      console.log("Blob type:", blob.type);
      console.log("Blob size:", blob.size);
      
      // Create blob with explicit PDF type if not set
      const pdfBlob = new Blob([blob], { type: 'application/pdf' });
      const url = URL.createObjectURL(pdfBlob);
      console.log("Blob URL created:", url);
      
      setSelectedReport({ ...report, viewUrl: url });
      setIsModalOpen(true);
    } catch (err) {
      console.error("Error loading report for viewing:", err);
      setError("Failed to load report for viewing");
    }
  };

  const handleCloseModal = () => {
    // Clean up blob URL to prevent memory leaks
    if (selectedReport?.viewUrl) {
      URL.revokeObjectURL(selectedReport.viewUrl);
    }
    setSelectedReport(null);
    setIsModalOpen(false);
  };

  const handleDownloadReport = async (report) => {
    try {
      const response = await apiClient.getEdiReport(report.filename);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = report.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Error downloading report:", err);
      setError("Failed to download report");
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  const getStatusColor = (report) => {
    // Simple status based on file age
    if (!report.last_modified) return 'text-gray-500';
    
    const daysSinceModified = (new Date() - new Date(report.last_modified)) / (1000 * 60 * 60 * 24);
    
    if (daysSinceModified <= 7) return 'text-green-600';
    if (daysSinceModified <= 30) return 'text-yellow-600';
    return 'text-gray-500';
  };

  const getStatusText = (report) => {
    if (!report.last_modified) return 'Unknown';
    
    const daysSinceModified = (new Date() - new Date(report.last_modified)) / (1000 * 60 * 60 * 24);
    
    if (daysSinceModified <= 7) return 'Recent';
    if (daysSinceModified <= 30) return 'Recent';
    return 'Older';
  };

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardContent className="flex items-center justify-center py-8">
            <div className="text-center">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
              <p>Loading EDI reports...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-6 w-6" />
            EDI Reports Viewer
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Controls */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search reports by filename or date..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  Sort by {sortBy}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setSortBy("effective_date")}>
                  Effective Date
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSortBy("filename")}>
                  Filename
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSortBy("parsed_date")}>
                  Date
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setSortBy("size")}>
                  File Size
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button 
              variant="outline" 
              onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
            >
              {sortOrder === "asc" ? "↑" : "↓"}
            </Button>

            <Button onClick={loadReports} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Reports Table */}
          {filteredReports.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              {reports.length === 0 ? "No EDI reports found" : "No reports match your search criteria"}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Filename</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Effective Date</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredReports.map((report, index) => (
                    <TableRow key={index}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-blue-500" />
                          <span className="truncate max-w-xs" title={report.filename}>
                            {report.filename}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {report.parsed_date ? formatDate(report.parsed_date) : 'N/A'}
                      </TableCell>
                      <TableCell>{formatFileSize(report.size)}</TableCell>
                      <TableCell>
                        <span className={getStatusColor(report)}>
                          {getStatusText(report)}
                        </span>
                      </TableCell>
                      <TableCell>{formatDate(report.effective_date)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleViewReport(report)}
                          >
                            <Eye className="h-4 w-4 mr-1" />
                            View
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDownloadReport(report)}
                          >
                            <Download className="h-4 w-4 mr-1" />
                            Download
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Summary */}
          <div className="mt-4 text-sm text-gray-600">
            Showing {filteredReports.length} of {reports.length} reports
          </div>
        </CardContent>
      </Card>

      {/* PDF Viewer Modal */}
      <Dialog open={isModalOpen} onOpenChange={handleCloseModal}>
        <DialogContent className="max-w-4xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {selectedReport?.filename}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-hidden">
            {selectedReport && selectedReport.viewUrl && (
              <div className="w-full h-[70vh] border rounded">
                {/* Try object tag first for better PDF support */}
                <object
                  data={selectedReport.viewUrl}
                  type="application/pdf"
                  className="w-full h-full"
                  onLoad={() => console.log("Object loaded successfully")}
                  onError={(e) => console.error("Object failed to load:", e)}
                >
                  {/* Fallback iframe */}
                  <iframe
                    src={selectedReport.viewUrl}
                    className="w-full h-full"
                    title={selectedReport.filename}
                    onLoad={() => console.log("Iframe loaded successfully")}
                    onError={(e) => console.error("Iframe failed to load:", e)}
                  />
                </object>
                
                {/* Fallback options */}
                <div className="mt-4 text-center">
                  <p className="text-sm text-gray-600 mb-2">
                    If the PDF doesn't display above, you can:
                  </p>
                  <div className="flex gap-2 justify-center">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => window.open(selectedReport.viewUrl, '_blank')}
                    >
                      Open in New Tab
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDownloadReport(selectedReport)}
                    >
                      Download PDF
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}