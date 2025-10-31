'use client';

import ProtectedRoute from "@/components/protected-route";
import AlignRxAnalysis from "@/components/align-rx-analysis";


export default function AlignRxAnalysisPage() {
  return (
    <ProtectedRoute>
      <AlignRxAnalysis />
    </ProtectedRoute>
  );
}