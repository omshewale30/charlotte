/*
This page will display the EDI reports in a table format
The table will have the following columns:
- Date
- Amount
- Status
- Action
The action column will have a button to view the report
The report will be displayed in a modal
*/

"use client";

import EDIReportsViewer from "@/components/edi-reports-viewer";
import ProtectedRoute from "@/components/protected-route";


export default function EDIViewerPage() {
    return (
      <ProtectedRoute>
        <EDIReportsViewer />
      </ProtectedRoute>
    );
  }