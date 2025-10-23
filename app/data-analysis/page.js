'use client';

import ProtectedRoute from "@/components/protected-route";
import DataAnalysis from "@/components/data-analysis";


export default function DataAnalysisPage() {
  return (
    <ProtectedRoute>
      <DataAnalysis />
    </ProtectedRoute>
  );
}