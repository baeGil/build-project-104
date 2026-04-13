"use client";

import Link from "next/link";
import { HealthStatus } from "@/components/HealthStatus";
import {
  FileText,
  MessageSquare,
  Clock,
  Database,
  Activity,
  ArrowRight,
} from "lucide-react";

// Mock stats - in real app these would come from API
const stats = [
  { label: "Documents Ingested", value: "12,458", icon: Database, trend: "+234 this week" },
  { label: "Recent Reviews", value: "156", icon: FileText, trend: "+12 today" },
  { label: "Avg Latency", value: "1.2s", icon: Clock, trend: "-0.3s vs last week" },
  { label: "System Health", value: "98.5%", icon: Activity, trend: "Operational" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-muted mt-1">
            Vietnamese Legal Contract Review System
          </p>
        </div>
        <div className="flex items-center gap-4 bg-white px-4 py-2 rounded-lg border border-slate-200">
          <span className="text-sm text-muted">API Status:</span>
          <HealthStatus />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-muted">{stat.label}</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    {stat.value}
                  </p>
                </div>
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Icon className="w-5 h-5 text-primary" />
                </div>
              </div>
              <p className="text-xs text-green-600 mt-3 font-medium">
                {stat.trend}
              </p>
            </div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          href="/review"
          className="group bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-primary/30 transition-all"
        >
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-colors">
              <FileText className="w-6 h-6 text-primary group-hover:text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-slate-900 group-hover:text-primary transition-colors">
                Review Contract
              </h3>
              <p className="text-muted mt-1">
                Upload or paste contract text to analyze compliance with
                Vietnamese law.
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted group-hover:text-primary group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

        <Link
          href="/chat"
          className="group bg-white rounded-xl border border-slate-200 p-6 shadow-sm hover:shadow-md hover:border-primary/30 transition-all"
        >
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-colors">
              <MessageSquare className="w-6 h-6 text-primary group-hover:text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-slate-900 group-hover:text-primary transition-colors">
                Ask Legal Question
              </h3>
              <p className="text-muted mt-1">
                Chat with AI about Vietnamese legal matters and get cited
                answers from the legal corpus.
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted group-hover:text-primary group-hover:translate-x-1 transition-all" />
          </div>
        </Link>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="p-6 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">
            Recent Activity
          </h2>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {[
              {
                action: "Contract reviewed",
                detail: "Software Service Agreement - 12 clauses analyzed",
                time: "2 minutes ago",
                status: "Completed",
              },
              {
                action: "Legal query answered",
                detail: "Question about labor contract termination",
                time: "15 minutes ago",
                status: "Completed",
              },
              {
                action: "Documents ingested",
                detail: "50 new legal documents added to corpus",
                time: "1 hour ago",
                status: "Completed",
              },
            ].map((activity, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0"
              >
                <div>
                  <p className="font-medium text-slate-900">{activity.action}</p>
                  <p className="text-sm text-muted">{activity.detail}</p>
                </div>
                <div className="text-right">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    {activity.status}
                  </span>
                  <p className="text-xs text-muted mt-1">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
