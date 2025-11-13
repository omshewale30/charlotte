/**
 * Data Analysis component for the application 
 * user can toggle between Master EDI and CHS EDI data
 * Master EDI data is the default data
 * CHS EDI data is the data that is used for the CHS department
 * Contains the logic for the data analysis page
 * Includes visualizations, tables, and Excel export functionality
 * Uses the APIClient to fetch data from the backend
 * Uses the useAuth hook to get the authentication headers
 */
"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles } from "lucide-react";
import { APIClient } from "@/lib/api-client";
import { useAuth } from "@/components/auth-context-msal";
import DataAnalysisToggle from "@/components/ui/data-analysis-toggle";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
    PieChart,
    Pie,
    Cell,
    Legend
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import AIOverviewCard from "@/components/ui/ai-overview";


export default function DataAnalysis() {
    const { getAuthHeaders } = useAuth();
    const apiClient = new APIClient(getAuthHeaders);

    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [loading, setLoading] = useState(false);
    const [aiOverviewLoading, setAiOverviewLoading] = useState(false);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);
    const [dataAnalysisMode, setDataAnalysisMode] = useState("master");
    const year = new Date().getFullYear();


    const formatCurrency = (value) => {
        if (value === null || value === undefined || isNaN(Number(value))) return "-";
        return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(value));
    };

    const formatNumber = (value) => {
        if (value === null || value === undefined || isNaN(Number(value))) return "-";
        return new Intl.NumberFormat(undefined).format(Number(value));
    };

    const handleAnalyze = async () => {
        if (!startDate || !endDate) {
            setError("Please select a start and end date.");
            return;
        }
        setLoading(true);
        setAiOverviewLoading(true);
        setError(null);
        try {
            const data = await apiClient.analyzeEdiRange({ start: startDate, end: endDate, mode: dataAnalysisMode });
            setResult(data);
            // AI overview is included in the response, so stop loading
            setAiOverviewLoading(false);
        } catch (e) {
            setError(e.message || "Failed to load analysis");
            setAiOverviewLoading(false);
        } finally {
            setLoading(false);
        }
    };
    // const handleUpdateSearchIndex = async () => {
    //     setIsUpdatingIndex(true);
    //     setUpdateStatus(null);
    
    //     try {
    //       const result = await updateSearchIndex(getAuthHeaders);
    //       setUpdateStatus({
    //         type: 'success',
    //         message: result.message,
    //         details: result.details
    //       });
    //     } catch (error) {
    //       setUpdateStatus({
    //         type: 'error',
    //         message: error.message || 'Failed to update search index'
    //       });
    //     } finally {
    //       setIsUpdatingIndex(false);
    
    //       // Clear status after 5 seconds
    //       setTimeout(() => {
    //         setUpdateStatus(null);
    //       }, 5000);
    //     }
    //   };
    

    const handleDownload = async () => {
        if (!startDate || !endDate) {
            setError("Please select a start and end date.");
            return;
        }
        setError(null);
        try {
            const blob = await apiClient.downloadEdiExcel({ start: startDate, end: endDate, mode: dataAnalysisMode });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${dataAnalysisMode}_edi_export_${startDate}_to_${endDate}.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            setError(e.message || "Failed to download Excel");
        }
    };
    const handleFinancialYear = (year) => {
        setStartDate(new Date(`${year}-07-01`).toISOString().split('T')[0]);
        setEndDate(new Date(`${year + 1}-06-30`).toISOString().split('T')[0]);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-background via-[rgba(75,156,211,0.02)] to-background relative overflow-hidden">
            {/* Background decorative elements */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-[#4B9CD3]/3 rounded-full blur-3xl"></div>
                <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-[#2B6FA6]/3 rounded-full blur-3xl"></div>
            </div>

            <div className="max-w-7xl mx-auto px-4 md:px-6 py-8 md:py-12 relative z-10 space-y-8">
                {/* Header Section */}
                <div className="mb-12 fade-in-up">
                    <div className="flex items-center gap-4 mb-4">
                        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] flex items-center justify-center shadow-lg">
                            <Sparkles className="h-7 w-7 text-white" />
                        </div>
                        <div>
                            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground tracking-tight">
                                Data <span className="bg-gradient-to-r from-[#4B9CD3] to-[#2B6FA6] bg-clip-text text-transparent">Analysis</span>
                            </h1>
                        </div>
                    </div>
                    <p className="text-lg md:text-xl text-muted-foreground md:ml-[4.5rem]">
                        Analyze EDI transactions and generate insights with AI-powered overviews
                    </p>
                </div>

                {/* Controls Section */}
                <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl fade-in-up-delay-1">
                    <CardHeader className="pb-6">
                        <CardTitle className="text-2xl font-bold text-foreground">Analysis Controls</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {/* Data Source Toggle */}
                        <div className="flex items-center gap-4 p-4 rounded-xl bg-gradient-to-r from-[#4B9CD3]/5 to-transparent border border-primary/10">
                            <label className="text-sm font-semibold text-foreground">Data Source:</label>
                            <DataAnalysisToggle value={dataAnalysisMode} onChange={setDataAnalysisMode} />
                        </div>

                        {/* Financial Year Quick Select */}
                        <div className="space-y-3">
                            <label className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Quick Select Financial Year</label>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                {[
                                    { label: `FY${String(year - 2).slice(-2)}-${String(year - 1).slice(-2)}`, year: year - 2 },
                                    { label: `FY${String(year - 1).slice(-2)}-${String(year).slice(-2)}`, year: year - 1 },
                                    { label: `FY${String(year).slice(-2)}-${String(year + 1).slice(-2)}`, year: year },
                                    { label: `FY${String(year + 1).slice(-2)}-${String(year + 2).slice(-2)}`, year: year + 1 }
                                ].map((fy, index) => (
                                    <Button 
                                        key={index}
                                        onClick={() => handleFinancialYear(fy.year)}
                                        variant="outline"
                                        className="border-2 border-primary/10 bg-card/60 backdrop-blur-sm hover:border-primary/30 hover:bg-card/80 transition-all duration-300 hover:scale-105"
                                    >
                                        {fy.label}
                                    </Button>
                                ))}
                            </div>
                        </div>
                    
                        {/* Date Range Inputs */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="flex flex-col gap-2">
                                <label className="text-sm font-semibold text-foreground">Start Date</label>
                                <input
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="border-2 border-primary/10 bg-card/60 backdrop-blur-sm text-foreground rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#4B9CD3]/20 focus:border-[#4B9CD3]/40 transition-all duration-300 hover:border-primary/20"
                                />
                            </div>
                            <div className="flex flex-col gap-2">
                                <label className="text-sm font-semibold text-foreground">End Date</label>
                                <input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="border-2 border-primary/10 bg-card/60 backdrop-blur-sm text-foreground rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#4B9CD3]/20 focus:border-[#4B9CD3]/40 transition-all duration-300 hover:border-primary/20"
                                />
                            </div>
                            <div className="flex gap-3 items-end">
                                <Button 
                                    onClick={handleAnalyze} 
                                    disabled={loading || !startDate || !endDate}
                                    className="flex-1 bg-gradient-to-br from-[#4B9CD3] to-[#2B6FA6] hover:from-[#2B6FA6] hover:to-[#0F3D63] text-white shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {loading ? <Loader2 className="h-5 w-5 animate-spin mr-2" /> : null}
                                    {loading ? "Loading..." : "Analyze"}
                                </Button>
                                <Button 
                                    variant="outline" 
                                    onClick={handleDownload} 
                                    disabled={!startDate || !endDate}
                                    className="flex-1 border-2 border-primary/20 bg-card/60 backdrop-blur-sm hover:border-primary/40 hover:bg-card/80 transition-all duration-300 disabled:opacity-50"
                                >
                                    Download Excel
                                </Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {error && (
                    <Card className="border-2 border-destructive/20 bg-destructive/10 backdrop-blur-sm fade-in-up-delay-2">
                        <CardContent className="p-4">
                            <div className="text-destructive font-medium">{error}</div>
                        </CardContent>
                    </Card>
                )}

            {result && (
                <div className="space-y-8 fade-in-up-delay-2">
                    {/* Summary Stats Cards */}
                    {(() => {
                        const summary = (result.analyses?.summary_totals || [])[0] || {};
                        return (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-lg hover:shadow-2xl hover:border-primary/30 transition-all duration-300 group">
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Total Rows</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-xl md:text-2xl font-bold text-foreground break-words">{formatNumber(result.row_count)}</div>
                                    </CardContent>
                                </Card>
                                <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-lg hover:shadow-2xl hover:border-primary/30 transition-all duration-300 group">
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Total Amount</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-xl md:text-2xl font-bold text-[#4B9CD3] break-words">{formatCurrency(summary.sum_amount)}</div>
                                    </CardContent>
                                </Card>
                                <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-lg hover:shadow-2xl hover:border-primary/30 transition-all duration-300 group">
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Average Amount</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-xl md:text-2xl font-bold text-foreground break-words">{formatCurrency(summary.avg_amount)}</div>
                                    </CardContent>
                                </Card>
                                <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-lg hover:shadow-2xl hover:border-primary/30 transition-all duration-300 group">
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Date Range</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-base md:text-lg font-semibold text-foreground break-words">{result.range?.start}</div>
                                        <div className="text-xs text-muted-foreground">to</div>
                                        <div className="text-base md:text-lg font-semibold text-foreground break-words">{result.range?.end}</div>
                                    </CardContent>
                                </Card>
                            </div>
                        );
                    })()}

                    {/* AI Overview */}
                    {(result.analyses?.ai_overview || aiOverviewLoading) && (
                        <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl overflow-hidden fade-in-up-delay-3">
                            <CardContent className="p-0">
                                {aiOverviewLoading ? (
                                    <AILoadingState />
                                ) : (
                                    <AIOverviewCard text={result.analyses?.ai_overview} />
                                )}
                            </CardContent>
                        </Card>
                    )}
                    {/* Charts */}
                    {(() => {
                        const daily = (result.analyses?.daily_totals || [])
                            .slice()
                            .sort((a, b) => (a.effective_date || "").localeCompare(b.effective_date || ""));
                        const byOriginatorRaw = (result.analyses?.by_originator || []);
                        const byReceiverRaw = (result.analyses?.by_receiver || []);

                        // Aggregate long tails into an "Other" slice to reduce label clutter
                        const topWithOther = (arr, nameKey) => {
                            const sorted = arr.slice().sort((a, b) => Number(b.sum_amount || 0) - Number(a.sum_amount || 0));
                            const TOP_N = 8;
                            const top = sorted.slice(0, TOP_N);
                            const rest = sorted.slice(TOP_N);
                            const otherTotal = rest.reduce((acc, r) => acc + Number(r.sum_amount || 0), 0);
                            return otherTotal > 0
                                ? [...top, { [nameKey]: "Other", sum_amount: otherTotal }]
                                : top;
                        };

                        const byOriginator = topWithOther(byOriginatorRaw, "originator");
                        const byReceiver = topWithOther(byReceiverRaw, "receiver");

                        const CAROLINA = "#4B9CD3";
                        const CAROLINA_DARK = "#2B6FA6";
                        const ACCENTS = [
                            // High-contrast, UNC-leaning palette (blues/teals with clear accents)
                            "#0F3D63", // deep navy
                            "#4B9CD3", // carolina blue
                            "#1E40AF", // indigo
                            "#10B981", // emerald
                            "#F59E0B", // amber accent
                            "#2563EB", // blue
                            "#22C55E", // green
                            "#F97316", // orange accent
                            "#111827", // near-black
                            "#06B6D4", // cyan
                            "#D97706", // dark amber
                            "#93C5FD"  // light blue
                        ];

                        // Custom external pie label positioned with radial offset
                        const RADIAN = Math.PI / 180;
                        const renderExternalLabel = ({ cx, cy, midAngle, outerRadius, percent, name }) => {
                            if (!percent || percent < 0.03) return null; // hide ultra-small labels
                            const radius = outerRadius + 18;
                            const x = cx + radius * Math.cos(-midAngle * RADIAN);
                            const y = cy + radius * Math.sin(-midAngle * RADIAN);
                            const labelText = `${(name || "").toString().slice(0, 20)} ${(percent * 100).toFixed(0)}%`;
                            const textAnchor = x > cx ? "start" : "end";
                            return (
                                <text x={x} y={y} fill="#334155" textAnchor={textAnchor} dominantBaseline="central" style={{ fontSize: 12 }}>
                                    {labelText}
                                </text>
                            );
                        };

                        return (
                            <div className="grid grid-cols-1 gap-8 fade-in-up-delay-3">
                                <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl">
                                    <CardHeader className="pb-4">
                                        <CardTitle className="text-2xl font-bold text-foreground flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                                                <Sparkles className="h-5 w-5 text-[#4B9CD3]" />
                                            </div>
                                            Daily Amounts
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="h-80">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={daily} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.3} />
                                                <XAxis dataKey="effective_date" tick={{ fontSize: 12 }} interval={Math.ceil(daily.length / 7)} />
                                                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${Number(v).toLocaleString()}`} />
                                                <Tooltip 
                                                    formatter={(v) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, "Sum Amount"]} 
                                                    labelFormatter={(l) => `Date: ${l}`}
                                                    contentStyle={{ 
                                                        backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                                                        border: '2px solid rgba(75, 156, 211, 0.2)',
                                                        borderRadius: '8px',
                                                        backdropFilter: 'blur(10px)'
                                                    }}
                                                />
                                                <Bar dataKey="sum_amount" fill={CAROLINA} radius={[8, 8, 0, 0]}>
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </CardContent>
                                </Card>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl">
                                        <CardHeader className="pb-4">
                                            <CardTitle className="text-2xl font-bold text-foreground flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                                                    <Sparkles className="h-5 w-5 text-[#4B9CD3]" />
                                                </div>
                                                By Originator
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="h-80">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Tooltip 
                                                        formatter={(v, n, e) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, e?.payload?.originator || ""]}
                                                        contentStyle={{ 
                                                            backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                                                            border: '2px solid rgba(75, 156, 211, 0.2)',
                                                            borderRadius: '8px',
                                                            backdropFilter: 'blur(10px)'
                                                        }}
                                                    />
                                                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 12 }} />
                                                    <Pie data={byOriginator} dataKey="sum_amount" nameKey="originator" cx="50%" cy="50%" outerRadius={88} minAngle={5} paddingAngle={2} labelLine={{ stroke: "#cbd5e1" }} label={renderExternalLabel}>
                                                        {byOriginator.map((_, idx) => (
                                                            <Cell key={`org-slice-${idx}`} fill={ACCENTS[idx % ACCENTS.length]} stroke="#ffffff" strokeWidth={2} />
                                                        ))}
                                                    </Pie>
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>

                                    <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl">
                                        <CardHeader className="pb-4">
                                            <CardTitle className="text-2xl font-bold text-foreground flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                                                    <Sparkles className="h-5 w-5 text-[#4B9CD3]" />
                                                </div>
                                                By Receiver
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="h-80">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Tooltip 
                                                        formatter={(v, n, e) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, e?.payload?.receiver || ""]}
                                                        contentStyle={{ 
                                                            backgroundColor: 'rgba(255, 255, 255, 0.95)', 
                                                            border: '2px solid rgba(75, 156, 211, 0.2)',
                                                            borderRadius: '8px',
                                                            backdropFilter: 'blur(10px)'
                                                        }}
                                                    />
                                                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 12 }} />
                                                    <Pie data={byReceiver} dataKey="sum_amount" nameKey="receiver" cx="50%" cy="50%" outerRadius={88} minAngle={5} paddingAngle={2} labelLine={{ stroke: "#cbd5e1" }} label={renderExternalLabel}>
                                                        {byReceiver.map((_, idx) => (
                                                            <Cell key={`rcv-slice-${idx}`} fill={ACCENTS[idx % ACCENTS.length]} stroke="#ffffff" strokeWidth={2} />
                                                        ))}
                                                    </Pie>
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>
                                </div>
                            </div>
                        );
                    })()}
                    {/* KPI cards */}


                    {/* Daily Totals Table */}
                    <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl fade-in-up-delay-4">
                        <CardHeader className="pb-4">
                            <CardTitle className="text-2xl font-bold text-foreground flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                                    <Sparkles className="h-5 w-5 text-[#4B9CD3]" />
                                </div>
                                Daily Totals
                            </CardTitle>
                            <p className="text-sm text-muted-foreground mt-2">Sum of amounts per day (first 60 rows)</p>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-96 overflow-auto rounded-lg border border-primary/10">
                                <table className="w-full text-sm">
                                    <thead className="sticky top-0 bg-gradient-to-r from-[#4B9CD3]/10 to-[#2B6FA6]/10 backdrop-blur-sm border-b border-primary/20">
                                        <tr>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground w-1/2">Date</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Sum Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(result.analyses?.daily_totals || [])
                                            .slice()
                                            .sort((a, b) => (a.effective_date || "").localeCompare(b.effective_date || ""))
                                            .slice(0, 60)
                                            .map((row, idx) => (
                                                <tr key={`daily-${idx}`} className="border-b border-primary/5 hover:bg-[#4B9CD3]/5 transition-colors duration-200">
                                                    <td className="px-4 py-3 text-foreground">{row.effective_date || "-"}</td>
                                                    <td className="px-4 py-3 font-semibold text-[#4B9CD3]">{formatCurrency(row.sum_amount)}</td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>

                    {/* By Originator Table */}
                    <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl fade-in-up-delay-4">
                        <CardHeader className="pb-4">
                            <CardTitle className="text-2xl font-bold text-foreground flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                                    <Sparkles className="h-5 w-5 text-[#4B9CD3]" />
                                </div>
                                By Originator
                            </CardTitle>
                            <p className="text-sm text-muted-foreground mt-2">Top 50 by total amount</p>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-96 overflow-auto rounded-lg border border-primary/10">
                                <table className="w-full text-sm">
                                    <thead className="sticky top-0 bg-gradient-to-r from-[#4B9CD3]/10 to-[#2B6FA6]/10 backdrop-blur-sm border-b border-primary/20">
                                        <tr>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Originator</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Count</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Sum Amount</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Avg Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(result.analyses?.by_originator || [])
                                            .slice()
                                            .sort((a, b) => Number(b.sum_amount || 0) - Number(a.sum_amount || 0))
                                            .slice(0, 50)
                                            .map((row, idx) => (
                                                <tr key={`org-${idx}`} className="border-b border-primary/5 hover:bg-[#4B9CD3]/5 transition-colors duration-200">
                                                    <td className="px-4 py-3 text-foreground">{row.originator || "-"}</td>
                                                    <td className="px-4 py-3">{formatNumber(row.count)}</td>
                                                    <td className="px-4 py-3 font-semibold text-[#4B9CD3]">{formatCurrency(row.sum_amount)}</td>
                                                    <td className="px-4 py-3">{formatCurrency(row.avg_amount)}</td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>

                    {/* By Receiver Table */}
                    <Card className="border-2 border-primary/10 bg-card/80 backdrop-blur-sm shadow-xl fade-in-up-delay-4">
                        <CardHeader className="pb-4">
                            <CardTitle className="text-2xl font-bold text-foreground flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#4B9CD3]/20 to-[#2B6FA6]/20 flex items-center justify-center">
                                    <Sparkles className="h-5 w-5 text-[#4B9CD3]" />
                                </div>
                                By Receiver
                            </CardTitle>
                            <p className="text-sm text-muted-foreground mt-2">Top 50 by total amount</p>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-96 overflow-auto rounded-lg border border-primary/10">
                                <table className="w-full text-sm">
                                    <thead className="sticky top-0 bg-gradient-to-r from-[#4B9CD3]/10 to-[#2B6FA6]/10 backdrop-blur-sm border-b border-primary/20">
                                        <tr>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Receiver</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Count</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Sum Amount</th>
                                            <th className="text-left px-4 py-3 font-semibold text-foreground">Avg Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(result.analyses?.by_receiver || [])
                                            .slice()
                                            .sort((a, b) => Number(b.sum_amount || 0) - Number(a.sum_amount || 0))
                                            .slice(0, 50)
                                            .map((row, idx) => (
                                                <tr key={`rcv-${idx}`} className="border-b border-primary/5 hover:bg-[#4B9CD3]/5 transition-colors duration-200">
                                                    <td className="px-4 py-3 text-foreground">{row.receiver || "-"}</td>
                                                    <td className="px-4 py-3">{formatNumber(row.count)}</td>
                                                    <td className="px-4 py-3 font-semibold text-[#4B9CD3]">{formatCurrency(row.sum_amount)}</td>
                                                    <td className="px-4 py-3">{formatCurrency(row.avg_amount)}</td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}
            </div>
        </div>
    );
}

// AI Loading State Component with rotating messages
const LOADING_MESSAGES = [
    "Crunching the latest data for you...",
    "AI is analyzing your numbers...",
    "Almost done...",
    "Generating insights...",
    "Processing financial patterns...",
];

function AILoadingState() {
    const [messageIndex, setMessageIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="relative overflow-hidden rounded-xl border border-slate-200/50 bg-gradient-to-br from-white via-slate-50 to-blue-50/60">
            <div className="px-6 py-8 md:px-8 md:py-10">
                <div className="flex items-center gap-3 mb-4">
                    <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#4B9CD3] via-[#2B6FA6] to-[#0F3D63] shadow-md text-white">
                        <Sparkles className="h-4 w-4 animate-pulse" />
                    </span>
                    <span className="text-base font-semibold text-slate-800 tracking-tight">
                        AI Overview
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    <Loader2 className="h-5 w-5 text-[#4B9CD3] animate-spin" />
                    <p className="text-slate-600 text-[1.08rem] font-medium animate-pulse">
                        {LOADING_MESSAGES[messageIndex]}
                    </p>
                </div>
            </div>
            <div
                className="pointer-events-none absolute inset-0 rounded-xl"
                aria-hidden="true"
                style={{
                    background: "radial-gradient(ellipse at top right, rgba(75, 156, 211, 0.1) 10%, transparent 70%)",
                    zIndex: 0,
                }}
            />
        </div>
    );
}
