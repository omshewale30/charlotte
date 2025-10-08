'use client';

import ProtectedRoute from "@/components/protected-route";
import Dashboard from "@/components/dashboard";


export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  );
}